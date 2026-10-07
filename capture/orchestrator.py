"""Capture orchestrator — perishable, impure, resumable, ledger-gated.

Captures ONE (model, prompt_variant) over a firm subgrid into an immutable
append-only CSV data/raw/runs_<subgrid>_<model>_<variant>.csv. The unit is one
rating cell = (seed_index, firm, macro_state). The per-cell seed is derived from
(master, firm_id, variant, seed_index) and DELIBERATELY OMITS macro_state, so for
a given firm every macro state sees an IDENTICAL seed — the macro context is the
only thing that differs, which is what lets a rating change be attributed to the
macro state (the through-the-cycle test).

Concurrency: a bounded ThreadPoolExecutor of `--concurrency` workers. API calls
happen OUTSIDE the lock; ledger mutation + CSV append happen INSIDE the lock.
Budget: a persisted global Ledger enforces the cap across ALL invocations of a run
(and, with --ledger-suffix, per parallel provider track). Worst-case cost is
reserved before each call, so the cap is safe under concurrency. On resume,
completed cells are skipped and never re-billed. ERROR is a first-class label.

Usage:
  PILOT_MOCK=1 python capture/orchestrator.py --subgrid pilot --model openai_4o_mini --variant v_terse
  python capture/orchestrator.py --subgrid pilot --model gemini_flash --variant v_ttc --concurrency 5
"""
from __future__ import annotations
import argparse, csv, hashlib, os, re, sys, threading, time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "config"))

import agent as agentmod          # noqa: E402
import secrets as secretstore     # noqa: E402
import ledger as ledgermod        # noqa: E402
import loader as C                # noqa: E402
from build_firms import load_firms  # noqa: E402

_HERE = Path(__file__).resolve().parent
_RAW = _HERE.parent / "data" / "raw"
_MANI = _HERE.parent / "manifest"

CSV_FIELDS = [
    "subgrid", "mode", "model_key", "api_model", "provider", "family",
    "prompt_variant", "seed_index", "firm_id", "tier", "sector", "stratum",
    "macro_state", "macro_kind", "macro_severity", "seed", "temperature",
    "timestamp_utc", "prompt_hash", "content_sha256", "rating", "rating_notch",
    "expected_notch", "pd_bps", "pd_1yr", "decision", "rationale",
    "system_fingerprint", "rating_logprobs", "input_tokens", "output_tokens",
    "cost_usd", "ok", "error", "key_id", "raw_response",
]


def cell_seed(master: int, firm_id: str, variant: str, seed_index: int) -> int:
    # NOTE: macro_state is intentionally NOT in the seed -> identical seed across
    # macro states for a matched (firm, variant, seed_index) cell.
    raw = f"{master}|{firm_id}|{variant}|{seed_index}"
    return int(hashlib.sha256(raw.encode()).hexdigest()[:8], 16) & 0x7FFFFFFF


def load_done(path: Path) -> set:
    done = set()
    if path.exists():
        for r in csv.DictReader(path.open()):
            if r.get("ok") == "True":
                done.add((int(r["seed_index"]), r["firm_id"], r["macro_state"]))
    return done


def state_plan(grid, sg):
    """Ordered list of (state_name, kind, severity) = economic macro states + placebo
    states for this subgrid."""
    plan = []
    for ms in sg.macro_states:
        plan.append((ms, "macro", int(grid.macro_states[ms])))
    for ps in getattr(sg, "placebo_states", []):
        plan.append((ps, "placebo", int(grid.placebo_states[ps])))
    # kind='ofat' deliberately, NOT 'macro': these 21 states reuse severities across
    # five factors, so pooling them on the macro axis would regress notch on an
    # ambiguous ordering and yield a meaningless "joint" slope. A dedicated kind keeps
    # every existing macro/placebo analysis from picking them up, and the OFAT analysis
    # slices them per factor by name. block_for() resolves them via the macro branch.
    for os_ in getattr(sg, "ofat_states", []):
        plan.append((os_, "ofat", int(grid.ofat_states[os_])))
    return plan


def detect_mock(path: Path):
    if not path.exists():
        return None
    try:
        with path.open() as f:
            row = next(csv.DictReader(f))
        return row.get("mode", "").upper() == "MOCK"
    except Exception:
        return None


def classify_error(err: str):
    e = (err or ""); el = e.lower()
    delay = None
    m = re.search(r"retry.?after['\":\s]+(\d+(?:\.\d+)?)", el) or \
        re.search(r"retrydelay['\":\s]+(\d+(?:\.\d+)?)s", el)
    if m:
        delay = float(m.group(1))
    if "cooling down" in el or ("keys" in el and "rate-limited" in el):
        return "exhausted", delay
    if "429" in e or "rate limit" in el or "rate_limit" in el or "rate-limited" in el \
            or "quota" in el or "resource_exhausted" in el:
        return "rate_limit", delay
    if any(k in el for k in ("timeout", "timed out", "connection", "503", "502",
                             "unavailable", "reset")):
        return "transient", delay
    return "other", delay


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--subgrid", default="pilot")
    ap.add_argument("--model", required=True)
    ap.add_argument("--variant", required=True)
    ap.add_argument("--concurrency", type=int, default=None)
    ap.add_argument("--spend-cap", type=float, default=None,
                    help="override the subgrid budget (used to split the cap across "
                         "parallel provider tracks)")
    ap.add_argument("--ledger-suffix", default="",
                    help="separate ledger file per parallel stream, e.g. _openai")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cfg = C.load_all()
    grid = cfg.grid
    sg = C.subgrid(cfg, args.subgrid)
    if args.model not in sg.models:
        print(f"[capture] ERROR: model {args.model!r} not in subgrid {args.subgrid!r} "
              f"({sg.models})"); return 2
    if args.variant not in sg.variants:
        print(f"[capture] ERROR: variant {args.variant!r} not in subgrid {args.subgrid!r} "
              f"({sg.variants})"); return 2

    mcfg = cfg.models.cfg(args.model).model_dump()
    provider = mcfg["provider"]
    master = int(grid.seed_master)
    # Per-model override wins so the row's `temperature` column is the value actually
    # SENT. gpt-6-astra rejects temperature=0 ("only the default (1)"); recording the
    # grid default here would stamp 0.0 on rows that ran at 1.0.
    temp = float(mcfg["temperature"]) if mcfg.get("temperature") is not None \
        else float(grid.judge_temperature)
    max_retries = int(grid.max_retries)
    workers = max(1, args.concurrency or int(grid.max_workers))
    plan = state_plan(grid, sg)              # [(state, kind, severity), ...]

    mock = os.environ.get("PILOT_MOCK") == "1"
    mode = "MOCK" if mock else "REAL"
    rpm = 0 if mock else (grid.rpm_limits or {}).get(provider, 0)
    cap = args.spend_cap if args.spend_cap is not None else float(
        getattr(grid.budgets, args.subgrid, grid.budgets.pilot))
    margin = float(grid.stop_margin_usd)

    firms = load_firms(sg.firms)
    cells = [(si, f, st, kind, sev) for si in sg.seed_indices for f in firms
             for (st, kind, sev) in plan]

    _RAW.mkdir(parents=True, exist_ok=True)
    out_csv = _RAW / f"runs_{args.subgrid}_{args.model}_{args.variant}.csv"

    if out_csv.exists():
        if not os.access(out_csv, os.W_OK):
            print(f"[capture] REFUSING: {out_csv.name} is read-only (frozen). "
                  f"chmod +w or remove to re-capture."); return 4
        prior = detect_mock(out_csv)
        if prior is not None and prior != mock:
            print(f"[capture] REFUSING: {out_csv.name} holds "
                  f"{'MOCK' if prior else 'REAL'} rows but this is a {mode} run."); return 5

    led = ledgermod.Ledger.load(
        _MANI / f"ledger_{args.subgrid}_{mode}{args.ledger_suffix}.json", cap, margin)
    wc = ledgermod.worst_case_cost(mcfg)
    bill_in = 0.0 if mock else mcfg["price_in"]
    bill_out = 0.0 if mock else mcfg["price_out"]

    done = load_done(out_csv)
    todo = [(si, f, st, kind, sev) for (si, f, st, kind, sev) in cells
            if (si, f["firm_id"], st) not in done]

    ok, projected_total = led.preflight_ok(wc * len(todo))
    print(f"[capture] {args.model}/{args.variant} ({mode}) subgrid={args.subgrid} "
          f"firms={sg.firms}")
    print(f"[capture] cells: {len(cells)} ({len(sg.seed_indices)} seeds x {len(firms)} "
          f"firms x {len(plan)} states [{len(sg.macro_states)} macro + "
          f"{len(getattr(sg,'placebo_states',[]))} placebo]); {len(done)} done, "
          f"{len(todo)} todo | workers={workers} rpm[{provider}]={rpm or 'none'}")
    print(f"[capture] ledger: spent ${led.cum_usd:.4f} / cap ${cap:.2f} | "
          f"worst-case this run ${wc*len(todo):.4f} | projected total ${projected_total:.4f}")
    if not ok:
        print(f"[capture] PREFLIGHT REFUSAL: projected ${projected_total:.4f} > "
              f"cap-margin ${cap - margin:.2f}. Not starting."); return 6
    if args.dry_run:
        print("[capture] DRY RUN ok."); return 0
    if not mock and not secretstore.get_pool(provider):
        print(f"[capture] ERROR: no usable key for provider {provider!r}."); return 2

    min_interval = (60.0 / rpm) if rpm and rpm > 0 else 0.0
    rl_lock = threading.Lock(); rl_next = [0.0]

    def throttle():
        if min_interval <= 0:
            return
        with rl_lock:
            now = time.monotonic(); t = max(now, rl_next[0]); rl_next[0] = t + min_interval
            wait = t - now
        if wait > 0:
            time.sleep(wait)

    new_file = (not out_csv.exists()) or out_csv.stat().st_size == 0
    fh = out_csv.open("a", newline="")
    writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
    if new_file:
        writer.writeheader()

    st = {"n_ok": 0, "n_err": 0, "n_done": 0, "stop": False}
    io_lock = threading.Lock()
    total = len(todo)

    def write_row(si, firm, state, kind, sev, seed, res):
        cost = ledgermod.price_of(bill_in, bill_out, res.input_tokens, res.output_tokens)
        decision = "rated" if res.ok else "ERROR"
        csha = hashlib.sha256((res.raw_response or "").encode()).hexdigest()
        v = res.verdict
        with io_lock:
            writer.writerow({
                "subgrid": args.subgrid, "mode": mode, "model_key": args.model,
                "api_model": mcfg["api_model"], "provider": provider, "family": mcfg["family"],
                "prompt_variant": args.variant, "seed_index": si, "firm_id": firm["firm_id"],
                "tier": firm["tier"], "sector": firm["sector"], "stratum": firm["stratum"],
                "macro_state": state, "macro_kind": kind, "macro_severity": sev,
                "seed": seed, "temperature": temp,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "prompt_hash": res.prompt_hash, "content_sha256": csha,
                "rating": (v.rating if res.ok else ""),
                "rating_notch": (v.notch if res.ok else ""),
                "expected_notch": (round(res.expected_notch, 4)
                                   if (res.ok and res.expected_notch is not None) else ""),
                "pd_bps": (v.pd_bps if (res.ok and v.pd_bps is not None) else ""),
                "pd_1yr": (v.pd_1yr if (res.ok and v.pd_1yr is not None) else ""),
                "decision": decision,
                "rationale": (v.rationale if res.ok else ""),
                "system_fingerprint": res.system_fingerprint or "",
                "rating_logprobs": (res.logprobs_json or "").replace("\n", " ")[:400],
                "input_tokens": res.input_tokens, "output_tokens": res.output_tokens,
                "cost_usd": round(cost, 6), "ok": res.ok, "error": res.error or "",
                "key_id": res.key_id,
                "raw_response": (res.raw_response or "").replace("\n", " ")[:1500],
            })
            st["n_done"] += 1
            st["n_ok" if res.ok else "n_err"] += 1
            if st["n_done"] % 20 == 0 or st["n_done"] == total:
                fh.flush()
            if st["n_done"] % 100 == 0 or st["n_done"] == total:
                pct = 100.0 * st["n_done"] / total if total else 0.0
                print(f"  ...{st['n_done']}/{total} ({pct:.0f}%), "
                      f"${led.cum_usd:.4f} spent, {st['n_err']} err")

    def process(cell):
        si, firm, state, kind, sev = cell
        if st["stop"]:
            return
        seed = cell_seed(master, firm["firm_id"], args.variant, si)
        if not led.reserve(wc):
            st["stop"] = True
            return
        try:
            for attempt in range(1, max_retries + 2):
                throttle()
                res = agentmod.run_agent(mcfg, firm, args.variant, state, kind, temp, seed)
                if res.ok:
                    led.commit(args.model, bill_in, bill_out,
                               res.input_tokens, res.output_tokens, wc)
                    write_row(si, firm, state, kind, sev, seed, res)
                    return
                led.commit(args.model, bill_in, bill_out,
                           res.input_tokens, res.output_tokens, 0.0)
                ekind, delay = classify_error(res.error)
                if ekind in ("rate_limit", "transient", "exhausted") and attempt <= max_retries:
                    if ekind == "exhausted":
                        wait = delay or 32.0
                    elif ekind == "rate_limit":
                        wait = delay or 2.0
                    else:
                        wait = 0.4 * (2 ** (attempt - 1))
                    time.sleep(min(45.0, wait))
                    continue
                write_row(si, firm, state, kind, sev, seed, res)
                with io_lock:
                    print(f"  ! {firm['firm_id']} {state} s{si} attempt {attempt} ERROR: {res.error}")
                return
        finally:
            led.release(wc)

    try:
        if workers == 1:
            for cell in todo:
                if st["stop"]:
                    break
                process(cell)
        else:
            with ThreadPoolExecutor(max_workers=workers) as ex:
                list(ex.map(process, todo))
    finally:
        fh.close()
        led.save()

    err_rate = st["n_err"] / max(1, st["n_done"])
    if st["stop"]:
        print(f"[capture] STOP: spend cap ${cap:.2f} guard tripped "
              f"(spent ${led.cum_usd:.4f}). Resume by re-running.")
    print(f"[capture] done: {st['n_ok']} ok, {st['n_err']} ERROR "
          f"({err_rate*100:.2f}%), spend ${led.cum_usd:.4f} -> {out_csv.name}")
    if err_rate > 0.02:
        print(f"[capture] WARNING: ERROR rate {err_rate*100:.2f}% > 2% — "
              f"capture NON-AUTHORITATIVE until re-run to <=2%.")
    if not st["stop"] and st["n_done"] == total:
        print(f"[capture] next: python capture/freeze.py --subgrid {args.subgrid} "
              f"--model {args.model} --variant {args.variant}")
    return 3 if st["stop"] else 0


if __name__ == "__main__":
    sys.exit(main())

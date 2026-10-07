"""Does de-identification actually hold? MEASURE it, do not assume it.

The real-fundamentals arm (AMENDMENT #7) keeps actual SEC ratios and strips the issuer's
identity. The whole design depends on the model NOT recognising the issuer: recognition
would let it recall that issuer's real rating, and the issuer's identity also implies a
time period, which entangles firm identity with the macro state.

So this asks each model, directly, to name the company behind a de-identified block, and
reports the identification rate. A near-zero rate is evidence the anonymisation held; a
high rate would MEASURE the confound rather than leave it assumed, and either outcome is
reportable. Synthetic firms are included as a NEGATIVE CONTROL -- they have no identity
to find, so any "confident" identification there calibrates the model's false-positive
rate and stops a bare count being over-read.

  python capture/contamination_test.py --model openai_4o --n 40
"""
from __future__ import annotations
import argparse, json, sys, time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent / "config"))
import agent as A              # noqa: E402
import loader as C             # noqa: E402
import build_firms as BF       # noqa: E402

_SYS = ("You are shown an anonymised corporate financial summary. Identify the company "
        "if you can. Reply with JSON only: "
        '{"company": "<name or UNKNOWN>", "confidence": <0.0-1.0>, "basis": "<=20 words"}')


def ask(mcfg, block: str, temperature: float, seed: int):
    user = ("Anonymised financial summary:\n" + block +
            "\n\nWhich specific company is this? Reply UNKNOWN if you cannot tell.")
    # One failed call must not abort the sweep. An earlier run lost 40 completed real-block
    # results because call #5 of the synthetic control raised, which also cost us the
    # NEGATIVE CONTROL -- the one number needed to interpret the real rate at all.
    # Retry with backoff. The first astra sweep lost 35 of 40 control calls: the key pool
    # hit a rate limit, agent.py benched all three keys, and the surfaced error was the
    # unrelated max_tokens message from the last fallback combo. A 5-call control cannot
    # establish a false-positive floor, which is the only reason the control exists.
    import time
    last = None
    for attempt in range(3):
        try:
            raw, tin, tout, key_id, fp, _e, _l = A.call_model(
                mcfg, _SYS, user, temperature, seed)
            break
        except Exception as e:
            last = e
            time.sleep(2.0 * (attempt + 1))
    else:
        return {"company": "CALL_FAIL", "confidence": None, "error": str(last)[:160]}
    try:
        d = json.loads(raw)
    except Exception:
        return {"company": "PARSE_FAIL", "confidence": None, "raw": raw[:160]}
    return {"company": str(d.get("company", ""))[:80],
            "confidence": d.get("confidence"), "basis": str(d.get("basis", ""))[:120]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="openai_4o")
    ap.add_argument("--n", type=int, default=40)
    a = ap.parse_args()
    cfg = C.load_all()
    mcfg = cfg.models.cfg(a.model).model_dump()
    temp = mcfg["temperature"] if mcfg.get("temperature") is not None else float(cfg.grid.judge_temperature)

    real = BF.load_firms("real")[: a.n]
    synth = BF.load_firms("full")[: a.n]
    out = {"model": a.model, "temperature": temp, "real": [], "synthetic": []}
    for label, firms in (("real", real), ("synthetic", synth)):
        named = 0
        for i, f in enumerate(firms):
            r = ask(mcfg, f["serialized"], temp, 1234 + i)
            time.sleep(0.4)          # pace the sweep; this is a diagnostic, not a capture
            claimed = (r["company"] or "").strip().upper() not in (
                "", "UNKNOWN", "N/A", "PARSE_FAIL", "CALL_FAIL", "NONE", "UNCLEAR")
            r["claimed_identification"] = claimed
            r["firm_id"] = f["firm_id"]
            out[label].append(r)
            named += bool(claimed)
        landed = sum(1 for r in out[label] if r["company"] not in ("CALL_FAIL",))
        rate = named / max(1, landed)
        out[f"{label}_identification_rate"] = rate
        out[f"{label}_calls_landed"] = landed
        print(f"[contam] {a.model} {label:10} claimed an identification in "
              f"{named}/{landed} landed blocks ({100*rate:.1f}%)"
              + (f"  [{len(firms)-landed} call failures]" if landed != len(firms) else ""))
    # the synthetic arm is the false-positive floor: real-minus-synthetic is the part
    # attributable to there actually being an identity to recover
    excess = out["real_identification_rate"] - out["synthetic_identification_rate"]
    out["excess_over_negative_control"] = excess
    print(f"[contam] excess over the synthetic negative control: {100*excess:+.1f} pp")
    from datetime import datetime, timezone
    out["sweep_utc"] = datetime.now(timezone.utc).isoformat()
    outdir = Path("results"); outdir.mkdir(exist_ok=True)
    # every sweep is kept under its own timestamp, and the canonical name points at the
    # sweep with the MOST LANDED CALLS -- never simply the most recent, because a sweep
    # truncated by a provider outage must not displace a complete one.
    stamped = outdir / f"contamination_{a.model}_{out['sweep_utc'][:19].replace(':','')}.json"
    stamped.write_text(json.dumps(out, indent=2))
    canon = outdir / f"contamination_{a.model}.json"
    landed = out.get("real_calls_landed", 0) + out.get("synthetic_calls_landed", 0)
    prev = 0
    if canon.exists():
        try:
            d = json.loads(canon.read_text())
            prev = d.get("real_calls_landed", 0) + d.get("synthetic_calls_landed", 0)
        except Exception:
            prev = 0
    if landed >= prev:
        canon.write_text(json.dumps(out, indent=2))
        print(f"[contam] -> {stamped.name} (canonical: {landed} landed >= previous {prev})")
    else:
        print(f"[contam] -> {stamped.name} ONLY; canonical kept "
              f"({prev} landed beats this sweep's {landed})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

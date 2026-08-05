"""Pre-flight probe: one tiny live call per model in a subgrid -> served-model
fingerprint + measured per-call price. Writes manifest/probe_receipts.json. This is
the ONLY place we confirm the provisional snapshot strings in models.yaml resolve
to a live served model, and it measures a real per-call token/price so the ledger's
projection is grounded. Probe spend is tiny but real; it is charged and reported.

  python capture/probe.py --subgrid pilot          # probe the 4 cheap pilot models
  python capture/probe.py --model openai_4o_mini    # probe one model
"""
from __future__ import annotations
import argparse, json, sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "config"))

import agent as agentmod       # noqa: E402
import ledger as ledgermod     # noqa: E402
import loader as C             # noqa: E402

_MANI = Path(__file__).resolve().parent.parent / "manifest"

_PROBE_FIRM = {
    "firm_id": "PROBE-000", "tier": "low_ig", "sector": "industrials",
    "stratum": "low_ig:industrials",
    "serialized": ("  Sector: diversified industrial manufacturer\n"
                   "  Revenue: 20,000 musd  (YoY growth +3.0%)\n"
                   "  EBITDA: 4,000 musd  (margin 20.0%)\n"
                   "  Interest expense: 500 musd  (EBITDA/interest 8.00x)\n"
                   "  Net debt: 8,000 musd  (net debt/EBITDA 2.00x)\n"
                   "  Free cash flow: 1,200 musd\n"
                   "  Current ratio: 1.40\n"
                   "  Retained earnings / total assets: +0.300\n"
                   "  Working capital / total assets: +0.120"),
}


def probe_model(model_key: str, mcfg: dict) -> dict:
    t0 = datetime.now(timezone.utc)
    res = agentmod.run_agent(mcfg, _PROBE_FIRM, "v_terse", "neutral", "macro",
                             temperature=0.0, seed=7)
    cost = ledgermod.price_of(mcfg["price_in"], mcfg["price_out"],
                              res.input_tokens, res.output_tokens)
    return {
        "model_key": model_key, "api_model": mcfg["api_model"], "provider": mcfg["provider"],
        "family": mcfg["family"], "ok": res.ok, "error": res.error,
        "rating": (res.verdict.rating if res.ok else None),
        "input_tokens": res.input_tokens, "output_tokens": res.output_tokens,
        "measured_call_usd": round(cost, 8), "key_id": res.key_id,
        "response_preview": (res.raw_response or "")[:160],
        "probed_utc": t0.isoformat(),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--subgrid", default="pilot")
    ap.add_argument("--model", default=None)
    args = ap.parse_args()
    cfg = C.load_all()
    models = [args.model] if args.model else C.subgrid(cfg, args.subgrid).models
    receipts = {}
    total = 0.0
    all_ok = True
    for mk in models:
        mcfg = cfg.models.cfg(mk).model_dump()
        r = probe_model(mk, mcfg)
        receipts[mk] = r
        total += r["measured_call_usd"]
        all_ok = all_ok and r["ok"]
        status = "OK " if r["ok"] else "ERR"
        print(f"[probe] {status} {mk:20s} {mcfg['api_model']:28s} "
              f"rating={r['rating']} in={r['input_tokens']} out={r['output_tokens']} "
              f"${r['measured_call_usd']:.6f}" + ("" if r["ok"] else f"  <- {r['error']}"))
    _MANI.mkdir(parents=True, exist_ok=True)
    (_MANI / "probe_receipts.json").write_text(json.dumps(
        {"config_hash": cfg.config_hash(), "subgrid": args.subgrid,
         "total_probe_usd": round(total, 6), "receipts": receipts},
        indent=2, sort_keys=True))
    print(f"[probe] total probe spend ${total:.6f} -> manifest/probe_receipts.json")
    if not all_ok:
        print("[probe] WARNING: at least one model failed to probe — fix models.yaml "
              "snapshot/keys before the real run.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

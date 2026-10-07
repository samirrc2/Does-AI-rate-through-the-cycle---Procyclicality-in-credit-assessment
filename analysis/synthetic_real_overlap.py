"""Compare the synthetic-firm generation intervals with the real-firm battery, tier by tier.

The manuscript and Table~\\ref{tab:firmspec} asserted that "29 of 30 synthetic-versus-real
metric-by-tier comparisons overlap, the exception is top-tier revenue scale". Nothing in the
artifact computed that: the count and the exception were asserted in a caption string, and the
comparison grid is 9 tier-defining lines x 5 tiers = 45, not 30. This computes it.

Two definitions are reported, because they say different things:

  min-max  the generator's draw interval intersects the full observed range of the real firms
           in that tier. With 9 to 25 firms per tier this range is wide, so overlap is close to
           automatic -- it holds in 44 of 45 cells and is therefore weak evidence.
  IQR      the draw interval intersects the real firms' interquartile range. This is the
           reported criterion: it asks whether the generator covers where real firms of that
           tier actually sit, not merely whether it touches an outlier.

The validation concerns MARGINAL distributions only. Every synthetic line is drawn
independently within its tier interval, so this says nothing about reproducing the joint
covariance structure of real filings.

  python3 analysis/synthetic_real_overlap.py
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent
sys.path.insert(0, str(ROOT / "capture")); sys.path.insert(0, str(ROOT / "config"))
import build_firms as BF   # noqa: E402

TIERS = ["high_ig", "low_ig", "crossover", "high_yield", "distressed"]
TIER_LBL = {"high_ig": "high IG", "low_ig": "low IG", "crossover": "crossover",
            "high_yield": "high yield", "distressed": "distressed"}
# the nine lines the generator draws per tier, in table order
VARS = ["revenue_musd", "rev_growth_pct", "ebitda_margin_pct", "net_debt_to_ebitda",
        "ebitda_to_interest", "fcf_margin_pct", "current_ratio",
        "retained_earn_to_assets", "wc_to_assets"]
LBL = {"revenue_musd": "revenue scale", "rev_growth_pct": "revenue growth",
       "ebitda_margin_pct": "EBITDA margin", "net_debt_to_ebitda": "net debt / EBITDA",
       "ebitda_to_interest": "EBITDA / interest", "fcf_margin_pct": "FCF margin",
       "current_ratio": "current ratio", "retained_earn_to_assets": "retained earnings / assets",
       "wc_to_assets": "working capital / assets"}


def real_value(f: dict, v: str):
    """The generator draws FCF as a margin; the filings give it in dollars. Derive it."""
    fd = f["fundamentals"]
    if v in fd:
        return fd[v]
    if v == "fcf_margin_pct" and fd.get("revenue_musd"):
        return 100.0 * fd["fcf_musd"] / fd["revenue_musd"]
    return None


def quantile(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    k = (len(xs) - 1) * p
    lo = int(k)
    return xs[lo] if lo + 1 >= len(xs) else xs[lo] + (k - lo) * (xs[lo + 1] - xs[lo])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", default=str(ROOT / "data" / "firms" / "real.jsonl"))
    ap.add_argument("--out", default=str(ROOT / "results" / "synthetic_real_overlap.json"))
    a = ap.parse_args()
    real_path = Path(a.real)
    if not real_path.exists():
        print(f"[overlap] {real_path} absent -> not checkable here"); return 2
    real = [json.loads(l) for l in real_path.read_text().splitlines() if l.strip()]
    P = BF._TIER_PROFILE

    cells, counts = [], {"minmax": 0, "iqr": 0}
    for v in VARS:
        for t in TIERS:
            spec = P[t].get(v)
            xs = [x for x in (real_value(f, v) for f in real if f["tier"] == t) if x is not None]
            if spec is None or len(xs) < 2:
                print(f"[overlap] no comparison for {v}/{t}", file=sys.stderr); continue
            lo, hi = float(spec[0]), float(spec[1])
            rmin, rmax = min(xs), max(xs)
            q1, q3 = quantile(xs, 0.25), quantile(xs, 0.75)
            mm = lo <= rmax and rmin <= hi
            iq = lo <= q3 and q1 <= hi
            counts["minmax"] += mm; counts["iqr"] += iq
            cells.append({"variable": v, "label": LBL[v], "tier": t, "n_real": len(xs),
                          "spec": [lo, hi], "real_range": [rmin, rmax], "real_iqr": [q1, q3],
                          "overlap_minmax": mm, "overlap_iqr": iq})

    out = {"n_comparisons": len(cells), "n_variables": len(VARS), "n_tiers": len(TIERS),
           "n_real_firms": len(real),
           "overlap_minmax": counts["minmax"], "overlap_iqr": counts["iqr"],
           "exceptions_iqr": [f"{c['label']} ({TIER_LBL[c['tier']]})"
                              for c in cells if not c["overlap_iqr"]],
           "exceptions_minmax": [f"{c['label']} ({TIER_LBL[c['tier']]})"
                                 for c in cells if not c["overlap_minmax"]],
           "definition_iqr": "generator draw interval intersects the real tier interquartile range",
           "definition_minmax": "generator draw interval intersects the real tier full range",
           "independence_caveat": "each synthetic line is drawn independently within its tier "
                                  "interval, so the comparison concerns marginal distributions "
                                  "only, not the joint covariance structure of real filings",
           "cells": cells}
    outp = Path(a.out); outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(f"[overlap] {len(cells)} comparisons ({len(VARS)} lines x {len(TIERS)} tiers), "
          f"{len(real)} real firms")
    print(f"[overlap] IQR overlap {counts['iqr']}/{len(cells)}; exceptions: "
          f"{out['exceptions_iqr'] or 'none'}")
    print(f"[overlap] full-range overlap {counts['minmax']}/{len(cells)}; exceptions: "
          f"{out['exceptions_minmax'] or 'none'}")
    try:
        shown = outp.relative_to(ROOT)
    except ValueError:            # an --out outside the repo is legitimate (regression runs)
        shown = outp
    print(f"-> {shown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

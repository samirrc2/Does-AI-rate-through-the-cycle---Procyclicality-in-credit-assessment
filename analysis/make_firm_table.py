"""Emit the synthetic-firm generation table (referee 1 comment 2).

The response letter states that the full tier-by-ratio generation table is reported in the
appendix. It was not -- this generates it, from capture/build_firms._TIER_PROFILE, so the
table is the actual sampling specification rather than a transcription of it.

  python3 analysis/make_firm_table.py --out paper/src/tables/table0_firm_profiles.tex
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "capture"))
sys.path.insert(0, str(_HERE.parent / "config"))
import build_firms as BF   # noqa: E402

TIERS = ["high_ig", "low_ig", "crossover", "high_yield", "distressed"]
TIER_LBL = {"high_ig": "High IG (AAA--AA)", "low_ig": "Low IG (A--BBB)",
            "crossover": "Crossover (BBB$-$/BB$+$)", "high_yield": "High yield (BB--B)",
            "distressed": "Distressed (CCC and below)"}
# row order and display names for the ratios that define a tier
ROWS = [("revenue_musd", "Revenue (USD m)", 0),
        ("rev_growth_pct", "Revenue growth (\\%)", 0),
        ("ebitda_margin_pct", "EBITDA margin (\\%)", 0),
        ("net_debt_to_ebitda", "Net debt / EBITDA ($\\times$)", 1),
        ("ebitda_to_interest", "EBITDA / interest ($\\times$)",  1),
        ("fcf_margin_pct", "FCF margin (\\%)", 0),
        ("current_ratio", "Current ratio", 1),
        ("retained_earn_to_assets", "Retained earnings / assets", 2),
        ("wc_to_assets", "Working capital / assets", 2)]


# The caption used to assert "29 of 30 metric-by-tier comparisons overlap, the exception is
# top-tier revenue scale". Nothing computed that, and the grid is 9 lines x 5 tiers = 45, not 30.
# The clause is now built from analysis/synthetic_real_overlap.py's artifact, so it cannot drift.
_OVL = Path(__file__).resolve().parent.parent / "results" / "synthetic_real_overlap.json"


def _overlap_clause() -> str:
    if not _OVL.exists():
        raise SystemExit(f"[firmtable] {_OVL} missing -- run analysis/synthetic_real_overlap.py first")
    o = json.loads(_OVL.read_text())
    # the exceptions are named in the appendix, which has room for the definition too
    return (f"Of the {o['n_comparisons']} line-by-tier cells, {o['overlap_iqr']} have a draw "
            r"interval intersecting the interquartile range of the real firms in that tier "
            r"(Appendix~\ref{app:robust}).")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="paper/src/tables/table0_firm_profiles.tex")
    a = ap.parse_args()
    P = BF._TIER_PROFILE
    OVERLAP_CLAUSE = _overlap_clause()
    L = [r"\begin{table}[tb]\centering\small",
         r"\caption{Synthetic-firm generation specification. Each firm draws every line "
         r"independently and uniformly from the interval shown for its credit-quality tier; "
         r"firms are stratified across the five tiers and eight sectors so the "
         r"fundamentals-implied ratings span the scale. Ranges were chosen so a tier's "
         r"implied rating lands in its band, not fitted to a reference population. "
         + OVERLAP_CLAUSE
         + r" Values are frozen and SHA-256'd before capture.}",
         r"\label{tab:firmspec}",
         r"\begin{tabular}{l" + "r" * len(TIERS) + "}",
         r"\toprule",
         "Line & " + " & ".join(TIER_LBL[t].split(" (")[0] for t in TIERS) + r" \\",
         r"\midrule"]
    for key, lbl, nd in ROWS:
        cells = []
        for t in TIERS:
            v = P[t].get(key)
            if v is None:
                cells.append("--"); continue
            lo, hi = v
            fmt = f"{{:.{nd}f}}"
            # "lo--hi" renders as an en dash, so a negative lower bound came out as "-14--1",
            # which reads as one mangled number. Spell the range and use a real minus sign.
            neg = lambda x: ("$-$" + x[1:]) if x.startswith("-") else x
            # the printed endpoint must round-trip to the spec value, or the table reports a
            # different interval than the generator draws from: at 0 dp the high-yield
            # EBITDA/interest band 1.6-3.2 printed as "2 to 3" and distressed 0.4-1.6 as "0 to 2"
            for raw in (lo, hi):
                if abs(round(float(raw), nd) - float(raw)) > 1e-12:
                    raise SystemExit(f"[firmtable] {key}/{t}: {raw} does not survive {nd}-dp "
                                     f"printing -- raise this row's precision")
            cells.append(f"{neg(fmt.format(lo))} to {neg(fmt.format(hi))}")
        L.append(f"{lbl} & " + " & ".join(cells) + r" \\")
    L += [r"\bottomrule", r"\end{tabular}\end{table}"]
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L) + "\n")
    print(f"[firmtable] {len(ROWS)} lines x {len(TIERS)} tiers -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

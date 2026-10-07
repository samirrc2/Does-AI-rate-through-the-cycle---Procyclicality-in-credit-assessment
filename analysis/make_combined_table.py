"""ONE per-model table: primary coefficients, revision arms and the macro decomposition.

Table 1 and the OFAT table were keyed on the same unit -- the model -- and every OFAT row
was already a row in Table 1, so they were two tables describing one set of objects. This
emits a single float with two panels: Panel A the per-model coefficients (all seven models),
Panel B the macro-factor decomposition (the four models that arm covers).

Two column decisions worth recording:
  * the 95% CI is folded into the beta cell rather than given its own column;
  * Swing is KEPT even though it looks like 4x beta. It is not: measured endpoint-to-endpoint
    the ratio runs 3.96--4.39 across models, and that spread is curvature information the
    fitted slope discards. Dropping it as "redundant" would have destroyed a measurement.

  python3 analysis/make_combined_table.py --out paper/src/tables/table1_per_model.tex
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent
DISP = {"gemini_pro": "Gemini Pro", "openai_astra": "GPT-6 Astra",
        "gemini_flash": "Gemini Flash", "gemini_flash_lite": "Gemini Flash-Lite",
        "openai_4o": "GPT-4o", "openai_41_mini": "GPT-4.1-mini",
        "openai_4o_mini": "GPT-4o-mini"}
ORDER = ["gemini_pro", "openai_astra", "gemini_flash", "gemini_flash_lite",
         "openai_4o", "openai_41_mini", "openai_4o_mini"]
OFAT_ORDER = ["openai_4o_mini", "openai_4o", "gemini_flash", "openai_astra"]
FACTORS = ["gdp", "unemp", "spread", "deflt", "standards"]


def _m(t: str) -> str:
    """Render a formatted number with a real minus sign, never a signed zero."""
    if t.startswith(("-", "+")) and float(t) == 0.0:
        t = t.lstrip("-+")            # a signed zero is just zero
    return ("$-$" + t[1:]) if t.startswith("-") else t


def n(x, nd=3):
    return "" if x is None else _m(f"{x:.{nd}f}")


# The note used to send readers to Fig. 2 for the D:U intervals. Fig. 2 plots the two
# HALF-SLOPES with their intervals, not the ratio's. The ratio's own firm-clustered intervals
# live in results/reviewer_revision.json, so the note now states them from there.
_REV = ROOT / "results" / "reviewer_revision.json"


def _du_clause() -> str:
    if not _REV.exists():
        raise SystemExit(f"[combined] {_REV} missing -- cannot state the D:U intervals")
    hs = json.loads(_REV.read_text())["half_slopes"]
    los = [v["ratio_down_over_up"]["ci95"][0] for v in hs.values()]
    his = [v["ratio_down_over_up"]["ci95"][1] for v in hs.values()]
    assert min(los) > 1.0, "a D:U interval includes one -- the note below would be wrong"
    return (r"The ratio has its own clustered intervals, with lower bounds from "
            f"${min(los):.2f}$ to ${max(los):.2f}$ and upper bounds reaching ${max(his):.2f}$. "
            r"All exclude one, and they overlap across models, so they do not rank them.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--claims", default=str(ROOT / "claims_revision.json"))
    ap.add_argument("--ofat", default=str(ROOT / "results" / "ofat.json"))
    ap.add_argument("--out", default="paper/src/tables/table1_per_model.tex")
    a = ap.parse_args()
    DU_CLAUSE = _du_clause()
    c = json.loads(Path(a.claims).read_text())["per_model_variant"]
    of = json.loads(Path(a.ofat).read_text())["models"] if Path(a.ofat).exists() else {}

    L = [r"\begin{table}[t]\centering\small",
         r"\caption{Per-model results. \textbf{Panel A}: procyclicality on byte-identical "
         r"fundamentals. $\beta$ = notches of downgrade per $+1$ macro-severity step under the "
         r"terse framing, with firm-clustered bootstrap 95\% CI; \textbf{Swing} = measured "
         r"boom$\to$severe-recession notches (not $4\beta$: the endpoint ratio runs "
         r"$3.96$--$4.39$, so the gap carries curvature); \textbf{D:U} = downside over upside "
         r"half-slope. Fig.~\ref{fig:asym} plots the two half-slopes with their intervals. "
         + DU_CLAUSE + r" \textbf{Resid.} and \textbf{PD-ret.} = $\beta$ and the retained fraction of "
         r"the log-odds PD slope under the through-the-cycle instruction; "
         r"\textbf{$\beta$ real} = the same coefficient on the real-fundamentals battery and "
         r"\textbf{$\Delta\beta$} its drift on re-measurement 2.5 months later (blank where the "
         r"model was not in that arm). \textbf{Panel B}: one macro indicator moved across the "
         r"same $-2\ldots+2$ range with the other four held neutral, so each column is "
         r"comparable to $\beta$ above; $\Sigma/\beta$ sums the five and divides by the joint "
         r"slope, below one meaning the indicators reinforce one another. "
         r"$^{\dagger}$interval includes zero.}",
         r"\label{tab:permodel}",
         r"\begin{tabular}{lrrrrrrr}",
         r"\toprule",
         r"\multicolumn{8}{l}{\emph{Panel A: procyclicality, through-the-cycle response, and "
         r"revision arms}}\\",
         r"\midrule",
         r"Model & $\beta$ (95\% CI) & Swing & D:U & Resid. (95\% CI) & PD-ret. & "
         r"$\beta$ real & "
         r"$\Delta\beta$ \\",
         r"\midrule"]
    for m in ORDER:
        t = c.get(f"{m}|v_terse", {}); ttc = c.get(f"{m}|v_ttc", {})
        if not t:
            continue
        ci = t.get("cyclicality_ci95") or [None, None]
        beta = n(t.get("cyclicality_notch_per_step"))
        cis = "" if ci[0] is None else f" [{_m(f'{ci[0]:.2f}')}, {_m(f'{ci[1]:.2f}')}]"
        dr = t.get("beta_drift_epoch")
        L.append(" & ".join([DISP[m], beta + cis,
                             n(t.get("endpoint_swing_notches"), 2),
                             n(t.get("asymmetry_ratio"), 1),
                             # Resid. carries its INTERVAL, because the through-the-cycle
                             # rating condition is a statement about the interval, not the
                             # point estimate. Without it the prose had to quote the CIs,
                             # which is the duplication this table exists to avoid.
                             (lambda b, c: "" if b is None else
                              n(b) + ("" if not c or c[0] is None
                                      else f" [{_m(f'{c[0]:.2f}')}, {_m(f'{c[1]:.2f}')}]"))(
                                 ttc.get("cyclicality_notch_per_step"),
                                 ttc.get("cyclicality_ci95")),
                             n(ttc.get("pd_retention_vs_terse"), 2),
                             n(t.get("real_beta")),
                             "" if dr is None else _m(f"{dr:+.3f}")]) + r" \\")
    if of:
        L += [r"\midrule",
              r"\multicolumn{8}{l}{\emph{Panel B: macro-factor decomposition (one indicator at "
              r"a time)}}\\",
              r"\midrule",
              r"Model & GDP & Unem. & Spread & Default & Standards & $\Sigma/\beta$ & \\",
              r"\midrule"]
        for m in OFAT_ORDER:
            r = of.get(m)
            if not r:
                continue
            cells = []
            for f in FACTORS:
                d = r["factors"][f]
                cells.append(_m(f"{d['slope']:.3f}") + ("" if d["excludes_zero"] else r"$^{\dagger}$"))
            L.append(" & ".join([DISP[m]] + cells
                                + [_m(f"{r['additivity_ratio_sum_over_joint']:.2f}"), ""]) + r" \\")
    L += [r"\bottomrule", r"\end{tabular}\end{table}"]
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L) + "\n")
    print(f"[combined] one table, two panels: {len(ORDER)} + {len(OFAT_ORDER)} rows -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

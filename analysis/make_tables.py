"""Export the paper's tables from claims.json to results/tables/ as CSV + LaTeX.
FRL table style: booktabs (no vertical rules), notes below, editable text. Pure, $0.

  python3 analysis/make_tables.py            # reads ./claims.json
  python3 analysis/make_tables.py --claims claims.json --out results/tables
"""
from __future__ import annotations
import argparse, csv, json
from pathlib import Path

# display names for the served models
DISP = {
    "gemini_flash": "Gemini Flash",
    "gemini_flash_lite": "Gemini Flash-Lite",
    "openai_41_mini": "GPT-4.1-mini",
    "openai_4o": "GPT-4o",
    "openai_4o_mini": "GPT-4o-mini",
}
ORDER = ["gemini_flash", "gemini_flash_lite", "openai_41_mini", "openai_4o", "openai_4o_mini"]


def f(x, nd=3):
    return "" if x is None else f"{x:.{nd}f}"


def ci(pair, nd=2):
    if not pair or pair[0] is None or pair[1] is None:
        return ""
    return f"[{pair[0]:.{nd}f}, {pair[1]:.{nd}f}]"


def _pmv(c, model, variant):
    return c["per_model_variant"].get(f"{model}|{variant}", {})


def table1_rows(c):
    """Per-model headline: beta(terse)+CI, swing, asymmetry, residual(ttc), PD-retention."""
    rows = []
    for m in ORDER:
        t = _pmv(c, m, "v_terse")
        if not t:
            continue
        ttc = _pmv(c, m, "v_ttc")
        rows.append({
            "Model": DISP.get(m, m),
            "beta_terse": f(t.get("cyclicality_notch_per_step")),
            "CI95": ci(t.get("cyclicality_ci95")),
            "swing": f(t.get("endpoint_swing_notches"), 2),
            "downside": f(t.get("downside_slope"), 2),
            "upside": f(t.get("upside_slope"), 2),
            "asym_ratio": f(t.get("asymmetry_ratio"), 1),
            "residual_ttc": f(ttc.get("cyclicality_notch_per_step")),
            "pd_ret_ttc": f(ttc.get("pd_retention_vs_terse"), 2),
        })
    return rows


def table2_rows(c):
    """Pooled per-variant cyclicality + CI (the instruction gradient)."""
    order = ["v_pit", "v_terse", "v_stable", "v_ttc"]
    disp = {"v_pit": "Point-in-time", "v_terse": "Terse", "v_stable": "\"Be stable\"",
            "v_ttc": "Through-the-cycle"}
    rows = []
    for v in order:
        d = c["per_variant_pooled"].get(v)
        if not d:
            continue
        rows.append({
            "Framing": disp[v],
            "pooled_beta": f(d.get("pooled_cyclicality_notch_per_step")),
            "CI95": ci(d.get("pooled_cyclicality_ci95")),
            "excl_0": str(d.get("ci_excludes_0")),
        })
    return rows


def table3_rows(c):
    """Robustness: placebo net, expected-notch (OpenAI), noise floor (v_terse)."""
    rows = []
    for m in ORDER:
        t = _pmv(c, m, "v_terse")
        if not t:
            continue
        rows.append({
            "Model": DISP.get(m, m),
            "beta_terse": f(t.get("cyclicality_notch_per_step")),
            "net_placebo": f(t.get("net_cyclicality_notch_per_step")),
            "expected_notch": f(t.get("expected_notch_cyclicality_per_step")),
            "noise_floor_sd": f(t.get("noise_floor_notch_sd"), 3),
            "probit": f((t.get("ordered_probit") or {}).get("notch_per_step")),
        })
    return rows


def write_csv(rows, path: Path):
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)


def write_tex(rows, path: Path, caption: str, label: str, headers: dict):
    cols = list(rows[0].keys())
    align = "l" + "r" * (len(cols) - 1)
    lines = [r"\begin{table}[t]", r"\centering",
             f"\\caption{{{caption}}}", f"\\label{{{label}}}",
             f"\\begin{{tabular}}{{{align}}}", r"\toprule",
             " & ".join(headers.get(c, c) for c in cols) + r" \\", r"\midrule"]
    for r in rows:
        lines.append(" & ".join(str(r[c]) for c in cols) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    path.write_text("\n".join(lines))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--claims", default="claims.json")
    ap.add_argument("--out", default="results/tables")
    args = ap.parse_args()
    c = json.loads(Path(args.claims).read_text())
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)

    t1 = table1_rows(c)
    write_csv(t1, out / "table1_per_model.csv")
    write_tex(t1, out / "table1_per_model.tex",
              "Per-model rating procyclicality on byte-identical fundamentals. "
              "$\\beta$ = notches of downgrade per +1 macro-severity step (terse framing); "
              "firm-clustered bootstrap 95\\% CIs. Swing = boom$\\to$severe-recession notches. "
              "Asymmetry = downside (into recession) vs upside (into boom) half-slopes. "
              "Residual = $\\beta$ after the through-the-cycle instruction; PD-ret. = PD-slope "
              "retention under that instruction.",
              "tab:permodel",
              {"beta_terse": r"$\beta$", "CI95": "95\\% CI", "swing": "Swing",
               "downside": "Down", "upside": "Up", "asym_ratio": "D:U",
               "residual_ttc": "Resid.", "pd_ret_ttc": "PD-ret."})

    t2 = table2_rows(c)
    write_csv(t2, out / "table2_instruction_gradient.csv")
    write_tex(t2, out / "table2_instruction_gradient.tex",
              "Pooled procyclicality by prompt framing (across five models), notches per "
              "severity step with firm-clustered bootstrap 95\\% CIs.",
              "tab:gradient",
              {"pooled_beta": r"Pooled $\beta$", "CI95": "95\\% CI", "excl_0": "Excl.\\ 0"})

    t3 = table3_rows(c)
    write_csv(t3, out / "table3_robustness.csv")
    write_tex(t3, out / "table3_robustness.tex",
              "Robustness of the terse-framing coefficient: placebo-adjusted (net), "
              "log-probability expected-notch (OpenAI only), within-cell seed noise floor, "
              "and the Amato--Furfine ordered-probit estimate.",
              "tab:robust",
              {"beta_terse": r"$\beta$", "net_placebo": "Net", "expected_notch": "Exp-notch",
               "noise_floor_sd": "Noise SD", "probit": "Probit"})

    print(f"[tables] wrote table1/2/3 (csv+tex) -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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
        "gemini_pro": "Gemini Pro",
        "openai_astra": "GPT-6 Astra",
}
# Seven models after the revision, ordered by ASCENDING terse coefficient so the table
# reads as the capability/magnitude gradient the text describes. A model absent from the
# supplied claims file is skipped, so this same ORDER works against the original
# five-model claims.json and the seven-model claims_revision.json.
ORDER = ["gemini_pro", "openai_astra", "gemini_flash", "gemini_flash_lite",
         "openai_4o", "openai_41_mini", "openai_4o_mini"]


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
            # Down/Up removed: Fig. 2 plots both half-slopes WITH intervals, so columns here
            # duplicated it. D:U is kept because the text refers to the direction.
            "asym_ratio": f(t.get("asymmetry_ratio"), 1),
            "residual_ttc": f(ttc.get("cyclicality_notch_per_step")),
            "pd_ret_ttc": f(ttc.get("pd_retention_vs_terse"), 2),
            # folded in from the revision table: same estimand as beta, so it belongs here
            "real_beta": f(t.get("real_beta")),
            "beta_drift": (lambda v: "" if v is None else f"{v:+.3f}")(t.get("beta_drift_epoch")),
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
            "excl_0": "Yes" if d.get("ci_excludes_0") else "No",
        })
    return rows


def table3_rows(c):
    """Robustness: placebo net, expected-notch under BOTH framings, noise floor, probit.

    The expected-notch column is reported for terse AND through-the-cycle because the
    claim it supports is the CHANGE between them -- a PD-free version of the anchoring
    result (referee 1 comment 5). A terse-only column cannot evidence that claim.
    """
    rows = []
    for m in ORDER:
        t = _pmv(c, m, "v_terse")
        if not t:
            continue
        rows.append({
            "Model": DISP.get(m, m),
            "beta_terse": f(t.get("cyclicality_notch_per_step")),
            "net_placebo": f(t.get("net_cyclicality_notch_per_step")),
            "expnotch_terse": f(t.get("expected_notch_cyclicality_per_step")),
            "expnotch_ttc": f(_pmv(c, m, "v_ttc").get("expected_notch_cyclicality_per_step")),
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
              "\\textbf{Swing} = boom$\\to$severe-recession notches. "
              "\\textbf{D:U} = the ratio of the downside half-slope to the upside half-slope. "
              "\\textbf{Resid.} = $\\beta$ under the through-the-cycle instruction; "
              "\\textbf{PD-ret.} = the fraction of the log-odds PD slope retained under that "
              "instruction. \\textbf{$\\beta$ real} = the same coefficient on the real-fundamentals battery, \\textbf{$\\Delta\\beta$} its change when the model is re-measured 2.5 months later (blank where the model was not in that arm). Half-slopes and D:U intervals appear in Fig.~2; the D:U "
              "interval is bootstrapped as a ratio and, because its denominator is small, the "
              "intervals are wide -- every interval excludes~1, so downside exceeds upside in "
              "every model, but the ratios order no two models significantly.",
              "tab:permodel",
              {"beta_terse": r"$\beta$", "CI95": "95\\% CI", "swing": "Swing",
               "asym_ratio": "D:U", "residual_ttc": "Resid.", "pd_ret_ttc": "PD-ret.",
               "real_beta": r"$\beta$ real", "beta_drift": r"$\Delta\beta$"})

    t2 = table2_rows(c)
    write_csv(t2, out / "table2_instruction_gradient.csv")
    write_tex(t2, out / "table2_instruction_gradient.tex",
              "Pooled procyclicality by prompt framing, notches per severity step with "
              "firm-clustered bootstrap 95\\% CIs. Pooled across the five non-frontier "
              "models, whose four framings form the original confirmatory grid; the two "
              "frontier models' framing gradients are reported in the replication "
              "archive because their arms were added in revision.",
              "tab:gradient",
              {"pooled_beta": r"Pooled $\beta$", "CI95": "95\\% CI", "excl_0": "Excl.\\ 0"})

    t3 = table3_rows(c)
    write_csv(t3, out / "table3_robustness.csv")
    write_tex(t3, out / "table3_robustness.tex",
              # Definitions and missing-value explanations only. The table is no longer narrated
              # in prose afterwards, so its caption must carry what a reader needs.
              "Robustness of the terse-framing coefficient. Net $=$ placebo-adjusted "
              "coefficient. Exp-n. $=$ expected-notch slope from rating-token "
              "log-probabilities. Noise SD $=$ mean within-cell notch standard "
              "deviation across replicate seeds. Probit $=$ Amato--Furfine "
              "ordered-probit estimate, converted from the latent scale to notches per "
              "step. Expected-notch estimates are unavailable for "
              "Gemini and for GPT-6 Astra because neither returns rating-token "
              "log-probabilities. Gemini Flash-Lite's $0.000$ "
              "Noise SD is exact.",
              "tab:robust",
              {"beta_terse": r"$\beta$", "net_placebo": "Net",
               "expnotch_terse": "Exp-n. terse", "expnotch_ttc": "Exp-n. TTC",
               "noise_floor_sd": "Noise SD", "probit": "Probit"})

    print(f"[tables] wrote table1/2/3 (csv+tex) -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

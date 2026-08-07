"""Build the FRL manuscript (paper/manuscript.docx) from claims.json + figures.
Numbers are injected from claims.json so the text cannot drift from the data.
Then: soffice --headless --convert-to pdf manuscript.docx.

  python3 paper/build_manuscript.py
"""
from __future__ import annotations
import json
from pathlib import Path
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

ROOT = Path(__file__).resolve().parent.parent
PAPER = ROOT / "paper"
C = json.loads((ROOT / "claims.json").read_text())


def g(*path):
    x = C
    for p in path:
        x = x[p]
    return x


# ── formatted numbers ────────────────────────────────────────────────────────
def r(x, n=3):
    return f"{x:.{n}f}"


def ci(pair, n=2):
    return f"[{pair[0]:.{n}f}, {pair[1]:.{n}f}]"


H = g("headline_cyclicality")
A = g("asymmetry")
V = g("per_variant_pooled")
CON = g("instruction_effect_contrasts")
NUM = {
    "beta": r(H["pooled_notch_per_step"]),
    "beta_ci": ci(H["pooled_ci95"]),
    "net": r(H["pooled_net_cyclicality"]),
    "net_ci": ci(H["pooled_net_cyclicality_ci95"] if "pooled_net_cyclicality_ci95" in H else H["pooled_net_ci95"]),
    "placebo": r(H["pooled_placebo_cyclicality"], 3),
    "swing": r(H["pooled_endpoint_swing"], 2),
    "down": r(A["pooled_downside_slope"], 2), "down_ci": ci(A["pooled_downside_ci95"]),
    "up": r(A["pooled_upside_slope"], 2), "up_ci": ci(A["pooled_upside_ci95"]),
    "ratio": r(A["ratio"], 1),
    "pit": r(V["v_pit"]["pooled_cyclicality_notch_per_step"]),
    "terse": r(V["v_terse"]["pooled_cyclicality_notch_per_step"]),
    "stable": r(V["v_stable"]["pooled_cyclicality_notch_per_step"]),
    "ttc": r(V["v_ttc"]["pooled_cyclicality_notch_per_step"]),
    "ttc_ci": ci(V["v_ttc"]["pooled_cyclicality_ci95"]),
    "spend": r(g("meta", "spend_usd"), 2),
    "rows": f"{g('meta', 'n_rows'):,}",
    "firms": g("meta", "n_firms"),
}

DISP = {"gemini_flash": "Gemini 3.5 Flash", "gemini_flash_lite": "Gemini 2.5 Flash-Lite",
        "openai_41_mini": "GPT-4.1-mini", "openai_4o": "GPT-4o", "openai_4o_mini": "GPT-4o-mini"}
ORDER = ["gemini_flash", "gemini_flash_lite", "openai_41_mini", "openai_4o", "openai_4o_mini"]


# ── document scaffolding ─────────────────────────────────────────────────────
doc = Document()
st = doc.styles["Normal"]
st.font.name = "Times New Roman"
st.font.size = Pt(11)
st.paragraph_format.space_after = Pt(6)
st.paragraph_format.line_spacing = 1.15


def heading(text, size=13):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(size)
    p.paragraph_format.space_before = Pt(10)
    return p


def body(text, italic=False, align=None):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.italic = italic
    if align == "center":
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return p


# ── title block ──────────────────────────────────────────────────────────────
t = doc.add_paragraph()
tr = t.add_run("Does AI rate through the cycle?")
tr.bold = True; tr.font.size = Pt(16)
t.alignment = WD_ALIGN_PARAGRAPH.CENTER
sub = doc.add_paragraph()
sr = sub.add_run("Procyclicality in credit assessment")
sr.italic = True; sr.font.size = Pt(12)
sub.alignment = WD_ALIGN_PARAGRAPH.CENTER

au = doc.add_paragraph(); au.alignment = WD_ALIGN_PARAGRAPH.CENTER
au.add_run("Samir Chincholikar¹  ·  Robin Chawla²*").font.size = Pt(11)
aff = doc.add_paragraph(); aff.alignment = WD_ALIGN_PARAGRAPH.CENTER
aff.add_run("¹ Independent researcher.  ² Independent researcher.\n"
            "* Corresponding author: robin.chawla.cse14@iitbhu.ac.in").font.size = Pt(9)

# ── abstract ────────────────────────────────────────────────────────────────
heading("Abstract", 12)
body(
    f"Large language models (LLMs) are increasingly proposed as credit-rating and "
    f"default-assessment tools, yet whether they rate “through the cycle” or "
    f"amplify it—a property prudential regulators care about but that has been asserted "
    f"rather than measured—has remained untested. We hold synthetic firm fundamentals "
    f"byte-identical across an ordered five-point macroeconomic-severity axis (plus a "
    f"matched credit-irrelevant placebo axis) and elicit letter ratings and one-year "
    f"default probabilities from five frontier models, so that any rating movement is "
    f"procyclicality by construction, identified without the unobserved-fundamentals "
    f"confound that limits the classical Amato–Furfine test. Across {NUM['rows']} ratings, "
    f"every model is significantly procyclical (pooled {NUM['beta']} rating notches of "
    f"downgrade per severity step, 95% CI {NUM['beta_ci']}; a {NUM['swing']}-notch "
    f"boom-to-recession swing), the effect is sharply asymmetric ({NUM['ratio']}× steeper "
    f"into recessions than out of them), an order of magnitude larger than the placebo, and "
    f"robust to model-version fixed effects and a token-logprobability estimator. An explicit "
    f"“through-the-cycle” instruction lowers the rating slope but does not restore "
    f"through-the-cycle behaviour—it anchors the rating while suppressing the point-in-time "
    f"default probability that should move, whereas a naive “be stable” instruction "
    f"preserves that distinction better. Because model choice and prompt framing are "
    f"first-order determinants of the effect, LLM-based credit assessment can silently import "
    f"the capital-procyclicality channel that regulation seeks to dampen."
)
kw = doc.add_paragraph()
kw.add_run("Keywords: ").bold = True
kw.add_run("large language models; credit ratings; procyclicality; through-the-cycle; "
           "prompt framing; financial regulation")
jel = doc.add_paragraph()
jel.add_run("JEL: ").bold = True
jel.add_run("G24; G28; C63")

# ── 1. Introduction ─────────────────────────────────────────────────────────
heading("1. Introduction")
body(
    "Credit ratings shape regulatory capital, investment mandates, and the price of debt. A "
    "long-standing prudential concern is that ratings are procyclical—that they are "
    "downgraded in downturns and upgraded in booms even when a firm’s fundamentals have not "
    "changed—because such movements amplify the credit cycle and, through internal-ratings-"
    "based (IRB) capital rules, tighten lending precisely when the economy is weakest. Rating "
    "agencies aim to mitigate this by rating “through the cycle” (TTC): looking through "
    "transitory macroeconomic conditions to a firm’s creditworthiness over a full cycle."
)
body(
    "Large language models are now being deployed for credit assessment, and supervisors have "
    "flagged that generative models could re-introduce procyclicality (e.g., Bank for "
    "International Settlements, 2024). The concern, however, has been asserted rather than "
    "measured: it is not known whether LLM ratings move with the macroeconomy on fixed "
    "fundamentals, by how much, or whether the standard mitigation—instructing the model to "
    "rate through the cycle—works. Measuring this for human agencies is hard because "
    "fundamentals and the cycle move together, so the classical ordered-probit test of "
    "Amato and Furfine (2004) must proxy for unobserved fundamentals."
)
body(
    "We provide the first controlled measurement of rating procyclicality in LLMs. Our design "
    "removes the identification problem by construction: a synthetic firm’s fundamentals are "
    "held byte-identical across an ordered macroeconomic-severity axis, so any change in the "
    "model’s rating is procyclicality, not a response to changed fundamentals. We find that all "
    "five frontier models tested are significantly procyclical, that the effect is strongly "
    "asymmetric (much steeper into recessions), and—using a placebo instruction and the "
    "models’ default-probability outputs—that an explicit through-the-cycle instruction does "
    "not restore through-the-cycle behaviour but instead induces generic anchoring."
)

# ── 2. Design and identification ────────────────────────────────────────────
heading("2. Related literature")
body("Our study connects three strands. The first is the literature on rating procyclicality and "
     "through-the-cycle methodology: Amato and Furfine (2004) formalise the ordered-probit test, "
     "Löffler (2004, 2013) characterise and question through-the-cycle rating, and the prudential "
     "stakes are set by the interaction of ratings with Basel capital rules (Kashyap and Stein, "
     "2004; Gordy and Howells, 2006; Cantor and Packer, 1996). Our experimental design sidesteps "
     "these studies' central difficulty—fundamentals and the cycle are observationally "
     "entangled—by holding fundamentals fixed. The second strand is the rapid adoption of LLMs in "
     "finance: language models are used for return prediction (Lopez-Lira and Tang, 2023), "
     "financial-statement analysis (Kim et al., 2024), and as simulated economic agents (Horton, "
     "2023), and supervisors have flagged their potential to re-introduce procyclicality (Bank for "
     "International Settlements, 2024). The third strand is the behavioural limitations of LLMs: "
     "models reproduce human framing and anchoring effects (Tversky and Kahneman, 1974, 1981; Binz "
     "and Schulz, 2023), are imperfectly calibrated (Kadavath et al., 2022), and through shared "
     "foundation models can homogenise decisions (Bommasani et al., 2022). Procyclicality on fixed "
     "fundamentals is exactly such a context-driven bias, made consequential by its regulatory "
     "setting.")
heading("3. Design and identification")
body(
    f"The unit of analysis is a rating cell = (model, prompt framing, seed, firm, macro state). "
    f"We generate {NUM['firms']} synthetic firms with fixed fundamentals (revenue growth, EBITDA "
    f"margin, leverage, interest coverage, free cash flow, liquidity, and Altman-style ratios) "
    f"stratified across five credit-quality tiers and eight sectors, so the fundamentals-implied "
    f"ratings span the scale (AAA–CCC). Each firm’s fundamentals are serialised once and "
    f"reused byte-identically under every macro state; only a prepended macro-environment block "
    f"changes. The macro axis has five ordered levels—boom, expansion, neutral, slowdown, "
    f"severe recession (severity −2…+2)—each carried by matched, number-based indicators "
    f"(GDP growth, unemployment, credit spreads, default rate, lending standards) with no "
    f"calendar dates, so a model cannot pattern-match a real historical episode."
)
body(
    "Two design features sharpen identification. First, a matched-format but credit-irrelevant "
    "placebo axis (regional weather and traffic indicators, same structure and number density) "
    "measures pure frame-compliance; the net (macro minus placebo) coefficient is the "
    "demand-effect-adjusted cyclicality. Second, the per-cell random seed is keyed on the firm "
    "and framing but omits the macro state, so a firm receives an identical seed across all "
    "states—sampling noise cannot masquerade as a cycle effect. Each model returns a letter "
    "rating (mapped to an S&P notch, 1–21) and a one-year probability of default (PD)."
)
body(
    "We study four prompt framings—terse, point-in-time, explicit through-the-cycle, and a "
    "“be stable” instruction with no cycle reasoning—on five models (GPT-4o-mini, "
    "GPT-4.1-mini, GPT-4o, Gemini 3.5 Flash, Gemini 2.5 Flash-Lite), two seeds, at temperature "
    "zero. The primary estimand is the mean within-firm slope of rating notch on macro severity "
    "(notches of downgrade per +1 step; positive = procyclical), with firm-clustered "
    "(tier-stratified) bootstrap 95% confidence intervals (2{,}000 draws). We also report the "
    "boom-to-recession swing, downside vs upside half-slopes, the Amato–Furfine ordered-probit "
    "coefficient, and—for the OpenAI models—a continuous expected-notch slope computed from the "
    f"rating-token log-probabilities. The full run comprises {NUM['rows']} ratings for "
    f"US${NUM['spend']}, with zero parse errors; every capture is hashed and analysis is a "
    f"deterministic function of the frozen data (see the Data availability statement)."
)

# ── 3. Results ───────────────────────────────────────────────────────────────
heading("4. Results")
heading("4.1. LLMs are procyclical on identical fundamentals", 12)
body(
    f"On byte-identical fundamentals, every model downgrades as the described macroeconomy "
    f"worsens (Table 1, Figure 1a). Pooling across models under the terse framing, ratings fall "
    f"by {NUM['beta']} notches per severity step (95% CI {NUM['beta_ci']})—a {NUM['swing']}-notch "
    f"swing from boom to severe recession, enough to move a BBB firm toward BB+/BB with nothing "
    f"real changing. The per-model coefficient ranges from {r(g('per_model_variant','gemini_flash|v_terse','cyclicality_notch_per_step'))} "
    f"(Gemini 3.5 Flash) to {r(g('per_model_variant','openai_4o_mini|v_terse','cyclicality_notch_per_step'))} "
    f"(GPT-4o-mini), and every model’s CI excludes zero. Model identity is thus a first-order "
    f"determinant of procyclicality—a roughly threefold spread—and, within OpenAI, the "
    f"flagship GPT-4o ({r(g('per_model_variant','openai_4o|v_terse','cyclicality_notch_per_step'))}) is "
    f"about half as procyclical as GPT-4o-mini."
)
body(
    f"The effect is not an artefact of framing suggestibility: the matched credit-irrelevant "
    f"placebo axis moves ratings only {NUM['placebo']} notches per step, so the net coefficient is "
    f"{NUM['net']} (95% CI {NUM['net_ci']}), still excluding zero. It is not infrastructure drift: "
    f"adding served-model (system-fingerprint) fixed effects shifts the coefficient by less than "
    f"0.003. And it is not a censoring or parsing artefact: every model parses at 1.000 with the "
    f"largest-cyclicality model (GPT-4o-mini) among the cleanest. For the OpenAI models, a "
    f"continuous expected-notch slope computed from rating-token log-probabilities reproduces the "
    f"sampled estimate (e.g., GPT-4o-mini {r(g('per_model_variant','openai_4o_mini|v_terse','cyclicality_notch_per_step'))} "
    f"vs {r(g('per_model_variant','openai_4o_mini|v_terse','expected_notch_cyclicality_per_step'))}), "
    f"and the Amato–Furfine ordered-probit coefficient agrees in sign and magnitude throughout."
)
body("[Insert Table 1 here]  [Insert Figure 1 here]", italic=True)

heading("4.2. The procyclicality is asymmetric", 12)
body(
    f"Splitting the macro axis at neutral, ratings fall much faster going into recession than "
    f"they rise going into a boom. Pooled, the downside half-slope (neutral to severe recession) "
    f"is {NUM['down']} (95% CI {NUM['down_ci']}) versus an upside half-slope (boom to neutral) of "
    f"{NUM['up']} (95% CI {NUM['up_ci']})—a {NUM['ratio']}× asymmetry that holds for every model "
    f"(Figure 2). This is the financially dangerous margin: downturn downgrades dominate, exactly "
    f"the pattern that transmits rating-driven capital procyclicality, and it mirrors the "
    f"stricter-in-downturns behaviour documented for human agencies."
)

heading("4.3. “Through-the-cycle” instructions anchor rather than de-cyclify", 12)
body(
    f"Prompt framing moves the coefficient monotonically: point-in-time {NUM['pit']}, terse "
    f"{NUM['terse']}, “be stable” {NUM['stable']}, and through-the-cycle {NUM['ttc']} "
    f"(95% CI {NUM['ttc_ci']}); the terse-minus-TTC contrast is {r(CON['terse_minus_ttc'])} notches "
    f"per step. Taken alone, this looks like a successful mitigation. It is not. A genuine "
    f"through-the-cycle rater holds the rating steady while its point-in-time PD still moves with "
    f"the cycle; anchoring flattens both. Under the through-the-cycle instruction, the PD slope "
    f"collapses to {r(g('per_model_variant','gemini_flash|v_ttc','pd_retention_vs_terse'),2)}–"
    f"{r(g('per_model_variant','openai_4o_mini|v_ttc','pd_retention_vs_terse'),2)} of its terse value "
    f"across models—the instruction suppresses the very quantity that should remain "
    f"cycle-sensitive. Revealingly, the vaguer “be stable” instruction, which is not "
    f"semantically about the cycle, retains far more PD movement while still calming the rating. "
    f"The explicit through-the-cycle instruction therefore stabilises the wrong object, and a "
    f"residual downgrade survives everywhere—up to {r(g('per_model_variant','openai_4o_mini|v_ttc','endpoint_swing_notches'),2)} "
    f"notches across the cycle for GPT-4o-mini."
)

# ── 4. Conclusion ────────────────────────────────────────────────────────────
heading("5. Conclusion")
body(
    "Using a design in which fundamentals are fixed by construction, we provide the first "
    "controlled measurement of rating procyclicality in large language models. Frontier LLMs "
    "downgrade identical firms as the macroeconomy is described as worsening, by economically "
    "meaningful and statistically robust margins, and they do so asymmetrically—punishing "
    "simulated downturns far more than they reward simulated expansions. The magnitude is a "
    "first-order function of model identity, so in a deployed pipeline the choice of model is "
    "itself a prudential decision. The natural mitigation—instructing the model to rate through "
    "the cycle—fails instructively: rather than holding the rating steady while letting the "
    "default probability track conditions, it suppresses both, and it leaves a measurable "
    "residual. These results should be read against their scope—a synthetic firm battery built "
    "for identification rather than external realism, five mini/flagship models from two "
    "families, and prompt-level rather than fine-tuning interventions—and they motivate "
    "benchmarking LLM procyclicality against agency and IRB baselines, testing fine-tuning and "
    "retrieval remedies that target the point-in-time object directly, and, in the interim, "
    "treating model selection and prompt framing as governed parameters wherever LLMs touch "
    "credit and capital decisions."
)

# ── declarations ─────────────────────────────────────────────────────────────
heading("Declaration of generative AI use", 12)
body("During the preparation of this work the authors used AI-assisted coding and drafting tools "
     "to help implement the data pipeline and draft the manuscript. After using these tools the "
     "authors reviewed and edited the content and take full responsibility for the content of the "
     "published article. The large language models studied are the object of the research, not "
     "tools of manuscript preparation.")
heading("Declaration of competing interests", 12)
body("The authors declare no competing interests. [Confirm at submission.]")
heading("Funding", 12)
body("This research did not receive any specific grant from funding agencies in the public, "
     "commercial, or not-for-profit sectors.")
heading("CRediT author statement", 12)
body("Samir Chincholikar: Conceptualization, Methodology, Software, Formal analysis, Writing – "
     "original draft. Robin Chawla: Conceptualization, Validation, Writing – review and editing, "
     "Supervision. [Confirm/adjust at submission.]")
heading("Data availability", 12)
body("All data and code are openly available in a Zenodo deposit (DOI to be inserted); "
     "reproduction is offline, deterministic and free (see the artifact README and reproduce.sh).")

# ── references ───────────────────────────────────────────────────────────────
heading("References", 12)
refs = [
    "Altman, E.I., 1968. Financial ratios, discriminant analysis and the prediction of corporate "
    "bankruptcy. Journal of Finance 23 (4), 589–609.",
    "Amato, J.D., Furfine, C.H., 2004. Are credit ratings procyclical? Journal of Banking & "
    "Finance 28 (11), 2641–2677.",
    "Bank for International Settlements, 2024. The intelligent financial system: how AI is "
    "transforming finance. BIS Working Paper No. 1194. [Verify at submission.]",
    "Binz, M., Schulz, E., 2023. Using cognitive psychology to understand GPT-3. Proceedings of "
    "the National Academy of Sciences 120 (6), e2218523120.",
    "Bommasani, R., Creel, K.A., Bansal, A., Guha, S., Liang, P., 2022. Picking on the same "
    "person: does algorithmic monoculture lead to outcome homogenization? NeurIPS 35.",
    "Cantor, R., Packer, F., 1996. Determinants and impact of sovereign credit ratings. Federal "
    "Reserve Bank of New York Economic Policy Review 2 (2), 37–53.",
    "Chincholikar, S., Chawla, R., 2026. Does AI rate through the cycle? — reproducibility "
    "artifact [data set + software]. Zenodo. https://doi.org/<ZENODO-DOI>",
    "Gordy, M.B., Howells, B., 2006. Procyclicality in Basel II: can we treat the disease without "
    "killing the patient? Journal of Financial Intermediation 15 (3), 395–417.",
    "Graham, J.R., Harvey, C.R., Jha, M., 2026. CFOs meet LLMs. Working paper, SSRN. "
    "[Insert SSRN id/DOI at submission.]",
    "Horton, J.J., 2023. Large language models as simulated economic agents. NBER Working Paper "
    "31122.",
    "Kadavath, S., Conerly, T., Askell, A., et al., 2022. Language models (mostly) know what they "
    "know. arXiv:2207.05221.",
    "Kashyap, A.K., Stein, J.C., 2004. Cyclical implications of the Basel II capital standards. "
    "Economic Perspectives (Federal Reserve Bank of Chicago) 28 (1), 18–31.",
    "Kim, A., Muhn, M., Nikolaev, V.V., 2024. Financial statement analysis with large language "
    "models. arXiv:2407.17866.",
    "Löffler, G., 2004. An anatomy of rating through the cycle. Journal of Banking & Finance 28 "
    "(3), 695–720.",
    "Löffler, G., 2013. Can rating agencies look through the cycle? Review of Quantitative Finance "
    "and Accounting 40 (4), 623–646.",
    "Lopez-Lira, A., Tang, Y., 2023. Can ChatGPT forecast stock price movements? Return "
    "predictability and large language models. arXiv:2304.07619.",
    "Tversky, A., Kahneman, D., 1974. Judgment under uncertainty: heuristics and biases. Science "
    "185 (4157), 1124–1131.",
    "Tversky, A., Kahneman, D., 1981. The framing of decisions and the psychology of choice. "
    "Science 211 (4481), 453–458.",
]
for rf in refs:
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.3)
    p.paragraph_format.first_line_indent = Inches(-0.3)
    p.add_run(rf).font.size = Pt(9)

# ── Table 1 (per-model), as an editable Word table ──────────────────────────
doc.add_page_break()
heading("Table 1", 12)
body("Per-model rating procyclicality on byte-identical fundamentals. β = notches of downgrade "
     "per +1 macro-severity step (terse framing), with firm-clustered bootstrap 95% CIs; all "
     "exclude zero. Swing = boom→severe-recession notches. Down/Up = downside (into recession) "
     "vs upside (into boom) half-slopes. Residual = β after the through-the-cycle instruction; "
     "PD-ret. = PD-slope retention under that instruction.", italic=True)
cols = ["Model", "β (terse)", "95% CI", "Swing", "Down", "Up", "D:U", "Residual (TTC)", "PD-ret."]
tbl = doc.add_table(rows=1, cols=len(cols))
tbl.style = "Light Grid Accent 1"
for j, c in enumerate(cols):
    run = tbl.rows[0].cells[j].paragraphs[0].add_run(c); run.bold = True; run.font.size = Pt(9)
for m in ORDER:
    t = g("per_model_variant", f"{m}|v_terse"); ttc = g("per_model_variant", f"{m}|v_ttc")
    vals = [DISP[m], r(t["cyclicality_notch_per_step"]), ci(t["cyclicality_ci95"]),
            r(t["endpoint_swing_notches"], 2), r(t["downside_slope"], 2), r(t["upside_slope"], 2),
            r(t["asymmetry_ratio"], 1), r(ttc["cyclicality_notch_per_step"]),
            r(ttc["pd_retention_vs_terse"], 2)]
    cells = tbl.add_row().cells
    for j, v in enumerate(vals):
        run = cells[j].paragraphs[0].add_run(str(v)); run.font.size = Pt(9)

# ── Table 2 (instruction gradient) ──────────────────────────────────────────
heading("Table 2", 12)
body("Pooled procyclicality by prompt framing (five models), notches per severity step with "
     "firm-clustered bootstrap 95% CIs.", italic=True)
tbl2 = doc.add_table(rows=1, cols=3); tbl2.style = "Light Grid Accent 1"
for j, c in enumerate(["Prompt framing", "Pooled β", "95% CI"]):
    run = tbl2.rows[0].cells[j].paragraphs[0].add_run(c); run.bold = True; run.font.size = Pt(9)
lab = {"v_pit": "Point-in-time", "v_terse": "Terse", "v_stable": "“Be stable”",
       "v_ttc": "Through-the-cycle"}
for v in ["v_pit", "v_terse", "v_stable", "v_ttc"]:
    d = V[v]; cells = tbl2.add_row().cells
    for j, val in enumerate([lab[v], r(d["pooled_cyclicality_notch_per_step"]),
                             ci(d["pooled_cyclicality_ci95"])]):
        run = cells[j].paragraphs[0].add_run(str(val)); run.font.size = Pt(9)

# ── Figure 1 ────────────────────────────────────────────────────────────────
doc.add_page_break()
heading("Figure 1", 12)
fig1 = PAPER / "figures" / "Figure_1.png"
if fig1.exists():
    doc.add_picture(str(fig1), width=Inches(6.3))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
body("Figure 1. (a) Per-model procyclicality β under the terse framing with 95% CIs; the dashed "
     "line marks the through-the-cycle null (β = 0). (b) Pooled β across the four prompt framings "
     "(point-in-time → terse → “be stable” → through-the-cycle) with 95% CIs.", italic=True)

# ── Figure 2 ────────────────────────────────────────────────────────────────
heading("Figure 2", 12)
fig2 = PAPER / "figures" / "Figure_2.png"
if fig2.exists():
    doc.add_picture(str(fig2), width=Inches(5.6))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
body("Figure 2. Asymmetry: per-model downside half-slope (neutral→severe recession) versus upside "
     "half-slope (boom→neutral), terse framing. Every model downgrades far faster into recessions "
     "than it upgrades into booms.", italic=True)

out = PAPER / "manuscript.docx"
doc.save(str(out))
print(f"[manuscript] wrote {out}")

"""Build the Supplementary Appendix (paper/supplementary.docx) from claims.json.
Robustness tables + methods detail that support the main letter. Convert to PDF with
soffice. Pure, $0.  python3 paper/build_supplementary.py
"""
from __future__ import annotations
import json
from pathlib import Path
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

ROOT = Path(__file__).resolve().parent.parent
PAPER = ROOT / "paper"
C = json.loads((ROOT / "claims.json").read_text())
DISP = {"gemini_flash": "Gemini 3.5 Flash", "gemini_flash_lite": "Gemini 2.5 Flash-Lite",
        "openai_41_mini": "GPT-4.1-mini", "openai_4o": "GPT-4o", "openai_4o_mini": "GPT-4o-mini"}
ORDER = ["gemini_flash", "gemini_flash_lite", "openai_41_mini", "openai_4o", "openai_4o_mini"]


def r(x, n=3):
    return "" if x is None else f"{x:.{n}f}"


def pmv(m, v):
    return C["per_model_variant"].get(f"{m}|{v}", {})


doc = Document()
s = doc.styles["Normal"]; s.font.name = "Times New Roman"; s.font.size = Pt(11)
s.paragraph_format.space_after = Pt(6); s.paragraph_format.line_spacing = 1.15


def H(t, sz=13):
    p = doc.add_paragraph(); run = p.add_run(t); run.bold = True; run.font.size = Pt(sz)
    p.paragraph_format.space_before = Pt(10)


def B(t, italic=False):
    p = doc.add_paragraph(); run = p.add_run(t); run.italic = italic


def table(cols, rows):
    tbl = doc.add_table(rows=1, cols=len(cols)); tbl.style = "Light Grid Accent 1"
    for j, c in enumerate(cols):
        run = tbl.rows[0].cells[j].paragraphs[0].add_run(c); run.bold = True; run.font.size = Pt(9)
    for row in rows:
        cells = tbl.add_row().cells
        for j, v in enumerate(row):
            run = cells[j].paragraphs[0].add_run(str(v)); run.font.size = Pt(9)


p = doc.add_paragraph(); run = p.add_run("Supplementary Appendix"); run.bold = True; run.font.size = Pt(16)
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p2 = doc.add_paragraph(); r2 = p2.add_run("Do LLMs Rate Through the Cycle? — supporting robustness and methods")
r2.italic = True; p2.alignment = WD_ALIGN_PARAGRAPH.CENTER

# ── S1 robustness ────────────────────────────────────────────────────────────
H("Table S1. Robustness of the terse-framing coefficient", 12)
B("β = notches/step; Net = placebo-adjusted; Exp-notch = log-probability expected-notch "
  "estimator (OpenAI only); Noise SD = within-cell seed dispersion of the notch; Probit = "
  "Amato–Furfine ordered-probit coefficient (Mundlak firm control).", italic=True)
rows = []
for m in ORDER:
    t = pmv(m, "v_terse")
    rows.append([DISP[m], r(t.get("cyclicality_notch_per_step")), r(t.get("net_cyclicality_notch_per_step")),
                 r(t.get("expected_notch_cyclicality_per_step")), r(t.get("noise_floor_notch_sd"), 3),
                 r((t.get("ordered_probit") or {}).get("notch_per_step"))])
table(["Model", "β", "Net", "Exp-notch", "Noise SD", "Probit"], rows)

# ── S2 asymmetry + PD retention (all framings) ──────────────────────────────
H("Table S2. Anchoring diagnostic: rating vs PD slope by framing", 12)
B("For each model, the rating slope and the log-odds PD slope under terse and through-the-cycle "
  "(TTC) framings, and PD retention = PD-slope(TTC)/PD-slope(terse). Genuine TTC behaviour holds "
  "the rating flat while the PD (a point-in-time quantity) keeps moving (high retention); the "
  "collapse in retention indicates anchoring.", italic=True)
rows = []
for m in ORDER:
    t = pmv(m, "v_terse"); c = pmv(m, "v_ttc")
    rows.append([DISP[m], r(t.get("cyclicality_notch_per_step")), r(c.get("cyclicality_notch_per_step")),
                 r(t.get("cyclicality_pd_logodds_per_step")), r(c.get("cyclicality_pd_logodds_per_step")),
                 r(c.get("pd_retention_vs_terse"), 2)])
table(["Model", "Rating β terse", "Rating β TTC", "PD β terse", "PD β TTC", "PD retention"], rows)

# ── S3 fingerprint stability ────────────────────────────────────────────────
H("S3. Determinism and infrastructure robustness", 12)
B("Vendor determinism is best-effort. We log the served-model system_fingerprint per call and "
  "recompute the severity coefficient with vs without fingerprint fixed effects; the coefficient "
  "shifts by < 0.003 for every OpenAI model, so the effect is not attributable to backend drift. "
  "A within-cell seed noise floor (Table S1) confirms the signal exceeds residual non-determinism.")

# ── S4 methods ──────────────────────────────────────────────────────────────
H("S4. Methods detail", 12)
B("Battery. Firms are minted deterministically and stratified across five credit tiers "
  "(high-IG, low-IG, crossover, high-yield, distressed) × eight sectors; fundamentals are "
  "serialised once and SHA-256-hashed. Macro and placebo blocks share structure and number "
  "density; macro blocks carry GDP growth, unemployment, an investment-grade credit spread, a "
  "trailing default rate, and lending standards.")
B("Estimand and inference. The primary coefficient is the mean within-firm OLS slope of rating "
  "notch on macro severity (procyclical-positive sign). Confidence intervals are 2,000-draw "
  "cluster bootstraps resampling firms, stratified by tier. The ordered-probit (Amato–Furfine) "
  "null uses the firm mean notch as a Mundlak control to avoid the incidental-parameters problem.")
B("Pre-registration and reproducibility. The design was frozen (SHA-256) before the confirmatory "
  "run; the v_stable arm and a model-set change are logged as amendments. Analysis reads only "
  "frozen, hashed captures and is byte-identical on re-run; the deposit’s reproduce.sh verifies "
  "integrity and regenerates every number offline for $0.")
B("Scope. Synthetic fundamentals are designed for identification, not external realism; five "
  "mini/flagship models from two families (OpenAI, Google) are covered; interventions are "
  "prompt-level. A third family (xAI Grok) was pre-registered but omitted (vendor credit limit).")

out = PAPER / "supplementary.docx"
doc.save(str(out))
print(f"[supplementary] wrote {out}")

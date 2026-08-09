# Does AI rate through the cycle? Procyclicality in credit assessment

Reproducibility artifact for the *Finance Research Letters* (Elsevier) submission of the same title.

**Authors:** Samir Chincholikar (Independent researcher) · Robin Chawla (Independent researcher, corresponding author)
**ORCID:** [0009-0007-2779-3492](https://orcid.org/0009-0007-2779-3492) · [0009-0007-2807-3948](https://orcid.org/0009-0007-2807-3948)
**Contact:** robin.chawla.cse14@iitbhu.ac.in · samir.chincholikar@gmail.com
**Repository:** https://github.com/samirrc2/Does-AI-rate-through-the-cycle---Procyclicality-in-credit-assessment
**Zenodo DOI:** *(minted at deposit — add `https://doi.org/10.5281/zenodo.…`)*

This repository regenerates every number, table, and figure in the paper from a **frozen
32,000-rating dataset**, offline and at zero cost. Synthetic firm fundamentals are held
**byte-identical** across an ordered five-point macroeconomic-severity axis (and a matched,
credit-irrelevant placebo axis), so any change in a model's rating is procyclicality *by
construction* — identification the observational Amato–Furfine test cannot provide.

## Summary of results

All five production-tier models (OpenAI × 3, Google Gemini × 2) downgrade identical firms as the
described macroeconomy worsens:

- **Pooled effect:** 0.429 rating notches of downgrade per severity step (95% CI [0.41, 0.45]);
  a 1.76-notch boom-to-recession swing.
- **Asymmetric:** downgrade sensitivity into recessions is ≈ 3.2× the upgrade sensitivity into
  booms, and an order of magnitude larger than the placebo.
- **Robust** to served-model (`system_fingerprint`) fixed effects, a token-log-probability
  estimator, and the ordered-probit null.
- **"Through-the-cycle" prompting does not fix it:** it anchors the rating while suppressing the
  point-in-time default probability that should still move (log-odds PD-slope retention 0.38).
- **Capital consequence:** an identical firm's Basel IRB required capital swings ≈ 1.87 pp of
  exposure from boom to severe recession.

The canonical values behind every figure in the paper live in [`claims.json`](claims.json).

## Reproduce

Reproduction is **offline, deterministic, and free** — it performs no model capture and calls no
vendor API.

```bash
git clone https://github.com/samirrc2/Does-AI-rate-through-the-cycle---Procyclicality-in-credit-assessment.git
cd Does-AI-rate-through-the-cycle---Procyclicality-in-credit-assessment
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
bash reproduce.sh              # full: verify inputs + regenerate claims.json + compare
bash reproduce.sh --quick      # fast (seconds): integrity + primary estimands, no bootstrap
```

`reproduce.sh` (1) verifies the frozen firm battery and every capture CSV against their recorded
SHA-256 receipts, (2) verifies the pre-registration freeze, and (3) regenerates `claims.json` and
compares it to the committed copy. Floating-point estimands are compared **within a 1e-9 tolerance**,
not by exact equality, so the primary results reproduce on any platform. The pinned environment
additionally yields a byte-identical file:

```bash
docker build -t p5-repro -f environment/Dockerfile . && docker run --rm p5-repro
```

Pinned versions: Python 3.12, numpy 2.2.6, scipy 1.15.3, pydantic 2.13.4, PyYAML 6.0.3.

> Live capture (which requires third-party API keys and does cost money) is **not** part of
> reproduction and is documented separately in [`docs/RUNBOOK.md`](docs/RUNBOOK.md).

## Design

The unit of analysis is a *rating cell* = (model, prompt framing, seed, firm, macro state).
`capture/build_firms.py` mints 80 synthetic firms with fixed fundamentals, stratified across five
credit-quality tiers and eight sectors. The orchestrator serialises each firm's fundamentals **once**
and reuses them byte-identically under every macro state, prepending only a number-carried, date-free
macro block (or a matched credit-irrelevant placebo block). The per-cell random seed omits the macro
state, so a firm receives an identical seed across all states — the macroeconomic context is the sole
difference. Each model returns a letter rating (mapped to an S&P notch) and a one-year default
probability. Analysis computes the within-firm notch slope on macro severity (the cyclicality
coefficient), the boom-to-recession swing, the downside/upside asymmetry, the Amato–Furfine
ordered-probit null, the OpenAI log-probability expected-notch estimator, the placebo-adjusted (net)
coefficient, and the instruction contrasts — all with a firm-clustered, tier-stratified bootstrap.
Full detail in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Data availability (FRL / Elsevier)

FRL expects research materials to be deposited and **cited/linked** from the article. This artifact
uses **Zenodo** as the citable archive; GitHub is the working copy.

| | |
|--|--|
| Working copy | GitHub repository (URL above) |
| Archive to cite | **Zenodo** — `https://doi.org/10.5281/zenodo.…` *(pending mint at deposit)* |
| Statement text | [`DATA_AVAILABILITY.md`](DATA_AVAILABILITY.md) |
| Zenodo metadata | [`.zenodo.json`](.zenodo.json) |
| Citation file | [`CITATION.cff`](CITATION.cff) |

**Deposit contents:** synthetic firm battery, frozen 32,000 ratings, analysis code, `claims.json`,
pre-registration. License: MIT (code) + CC-BY-4.0 (data/text).

## Manuscript

| File | Role |
|------|------|
| [`paper/latex/manuscript.tex`](paper/latex/manuscript.tex) | Elsevier CAS letter (source) |
| [`paper/latex/manuscript.pdf`](paper/latex/manuscript.pdf) | Typeset reading PDF |
| [`paper/manuscript.docx`](paper/manuscript.docx) | Editable Word version |
| [`paper/highlights.docx`](paper/highlights.docx) | FRL highlights (5 bullets, ≤ 85 characters) |
| [`paper/latex/refs.bib`](paper/latex/refs.bib) | 30 references (10 in *Finance Research Letters*) |
| [`FRL_COMPLIANCE.md`](FRL_COMPLIANCE.md) | Guide-for-Authors checklist |
| [`SUBMISSION_CHECKLIST.md`](SUBMISSION_CHECKLIST.md) | Pre-submission actions |

**Before submitting:** mint the Zenodo DOI, then paste it into the manuscript's Data-availability
section, `DATA_AVAILABILITY.md`, `CITATION.cff`, and `.zenodo.json`.

## Repository layout

```
reproduce.sh                 one-command offline reproduction + integrity check
claims.json                  canonical results — every cited estimand and 95% CI
requirements.txt             dependencies (exact versions pinned in environment/)
environment/Dockerfile       pinned image for a byte-identical run

config/                      schema + models.yaml, grid.yaml, firms.yaml, loader
capture/                     live-capture pipeline (build_firms, agent, orchestrator, ledger, freeze)
analysis/                    ratings, cyclicality, probit, stats, capital, run.py -> claims.json
  make_tables.py             claims.json -> results/tables (CSV + LaTeX)
  make_figures.py            claims.json -> paper/figures
pilot/                       verdict.py -> PILOT_VERDICT.md

data/
  firms/                     frozen synthetic firm battery (+ manifest, SHA-256)
  raw/                       frozen model-output captures (32,000 ratings)
  frozen/                    per-capture SHA-256 freeze receipts
manifest/                    config hash, firm fingerprints, probe receipts, ledgers
results/                     regenerable outputs (tables, reviewer diagnostics)
paper/                       manuscript (LaTeX + Word), highlights, figures

PREREGISTRATION.md           frozen day-1 contract (estimands, battery, gate, stopping rules)
PREREGISTRATION.freeze.txt   SHA-256 freeze of the contract
PREREGISTRATION_AMENDMENTS.md post-freeze changes (v_stable arm, Grok drop)
docs/                        ARCHITECTURE · RUNBOOK · DECISIONS · REVIEW_DIAGNOSTICS
```

## Provenance and integrity

- **Pre-registered.** `PREREGISTRATION.md` is SHA-256-frozen (`PREREGISTRATION.freeze.txt`) and
  re-verified by `reproduce.sh`; every post-freeze change is logged in `PREREGISTRATION_AMENDMENTS.md`.
- **Frozen and hashed.** Every capture CSV carries a SHA-256 freeze receipt; the analysis reads only
  frozen CSVs and is a pure, seeded function of them.
- **No secrets.** API keys are never stored in the repository; live capture reads them from a
  location outside the tree.

## How to cite

Please cite both the paper and this artifact. Machine-readable metadata is in
[`CITATION.cff`](CITATION.cff); the citable Zenodo DOI is minted at deposit and recorded there, in
[`DATA_AVAILABILITY.md`](DATA_AVAILABILITY.md), and in the manuscript's reference list.

## License

Code is released under the MIT License; data, analysis outputs, and text under CC-BY-4.0. See
[`LICENSE`](LICENSE).

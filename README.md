# Does AI rate through the cycle? Procyclicality in credit assessment

Reproducibility artifact for the *Finance Research Letters* (Elsevier) paper of the same title.

**Authors:** Samir Chincholikar (Independent researcher) · Robin Chawla (Independent researcher, corresponding author)
**ORCID:** [0009-0007-2779-3492](https://orcid.org/0009-0007-2779-3492) · [0009-0007-2807-3948](https://orcid.org/0009-0007-2807-3948)
**Contact:** robin.chawla.cse14@iitbhu.ac.in · samir.chincholikar@gmail.com
**Repository:** https://github.com/samirrc2/Does-AI-rate-through-the-cycle---Procyclicality-in-credit-assessment
**Zenodo DOI:** [10.5281/zenodo.21864042](https://doi.org/10.5281/zenodo.21864042)

This repository regenerates every number, table, and figure in the paper from a **frozen
80,590-assessment dataset**, offline and at zero cost. Synthetic firm fundamentals are held
**byte-identical** across an ordered five-point macroeconomic-severity axis (and a matched,
credit-irrelevant placebo axis), so any change in a model's rating is procyclicality *by
construction* — identification the observational Amato–Furfine test cannot provide.

## Summary of results

All seven models (OpenAI × 4, Google Gemini × 3), spanning both families' full capability range
to the frontier tier, downgrade identical firms as the
described macroeconomy worsens:

- **Pooled effect:** 0.429 rating notches of downgrade per severity step (95% CI [0.41, 0.45]);
  a 1.76-notch boom-to-recession swing.
- **Asymmetric:** downgrade sensitivity into recessions is ≈ 3.2× the upgrade sensitivity into
  booms, and an order of magnitude larger than the placebo.
- **Robust** to served-model (`system_fingerprint`) fixed effects, a token-log-probability
  estimator, and the Amato--Furfine ordered probit.
- **"Through-the-cycle" prompting does not fix it:** it anchors the rating while suppressing the
  point-in-time default probability that should still move. Log-odds PD retention runs from
  0.587 down to −0.106 across the seven models, below the 0.75 reporting threshold in every one.
- **Capital consequence:** an identical firm's Basel IRB required capital swings ≈ 1.81 pp of
  exposure from boom to severe recession (95% CI [1.67, 1.94]), pooled across the five original
  models and computed on a ladder carrying the Basel 0.05% PD input floor.

The canonical values behind every figure in the paper live in [`claims.json`](claims.json).

## Reproduce

Reproduction is **offline, deterministic, and free** — it performs no model capture and calls no
vendor API.

```bash
git clone https://github.com/samirrc2/Does-AI-rate-through-the-cycle---Procyclicality-in-credit-assessment.git
cd Does-AI-rate-through-the-cycle---Procyclicality-in-credit-assessment
python3 -m venv .venv && source .venv/bin/activate   # Python 3.10+ required
pip install -r requirements.txt
bash reproduce.sh              # full: verify inputs + unit tests + regenerate claims.json + SHA match
bash reproduce.sh --quick      # fast (seconds): integrity + unit tests + primary estimands
python -m unittest tests.test_canonicalize -v   # canonicalize serialization only
```

`reproduce.sh` (1) verifies the frozen firm batteries and all 57 capture CSVs against their recorded
SHA-256 receipts, (2) verifies the pre-registration freeze, (3) regenerates `claims.json` and requires
a **byte-identical** SHA-256 match to the committed file, and (4) regenerates the seven revision
artifacts — `claims_revision.json`, `reviewer_revision.json`, `real_arm.json`, `ofat.json`,
`seeds_epochs.json`, `joint_spec.json`, `synthetic_real_overlap.json` — and byte-compares each. Floats are integer-quantized to
12 decimal places before write (`analysis/canonicalize.py`), so the hash is stable across platforms.

Optional pinned image (same check):

```bash
docker build -t p5-repro -f environment/Dockerfile . && docker run --rm p5-repro
```

The committed results regenerate byte-for-byte under Python 3.11.5 with numpy 2.4.6, scipy 1.17.1, pydantic 2.13.4, PyYAML 6.0.3, matplotlib 3.11.2 and pymupdf 1.28.2 (recorded in `results/environment.json`; `reproduce.sh` re-verifies the reproduction on every run). `requirements.txt` sets minimums, not pins, so a newer set may also work; Python 3.10 is a hard floor because the config schema uses PEP 604 annotations.

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
ordered probit, the OpenAI log-probability expected-notch estimator, the placebo-adjusted (net)
coefficient, and the instruction contrasts — all with a firm-clustered, tier-stratified bootstrap.
Full detail in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Data availability (FRL / Elsevier)

FRL expects research materials to be deposited and **cited/linked** from the article. This artifact
uses **Zenodo** as the citable archive; GitHub is the working copy.

| | |
|--|--|
| Working copy | GitHub repository (URL above) |
| Archive to cite | **Zenodo** — [10.5281/zenodo.21864042](https://doi.org/10.5281/zenodo.21864042) |
| Statement text | [`DATA_AVAILABILITY.md`](DATA_AVAILABILITY.md) |
| Zenodo metadata | [`.zenodo.json`](.zenodo.json) |
| Citation file | [`CITATION.cff`](CITATION.cff) |

**Deposit contents:** synthetic and real firm batteries, 80,590 frozen assessments, analysis code,
`claims.json` and `claims_revision.json`,
pre-registration. License: MIT (code) + CC-BY-4.0 (data/text).

## Manuscript

| File | Role |
|------|------|
| [`paper/src/manuscript.tex`](paper/src/manuscript.tex) | Elsevier CAS letter (source) |
| [`paper/out/manuscript.pdf`](paper/out/manuscript.pdf) | Typeset reading PDF |
| [`paper/out/manuscript.docx`](paper/out/manuscript.docx) | Editable Word version |
| [`paper/out/highlights.docx`](paper/out/highlights.docx) | FRL highlights (5 bullets, ≤ 85 characters) |
| [`paper/src/refs.bib`](paper/src/refs.bib) | 29 references (5 in *Finance Research Letters*) |
| [`paper/out/manuscript_tracked.pdf`](paper/out/manuscript_tracked.pdf) | Tracked-changes PDF against the submitted version |
| [`paper/out/manuscript_anonymous.pdf`](paper/out/manuscript_anonymous.pdf) | Double-blind PDF |
| [`paper/out/FRL-Response-to-Reviewers.pdf`](paper/out/FRL-Response-to-Reviewers.pdf) | Point-by-point response |

**Before submitting:** run `bash paper/tools/build_all.sh`, which rebuilds every deliverable above
and runs the staleness, word-count, number-binding, table and locator gates in one pass.

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
  make_figures.py            claims.json -> paper/src/figures (7-model forest + gradient)
pilot/                       verdict.py -> PILOT_VERDICT.md

data/
  firms/                     frozen synthetic firm battery (+ manifest, SHA-256)
  raw/                       frozen model-output captures (80,590 retained assessments)
  frozen/                    per-capture SHA-256 freeze receipts
manifest/                    config hash, firm fingerprints, probe receipts, ledgers
results/                     regenerable outputs (tables, reviewer diagnostics)
paper/
  src/                       manuscript sources only — .tex, .bib, class files, tables, figures
  out/                       every generated deliverable — PDFs and Word files, nothing else
  tools/                     build.sh, build_tracked.sh, build_response.py and the checkers
  reviews/                   the referee reports

PREREGISTRATION.md           frozen day-1 contract (estimands, battery, gate, stopping rules)
PREREGISTRATION.freeze.txt   SHA-256 freeze of the contract
PREREGISTRATION_AMENDMENTS.md post-freeze changes (8 amendments: v_stable arm, Grok drop,
                             title, frontier probe + grids, OFAT decomposition, real-fundamentals
                             and replication-stability arms, configuration hash)
docs/                        ARCHITECTURE · RUNBOOK · DECISIONS · REVIEW_DIAGNOSTICS
```

## Provenance and integrity

- **Pre-registered.** `PREREGISTRATION.md` is SHA-256-frozen (`PREREGISTRATION.freeze.txt`) and
  re-verified by `reproduce.sh`; every post-freeze change is logged in `PREREGISTRATION_AMENDMENTS.md`.
- **Frozen and hashed.** Every capture CSV carries a SHA-256 freeze receipt; the analysis reads only
  frozen CSVs and is a pure, seeded function of them.
- **Capture-level error gate.** `capture/freeze.py` refuses to freeze any capture whose error rate
  exceeds the 2% threshold set in `PREREGISTRATION.md` §5. It rejects a whole file and has no
  mechanism for discarding individual rows, so four captures were excluded entirely rather than
  trimmed. Three were extra-seed captures, which is why three models carry two replicates per cell
  rather than five; the fourth was a real-firm GPT-6 Astra through-the-cycle run that feeds no
  reported result. All four are listed with error rates and causes in
  `results/revision_extras.json`.
- **No secrets.** API keys are never stored in the repository; live capture reads them from a
  location outside the tree.

## How to cite

Please cite both the paper and this artifact. Machine-readable metadata is in
[`CITATION.cff`](CITATION.cff); the citable Zenodo DOI is
[10.5281/zenodo.21864042](https://doi.org/10.5281/zenodo.21864042), also recorded in
[`DATA_AVAILABILITY.md`](DATA_AVAILABILITY.md) and in the manuscript's reference list.

## License

Code is released under the MIT License; data, analysis outputs, and text under CC-BY-4.0. See
[`LICENSE`](LICENSE).

# Do LLMs Rate Through the Cycle?
### Reproducibility artifact — the first controlled measurement of procyclicality in LLM credit ratings

This repository regenerates every number, table, and figure in the Finance Research
Letters submission *"Do LLMs Rate Through the Cycle?"* from a **frozen 32,000-rating
dataset**. Firm fundamentals are held **byte-identical** across an ordered five-point
macroeconomic-severity axis (plus a matched credit-irrelevant placebo axis), so any
rating movement is procyclicality *by construction* — an identification the classical
Amato–Furfine test cannot achieve.

**Headline result.** All five frontier LLMs are significantly procyclical on identical
fundamentals — pooled **0.43 rating notches of downgrade per severity step**
(95% CI [0.41, 0.45]), a 1.76-notch boom-to-recession swing, ~3–4× steeper into
recessions than out of them, robust to model-version (`system_fingerprint`) fixed
effects and an order of magnitude larger than the placebo. An explicit
"through-the-cycle" instruction does not restore through-the-cycle behaviour — it
anchors the rating while suppressing the point-in-time default probability that should
move.

---

## Reproduce (offline, deterministic, $0 — no vendor API, no cost)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # analysis needs: pydantic, PyYAML, numpy, scipy
bash reproduce.sh                         # verify frozen inputs + regenerate + compare
```

`reproduce.sh` (1) verifies the frozen firm battery and every capture CSV against their
recorded SHA-256 hashes, (2) verifies the pre-registration freeze, (3) regenerates
`claims.json` and checks it against the committed copy. It performs **no** model
capture. For a byte-identical run in a pinned environment, use `environment/Dockerfile`:

```bash
docker build -t p5-repro -f environment/Dockerfile . && docker run --rm p5-repro
```

Live model capture (which requires third-party API keys and does cost money) is
**not** part of reproduction; it is documented separately in `docs/RUNBOOK.md`.

## Repository structure

```
reproduce.sh              one-command offline reproduction + integrity check
requirements.txt          analysis dependencies (pinned in environment/)
claims.json               CANONICAL results — every cited number + 95% CI
LICENSE                   code MIT · data/text CC-BY-4.0
CITATION.cff              how to cite this artifact
.zenodo.json              Zenodo deposit metadata
DATA_AVAILABILITY.md      FRL Option-C data statement (Zenodo DOI)

config/                   schema, models.yaml, grid.yaml, firms.yaml, loader
capture/                  live-capture pipeline (agent, orchestrator, ledger, probe, freeze)
analysis/                 ratings, cyclicality, probit, stats, run (-> claims.json), review_diag
pilot/                    verdict.py -> PILOT_VERDICT.md / PILOT_RESULTS.md
run_all.sh  status.py     capture runner + live progress (live path only)
freeze_prereg.py          re-hash the pre-registration

data/
  firms/                  frozen synthetic firm battery (+ manifest, SHA-256)
  raw/                    frozen model-output captures (32,000 ratings)
  frozen/                 per-capture SHA-256 freeze receipts
manifest/                 config hash, firm fingerprints, probe receipts, ledgers, spend
environment/              Dockerfile + pinned versions (byte-identical run)
metadata/                 metadata.yml (deposit metadata)
results/                  derived, regenerable outputs
  tables/                 table1-3 (csv + LaTeX), regenerated from claims.json
  review_diag_full.txt    full-run reviewer diagnostics dump
paper/                    the FRL manuscript (single source of truth)
  latex/                  Elsevier CAS (cas-sc) submission set
    manuscript.tex/.pdf   the letter in the official Elsevier template
    refs.bib              18-reference bibliography
    tables/  *.tex        claims-gated LaTeX tables
    Figure_1/2.pdf  cas-*.cls/.sty/.bst  build.sh
  highlights.txt          FRL highlights (<=85 chars each)
  figures/                Figure_1, Figure_2 source (vector PDF + 300-dpi PNG)
SUBMISSION_CHECKLIST.md    FRL requirement-by-requirement status
analysis/make_tables.py    claims.json -> results/tables
analysis/make_figures.py   claims.json -> paper/figures

PREREGISTRATION.md        frozen day-1 contract (estimands, battery, gate, stops)
PREREGISTRATION.freeze.txt   SHA-256 freeze of the contract
PREREGISTRATION_AMENDMENTS.md   post-freeze changes (v_stable arm, Grok drop, ...)
docs/                     ARCHITECTURE · RUNBOOK · DECISIONS · RELATED_WORK ·
                          REVIEW_DIAGNOSTICS · killshot-report (novelty sweep)
```

## Design in one paragraph

The unit is a *rating cell* = (model, prompt framing, seed, firm, macro state).
`build_firms.py` mints synthetic firms with fixed fundamentals stratified across five
credit tiers × eight sectors; the orchestrator serializes each firm's fundamentals
**once** and reuses them byte-identically under every macro state, prepending only a
number-carried, era-free macro block (and a matched credit-irrelevant placebo block).
The per-cell seed omits the macro state, so a firm sees an identical seed across all
states — the macro context is the sole difference. Each model returns a letter rating
(→ S&P notch) and a one-year default probability. Analysis reduces replicate seeds to a
per-cell median notch and computes the within-firm notch slope on macro severity (the
cyclicality coefficient), the boom→recession swing, the downside/upside asymmetry, the
Amato–Furfine ordered-probit null, the OpenAI log-probability expected-notch estimator,
the placebo-adjusted (net) coefficient, and the instruction contrasts — all with a
firm-clustered bootstrap. See `docs/ARCHITECTURE.md`.

## Provenance & integrity

- **Pre-registered.** `PREREGISTRATION.md` is SHA-256-frozen (`PREREGISTRATION.freeze.txt`);
  `reproduce.sh` re-verifies it. Post-freeze changes are in `PREREGISTRATION_AMENDMENTS.md`.
- **Frozen + hashed.** Every capture CSV has a SHA-256 freeze receipt; analysis reads
  only frozen CSVs and is a pure, seeded function of them.
- **Novelty sweep.** `docs/killshot-report.md` documents the 12-vector prior-art sweep
  (no direct hit).

## How to cite

See `CITATION.cff`. The Zenodo DOI (minted at deposit) is recorded there,
in `DATA_AVAILABILITY.md`, and in the manuscript's reference list.

## License

Code: MIT. Data, analysis outputs, and text: CC-BY-4.0. See `LICENSE`.

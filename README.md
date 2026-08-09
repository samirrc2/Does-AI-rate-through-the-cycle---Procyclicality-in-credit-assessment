# Does AI rate through the cycle?

Reproducibility artifact for ***Finance Research Letters*** (Elsevier).

**Title:** Does AI rate through the cycle? Procyclicality in credit assessment  

**Authors:** Samir Chincholikar; Robin Chawla (corresponding)  
**ORCID:** [0009-0007-2779-3492](https://orcid.org/0009-0007-2779-3492); [0009-0007-2807-3948](https://orcid.org/0009-0007-2807-3948)  
**Contact:** robin.chawla.cse14@iitbhu.ac.in; samir.chincholikar@gmail.com  
**GitHub:** https://github.com/samirrc2/Does-AI-rate-through-the-cycle---Procyclicality-in-credit-assessment  
**Zenodo DOI:** *(add `https://doi.org/10.5281/zenodo.…` when minted)*  

**One finding:** On **byte-identical** firm fundamentals, five production-tier LLMs are
procyclical — pooled **0.43 notches/step** (95% CI [0.41, 0.45]); boom→recession ~1.76
notches; ~3× steeper into recessions than out. A “through-the-cycle” prompt anchors
ratings rather than restoring true TTC behaviour.

---

## Reproduce (offline, no API keys, $0)

```bash
git clone https://github.com/samirrc2/Does-AI-rate-through-the-cycle---Procyclicality-in-credit-assessment.git
cd Does-AI-rate-through-the-cycle---Procyclicality-in-credit-assessment
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
bash reproduce.sh
```

What it does: verifies frozen SHA-256s + preregistration → regenerates `claims.json` →
compares to the committed file. **No** live model capture.

- Fast check: `bash reproduce.sh --quick`
- Byte-identical full hash (recommended for archive):  
  `docker build -t p5-repro -f environment/Dockerfile . && docker run --rm p5-repro`

Live API capture (cost/keys) is **not** required to reproduce published numbers — see
[`docs/RUNBOOK.md`](docs/RUNBOOK.md).

---

## Data availability (FRL / Elsevier)

FRL expects research materials to be deposited and **cited/linked** from the article.
This artifact uses **Zenodo** as the citable archive; GitHub is the working copy.

| | |
|--|--|
| Working copy | GitHub URL above |
| Archive to cite | **Zenodo** — `https://doi.org/10.5281/zenodo.…` *(pending)* |
| Statement text | [`DATA_AVAILABILITY.md`](DATA_AVAILABILITY.md) |
| Zenodo metadata | [`.zenodo.json`](.zenodo.json) |
| Citation file | [`CITATION.cff`](CITATION.cff) |

**Deposit contents:** synthetic firm battery, frozen 32,000 ratings, analysis code,
`claims.json`, preregistration. License: MIT (code) + CC-BY-4.0 (data/text).

---

## Manuscript (*Finance Research Letters*)

| File | Role |
|------|------|
| [`paper/latex/manuscript.tex`](paper/latex/manuscript.tex) | Elsevier CAS letter (source) |
| [`paper/latex/manuscript.pdf`](paper/latex/manuscript.pdf) | Reading PDF |
| [`paper/manuscript.docx`](paper/manuscript.docx) | Word upload option |
| [`paper/highlights.txt`](paper/highlights.txt) / [`.docx`](paper/highlights.docx) | FRL highlights |
| [`FRL_COMPLIANCE.md`](FRL_COMPLIANCE.md) | Guide-for-Authors checklist |
| [`SUBMISSION_CHECKLIST.md`](SUBMISSION_CHECKLIST.md) | Pre-submit actions |

**Before submit:** mint Zenodo DOI → paste into manuscript Data availability,
`DATA_AVAILABILITY.md`, `CITATION.cff`, and `.zenodo.json`.

---

## Layout (short)

```
reproduce.sh, requirements.txt, claims.json
data/firms  data/raw  data/frozen     # frozen hashed inputs
analysis/   config/                   # offline analysis
paper/latex/                          # FRL CAS manuscript
environment/Dockerfile                # pinned byte-identical run
```

Design detail: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

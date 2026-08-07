# FRL submission checklist — "Do LLMs Rate Through the Cycle?"

Status of every Finance Research Letters requirement. ✅ done · ✍️ needs author input.

## Manuscript files (in `paper/`)
| Item | FRL rule | Status | File |
|---|---|---|---|
| Main text | ≤ 2,500 words (excl. abstract/refs/tables/figs/declarations) | ✅ **~1,600 words** | `latex/manuscript.tex` |
| **Elsevier CAS template** | official `cas-sc` class | ✅ **the submission** (single source) | `paper/latex/` |
| Editable source | .docx or .tex (no PDF as source) | ✅ .tex (CAS) | `latex/manuscript.tex` |
| Reading copy | — | ✅ | `latex/manuscript.pdf` |
| Abstract | ≤ 250 words, standalone, no refs | ✅ **205 words** | in manuscript |
| Highlights | 3–5 bullets, ≤ 85 chars each | ✅ 5 bullets, all ≤ 76 | `highlights.txt` |
| Keywords | 1–7 | ✅ 6 | in manuscript |
| Numbered sections | 1, 1.1, … | ✅ §1–4 | in manuscript |
| Tables | editable text, captions, notes below, no vertical rules | ✅ Tables 1–2 + Appendix Table 3 | in `manuscript.tex` |
| Figures | numbered, captioned, ≥300 dpi + vector | ✅ Fig 1–2 (PDF + 300-dpi PNG) | `figures/` |
| Robustness/appendix | robustness + methods | ✅ | Appendix in `manuscript.tex` |
| References | Harvard author–date, DOIs | ✅ **21 real references** (all web-verified, 0 placeholders) | `latex/refs.bib` |

## Declarations (in the manuscript, before references)
| Item | Status |
|---|---|
| Declaration of generative AI use | ✅ drafted |
| Competing interests | ✍️ confirm ("none" drafted) |
| Funding | ✅ "no specific grant" drafted |
| CRediT author statement | ✍️ confirm roles (draft provided) |
| Data availability | ✅ drafted (Zenodo DOI slot) |

## Authorship / admin
| Item | Status |
|---|---|
| Title page (authors, affiliations) | ✅ Samir Chincholikar; Robin Chawla |
| Corresponding author + institutional email | ✅ Robin Chawla · robin.chawla.cse14@iitbhu.ac.in |
| ORCID (all authors) | ✅ recorded in CITATION.cff / metadata |
| Submission fee USD $200 | ✍️ pay at submission |
| Single-anonymised review | ✅ no manuscript anonymisation needed |
| SSRN preprint (optional, free) | ✍️ opt in if desired |

## Data / reproducibility (FRL Option C)
| Item | Status |
|---|---|
| Data + code deposited in a repository | ✍️ upload the folder to **Zenodo**, mint DOI |
| Data availability statement citing the deposit | ✅ `DATA_AVAILABILITY.md` + in manuscript |
| Reproducible from frozen data, offline, $0 | ✅ `reproduce.sh` (verified) |

## Before you click submit
1. Insert the reserved **Zenodo DOI** in: `paper/latex/refs.bib` (artifact entry) + `manuscript.tex` (Data availability),
   `DATA_AVAILABILITY.md`, `CITATION.cff`, `.zenodo.json`.
2. Confirm/adjust the **CRediT** roles and the **competing-interests** line.
3. Finalise the **secondary references** (framing-effect, LLM-calibration, structural
   rating-standards, Markov migration) with exact bibliographic details — see
   `docs/RELATED_WORK.md`.
4. Delete the stray `results/_preview_p1.png` (render artefact) on your machine.
5. (Optional) expand the main text toward ~2,000–2,400 words if a reviewer wants more depth —
   there is ample headroom under the 2,500 cap.

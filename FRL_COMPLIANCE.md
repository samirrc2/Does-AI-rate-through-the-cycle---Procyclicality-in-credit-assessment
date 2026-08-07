# FRL author-guide compliance — line-by-line

Every requirement from the Finance Research Letters *Guide for Authors* (the PDF in the
FRL folder), mapped to our submission. ✅ met · ✍️ author action at submission.
Primary manuscript = the Elsevier CAS LaTeX in `paper/latex/`.

## Scope & length
| # | Guide requirement | Status | Where / note |
|---|---|---|---|
| 1 | In scope: challenges methods / methodological contingency; not a single-country replication | ✅ | First controlled test of an asserted-but-unmeasured property |
| 2 | Main text **< 2,500 words** (excl. abstract, refs, tables, figures, captions, declarations, appendices) | ✅ **~1,600 words** | `manuscript.tex` §1–5 |
| 3 | Concise, clearly written, conveys novelty | ✅ | intro states RQ + 3 contributions |

## Front matter
| # | Requirement | Status | Where |
|---|---|---|---|
| 4 | Title succinct & meaningful | ✅ | "Do LLMs Rate Through the Cycle? …" |
| 5 | Abstract **≤ 250 words**, standalone, factual, minimal refs | ✅ **205 words** | `\begin{abstract}` |
| 6 | Keywords 1–7, English | ✅ 6 | `\begin{keywords}` |
| 7 | Highlights: separate file, 3–5 bullets, **≤ 85 chars each** | ✅ 5 bullets ≤76 | `paper/highlights.txt` (+ in CAS) |
| 8 | JEL classification | ✅ G24; G28; C63 | (CAS front matter) |
| 9 | Title page: authors, affiliations, corresponding contact | ✅ | CAS `\author`/`\affiliation`/`\cormark` |
| 10 | Corresponding author: **institutional email + verified institution** | ✍️ | Robin: `robin.chawla.cse14@iitbhu.ac.in` (email institutional; affiliation listed "Independent researcher" per author choice — confirm this is acceptable to you) |
| 11 | ORCID for **all** authors | ✅ | 0009-0007-2779-3492; 0009-0007-2807-3948 |

## Structure & formatting
| # | Requirement | Status | Where |
|---|---|---|---|
| 12 | Numbered sections 1, 1.1, … ; abstract unnumbered | ✅ | §1–5, subsections 4.1–4.3 |
| 13 | Cross-reference by number (not "the text") | ✅ | `Section~\ref`, `Table~\ref`, `Fig.~\ref` |
| 14 | Tables: editable text, captions, notes below, no vertical rules; cited in text | ✅ | Tables 1–2 + Appendix; booktabs |
| 15 | Figures: numbered, captioned, cited; vector/≥300 dpi | ✅ | Fig. 1–2 (vector PDF) |
| 16 | Figures/tables freestanding (understandable without the text) | ✅ | self-contained captions + notes |
| 17 | Same font, black throughout; no highlighting | ✅ | LaTeX default |
| 18 | Equations/variables as editable text | ✅ (n/a — no display math) | |
| 19 | Editable source: .tex or .docx (no PDF as source) | ✅ | `.tex` (CAS) — single source |

## References
| # | Requirement | Status | Where |
|---|---|---|---|
| 20 | All in-text cites in the list and vice versa | ✅ (0 undefined) | 18 refs, all cited |
| 21 | Author-date style; "et al." for 3+; consistent | ✅ | natbib authoryear (cas-model2-names) |
| 22 | DOIs encouraged; complete data (authors/title/year/venue/pages) | ✅ (verify pages/DOIs at proof) | `refs.bib` |
| 23 | Abstract references in full (if any) | ✅ n/a | abstract has none |

## Declarations (a section before the reference list)
| # | Requirement | Status | Where |
|---|---|---|---|
| 24 | **Declaration of generative AI use** (new section before refs) | ✅ | `\section*{Declaration of generative AI use}` |
| 25 | Declaration of competing interest | ✅ | present |
| 26 | Funding (or state none) | ✅ | "no specific grant" |
| 27 | CRediT author statement | ✅ | `\credit{}` + `\printcredits` |
| 28 | Acknowledgements (only if help received) before refs | ✅ n/a | none needed |
| 29 | Data availability statement | ✅ | present + `DATA_AVAILABILITY.md` |

## Research data (Option C)
| # | Requirement | Status | Where |
|---|---|---|---|
| 30 | Deposit data/code in a repository; cite/link it | ✍️ Zenodo DOI at release | GitHub pushed; Zenodo pending |
| 31 | Data statement citing the deposit | ✅ | Data availability + `refs.bib` artifact |

## Submission-system checklist (Guide §"Submission checklist")
| # | Requirement | Status | Note |
|---|---|---|---|
| 32 | Corresponding author full contact (email, postal, phone) | ✍️ | enter in Editorial Manager |
| 33 | All files uploaded (manuscript, highlights, figures, tables, supplementary) | ✍️ | upload set from `paper/` |
| 34 | Spelling & grammar checked | ✅ | proofread |
| 35 | Refs cited ↔ listed | ✅ | verified 0 undefined |
| 36 | Permissions for any copyrighted material | ✅ n/a | all original/synthetic |
| 37 | Submission fee **USD $200** | ✍️ | pay at submission |
| 38 | Position paper in current literature; state contribution to theory/practice | ✅ | §2 Related literature + intro contributions |

## Author actions remaining
1. Mint the **Zenodo DOI** (cut a GitHub release) → paste into `manuscript.tex` (`refs.bib` artifact
   entry + Data availability), `DATA_AVAILABILITY.md`, `CITATION.cff`, `.zenodo.json`; recompile.
2. Confirm the corresponding-author **email/affiliation** pairing (#10) is acceptable to you.
3. Pay the $200 fee; enter full corresponding-author contact details in Editorial Manager.
4. Verify reference **page numbers/DOIs** at proof (FRL applies its own style post-acceptance).

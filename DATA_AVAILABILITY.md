# Data availability statement

*(For the Finance Research Letters submission — Elsevier research-data practice:
deposit supporting materials in a repository, then cite and link them from the article.)*

All data and code required to reproduce every number, table and figure in this article
are openly available on GitHub and will be archived on Zenodo:

https://github.com/samirrc2/Does-AI-rate-through-the-cycle---Procyclicality-in-credit-assessment

> Chincholikar, S. & Chawla, R. (2026). *Does AI rate through the cycle? —
> reproducibility artifact* [data set + software]. Zenodo.
> https://doi.org/10.5281/zenodo.<ID>

Insert the minted Zenodo URL (`https://doi.org/10.5281/zenodo.…`) here, in
`CITATION.cff`, `.zenodo.json`, and the manuscript Data availability / reference list.

The deposit contains:

- **Synthetic firm battery** (`data/firms/*.jsonl`) — deterministically generated,
  SHA-256-hashed. No real firms or real financial data are used.
- **Frozen model-output captures** (`data/raw/*.csv`, 32,000 ratings) with per-file
  SHA-256 freeze receipts (`data/frozen/*.freeze.json`).
- **Analysis code** (`config/`, `capture/`, `analysis/`, `pilot/`) and the canonical
  results (`claims.json`).
- **Provenance**: frozen pre-registration (`PREREGISTRATION.md` +
  `PREREGISTRATION.freeze.txt` + amendments), decision log, and novelty sweep.

**Reproduction is offline, deterministic and free** — `bash reproduce.sh` regenerates
the analysis from the frozen captures and requires a byte-identical `claims.json`
(floats are integer-quantized to 12 decimals for cross-platform stability; no vendor
API calls, no cost). Live model capture (OpenAI / Google keys) is documented in
`docs/RUNBOOK.md` but is **not** needed to reproduce the reported results.

No proprietary, personal, or confidential data are used or distributed.

# Data availability statement

*(For the Finance Research Letters submission — Elsevier research-data practice:
deposit supporting materials in a repository, then cite and link them from the article.)*

All data and code required to reproduce every number, table and figure in this article
are openly available on GitHub and archived on Zenodo:

https://github.com/samirrc2/Does-AI-rate-through-the-cycle---Procyclicality-in-credit-assessment

> Chincholikar, S. & Chawla, R. (2026). *Does AI rate through the cycle? —
> reproducibility artifact* [data set + software]. Zenodo.
> https://doi.org/10.5281/zenodo.21864041

That is the concept DOI: it always resolves to the newest deposited version. Cite it
rather than a per-version DOI, so the citation keeps pointing at the archive that matches
the published article.

The deposit contains:

- **Synthetic firm battery** (`data/firms/full.jsonl`, `pilot.jsonl`) — 80 and 40
  deterministically generated, SHA-256-hashed firms. No proprietary data.
- **Real-firm battery** (`data/firms/real.jsonl`, 80 firms) — built in revision from
  public SEC company facts, with the fetched filings cached in `data/sec_cache/`. The
  figures are public regulatory disclosures; no licensed or personal data are used.
- **Frozen model-output captures** (`data/raw/*.csv`, 61 files, 99,366 rows) with
  per-file SHA-256 freeze receipts (`data/frozen/*.freeze.json`, 57 receipts covering
  90,291 rows). The reported analysis reads 80,691 of those rows, of which 101 are
  recorded API failures and 80,590 are retained observations.
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

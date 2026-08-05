# Data availability statement

*(For the Finance Research Letters submission — satisfies the journal's Research-data
"Option C": data deposited in a repository and cited/linked from the article.)*

All data and code required to reproduce every number, table and figure in this article
are openly available in a Zenodo deposit:

> Chincholikar, S. (2026). *Do LLMs Rate Through the Cycle? — reproducibility
> artifact* [data set + software]. Zenodo. https://doi.org/<ZENODO-DOI>  ← *to be
> minted at deposit; insert the reserved DOI here and in the manuscript reference list.*

The deposit contains:

- **Synthetic firm battery** (`data/firms/*.jsonl`) — deterministically generated,
  SHA-256-hashed. No real firms or real financial data are used.
- **Frozen model-output captures** (`data/raw/*.csv`, 32,000 ratings) with per-file
  SHA-256 freeze receipts (`data/frozen/*.freeze.json`).
- **Analysis code** (`config/`, `capture/`, `analysis/`, `pilot/`) and the canonical
  results (`claims.json`).
- **Provenance**: the frozen pre-registration (`PREREGISTRATION.md` +
  `PREREGISTRATION.freeze.txt` + amendments), decision log, and the kill-shot novelty
  sweep.

**Reproduction is offline, deterministic and free** — `bash reproduce.sh` regenerates
the analysis from the frozen captures and verifies it against the committed results
(no vendor API calls, no cost). Live model capture, which does require third-party
vendor API keys (OpenAI, Google), is documented in `RUNBOOK.md` but is **not** needed
to reproduce the reported results.

No proprietary, personal, or confidential data are used or distributed.

# ARCHITECTURE — P5

## The wall

```
        ┌───────────────────────────┐        ┌────────────────────────────┐
        │   CAPTURE  (perishable)   │        │   ANALYSIS  (reproducible) │
        │   impure · costs money    │  ───▶  │   pure · $0 · byte-stable  │
        │   live vendor APIs        │ frozen │   reads FROZEN csv only    │
        │   resumable · quota-aware │  csv   │   seeded · deterministic   │
        └───────────────────────────┘        └────────────────────────────┘
```

No analysis module issues a network call or reads an unfrozen CSV. Capture writes
append-only raw CSVs and a freeze receipt (SHA-256); analysis consumes only frozen
CSVs and emits `claims.json`. Re-running analysis on the same frozen inputs is
byte-identical (verified: matching SHA-256 across runs).

## The atom: a *rating cell*

```
rating cell = (model_key, prompt_variant, seed_index, firm_id, macro_state)
           →  one constrained-JSON credit-rating call
           →  {"rating": "BBB", "pd_1yr": 0.021, "rationale": "..."}
           →  rated | ERROR   (+ provenance: rating_notch, macro_severity,
                               prompt_hash, seed, content SHA-256, retrieved_at)
```

The firm battery is minted once, offline, deterministically, and frozen (hashed).
Each firm's fundamentals are serialized ONCE and reused **byte-identically** across
every macro state; the orchestrator prepends only the macro-environment block.

Two axes of states are captured per firm: the **economic** macro axis (severity
−2…+2) and a matched-format, credit-irrelevant **placebo** axis (weather/traffic,
severity −2…+2). The NET (economic − placebo) slope is the demand-effect-adjusted
cyclicality. For OpenAI models, `logprobs` on the rating token yield a continuous
**expected-notch**; `system_fingerprint` is logged per call and a within-cell seed
**noise floor** is reported (vendor determinism is best-effort). PD is elicited in
**basis points**. New CSV columns: `macro_kind`, `expected_notch`, `pd_bps`,
`system_fingerprint`, `rating_logprobs`.

## The identification (why this beats the classical test)

- Fundamentals are **byte-identical** across macro states for a firm → the macro
  context is the *only* thing that varies within a firm's five cells.
- The per-cell seed is keyed on `(seed_master, firm_id, variant, seed_index)` and
  **deliberately omits `macro_state`** → every macro state sees an *identical* seed
  at a matched cell, so sampling noise is not a confound.
- Therefore the **within-firm** slope of rating-notch on macro severity is a clean
  cyclicality estimate. The classical Amato–Furfine ordered probit must proxy for
  unobserved fundamentals (Koopman critique); here fundamentals are fixed by
  construction, so that critique dissolves.

## Data flow

```
config/firms.yaml ─┐
config/grid.yaml  ─┼─▶ capture/build_firms.py ─▶ data/firms/*.jsonl (+ manifest, SHA-256)
config/models.yaml ┘                                    │
                                                        ▼
config/{models,grid}.yaml ─▶ capture/orchestrator.py ─▶ data/raw/runs_<subgrid>_<model>_<variant>.csv
   (agent.py provider router + macro block; ledger.py priced gate; PILOT_MOCK swaps a fake rater)
                                                        │  capture/freeze.py
                                                        ▼
                                           data/frozen/<...>.freeze.json (SHA-256, read-only CSV)
                                                        │
analysis/{ratings,cyclicality,probit,stats}.py ─▶ analysis/run.py ─▶ claims.json
                                                        │
                                           pilot/verdict.py ─▶ pilot/PILOT_VERDICT.md
```

## Modules

**capture/**
- `secrets.py` — loads `../API Keys/keys.env.txt`; provider→key numbered pool with
  round-robin/failover on 429/quota; env wins over file.
- `probe.py` — one 1-token live call per model → served-model fingerprint + measured
  per-call price → `manifest/probe_receipts.json`. Refuses to proceed if unreachable.
- `build_firms.py` — deterministic offline firm generator (tier×sector profiles),
  stratified, hashed, frozen. Fundamentals serialized ONCE, reused byte-identically.
- `agent.py` — OpenAI-compatible / Gemini router. Builds the rating prompt (terse /
  ttc / pit) + prepends the macro block, parses strict JSON → rating notch + PD.
  Contains the deterministic `PILOT_MOCK` fake rater (procyclical, TTC-dampened).
- `ledger.py` — per-model priced spend; **HARD abort** the instant projected/actual
  cumulative spend crosses the cap; worst-case reservation makes the cap safe under
  concurrency; `--ledger-suffix` gives each parallel track its own sub-ledger.
- `orchestrator.py` — bounded worker pool; API call OUTSIDE the lock, ledger + append
  INSIDE the lock; resumable (append-only, keyed by (seed,firm,macro)); freeze on
  landing. Macro-invariant seed is set here.

**analysis/** (pure, $0)
- `ratings.py` — frozen-CSV loader → `RatingTable`; reduces replicate seeds to a
  per-(model,variant,firm,macro) median notch + mean PD; dispersion diagnostics.
- `cyclicality.py` — within-firm notch slope (primary), boom→recession endpoint
  swing, PD log-odds cyclicality, churn + Spearman across extremes, monotonicity,
  pooled-across-models + per-variant, instruction-effect contrast.
- `probit.py` — Amato–Furfine **ordered-probit null** (Mundlak firm-mean control);
  numpy/scipy MLE with a graceful OLS fallback. Under the TTC null the macro
  coefficient is 0.
- `stats.py` — seeded **cluster bootstrap over firms** (tier-stratified), 95% CIs;
  Wilson CIs for proportions.
- `run.py` — SINGLE ENTRYPOINT → `claims.json` (every cited number + CI + the
  config/firms hash that produced it) + the three pilot-gate booleans.

**config/**
- `schema.py` — one pydantic-v2 schema; the atom is a rating cell; the S&P
  letter→notch map.
- `models.yaml` — registry (pilot cheap subset + full set; prices; snapshots; probe
  slots; `pilot: true|false`).
- `grid.yaml` — models × variants × seeds × macro states; subgrids; budgets; the
  ordered macro-severity axis.
- `firms.yaml` — firm battery spec (tiers, sectors, sizes, seed).
- `loader.py` — resolves configs into rating cells; enforces the pilot-cheap guard.

**pilot/** — pilot outputs, `PILOT_RESULTS.md`, `PILOT_VERDICT.md`.
**manifest/** — config hash, firm fingerprints, seeds, ledgers, spend totals.
**run_all.sh** — `SUBGRID`, `PILOT_MOCK`, `CONC`, `PARALLEL`, `RESET`.
**status.py** — live capture progress against expected cell counts.

## Invariants
- ERROR is first-class; never coerced to a rating.
- Runs are append-only; captures are frozen+hashed on landing; frozen CSVs read-only.
- Spend cap is hard, pre-reserved under concurrency, pre-flight-checked, and
  (in PARALLEL mode) partitioned across provider tracks so the sum cannot cross it.
- Analysis is a pure function of frozen inputs + seeds.
- Fundamentals are byte-identical across macro states; the seed is macro-invariant.

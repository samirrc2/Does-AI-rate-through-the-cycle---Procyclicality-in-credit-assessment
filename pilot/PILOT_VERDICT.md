# PILOT_VERDICT — P5 (Do LLMs Rate Through the Cycle?)

**Subgrid:** `full`  ·  **Mode:** `REAL`  ·  **Config hash:** `57c8b3991ffb253f`
**Models:** gemini_flash, gemini_flash_lite, openai_41_mini, openai_4o, openai_4o_mini
**Macro axis:** {'boom': -2, 'expansion': -1, 'neutral': 0, 'severe_recession': 2, 'slowdown': 1}
**Firms:** pilot sha256 `604d47dab58b32ac...`  ·  **Analysis seed:** 4242  ·  **Bootstrap draws:** 2000

> Pre-registered pilot gate (PREREGISTRATION §5). All three must hold to clear the
> full run. This file only reports; it never starts the full run. Note: PASS gates
> on the design being able to MEASURE the coefficient — it does NOT require a
> particular sign. A tight CI around 0 (a genuine TTC null) is a valid result.

## Criterion 1 — Ran clean  🟢 GREEN
End-to-end, resumable, **0 ERROR** / 32000 rows
(0.000 rate, threshold ≤ 0.02), total spend
**$13.6859** ≤ cap **$40.00**.
Every declared capture froze (freeze.py enforces ≤ 2% ERROR per CSV).

## Criterion 2 — Ratings measurable & dispersed  🟢 GREEN
Pooled rating notch: mean **11.6** (target interior band [4, 18]),
sd **4.79** (≥1.5), **20** distinct notches (≥6),
parse rate **1.000** (≥0.90).
Dispersed & interior — a macro shift has room to move in either direction.

## Criterion 3 — Cyclicality coefficient estimable  🟢 GREEN
Headline pooled cyclicality (v_terse) = **0.429** notches/step,
95% CI **[0.41, 0.45]**; ordered-probit null estimable: **True**.
Scientific read: **PROCYCLICAL: 0.429 notches downgraded per +1 macro-severity step (CI [0.41, 0.45] excludes 0)**.
Demand-effect control: placebo slope **0.042** notch/step (frame-compliance floor) → **NET 0.387** notch/step, CI [0.36, 0.41] (excludes 0: True). The net is the procyclicality that survives after removing pure suggestibility to a matched, credit-irrelevant frame.

---

## PILOT: PASS → cleared for full run

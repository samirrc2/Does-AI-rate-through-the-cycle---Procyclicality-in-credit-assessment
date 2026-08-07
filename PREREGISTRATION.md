# PREREGISTRATION — P5: Does AI rate through the cycle?

> Freeze this file (SHA-256) BEFORE any real credit-rating call, so the confirmatory
> claims are pre-registered. Post-freeze changes go in `PREREGISTRATION_AMENDMENTS.md`.

## 1. Question
When a large language model assigns a credit rating, does it rate **through the
cycle** (invariant to transitory macro conditions given fixed fundamentals) or
**procyclically** (downgrading in recessions, upgrading in booms) even though the
fundamentals have not changed? This is the first controlled test of the property
for LLM raters.

## 2. Design (the identification)
- **Fixed synthetic fundamentals.** `build_firms.py` mints firms with fundamentals
  stratified across 5 credit tiers × 8 sectors. A firm's fundamentals are serialized
  ONCE and reused **byte-identically** across every macro state.
- **Factorial macro perturbation.** An ordered 5-point macro-severity axis is the
  only thing that changes: `boom(-2) < expansion(-1) < neutral(0) < slowdown(+1) <
  severe_recession(+2)`. Macro blocks carry severity purely in numbers (GDP,
  unemployment, IG credit spread, default rate, lending standards), matched in tone
  and length, with **no calendar dates and no historical-era cues**, so a model
  cannot pattern-match a real crisis (2008/2020) instead of responding to the
  stylized gradient (Graham–Harvey–Jha contamination control; RELATED_WORK §1).
- **Placebo (demand-effect) arm — REQUIRED.** A parallel 5-point gradient on a
  matched-format but credit-IRRELEVANT axis (regional weather/traffic, same structure
  and number density). Movement across it is pure frame-compliance (suggestibility);
  the **NET = macro − placebo** slope is the demand-effect-adjusted cyclicality
  (RELATED_WORK §2).
- **Macro-invariant seed.** The per-cell seed is keyed on
  `(seed_master, firm_id, variant, seed_index)` and omits `macro_state`, so a firm
  sees an identical seed across all macro states.
- **Four prompt arms.** `v_terse` (plain), `v_ttc` (explicit through-the-cycle),
  `v_pit` (explicit point-in-time), and — full run only, added post-pilot
  (AMENDMENT #1) — `v_stable` (instruction-level PLACEBO: "assign a stable rating,"
  with NO cycle reasoning). `v_stable` separates genuine TTC reasoning from generic
  "be stable" compliance: if it flattens the rating (and PD) as much as `v_ttc`, then
  `v_ttc` is anchoring, not through-the-cycle.
- **Output.** `{"rating": <S&P letter>, "pd_1yr": <decimal>, "rationale": ≤30w}`,
  rating → notch 1(D)…21(AAA).

## 3. Estimands (pre-registered)
1. **Primary — cyclicality coefficient β**: mean WITHIN-FIRM slope of rating-notch on
   macro severity, reported as **notches of downgrade per +1 severity step**
   (positive = procyclical, 0 = TTC null). Pooled across models per variant; also
   per (model, variant). CI: cluster bootstrap over firms (tier-stratified),
   `analysis_seed=4242`, 2000 draws. Reported BOTH raw and **NET of placebo**
   (β_macro − β_placebo) — the net is the demand-effect-adjusted headline.
1b. **Expected-notch β (OpenAI co-primary)**: the same within-firm slope computed on
   the **logprobs expected-notch** (probability-weighted rating over the token
   distribution) — a lower-variance estimate than sampled draws. Robustness arm for
   Gemini (no logprobs access).
2. **Endpoint swing**: mean(notch|boom) − mean(notch|severe_recession) — total
   procyclical swing across the full cycle, in notches.
3. **Amato–Furfine ordered-probit null**: ordered probit of notch on macro severity
   with a Mundlak firm-mean control; macro coefficient = 0 under the TTC null.
4. **PD cyclicality (secondary)**: PD elicited in **basis points**; analyzed as mean
   within-firm slope of **log-odds(PD)** on severity + rank-correlation across states
   (ordinal-robust). Expect round-value clustering; PD does NOT gate the pilot
   (calibration lit; RELATED_WORK §4).
5. **Instruction effect**: `terse − ttc` and `pit − ttc` pooled cyclicality contrasts
   (does an explicit TTC instruction reduce procyclicality?).
5b. **Anchoring test (AMENDMENT #1, full run)**: the `v_ttc − v_stable` contrast on
   BOTH the rating slope and the PD slope, plus per-model PD-retention
   (pd_slope under the instruction / pd_slope under v_terse). Genuine TTC ⇒ rating
   flat but PD retained (moves PIT); anchoring ⇒ both flat and `v_ttc ≈ v_stable`.
   The pilot found ANCHORING (PD retention 0.24–0.29); `v_stable` confirms whether
   the "be stable" instruction alone reproduces it.
6. **Robustness**: dose-response monotonicity, churn (fraction of firms moving ≥1/≥2
   notches across extremes), Spearman rank correlation across extreme states.

The claim is confirmed procyclical if β’s CI excludes 0 on the positive side and the
sign agrees across estimands 1–3; it is a confirmed TTC null if β’s CI is a tight
interval containing 0. Both are reportable results.

## 4. Grid
- **Pilot** (cheap models only): `openai_4o_mini, openai_41_mini, gemini_flash,
  gemini_flash_lite` × `{v_terse, v_ttc, v_pit}` × 2 seeds × (5 macro + 5 placebo) ×
  40 firms = **9,600 calls** (2,400 per model). Budget **$10 HARD**.
- **Full** (after PASS + go-ahead): adds `openai_4o` (flagship), the 80-firm battery,
  and the `v_stable` arm (4 variants). `xai_grok` was in the plan but is temporarily
  DROPPED (xAI out of credits, probe 403; AMENDMENT #2) — re-added by resume when
  credits return. 5 models × 4 variants × 2 seeds × (5 macro + 5 placebo) × 80 firms =
  **32,000 cells**. Budget **$40 HARD** (AMENDMENT #1; real projection ~$15 without
  Grok).

## 5. Pilot gate (all three required to clear the full run)
1. **Ran clean** — error_rate ≤ 2% (freeze.py enforces this per capture, so every
   frozen CSV is already ≤ 2%; a stray 429 in thousands of live calls is expected and
   tolerated) AND cumulative spend ≤ cap.
2. **Ratings measurable & dispersed** — parse rate ≥ 0.90; pooled mean notch in the
   interior band **[4, 18]**; ≥ 6 distinct notches; notch sd ≥ 1.5. Otherwise
   **KILL**: with no dispersion a macro shift has nothing to move against.
3. **Cyclicality estimable** — the pooled primary-arm coefficient has a finite
   bootstrap CI AND the ordered-probit null fits. PASS gates on *measurability*, not
   on a sign; a tight CI around 0 (genuine TTC) is a valid result.

Verdict precedence: degenerate-ratings **KILL** > operational **FAIL** >
estimability **FAIL** > **PASS**.

## 6. Reduction & analysis rules
- Replicate seeds reduce to a per-cell **median notch**, **mean expected-notch**, and
  **mean PD**; ERROR rows are excluded; an all-ERROR cell is NA and drops that firm
  from that arm's support.
- A firm contributes to an arm only if it has a non-NA value under **every** state of
  that axis (a full cycle curve).
- **Determinism is best-effort:** `system_fingerprint` is logged per call (a mid-run
  change is a batch-effect covariate); a within-cell seed **noise floor** is reported
  so the signal can be read against residual non-determinism (RELATED_WORK §3).
- Analysis reads **frozen CSVs only** and is a pure, seeded function of them
  (byte-identical on re-run — verified).

## 7. Integrity / dual-use
- No real company names, no real financials, no calendar dates — a synthetic battery,
  not a lookup of real ratings.
- We **measure** whether ratings move with the cycle; no arm optimizes a firm toward
  a target rating or searches for rating-gaming inputs.
- Framing is supervisory throughout (a measurement for regulators / rating-system
  designers concerned with procyclicality — BIS WP1194, ECB priorities).

## 8. Stops
- Pilot KILL (criterion 2) → ratings degenerate; the design cannot measure the
  object; do not proceed.
- Pilot FAIL (criterion 1 or 3) → fix and re-run the pilot; do not proceed to full.
- Budget stop → ledger hard-abort; resume by re-running; never exceed the cap.

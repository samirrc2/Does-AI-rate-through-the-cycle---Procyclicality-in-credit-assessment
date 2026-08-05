# DECISIONS — P5 (append-only)

Judgment calls made while building P5. Append; never rewrite history.

**D1 — Deterministic mock rater (`PILOT_MOCK=1`).** `agent.py` ships a fake rater
that (a) disperses ratings across firms via tier base notch + firm hash (variance to
move), and (b) shifts ratings PROCYCLICALLY with macro severity, DAMPENED under
`v_ttc`. This lets the whole capture→analysis→verdict pipeline run offline for $0 and
exercise both the signal and the instruction-effect paths. The mock is a **pipeline
validator, not a scientific result**; PILOT_RESULTS/VERDICT print a MOCK banner. The
$0 dry-run: 4,800 pilot cells, 0 ERROR, PASS, ≈1.06 notch/step terse vs ≈0.35 ttc.

**D2 — Cyclicality primary = within-firm notch slope.** Because fundamentals are
byte-identical across macro states, the within-firm slope of notch on severity is a
clean, assumption-light cyclicality estimate (no proxy for unobserved fundamentals).
The ordered probit (D5) is retained as the Amato–Furfine "null model" robustness, not
the primary — it needs a firm control and a latent-scale conversion.

**D3 — Macro-invariant seed.** The per-cell seed omits `macro_state`, so each firm
sees an identical seed across all five macro states. This removes sampling noise as a
confound for the macro effect, mirroring the version-isolation seed in P2.

**D4 — Five ordered macro states, not two.** A 5-point severity axis
(boom…severe_recession) gives a dose-response curve and a monotonicity check, a
stronger Amato–Furfine analogue than a single expansion↔recession contrast. Costs
2.5× a 2-state design; still ≪ $10 at pilot.

**D5 — Ordered probit uses a Mundlak (firm-mean) control, not firm dummies.** Full
firm fixed effects with 40–80 firms × ~20 ordinal categories triggers the
incidental-parameters problem. The firm's mean notch as a continuous control nets out
firm-level creditworthiness while keeping the MLE well-conditioned. `probit.py` falls
back to the pooled within-firm OLS slope if numpy/scipy are absent, recording
`estimator='ols_fallback'`, so analysis never breaks.

**D6 — Three prompt arms (terse / ttc / pit).** The explicit through-the-cycle vs
point-in-time contrast is a headline hook: does telling the model to "rate through the
cycle" actually reduce its procyclicality? The mock confirms the pipeline resolves the
contrast (pit > terse > ttc). All three are in the pilot (still cheap).

**D7 — Cluster bootstrap over FIRMS, tier-stratified.** Firm is the natural cluster
(fixed fundamentals, full macro curve). Stratifying the resample by tier preserves the
credit-quality dispersion in every draw so CIs aren't inflated by occasionally drawing
an all-one-tier sample.

**D8 — PASS gates on measurability, not sign.** Unlike P4 (which needs a signal > 1),
P5 is the first controlled test, so a well-measured TTC null (tight CI around 0) is a
publishable result. Criterion 3 therefore requires the coefficient to be ESTIMABLE
with a finite CI; the sign is reported, not gated. Degenerate ratings (no dispersion)
remain a KILL — there the design can measure nothing.

**D9 — Rating output = letter + 1yr PD.** Letter → notch is the primary (clean for the
ordered probit); PD gives a second continuous cyclicality measure (log-odds per step)
and a cross-check. Percent-style PDs (>1) are divided by 100 on parse.

**D10 — PARALLEL mode splits the cap per provider track.** Running provider tracks
concurrently uses one ledger per track (`--ledger-suffix`) and an equal share of the
global cap (`--spend-cap = cap / n_tracks`), so the SUM across tracks still cannot
cross the budget. Sequential mode (default) keeps a single global ledger and the exact
cap guarantee — the defensible pilot path.

**D11 — Anthropic key intentionally unused.** Primary + validator families are OpenAI,
Google (Gemini), and — full run only — xAI (Grok), matching P4's provider set.

--- 2026-07 external review (Graham-Harvey-Jha + demand-effect + determinism) ---

**D12 — Generic, number-carried, era-free macro blocks.** Graham-Harvey-Jha ("CFOs
Meet LLMs") show frontier LLMs reproduce date-specific human macro sentiment from
training data. If our macro blocks read like 2008/2020, the model may pattern-match
the real crisis instead of our stylized gradient. So the blocks carry the severity
purely in numbers (GDP / unemployment / IG spread / default rate / lending standards),
matched in tone + length, with NO dates and NO era cues (`agent.py::_MACRO_BLOCKS`).

**D13 — Placebo arm (demand-effect control) is now REQUIRED, not optional.** The
framing-effect literature (GPT-4o near-maximal framing sensitivity) means a referee
will argue the coefficient measures suggestibility, not procyclicality. We add a
matched-format, credit-IRRELEVANT gradient (regional weather/traffic, same structure
and number density) as `placebo_states`. The headline is now reported BOTH raw and
NET (macro − placebo); the net is the procyclicality surviving pure frame-compliance.
Cost: pilot grows to 9,600 cells (5 macro + 5 placebo) — still ≪ $10.

**D14 — Logprobs expected-notch + system_fingerprint logging.** Vendor determinism is
best-effort (OpenAI/Azure docs: variability even with matched seed+fingerprint). So:
(a) log `system_fingerprint` per call (a mid-run change is a batch-effect covariate);
(b) report a within-cell seed **noise floor**; (c) for OpenAI, request logprobs on the
rating token and compute a continuous **expected-notch** (probability-weighted over
alternative rating tokens) — a much lower-variance cyclicality measure from one call,
co-primary for OpenAI and robustness for Gemini (no equivalent access). Implemented
best-effort: `expected_notch` is populated when the rating localizes cleanly in the
token stream, else None; raw top-logprobs are stored for offline richer analysis.

**D15 — PD in basis points, log-scale, ordinal-robust, non-gating.** Calibration lit:
RLHF LLMs are poorly calibrated and verbalized confidence is scale-dependent. So PD is
elicited in basis points, analyzed as log-odds + rank-correlation across states, and
kept SECONDARY — the pilot gates on rating dispersion, never on PD quality.

**D21 — Full run: Grok dropped (xAI out of credits) + macOS bash-3.2 fix.** `probe
--subgrid full` succeeded for all 5 OpenAI/Gemini models (incl. gpt-4o at
$0.0013/call) but Grok returned 403 (xAI team over spending limit). Dropped `xai_grok`
from the full subgrid (AMENDMENT #2); re-add + resume when credits return. Separately,
`run_all.sh` PARALLEL mode used `declare -A` (bash 4+) and failed on macOS's default
bash 3.2 — rewritten with POSIX word lists. Full run is now 5 models × 4 variants × 2
seeds × 10 states × 80 firms = 32,000 cells, projected ~$15, cap $40.

**D20 — Add the `v_stable` anchoring-control arm to the full run (pre-registration
AMENDMENT #1).** Motivated by D19: the pilot showed `v_ttc` anchors (flattens rating +
PD). `v_stable` ("assign a stable rating," no cycle language) is the instruction-level
placebo that tests whether a bare "be stable" instruction reproduces `v_ttc`'s
flattening. If `v_ttc ≈ v_stable` on both rating and PD slopes → the TTC label adds
nothing (confirmed anchoring); if `v_ttc` retains PD movement that `v_stable` kills →
`v_ttc` is doing something more TTC-like. Full subgrid only (pilot unchanged); budget
$25 → $40 for the 4th variant × 6 models; pre-registration re-frozen. Analysis is
variant-agnostic, no code change needed.

**D19 — Finding #1 REFRAMED: the TTC instruction is anchoring, not through-the-cycle
(reviewer diagnostics, `analysis/review_diag.py`, real pilot data).** The PD-divergence
test the first write-up lacked: a genuine TTC rater holds the RATING flat while its PD
(point-in-time) still MOVES. On the real pilot, under v_ttc the PD slope collapses to
0.24–0.29 of its terse value in 3 of 4 models — the instruction flattens BOTH objects,
stabilizing the wrong one. So "the instruction dampens 65%" becomes "the instruction
induces generic anchoring (a new failure mode), not through-the-cycle reasoning; and
for gpt-4o-mini it barely bites (0.39 notch/step residual)." Also established on real
data: (a) ASYMMETRY — every model downgrades ~3× harder into recessions than it
upgrades into booms (the dangerous, human-agency-matching margin); (b) the logprobs
expected-notch estimator CONFIRMS the sampled slope (0.485 vs 0.491; 0.705 vs 0.731);
(c) fingerprint FE moves the coefficient < 0.003 → not infrastructure drift; (d)
gpt-4o-mini parses 1.000 → "most procyclical" is not a format artifact. Full details:
REVIEW_DIAGNOSTICS.md. These fold into the confirmatory full-run analysis.

**D18 — Pre-registration frozen post-pilot, pre-full-run (2026-07-15).**
`PREREGISTRATION.md` sha256 `841d465b…`, config_hash `757bed60…` (the exact config
the pilot ran under), written to `PREREGISTRATION.freeze.txt` via `freeze_prereg.py`.
The pilot was exploratory (design validation + gate); freezing now makes the FULL run
(gpt-4o + Grok + 80 firms) confirmatory against a fixed contract. Live pilot headline
under this contract: pooled terse cyclicality **0.437 notch/step** (net of placebo
0.389), CI excludes 0; the explicit TTC instruction dampens it ~65% (terse 0.437 →
ttc 0.151); gpt-4o-mini most procyclical (0.731 terse, 0.984 pit), Gemini mildest
(~0.24–0.29). Placebo floor ~0.05 everywhere → not suggestibility.

**D17 — Criterion-1 uses the ≤2% ERROR threshold, not literally 0 (first live run).**
The first REAL pilot (2026-07-15) captured all 9,600 cells across 4 models for $1.91
with **1 ERROR** (0.0001 rate) — a single OpenAI 429 that exhausted its retries on one
placebo cell while the org's daily request cap was near-exhausted. `verdict.py`
Criterion 1 had an extra `n_error == 0` conjunct that FAILED the pilot despite the
pre-registered §5 threshold being *error_rate ≤ 2%* (and freeze.py already enforcing
≤2% per capture — all 12 CSVs froze). Requiring literally 0 errors is unachievable in
live API capture and contradicts the pre-registered spec. Fix: Criterion 1 = (error
rate ≤ 2%) AND (spend ≤ cap); PREREGISTRATION §5 wording reconciled (the "0 ERROR"
phrasing removed). This reconciles code to the pre-registered threshold BEFORE the
pre-registration freeze — not a post-hoc loosening. The dropped cell (one firm ×
placebo_storm) becomes NA and does not affect the macro-axis estimand.

**D16 — Firm-id uniqueness fix.** `sector[:3]` collided (consumer_staples /
consumer_discretionary → 'con'), silently merging firms (support fell to 38/40).
Replaced with a unique 3-letter sector-code map (`_SECTOR_CODE`). Firms hash changed;
battery regenerated. (Caught by the offline verification's firm-count check.)

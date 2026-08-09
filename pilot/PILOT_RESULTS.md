# PILOT_RESULTS — P5  (mode=REAL)

Config hash `57c8b3991ffb253f` · firms(pilot) `604d47dab58b32ac...` · seed 4242 · draws 2000.
32000 rows, 0 ERROR (0.000), spend $13.6859.
Firms: 80 · macro axis: {'boom': -2, 'expansion': -1, 'neutral': 0, 'severe_recession': 2, 'slowdown': 1}.

**Headline (primary arm `v_terse`, pooled across models):**
cyclicality = **0.429 notches downgraded per +1 macro-severity step**,
95% CI [0.41, 0.45]; endpoint (boom→severe recession) swing =
1.756 notches. → **PROCYCLICAL: 0.429 notches downgraded per +1 macro-severity step (CI [0.41, 0.45] excludes 0)**

## Pooled cyclicality by prompt variant
| variant | notch/step | 95% CI | excludes 0 | endpoint swing |
|---|---|---|---|---|
| v_pit | 0.516 | [0.49, 0.54] | True | 2.106 |
| v_stable | 0.329 | [0.30, 0.35] | True | 1.344 |
| v_terse | 0.429 | [0.41, 0.45] | True | 1.756 |
| v_ttc | 0.160 | [0.14, 0.18] | True | 0.640 |

## Instruction-effect contrasts (does an explicit TTC instruction dampen procyclicality?)
| contrast | Δ notch/step |
|---|---|
| pit_minus_ttc | 0.356 |
| stable_minus_ttc | 0.169 |
| terse_minus_stable | 0.100 |
| terse_minus_ttc | 0.269 |

> A positive `terse_minus_ttc` / `pit_minus_ttc` means the explicit through-the-cycle
> instruction REDUCED procyclicality relative to the terse / point-in-time framing.

## Per model × variant
| model | variant | family | cyclicality (notch/step) | 95% CI | endpoint swing | probit notch/step | estimator |
|---|---|---|---|---|---|---|---|
| gemini_flash_lite | v_pit | google | 0.280 | [0.24, 0.32] | 1.137 | 0.392 | ordered_probit |
| gemini_flash_lite | v_stable | google | 0.270 | [0.24, 0.30] | 1.087 | 0.331 | ordered_probit |
| gemini_flash_lite | v_terse | google | 0.285 | [0.25, 0.32] | 1.150 | 0.235 | ordered_probit |
| gemini_flash_lite | v_ttc | google | 0.056 | [0.03, 0.08] | 0.225 | 0.243 | ordered_probit |
| gemini_flash | v_pit | google | 0.303 | [0.27, 0.35] | 1.294 | 0.205 | ordered_probit |
| gemini_flash | v_stable | google | 0.185 | [0.15, 0.22] | 0.750 | 0.257 | ordered_probit |
| gemini_flash | v_terse | google | 0.230 | [0.19, 0.27] | 0.963 | 0.272 | ordered_probit |
| gemini_flash | v_ttc | google | 0.059 | [0.03, 0.08] | 0.231 | 0.122 | ordered_probit |
| openai_41_mini | v_pit | openai | 0.552 | [0.49, 0.61] | 2.219 | 0.471 | ordered_probit |
| openai_41_mini | v_stable | openai | 0.349 | [0.30, 0.41] | 1.438 | 0.273 | ordered_probit |
| openai_41_mini | v_terse | openai | 0.471 | [0.41, 0.53] | 1.938 | 0.307 | ordered_probit |
| openai_41_mini | v_ttc | openai | 0.096 | [0.06, 0.13] | 0.406 | 0.177 | ordered_probit |
| openai_4o_mini | v_pit | openai | 1.043 | [0.96, 1.13] | 4.263 | 0.929 | ordered_probit |
| openai_4o_mini | v_stable | openai | 0.586 | [0.53, 0.65] | 2.381 | 0.500 | ordered_probit |
| openai_4o_mini | v_terse | openai | 0.775 | [0.69, 0.86] | 3.181 | 0.726 | ordered_probit |
| openai_4o_mini | v_ttc | openai | 0.403 | [0.34, 0.47] | 1.625 | 0.375 | ordered_probit |
| openai_4o | v_pit | openai | 0.401 | [0.36, 0.45] | 1.619 | 0.316 | ordered_probit |
| openai_4o | v_stable | openai | 0.256 | [0.21, 0.30] | 1.062 | 0.304 | ordered_probit |
| openai_4o | v_terse | openai | 0.387 | [0.34, 0.43] | 1.550 | 0.403 | ordered_probit |
| openai_4o | v_ttc | openai | 0.187 | [0.15, 0.22] | 0.713 | 0.257 | ordered_probit |

## Demand-effect control (placebo arm)
| variant | macro slope | placebo slope | NET (macro−placebo) | net CI | net excl. 0 |
|---|---|---|---|---|---|
| v_pit | 0.516 | 0.049 | 0.467 | [0.44, 0.49] | True |
| v_stable | 0.329 | 0.027 | 0.302 | [0.28, 0.33] | True |
| v_terse | 0.429 | 0.043 | 0.387 | [0.36, 0.41] | True |
| v_ttc | 0.160 | 0.012 | 0.148 | [0.13, 0.17] | True |

> The placebo axis is a matched-format, credit-irrelevant gradient (regional
> weather/traffic). Movement across it is pure frame-compliance (suggestibility);
> the NET coefficient is the procyclicality that survives it — the number a referee
> can't dismiss as a demand effect.

## Robustness & determinism controls
- Cyclicality reported four ways: within-firm notch slope (primary), boom→recession
  endpoint swing, Amato–Furfine ordered-probit macro term, and — for OpenAI models —
  the **logprobs expected-notch** slope (continuous, ~many-seeds-from-one-call).
  Expected-notch available for 19200 OpenAI cells.
- PD is elicited in **basis points** and analyzed as **log-odds** + rank-correlation
  across states (ordinal-robust); PD is secondary and does not gate the pilot.
- **Noise floor** (within-cell seed dispersion of the notch) is reported per model×
  variant so the cyclicality signal can be read against residual non-determinism —
  vendor determinism is best-effort (seed omits macro state by design).
- **system_fingerprint** is logged per call; a mid-run change is a batch-effect
  covariate. Distinct fingerprints per model: openai_41_mini=36, openai_4o=6, openai_4o_mini=33.

> REAL capture.

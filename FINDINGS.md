# Does AI rate through the cycle? — Abstract, Results, Conclusion

*Confirmatory full run: 5 frontier LLMs · 80 synthetic firms · 5-point macro-severity
axis + matched placebo · 4 prompt framings · 2 seeds · 32,000 ratings · 0 ERROR ·
$13.69. Firm-clustered bootstrap 95% CIs (2,000 draws, seed 4242). Config hash
`57c8b399…`; pre-registration `ecee9a81…`.*

## Abstract

Large language models are increasingly proposed as credit-rating and default-
assessment engines, yet whether they rate "through the cycle" or instead amplify it —
a property prudential regulators care about but that has been asserted rather than
measured — has remained untested. We hold synthetic firm fundamentals **byte-identical**
across an ordered five-point macroeconomic-severity axis and elicit letter ratings and
one-year default probabilities from five frontier models, so that any rating movement
is procyclicality *by construction*, identified without the unobserved-fundamentals
confound that limits the classical Amato–Furfine test. Across 32,000 ratings, every
model is significantly procyclical — pooling to **0.43 rating notches of downgrade per
severity step (95% CI [0.41, 0.45]), a 1.76-notch swing from boom to deep recession** —
the effect is sharply **asymmetric** (roughly three-to-four times steeper going into
recessions than coming out of them), an order of magnitude larger than a matched
credit-irrelevant placebo, unchanged by model-version fixed effects, and corroborated
by token-logprobability expected ratings. An explicit "through-the-cycle" instruction
lowers the rating slope but **does not restore through-the-cycle behaviour**: it anchors
the rating while suppressing the point-in-time default probability that *should* move,
whereas a naive "be stable" instruction preserves that distinction better, and a
residual downgrade — up to 1.6 notches for the most sensitive model — survives in every
case. Because model choice and prompt framing are first-order determinants of the
effect, LLM-based credit assessment can silently import the capital-procyclicality
channel that regulation is designed to dampen.

## Summary of results

Procyclicality β = notches of downgrade per +1 macro-severity step (positive =
procyclical); firm-clustered bootstrap 95% CIs; all estimates exclude 0.

| Model (family) | β, terse [95% CI] | Boom→recession swing (notches) | Downside : upside (asymmetry) | Residual β after TTC instruction | PD retention: "be stable" / "TTC" |
|---|---|---|---|---|---|
| Gemini 3.5 Flash | 0.230 [0.193, 0.267] | 0.96 | 0.38 : 0.10 (3.9×) | 0.06 | 0.70 / 0.22 |
| Gemini 2.5 Flash-Lite | 0.285 [0.248, 0.323] | 1.15 | 0.45 : 0.13 (3.6×) | 0.06 | 0.88 / 0.34 |
| GPT-4.1-mini | 0.471 [0.411, 0.527] | 1.94 | 0.77 : 0.20 (3.9×) | 0.10 † | 0.78 / 0.24 |
| GPT-4o | 0.387 [0.342, 0.428] | 1.55 | 0.59 : 0.18 (3.3×) | 0.19 | 0.78 / 0.52 |
| GPT-4o-mini | 0.775 [0.694, 0.856] | 3.18 | 1.15 : 0.44 (2.6×) | 0.40 | 0.92 / 0.59 |
| **Pooled (5 models)** | **0.429 [0.405, 0.454]** | **1.76** | **≈ 3.5×** | **0.160 [0.141, 0.179]** | — |

Pooled coefficient net of the credit-irrelevant placebo arm: **0.387 [0.363, 0.412]**
(the placebo frame moves ratings ≈ 0.05 notch/step). Pooled instruction gradient:
point-in-time 0.516 → terse 0.429 → "be stable" 0.329 → through-the-cycle 0.160 (all
CIs exclude 0). Robustness: for the OpenAI models the token-logprobability expected-
notch slope matches the sampled slope within ≤ 0.05, and adding served-model
(`system_fingerprint`) fixed effects shifts β by < 0.003; every model parses at 1.000
with 0 ERROR. † GPT-4.1-mini's post-TTC residual (0.096) does not exceed its within-cell
noise floor (0.114) and is therefore not distinguishable from zero.

## Conclusion

Using a design in which fundamentals are fixed by construction, we provide the first
controlled measurement of rating procyclicality in large language models, and it is
unambiguous: frontier LLMs downgrade identical firms as the macroeconomy is described
as worsening, by economically meaningful and statistically robust margins, and they do
so **asymmetrically** — punishing simulated downturns far more than they reward
simulated expansions, the precise pattern that transmits rating-driven capital
procyclicality. The magnitude is a first-order function of model identity (a ~3.4×
spread across five models, with the flagship GPT-4o roughly half as procyclical as
GPT-4o-mini), which means that in a deployed pipeline the choice of model is itself a
prudential decision. The natural mitigation — instructing the model to "rate through
the cycle" — fails in an instructive way: rather than holding the rating steady while
letting the point-in-time default probability track conditions, the instruction
suppresses *both*, anchoring the model onto the wrong object, and it leaves a residual
downgrade of up to 1.6 notches; a vaguer "be stable" instruction, revealingly,
preserves the through-the-cycle/point-in-time distinction better than the semantically
correct one. These results should be read against their scope — a synthetic, tier-
stratified firm battery designed for identification rather than external realism, five
mini/flagship models from two families, and prompt-level rather than fine-tuning
interventions — and they motivate a clear agenda: benchmarking LLM rating procyclicality
against agency and IRB-model baselines, testing fine-tuning and retrieval remedies that
target the point-in-time object directly, and, in the interim, treating model selection
and prompt framing as governed parameters wherever LLMs touch credit and capital
decisions.

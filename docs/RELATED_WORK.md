# RELATED_WORK — P5 (positioning + contamination controls)

Curated for the intro / related-work section and the referee-defense. Grouped by
the job each citation does. (Some are pre-registration-relevant design constraints,
not just references — see the "Design implication" lines.)

## 1. The mechanism our design relies on — and its contamination risk
- **Graham, Harvey & Jha, "CFOs Meet LLMs" (SSRN, June 2026; rev. this month).**
  Prompts an LLM to role-play the CFO of a specific company at a specific date and
  reproduces individual human responses on the Duke–Fed CFO Survey economic-optimism
  question (2002–2025), surviving firm and year-quarter fixed effects. **Why it
  matters for us:** (a) direct evidence that frontier LLMs encode *date-specific
  macro states* from training data with enough fidelity to reproduce human
  sentiment — a citation for our mechanism; (b) a **contamination warning** — if our
  macro blocks read like recognizable historical episodes (2008, 2020), a model may
  pattern-match to the *real* crisis rather than respond to our stylized severity
  gradient. **Design implication (IMPLEMENTED):** macro blocks are generic,
  number-carried, matched in tone/length, with **no calendar dates and no era cues**
  (`agent.py::_MACRO_BLOCKS`; DECISIONS D12). Cite Graham–Harvey–Jha in the intro
  *before* a referee cites it at us. Big names entering the "LLM as macro-sensitive
  economic agent" space → **scoop risk MEDIUM → MEDIUM-HIGH**; compress the timeline.

## 2. The demand-effect / suggestibility threat (why the placebo arm is necessary)
- **Prospect-theory replication of GPT-4o (framing effects).** GPT-4o shows
  near-maximal framing effects in some scenarios — flipping from maximal
  risk-aversion to maximal risk-seeking on semantic frame alone. **Cognitive-bias
  study:** neither GPT-3.5 nor GPT-4 gave correct responses on framing tasks.
  **Why it matters:** a referee will argue our coefficient measures *suggestibility*
  (frame-compliance), not procyclicality. **Design implication (IMPLEMENTED):** a
  matched-format, credit-irrelevant **placebo arm** (regional weather/traffic with
  the same structure + number density); the **NET = macro − placebo** slope is the
  demand-effect-adjusted cyclicality (`grid.yaml::placebo_states`; `cyclicality.py::
  net_cyclicality`; DECISIONS D13). Also: carry the severity gradient with numbers
  (GDP/unemployment/spreads), matched tone + length — done.

## 3. Determinism is best-effort (why the noise floor + fingerprint logging exist)
- **OpenAI reproducible-outputs docs:** determinism is a *best effort*;
  `system_fingerprint` changes when OpenAI updates its backend config.
  **Azure OpenAI docs:** even with matching seed + fingerprint, response variability
  is "currently not uncommon." **Design implication (IMPLEMENTED):** (a) log
  `system_fingerprint` per call, treat a mid-run change as a batch-effect covariate;
  (b) report a **noise floor** (within-cell seed dispersion of the notch); (c) for
  OpenAI, capture **logprobs on the rating token** → a continuous expected-notch
  measure (effectively many seeds from one call), a co-primary for OpenAI and a
  robustness arm for Gemini (which lacks equivalent access) (DECISIONS D14).

## 4. PD is noisier than the rating (why PD is secondary, in basis points, log-scale)
- **LLM calibration lit:** RLHF-tuned LLMs are poorly calibrated; verbalized
  confidence is an *elicited behavior*, and the response scale itself shapes the
  reported numbers. **Design implication (IMPLEMENTED):** elicit PD in **basis
  points**; analyze **log-PD** + **rank-correlation across states** (ordinal-robust);
  expect clustering at round values; **do not gate the pilot on PD** — gate on rating
  dispersion (DECISIONS D15).

## 5. Human-magnitude benchmarks (to headline a *comparison*, not a raw coefficient)
- **Structural-model paper on procyclical rating standards:** agencies are *stricter*
  in downturns — firms get overly pessimistic ratings in recessions vs expansions.
  Anticipates our asymmetry hypothesis (downgrades in bad states exceeding upgrades in
  good ones) and gives a **human-agency effect size** to benchmark against
  ("LLMs are X× more/less procyclical than the agencies").
- **Amato & Furfine (2004, JBF):** the ordered-probit procyclicality test we port.
- **Sovereign-ratings ordered-probit (African sovereigns):** 3 of 4 agencies act
  procyclically — same econometric machinery; a footnote showing the AF framework has
  an established replication tradition we extend.
- **Markov rating-migration conditional on economic states (arXiv 2403.14868):**
  classical (non-LLM) TTC/PIT econometrics — foundation, not a competitor.

## 6. Nearest adjacent LLM work (does NOT kill — confirmed by the sweep)
- **CreditAudit (arXiv 2602.02515, Feb 2026)** — scenario-induced *model* stability,
  not firm-rating-vs-macro-state; no fixed-fundamentals design. Primary scoop-risk
  watch item; check for a v2 fixed-fundamentals arm.
- **Forecasting Credit Ratings… (arXiv 2407.17624)** — macro as a *predictive input*,
  not a controlled perturbation; fundamentals not held fixed.
- **LLM-Generated Counterfactual Stress Scenarios (arXiv 2512.07867)** — LLM generates
  macro scenarios; does not rate firms under fixed fundamentals.
- **ChatGPT-based credit rating & default forecasting (Springer JDIM, 2025)** —
  observational rating model; no macro perturbation.

> The sweep's CLEAR verdict survives a fresh look (2026-07): a dedicated hunt for
> synthetic/identical fundamentals + LLM rater + macro perturbation found nothing —
> the closest new arrivals (CFO paper, stress-scenario pipeline, CreditAudit) all sit
> on adjacent cells. No DIRECT_HIT.

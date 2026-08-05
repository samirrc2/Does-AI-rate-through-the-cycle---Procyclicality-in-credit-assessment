# REVIEW DIAGNOSTICS — P5 pilot (real data, $0)

> **Note.** The tables below are from the exploratory **pilot** (4 models). The
> CONFIRMATORY **full-run** numbers (5 models, incl. GPT-4o; the numbers cited in the
> paper) are in `results/review_diag_full.txt`, `claims.json`, and `FINDINGS.md`. The
> full run confirmed every pilot finding: pooled procyclicality 0.43 notch/step
> [0.41, 0.45]; asymmetry ~3.3×; the TTC instruction anchors (suppresses PD). Regenerate
> with `python3 analysis/review_diag.py --subgrid full`.


Answers to the 2026-07-15 reviewer, computed on the frozen REAL pilot captures
(`analysis/review_diag.py --subgrid pilot`). These fold into the confirmatory
full-run analysis. **The most important result: the TTC instruction is NOT genuine
through-the-cycle behavior — it is generic anchoring.**

## 1. TTC diagnostic — genuine rating philosophy vs generic anchoring  ⚠️ KEY
A genuine TTC rater holds the *rating* flat while its *PD* (a point-in-time
quantity) still moves with the macro. Anchoring flattens both. PD-retention =
pd_slope(ttc) / pd_slope(terse).

| model | rating slope terse→ttc | pd slope terse→ttc | PD retention | verdict |
|---|---|---|---|---|
| gemini_flash | 0.241 → 0.070 | 0.238 → 0.056 | **0.24** | ANCHORING |
| gemini_flash_lite | 0.285 → 0.040 | 0.244 → 0.069 | **0.28** | ANCHORING |
| openai_41_mini | 0.491 → 0.102 | 0.311 → 0.090 | **0.29** | ANCHORING |
| openai_4o_mini | 0.731 → 0.390 | 0.244 → 0.129 | 0.53 | weak-effect (instruction barely worked) |

**Reinterpretation of finding #1:** the TTC instruction does not induce through-the-
cycle reasoning. In the three models where it flattens the rating, it flattens the PD
*just as much* (retention 0.24–0.29) — it stabilizes the wrong object. PD is point-in-
time and *should* move across the cycle; a genuine TTC model would keep PD moving.
So the instruction induces **generic anchoring / suppression of movement**, a new
failure mode — a materially weaker deployment story than "the instruction works," and
a more interesting finding. In gpt-4o-mini the instruction barely bites at all (rating
still 0.39/step).

## 2. Estimator range + noise floor (small coefficients are fragile)
Every coefficient clears its within-cell seed **noise floor** (noise SD 0.00–0.09;
coefs far larger) — the signal is real, not sampling jitter. But at the low (ttc) end
the **linear vs ordered-probit estimates diverge**, so the residual-TTC magnitude is
reported as a RANGE, not a point:

| model | ttc linear | ttc probit | reported range | boom→recession swing |
|---|---|---|---|---|
| gemini_flash | 0.070 | 0.012 | [0.01, 0.07] | 0.28 notch |
| gemini_flash_lite | 0.040 | 0.088 | [0.04, 0.09] | 0.13 notch |
| openai_41_mini | 0.102 | 0.006 | [0.01, 0.10] | 0.38 notch |
| openai_4o_mini | 0.390 | 0.571 | **[0.39, 0.57]** | **1.60 notch** |

## 3. Residual reframing (regulator-facing)
Even taking the dampening at face value, the instruction leaves a **measurable
residual**, worst for gpt-4o-mini: **0.39–0.57 notch/step, a 1.6-notch boom→recession
swing after explicit TTC instruction.** Honest headline: *"the best available prompt-
level fix is cheap, partial and model-dependent — it dampens most of the effect but
does not restore through-the-cycle behavior, and for gpt-4o-mini it leaves the
majority of a full notch per severity step in place."* Under IRB-style capital rules,
even ~0.15 notch/step of systematic downturn drift is the capital-procyclicality
channel BIS flags.

## 4a. Asymmetry — the financially dangerous margin  (downside ≫ upside)
Downside slope (neutral→severe recession) vs upside slope (boom→neutral), notch/step:

| model (v_terse) | downside (into recession) | upside (into boom) | ratio |
|---|---|---|---|
| gemini_flash | 0.394 | 0.100 | 3.9× |
| gemini_flash_lite | 0.425 | 0.163 | 2.6× |
| openai_41_mini | 0.775 | 0.219 | 3.5× |
| openai_4o_mini | 1.150 | 0.369 | 3.1× |

Every model downgrades **~3× harder going into a recession than it upgrades going into
a boom.** This is the asymmetry the human-agency literature found for agencies
(stricter standards in downturns) — now measured for LLMs, and the bridge to an
Amato–Furfine magnitude comparison.

## 4b. Expected-notch (OpenAI logprobs) — highest-precision estimator, in the main table
The continuous logprobs estimator CONFIRMS the sampled within-firm slope:

| model | variant | sampled linear | expected-notch (logprobs) |
|---|---|---|---|
| openai_41_mini | v_terse | 0.491 | 0.485 |
| openai_41_mini | v_pit | 0.613 | 0.588 |
| openai_4o_mini | v_terse | 0.731 | 0.705 |
| openai_4o_mini | v_pit | 0.984 | 0.993 |

## obs-1. Parse / format — "most procyclical" is NOT a format artifact
| model | n | err | parse rate | distinct ratings | mean out-tok |
|---|---|---|---|---|---|
| gemini_flash | 2400 | 0 | 1.000 | 18 | 67.6 |
| gemini_flash_lite | 2400 | 0 | 1.000 | 17 | 56.6 |
| openai_41_mini | 2400 | 0 | 1.000 | 14 | 46.3 |
| openai_4o_mini | 2400 | 1 | 1.000 | 13 | 39.6 |

gpt-4o-mini parses at 1.000 with the *fewest* distinct ratings (13) yet the *largest*
cyclicality — a real behavior, not fragility. Rules out the masquerade.

## obs-2. Fingerprint stability — the effect is NOT infrastructure drift
Severity coefficient with firm FE only vs firm + `system_fingerprint` FE:

| model (v_terse) | firm FE | firm + fingerprint FE | Δ |
|---|---|---|---|
| openai_41_mini | 0.491 | 0.493 | +0.002 |
| openai_4o_mini | 0.731 | 0.734 | +0.003 |

Adding fingerprint fixed effects moves the coefficient by < 0.003 — the cyclicality is
**not** attributable to OpenAI backend drift, despite 22–30 distinct fingerprints over
the run.

---

### Net effect on the paper's story
The headline is stronger and more defensible than "we found a fix":
1. LLMs are procyclical on fixed fundamentals (0.44 notch/step terse, net of placebo
   0.39) — confirmed by the high-precision logprobs estimator and robust to
   infrastructure drift.
2. The effect is **asymmetric** — ~3× steeper into recessions — the dangerous margin.
3. The TTC instruction does **not** deliver through-the-cycle behavior; it induces
   **anchoring** (suppresses PD too), stabilizing the wrong object — a new failure
   mode, not a fix. For gpt-4o-mini it barely works at all.

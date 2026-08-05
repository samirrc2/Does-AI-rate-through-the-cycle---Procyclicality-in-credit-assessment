# Kill-Shot Sweep — P5: Do LLMs Rate Through the Cycle?

**Topic:** P5 · rating procyclicality
**Framework cell:** B7 → rung 5 (economic mechanism)
**Claim:** First controlled test of whether LLM credit ratings are through-the-cycle — fixed synthetic fundamentals, factorial macro-context perturbation, Amato–Furfine ordered-probit null, cyclicality coefficient in notches per macro state.
**Kill rule:** kill if — controlled macro/cycle perturbation **+** LLM/GPT rater **+** credit-rating or PD task **+** fundamentals held fixed (ALL four conjuncts required).
**Swept:** 2026-07-15 · 12 vectors (incl. dedicated procyclicality battery) · sources: web + arXiv + Semantic Scholar + OpenAlex + Crossref + BIS/SSRN

**Status line — Novelty: CLEAR · Feasibility: FEASIBLE**

---

## Verdict table

| # | Vector (query) | Closest finding | Label | Kill? |
|---|----------------|-----------------|-------|-------|
| 1 | LLM credit-rating procyclicality / through-the-cycle | Amato & Furfine 2004 (JBF) — human/agency procyclicality, ordered-probit null | FOUNDATION | No |
| 2 | GPT rating under macro scenario, fixed fundamentals, PIT | *Forecasting Credit Ratings…* 2407.17624 — macro as **predictive input**, no controlled perturbation, no fixed-fundamentals identification | ADJACENT | No |
| 3 | LLM credit-risk business-cycle sensitivity (prompt experiment) | *Interpretable LLMs for Credit Risk* 2506.04290 (review); *Post-hoc Explainability* 2602.18895 — explainability/fairness, no cyclicality object | ADJACENT | No |
| 4 | GenAI procyclicality, credit scoring, recession | BIS WP1194 (2024) — **names** GenAI herding/procyclicality, measures nothing; CECL procyclicality lit | FOUNDATION / reg hook | No |
| 5 | LLM risk aversion, state-dependent macro framing | *Ethics & Risk Preferences of LLMs* 2406.01168; *Rational Investors?* 2402.12713 — psychology-framed, no rating object, no capital consequence | ADJACENT | No |
| 6 | LLM counterfactual perturbation, synthetic firm, fundamentals fixed | *LLM-Generated Counterfactual Stress Scenarios* 2512.07867 — LLM **generates** macro scenarios, does not rate firms under fixed fundamentals | ADJACENT | No |
| 7 | TTC/PIT LLM rating philosophy | Markov rating migration conditional on economic states 2403.14868 — classical econometrics, no LLM | FOUNDATION | No |
| 8 | Amato–Furfine ordered-probit LLM replication | Amato–Furfine 2004 only; no LLM/GPT replication exists | FOUNDATION | No |
| 9 | ChatGPT rating consistency across economic conditions | *ChatGPT & Perception Biases in Investments* (ASU 2025) — investment perception bias, not rating cyclicality | ADJACENT | No |
| 10 | ChatGPT-based credit rating (observational) | *ChatGPT based credit rating and default forecasting* (Springer 2025) — observational rating model, no macro perturbation | ADJACENT | No |
| 11 | LLM rating stability / robustness, 2026 | **CreditAudit 2602.02515** (Feb 2026) — scenario-induced fluctuation as a stability signal; grades the **model** (AAA–BBB), not firm-rating-vs-macro-state; no fixed-fundamentals identification, no cyclicality coefficient | TEMPLATE_VISIBLE (conf ~0.6) | No |
| 12 | BIS GenAI procyclicality (WP1194) | BIS WP1194 — GenAI procyclicality asserted verbatim, unmeasured | FOUNDATION / reg hook | No |

**No DIRECT_HIT on any vector.** No paper satisfies all four kill-rule conjuncts. The nearest, 2407.17624, fails two conjuncts (macro is a predictive input, not a controlled perturbation; fundamentals are not held fixed). The Amato–Furfine test does not exist even for classical ML underwriting, let alone LLMs.

---

## Human-review queue

Two items to eyeball before committing compute — neither kills, but both are close-neighborhood and recent:

1. **CreditAudit — 2nd Dimension for LLM Evaluation and Selection** (arXiv 2602.02515, Feb 2026). Reports scenario-induced fluctuation of an LLM's ability and maps volatility to credit-style grades. *Why it doesn't kill:* the object is the **model's** stability, not the procyclicality of firm ratings; no synthetic-fundamentals-fixed design, no macro-state factorial, no notches-per-macro-state coefficient, no Amato–Furfine null. *Why review it:* it is the closest formalism (prompt-induced rating fluctuation) and it is fresh — this is your primary scoop-risk driver. Confirm it does not add a fixed-fundamentals macro arm in a v2.

2. **ChatGPT based credit rating and default forecasting** (Springer, JDIM, Mar 2025). *Why it doesn't kill:* observational multi-source rating model; no controlled macro perturbation, no cyclicality measurement. Cite as adjacent prior art.

---

## Feasibility gate

| Probe | Level | Trigger | Evidence |
|-------|-------|---------|----------|
| P1 Measurability (soft) | 🟢 GREEN | robust; does not flip under alt metrics | Cyclicality coefficient (notches/macro-state) backstopped by 2 alt operationalizations of the same claim — mean rating shift (expansion vs recession) and rank correlation across macro states. Biggest measurement threat: prompt-order / date-leakage artifacts, mitigated by byte-identical fundamentals + fictional/relative dates (P3 fingerprinting lesson). |
| P2 Critical-cell count (hard) | 🟢 GREEN | N ≥ min_critical_cell (25) | The broad LLM × credit-rating × macro cell clearly exceeds threshold: a 2020–2025 systematic review alone screens 60 LLM-credit-risk papers (2506.04290), plus 2407.17624, CreditAudit, 2512.07867, Springer 2025, ZiGong 2502.16159, Foundation-Models-for-Credit 2605.18147. *Caveat:* the OpenAlex/S2 count endpoint returned empty via the fetch tool this run — count is evidence-inferred, not programmatically confirmed. Re-run `killshot feasibility P5 --pre` when the API is reachable to lock the number. |
| P3 Corpus precision (soft) | 🟢 GREEN | on-topic rate well above 0.40 | Main-query hits are overwhelmingly on-topic (LLM + credit/rating + macro); keyword-collision noise (RL "credit assignment", medical bias) was rare and easily filtered. |
| P4 Confirmation risk (soft) | 🟢 GREEN | not already-established | BIS WP1194 and BIS WP116/129 **assert** GenAI/model procyclicality as a concern but provide **no measurement** for LLM raters. The claim is asserted-but-untested, not consensus-confirmed — measuring it is a contribution, not a restatement. |
| P5 Signal observability (hard) | 🟢 GREEN | window [2022–2026] adequately covered | The rating object (GPT-4-class LLMs) exists from 2023+; macro variation across the window is real and promptable. No coverage hole that would starve the signal. |

**Feasibility verdict: FEASIBLE** — no HARD-probe RED. Deciding note: P2 and P5 both green; measurability robust under alternatives.

---

## Scoop risk

**MEDIUM.** Trigger: one TEMPLATE_VISIBLE at conf ~0.6 (CreditAudit, Feb 2026) plus a cluster of recent ADJACENT rating/stability papers (2512.07867, Springer 2025) in the last ~12 months. The bias literature is circling and regulators (BIS WP1194; ECB priorities) are loudly asking the question — but nobody has built the controlled fixed-fundamentals × macro-state test with a cyclicality coefficient. The 2–3 quarter window in the eval is real. Sequence accordingly.

---

## Final verdict

**✅ CLEAR & FEASIBLE** — 12 vectors swept (incl. dedicated procyclicality battery); 0 DIRECT_HIT; 6 FOUNDATION (Amato–Furfine 2004, BIS WP129, BIS WP116, BIS WP1194, Koopman-lineage/Markov-migration, CECL procyclicality), 5 ADJACENT non-killing, 1 TEMPLATE_VISIBLE (CreditAudit, does not port to a fixed-fundamentals rating test). Identification note stands: byte-identical synthetic fundamentals dissolve the Koopman unobserved-factor critique by construction, so the design beats the classical original on the exact axis referees will press.

**Recommendation:** proceed to the ~$300 pilot. This is a genuine open cell — "named but not measured" (BIS WP1194 verbatim) rather than closed. Watch CreditAudit for a v2 fixed-fundamentals arm; that is the single most likely way this gets scooped.

*Verdict is auto-derived from the sweep. Set it authoritatively via `killshot verdict P5 clear --note "…"`.*

---

### Sources
- [Amato & Furfine 2004 — Are credit ratings procyclical? (BIS WP129)](https://www.bis.org/publ/work129.pdf)
- [BIS WP116 — Credit risk measurement and procyclicality](https://www.bis.org/publ/work116.pdf)
- [BIS WP1194 — Intelligent financial system: how AI is transforming finance](https://www.bis.org/publ/work1194.pdf)
- [Forecasting Credit Ratings: Traditional Methods Outperform Generative LLMs (2407.17624)](https://arxiv.org/abs/2407.17624)
- [CreditAudit: 2nd Dimension for LLM Evaluation and Selection (2602.02515)](https://arxiv.org/abs/2602.02515)
- [LLM-Generated Counterfactual Stress Scenarios for Portfolio Risk (2512.07867)](https://arxiv.org/abs/2512.07867)
- [Interpretable LLMs for Credit Risk: A Systematic Review and Taxonomy (2506.04290)](https://arxiv.org/abs/2506.04290)
- [Could LLMs work as Post-hoc Explainability Tools in Credit Risk Models? (2602.18895)](https://arxiv.org/abs/2602.18895)
- [AI as Decision-Maker: Ethics and Risk Preferences of LLMs (2406.01168)](https://arxiv.org/abs/2406.01168)
- [Are LLMs Rational Investors? (2402.12713)](https://arxiv.org/abs/2402.12713)
- [A Markov approach to credit rating migration conditional on economic states (2403.14868)](https://arxiv.org/abs/2403.14868)
- [ChatGPT based credit rating and default forecasting (Springer, JDIM 2025)](https://link.springer.com/article/10.1007/s42488-025-00143-6)
- [ChatGPT and Perception Biases in Investments (ASU 2025)](https://finance-conference.wpcarey.asu.edu/sites/g/files/litvpz3416/files/2025-01/ChatGPT%20and%20Perception%20Biases%20in%20Investments.pdf)

---

## ADDENDUM — 2026-07 external review (post-sweep, pre-flight)

**New adjacent paper added to the queue (does NOT kill):**
- **Graham, Harvey & Jha, "CFOs Meet LLMs"** (SSRN Jun 2026, rev. Jul 2026). LLM
  role-plays a specific CFO at a specific date and reproduces individual Duke–Fed CFO
  Survey optimism responses, surviving firm and year-quarter FE. Adjacent cell: no
  rating object, no fixed-fundamentals perturbation. **Two consequences:** (1) it is a
  citation for our mechanism (LLMs encode date-specific macro states) AND a
  contamination warning (keep macro blocks synthetic/generic, not just undated); (2)
  Graham & Harvey entering the "LLM as macro-sensitive economic agent" space →
  **scoop risk MEDIUM → MEDIUM-HIGH; compress the timeline.**

**Verdict unchanged: CLEAR & FEASIBLE.** A fresh dedicated hunt for
synthetic/identical-fundamentals + LLM rater + macro perturbation found nothing; the
closest new arrivals (CFO paper, stress-scenario pipeline, CreditAudit) all sit on
adjacent cells. No DIRECT_HIT.

**Pre-flight design changes IMPLEMENTED in the P5 codebase (see DECISIONS D12–D16,
RELATED_WORK.md):**
1. Generic, number-carried, **era-free macro blocks** (anti-contamination).
2. **Placebo arm** (matched credit-irrelevant gradient) → NET = macro − placebo, the
   demand-effect-adjusted coefficient. Pilot grows 4,800 → 9,600 cells (still ≪ $10).
3. **Logprobs expected-notch** on OpenAI (continuous, low-variance; co-primary) +
   Gemini as robustness arm.
4. **system_fingerprint** logged per call (batch-effect covariate) + within-cell
   **noise floor**.
5. **PD in basis points**, log-odds + rank-correlation, secondary/non-gating.
6. Cite Graham–Harvey–Jha in the intro before a referee cites it at us.

# PREREGISTRATION AMENDMENTS — P5

Post-freeze changes to the pre-registration. Each entry records what changed, why,
and the date, and triggers a re-freeze of `PREREGISTRATION.freeze.txt`.

Original freeze: PREREGISTRATION.md sha256
`841d465b9e407eea08bc07e04471b521ccf19969fa4ff37bcef708ebb21f022b`,
config_hash `757bed608aa28d19`, frozen 2026-07-15 (the exact config the PILOT ran
under). The pilot is confirmatory-gating under that hash; the amendment below applies
only to the FULL run and is declared BEFORE any full-run capture.

## AMENDMENT #3 — final title (2026-08-07, cosmetic; no design change)
The manuscript title was finalised to **"Does AI rate through the cycle? Procyclicality
in credit assessment"** (working title had been "Do LLMs Rate Through the Cycle?"). This
is a **title-only** change: no estimand, battery, macro/placebo axis, prompt framing,
seed rule, or pilot-gate criterion is altered. `PREREGISTRATION.md` was re-frozen for the
new header (sha256 `fb3ebe49…`); the substantive pre-registered design is byte-for-byte
unchanged and all analysis outputs (`claims.json`) are identical.

## AMENDMENT #1 — add the `v_stable` anchoring-control arm (2026-07-15, pre-full-run)
**What.** A fourth prompt variant `v_stable` ("assign a stable rating," NO
through-the-cycle / rating-philosophy language) is added to the FULL subgrid. Budget
cap raised $25 → $40 to fit 4 variants × 6 models (incl. gpt-4o + Grok).

**Why.** The pilot's PD-divergence diagnostic (REVIEW_DIAGNOSTICS.md; DECISIONS D19)
showed `v_ttc` induces ANCHORING — it flattens the rating AND the PD (PD retention
0.24–0.29), rather than holding the rating flat while PD moves point-in-time. `v_stable`
is the clean control: if a bare "be stable" instruction reproduces `v_ttc`'s flattening
(`v_ttc ≈ v_stable` on both rating and PD slopes), the TTC label adds nothing and the
"instruction works" reading is falsified in favour of generic-anchoring. This was
motivated by the pilot and is declared before any full-run call, so the full run
remains confirmatory for it.

**Scope.** FULL subgrid only. The pilot (3 variants, config_hash `757bed60…`) is
unchanged and its frozen results stand. Analysis/diagnostics are variant-agnostic
(they loop over the subgrid's declared variants), so no analysis-code change is
required.

**Estimand added.** §3 item 5b — the `v_ttc − v_stable` contrast on rating and PD
slopes + per-model PD-retention.

**Re-freeze (2026-07-15).** `freeze_prereg.py` re-run. Amended contract for the FULL
run: PREREGISTRATION.md sha256
`6bf499f362018ec73ebf0e034ae5513e81fa8c06f6c47dcaeb43989185ca4c1e`,
config_hash `02986021d2905265`. (The global config_hash changed from `757bed60…`
because grid.yaml gained the `v_stable` variant and the $40 cap; the PILOT subgrid's
cells are unchanged and its frozen results — captured under `757bed60…` — stand. The
per-row provenance in the pilot CSVs, not the global label, is what pins the pilot
data.)

## AMENDMENT #2 — drop `xai_grok` from the full run (2026-07-15, xAI out of credits)
**What.** `xai_grok` removed from the FULL subgrid models (5 models: OpenAI ×3,
Gemini ×2). **Why.** `probe --subgrid full` returned a 403: the xAI team is out of
credits / over its monthly spending limit, so Grok cannot be called. Rather than let
every Grok cell ERROR (which would block freezing/analysis), Grok is dropped.
**Scope.** FULL subgrid only; `xai_grok` remains in `models.yaml`. When xAI credits
are restored, re-add it to the full `models:` list and re-run `SUBGRID=full
./run_all.sh` — the capture is resumable and re-bills only the missing Grok cells.
Loss: the third model family (xAI). OpenAI (incl. gpt-4o flagship) + Google remain;
this matches the pilot's 2-family scope. Re-freeze after this edit.

**Also (not a pre-registration change): `run_all.sh` PARALLEL mode fixed for macOS
bash 3.2** — the provider-track grouping used `declare -A` (bash 4+); rewritten with
POSIX-style word lists. No effect on estimands.

## AMENDMENT #4 — frontier-tier probe arm `probe_astra` (2026-09-29, referee revision)

**What.** A new model `openai_astra` (`gpt-6-astra`) and a new subgrid `probe_astra`
= 1 model × {`v_terse`, `v_ttc`} × 2 seeds × (5 macro + 5 placebo) × the 40-firm
pilot battery = **1,600 calls**. `ModelCfg` gains an optional `temperature` override.

**Why.** Referee #1 (comment 4) asks for "additional model families **or** stronger
frontier models"; referee #2 (comment 1) asks whether the findings "remain similar
when using a state-of-the-art model", naming GPT-5 Pro and GPT-6 Astra. `gpt-6-astra`
is the referee's own nomination and the frontier endpoint of the OpenAI capability
gradient already in Table 1 (4o-mini 0.775 → 4.1-mini 0.471 → 4o 0.387 → astra).

This arm is declared as a **go/no-go probe, not a confirmatory test**: it establishes
whether β at the frontier is near zero or within the incumbent range before the full
frontier grids are committed. 40 firms keeps the cluster count clear of the
few-clusters (5–30) over-rejection zone, and distinguishing β≈0 from β≈0.3 requires
no more precision than this. It is exploratory by construction and is reported as
such; the confirmatory frontier grids, if run, are a separate declared arm.

**Measured constraint (2026-09-29, live API).** `gpt-6-astra` **refuses
`temperature=0`** ("Unsupported value: 'temperature' does not support 0 with this
model. Only the default (1)") and **refuses `logprobs`**. Three consequences, all
declared rather than absorbed:

1. The frontier arm runs at **t=1** while every incumbent arm ran at t=0. β is
   therefore **not strictly temperature-matched** across the comparison, and any
   frontier-vs-incumbent contrast must state this. It is a bound on comparability,
   not a defect: t=1 adds per-cell sampling variance, which widens CIs and biases
   *against* detecting a slope, so it cannot manufacture procyclicality.
2. Seeds are **2, not 1**, so per-cell sampling noise is averaged rather than assumed
   away, and the arm yields a t=1 within-cell noise floor the t=0 arms cannot give.
   This also speaks to referee #2's minor comment on temperature=0 and CI width.
3. The log-probability expected-notch estimator is **unavailable** here, exactly as
   for the Gemini arms (Table 3, "OpenAI only" column).

**Provenance fix (not a design change).** `orchestrator.py` recorded
`grid.judge_temperature` into every row's `temperature` column. With a model that
refuses the grid default, that would have stamped `0.0` on rows which actually ran at
`1.0`. The row now records the **effective** temperature sent. Incumbent models set no
override, resolve to `judge_temperature` as before, and their frozen CSVs are
unaffected — verified by fault injection (the pre-fix expression records 0.0 for
`openai_astra`; the fixed expression records 1.0; both record 0.0 for `openai_4o` and
`gemini_flash`).

**Scope.** Additive only. No existing subgrid, model entry, firm battery, estimand or
analysis path is modified; all frozen `full`/`pilot` results stand unchanged, pinned by
their per-row provenance. `config_hash` changes because `models.yaml`, `grid.yaml` and
`schema.py` gained the entries above. Re-freeze after this edit.

**Sizing (measured, not assumed).** The single pre-flight probe call returned
in=358 / out=61 tokens with `reasoning_tokens=0` at `reasoning_effort=low`, measured
cost $0.00663/call. `max_tokens` is therefore set to 512 (~8x headroom) rather than a
round 2048, which keeps the ledger's worst-case projection — and so the hard spend
cap — a real guard: projected worst case falls from ~$172 to ~$49 for the 1,600-call
arm against an expected actual spend of ~$10.60.

**Declared cap (added after the arm ran; no effect on captured data).**
`budgets.probe_astra = 55.00` is now declared in `grid.yaml` and `Budgets`. The arm ran
under `--spend-cap 55` and the ledger recorded `cap=55.0, cum_usd=11.7197`, so the run
was always inside its own cap. The declaration was added because
`analysis/run.py`'s `ran_clean` gate re-derives the cap from `budgets.<subgrid>` and
falls back to the $10 **pilot** cap for any undeclared subgrid — which reported a
spurious `clean=False` for a run that never breached its real ceiling. Declaring the
budget makes the gate compare against the right number (`clean=True`). The underlying
fragility remains and is on the revision's fix list: `ran_clean` should read the cap the
ledger itself recorded rather than re-deriving it from config.

**Outcome (exploratory, as declared).** 1,600 calls, 0 errors, parse rate 1.000, spend
$11.72. Terse beta = 0.214 notches/step, firm-clustered bootstrap 95% CI [0.179, 0.245];
placebo 0.031, net 0.182 CI [0.149, 0.213]. Both exclude zero. Asymmetry D:U = 3.11.
Under `v_ttc` the rating slope flattens to -0.046 (net -0.020, CI includes zero) while
log-odds PD retention is -0.104. The go/no-go question ("is beta at the frontier near
zero?") is answered NO, so the confirmatory frontier grids proceed as planned.

## AMENDMENT #5 — confirmatory frontier grids `frontier` (2026-09-29, referee revision)

**What.** A new model `gemini_pro` (`gemini-pro-latest`) and a new subgrid `frontier` =
{`openai_astra`, `gemini_pro`} × all 4 framings × 2 seeds × (5 macro + 5 placebo) × the
**80-firm** battery = **12,800 calls**, budget $250. `Budgets` gains `frontier`.

**Why.** The AMENDMENT #4 probe answered its go/no-go question (frontier β = 0.214, CI
[0.179, 0.245], excludes zero), so the confirmatory arm proceeds. These are the frontier
tier of families **already in the study**, so no new vendor is introduced: `gpt-6-astra`
completes the OpenAI gradient (4o-mini → 4.1-mini → 4o → astra) and `gemini-pro` the
Google one (Flash-Lite → Flash → Pro). Referee #1's comment 4 offers "additional model
families **or** stronger frontier models" and is satisfied by the latter; referee #2's
comment 1 asks for "a state-of-the-art model" and names GPT-6 Astra specifically.

Both run the **full** grid rather than a slice, so they are directly comparable to the
incumbents on every dimension and no slice-matched recomputation is needed.

**Measured constraints (2026-09-29, live API).** Each new model violates a different
design default, and each is declared rather than absorbed:

| | `gpt-6-astra` | `gemini-pro-latest` |
|---|---|---|
| `temperature=0` | **REFUSED** (t=1 only) | accepted — temperature-matched |
| thinking/reasoning off | `reasoning_effort=low`, 0 reasoning tokens observed | **CANNOT disable** ("Budget 0 is invalid. This model only works in thinking mode") |
| `logprobs` | **REFUSED** | n/a (never available on Gemini) |

So the two frontier arms are asymmetric with each other and with the incumbents: astra is
not temperature-matched, and Pro necessarily thinks where the Flash arms had
`thinking_budget: 0`. Neither asymmetry can manufacture procyclicality — both add
per-call variance, which widens CIs and biases *against* detecting a slope — but any
frontier-vs-incumbent contrast must state them. `thinking_budget` is left UNSET for Pro:
a low budget (128) cuts billed output ~33% but handicaps the capability under test, and
referee #2's premise is that a practitioner would deploy the sophisticated model, so it is
evaluated at its default reasoning effort.

**Cost accounting fix (material; not a design change).** `agent.py`'s Gemini path returned
`candidates_token_count` as the output token count and **ignored
`thoughts_token_count`**, which Google bills as output. This was harmless for the Flash
arms (`thinking_budget: 0` → zero thought tokens, so their frozen `cost_usd` is
unaffected — verified by fault injection) but understated `gemini-pro` by **4.3×**, which
would have written wrong `cost_usd` values into the artifact and let the hard spend cap
under-bind. Thought tokens are now counted as output.

**Sizing (measured on the real prompt, not assumed).** astra $0.00663/call;
`gemini-pro` $0.0127/call including thought tokens → expected total ~$124. Pro's
`max_tokens` is 4096 because the pipeline probe billed **1010** output tokens against an
initial 1024 cap — one step from truncation, which returns empty content and would have
mass-ERRORed the arm. The budget is $250 rather than $150 because preflight tests
cumulative spend plus *this* capture's worst case ($79.8 for a 1,600-call Pro capture);
$150 would have refused the final Pro capture mid-run.

**Scope.** Additive. No existing subgrid, model, battery, estimand or analysis path is
modified; frozen `full`/`pilot`/`probe_astra` results stand. Re-freeze after this edit.

## AMENDMENT #6 — OFAT macro-factor decomposition `ofat` (2026-09-29, referee revision)

**What.** A new `ofat_states` axis (21 states) and a new subgrid `ofat` = 4 models ×
`v_terse` × 2 seeds × 21 states × the 80-firm battery = **13,440 calls**, budget $150.
`GridCfg` gains `ofat_states`, `Subgrid` gains `ofat_states`, `state_plan` emits
`kind='ofat'`, and `agent.py` registers 21 `_OFAT_BLOCKS`.

**Why.** Referee #1 comment 3: the five joint states move all five indicators together
and monotonically, so the main design cannot identify WHICH macro signal drives the
rating change. Each OFAT state moves ONE factor across the same −2..+2 severity range
while holding the other four at their NEUTRAL values, so a per-factor slope is measured
on the identical scale as the joint slope and is directly comparable to it.

**Design.** Factor levels are taken **verbatim** from the joint states, so an OFAT cell
at severity *s* differs from the joint cell at *s* only in which factors moved — no new
numbers enter the design. Severity 0 is all-neutral for every factor, so it is emitted
once as `ofat_neutral`, which is **byte-identical** to the joint `neutral` block
(verified). 5 factors × 4 off-neutral levels + 1 shared neutral = 21 states.

**A separate axis, deliberately.** These states REUSE severities across the five
factors, and `macro_states` carries a validator requiring distinct severities. That
check guards the joint axis's identification and was **not** relaxed; OFAT was given its
own `ofat_states` map and its own `kind='ofat'` instead. Consequences: pooling all 21 on
the macro axis would regress notch on an ambiguous state ordering and produce a
meaningless "joint" slope, so the dedicated kind keeps every existing macro/placebo
analysis from picking these cells up, and the OFAT analysis slices them per factor by
name. Verified additive: `pilot`, `full`, `frontier` and `probe_astra` still plan exactly
10 cells per (model, variant) split 5 macro / 5 placebo.

**Scope choices.** No placebo axis — the placebo tests credit-IRRELEVANCE, whereas this
decomposes the macro axis itself, so a placebo arm would add cost and answer nothing.
Terse framing only — the question concerns macro signals, not instructions. Four models
rather than seven — a mechanism decomposition needs enough models to show the ranking is
consistent, not every model: `openai_4o_mini` (most cyclical, clearest signal),
`openai_4o` (mid), `gemini_flash` (second family), `openai_astra` (does the driver
ranking change at the frontier?). Expected spend ~$30; astra dominates it.

**Scope.** Additive. No existing subgrid, model, battery, estimand or frozen result is
modified. Re-freeze after this edit.

**Provider-track split (AMENDMENT #6, added mid-run).** Google prepaid credits were
exhausted partway through the OFAT arm, so `gemini_flash` was parked and the OpenAI
models continued. On restoration the Gemini model was run CONCURRENTLY on its own
ledger (`--ledger-suffix _gemini`, `--spend-cap 10`) rather than against the global one,
because two concurrent captures sharing a single ledger file race on `cum_usd` and the
exact-cap guarantee is lost -- this is the same split-cap pattern `run_all.sh`'s
PARALLEL mode uses. `budgets.ofat` was raised 150 -> 160 so the declared budget remains
the SUM of the two track ceilings (150 OpenAI + 10 Gemini); it is a bookkeeping change,
not additional spend. Capture is resumable, so only the missing Gemini cells were billed.

## AMENDMENT #7 — real-fundamentals arm and replication-stability arm (2026-09-29)

**What.** Two additive subgrids and one new firm battery.

*(a) `real` — real fundamentals (referee 1 comments 1 and 2).* A new battery
`data/firms/real.jsonl`: 80 firms whose fundamentals are ACTUAL FY2024 figures from SEC
XBRL frames (public domain, so the cache ships with the artifact and the build is offline
reproducible). Subgrid = 4 models × {`v_terse`,`v_ttc`} × 2 seeds × (5 macro + 5 placebo)
× 80 real firms = **12,800 calls**, budget $150. `Subgrid.firms` admits `"real"`;
`load_firms()` needed no change.

*Why real fundamentals but synthetic identity.* Real **firms** would break the design: a
recognised issuer lets the model recall that issuer's actual rating, and the issuer's
identity also implies a time period, entangling firm identity with the macro state and
destroying the byte-identical counterfactual. That objection attaches to IDENTITY, not to
the numbers. So the arm keeps real ratios and strips identity — no name, ticker, CIK or
date reaches the block, and the serializer is IMPORTED from `build_firms.py` so a real and
a synthetic block are byte-identical in FORM. Financials (SIC 6000–6499) are excluded
because EBITDA/interest and net debt/EBITDA are not meaningful bank credit metrics.
Tier assignment uses stated coverage × leverage thresholds mirroring the synthetic
profiles, so it is auditable rather than fitted.

*De-identification is MEASURED, not assumed.* `capture/contamination_test.py` asks each
model to name the company behind a block and reports the identification rate, with the
synthetic battery as a NEGATIVE CONTROL so the false-positive floor is visible. GPT-4o:
**0/40 real, 0/40 synthetic, excess +0.0 pp.**

*(b) `seeds` — replication stability (referee 1 comment 7).* Three additional seeds
(2,3,4) on the terse condition, all seven models, both axes = **16,800 calls**, budget
$120, giving 5 seeds per cell on the condition every headline number comes from. Frontier
models included deliberately: excluding them would invite the objection that stability was
only tested on the older arms.

**Known limitation, reported rather than smoothed over.** Comparing the synthetic tier
ranges against the real distributions, 29 of 30 metric-tier comparisons overlap. The
exception is **`high_ig` revenue scale**: synthetic specifies $40–180bn, real top-tier
filers in this sample run $0.8–14.9bn (median $2.2bn) — no overlap. Real `high_ig` firms
also carry net cash (median net debt/EBITDA −0.30) where the synthetic profile assumes
0.2–1.3. Scale is the one dimension that cannot bias the estimand, because the macro
effect is measured WITHIN firm and every credit-relevant ratio overlaps; and the real pool
is size-biased because only 1,337 filers report `InterestExpense`. The honest claim is
therefore specific: the synthetic battery's credit-relevant ratios are representative, its
top-tier scale assumption is not.

**Scope.** Additive. No existing subgrid, model, battery, estimand or frozen result is
modified. Re-freeze after this edit.

**Track-cap correction (AMENDMENT #7, added after a preflight refusal).** The `seeds`
arm's provider-track split was $90 OpenAI + $30 Gemini. `gemini_pro` was then REFUSED at
preflight: its `max_tokens` of 4096 against `price_out` 12 gives a single 2,400-call
capture a worst case of $119.76, which no $30 ceiling can clear. `budgets.seeds` is raised
120 -> 230 and the Gemini track cap to $140, so track ceilings again sum to the declared
budget. This moves a projection ceiling, not expected spend: the Gemini seeds track had
spent $0.94 at that point and the arm's expected total is ~$49. Recorded because the
refusal is visible in the run log and a reader should know why the declared number moved.

**Non-authoritative captures, re-run rather than frozen.** Two `openai_astra` captures
(`real/v_ttc`, `seeds/v_terse`) finished with ERROR rates of 10.25% and 4.62%, above the
artifact's 2% freezing threshold, and `freeze.py` correctly REFUSED to issue receipts for
them. The cause was ours: a contamination-test sweep was running against the same OpenAI
key pool as a 48-worker capture, so the pool was rate-limited by our own diagnostic. Both
captures were resumed to completion with the diagnostic stopped; capture is resumable, so
only missing cells were re-billed. No partial capture was frozen or analysed.

## AMENDMENT #8 — configuration hash after the revision arms (2026-10-05)

**What changed.** `claims.json` recorded `meta.config_hash = 57c8b3991ffb253f`, the hash of
`config/` as it stood for the confirmatory study. Adding the amendment arms put their budgets,
tracks and models into `config/grid.yaml` and `config/models.yaml`, so the hash is now
`690d08754beda055` and `PREREGISTRATION.freeze.txt` records the corresponding re-freeze.

**Why this is not a protocol change.** The configuration diff is purely additive. Comparing the
flattened key sets against the committed version: `config/grid.yaml` 57 keys added, 0 removed,
0 changed; `config/models.yaml` 23 added, 0 removed, 0 changed. No pre-existing key moved, so
every parameter the confirmatory study was frozen against -- seeds, seed mode, temperature, runs,
ticker list, dates, configurations, forward-return horizon -- is byte-identical to the frozen
protocol. The hash moved because the file grew, not because the design did.

**Evidence that no result moved.** `claims.json` was regenerated from the frozen captures under
the current configuration and compared leaf by leaf against the previously committed file: of
1,354 leaves, exactly one differs, `meta.config_hash`. All 1,137 numeric leaves are identical.
The regenerated file is the one now in the repository, so `reproduce.sh` verifies byte-identically
again instead of failing on a provenance stamp.

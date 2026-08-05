# PREREGISTRATION AMENDMENTS — P5

Post-freeze changes to the pre-registration. Each entry records what changed, why,
and the date, and triggers a re-freeze of `PREREGISTRATION.freeze.txt`.

Original freeze: PREREGISTRATION.md sha256
`841d465b9e407eea08bc07e04471b521ccf19969fa4ff37bcef708ebb21f022b`,
config_hash `757bed608aa28d19`, frozen 2026-07-15 (the exact config the PILOT ran
under). The pilot is confirmatory-gating under that hash; the amendment below applies
only to the FULL run and is declared BEFORE any full-run capture.

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

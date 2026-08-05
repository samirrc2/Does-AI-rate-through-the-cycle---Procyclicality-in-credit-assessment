# RUNBOOK — P5

Exact commands. **CAPTURE runs on your local machine** (where the API keys and
network live); the Cowork sandbox cannot reach the vendor APIs. **ANALYSIS runs
anywhere for $0.** Nothing beyond the pilot runs until the pilot passes and you
say go.

Prereqs (local):
```bash
cd "NIW/Paper 5"
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# keys are read from ../API Keys/keys.env.txt automatically (OPENAI_API_KEY_1..,
# GEMINI_API_KEY_1.., XAI_API_KEY). The Anthropic key is intentionally unused.
```

### TL;DR — run the pilot (copy-paste)
```bash
cd "NIW/Paper 5"
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

PILOT_MOCK=1 ./run_all.sh                  # 1. dry-run: proves it works for $0 → PILOT: PASS
python3 capture/probe.py --subgrid pilot   # 2. confirm models resolve (tiny real spend)
RESET=1 SUBGRID=pilot ./run_all.sh         # 3. the real pilot: ≤$10, ledger-gated, resumable
cat pilot/PILOT_VERDICT.md                 # 4. read the verdict, then stop for go-ahead
```
That's the whole pilot. Steps 1–4, in order. Nothing spends real money until step 2.

---

## 0. Offline dry-run — prove the pipeline for $0 (do this first, anywhere)
Deterministic fake rater, no network, no spend. Must end in `PILOT: PASS`.
```bash
PILOT_MOCK=1 ./run_all.sh
# also verifiable piecemeal:
python3 capture/build_firms.py                   # firm battery (offline, $0), SHA-256 frozen
python3 capture/ledger_selftest.py               # proves the hard $10 cap aborts
```
Expected: `PILOT: PASS → cleared for full run`, 9,600 rows, 0 ERROR, spend $0.0000,
and an illustrative procyclical signal that is dampened under the TTC arm.

---

## (a) Pre-flight / probe — confirm models resolve + measure real per-call price
One tiny live call per pilot model → served-model fingerprint + measured price into
`manifest/probe_receipts.json`. Fixes the provisional snapshot strings in
`config/models.yaml` if any 404. Tiny real spend (fractions of a cent).
```bash
python3 capture/probe.py --subgrid pilot
# if a model errors, edit config/models.yaml api_model to the current snapshot,
# log it in DECISIONS.md, and re-probe.
```

Optional pre-flight cost check (no calls made):
```bash
for m in openai_4o_mini openai_41_mini gemini_flash gemini_flash_lite; do
  for v in v_terse v_ttc v_pit; do
    python3 capture/orchestrator.py --subgrid pilot --model $m --variant $v --dry-run
  done
done
# each prints projected worst-case spend vs the $10 cap and refuses if over.
```

---

## (b) The real pilot — ≤ $10, ledger-gated (spends money)

> **First real run:** clear the offline dry-run's MOCK artifacts once, or capture
> will refuse on a MOCK/REAL mode mismatch:
> ```bash
> RESET=1 SUBGRID=pilot ./run_all.sh        # clears mock CSVs/receipts/ledger, then runs the REAL pilot
> ```
> (`RESET=1` only clears when you ask; REAL captures are otherwise append-only.)

The ledger enforces `$10` across ALL captures; it hard-aborts the instant
projected-or-actual cumulative spend would cross the cap. Resumable: re-run to
continue; completed cells are never re-billed.
```bash
./run_all.sh                    # SUBGRID defaults to pilot; CONC defaults to 5
# faster: run provider tracks in parallel (each gets its own ledger + half the cap):
PARALLEL=1 CONC=8 ./run_all.sh
# or one model/variant at a time (same global ledger):
python3 capture/orchestrator.py --subgrid pilot --model openai_4o_mini --variant v_terse
python3 capture/freeze.py       --subgrid pilot --model openai_4o_mini --variant v_terse
```
Watch progress in another shell: `python3 status.py --subgrid pilot --watch`.
If the ledger trips, the run stops cleanly and prints the spend; just re-run to
resume. A capture with > 2% ERROR is non-authoritative — `freeze.py` refuses it.

---

## (c) Analysis + verdict — pure, $0, reproducible
Reads frozen CSVs only; byte-identical on re-run.
```bash
python3 analysis/run.py --subgrid pilot          # -> claims.json (every cited number + CI)
python3 pilot/verdict.py                          # -> pilot/PILOT_VERDICT.md, PILOT_RESULTS.md
python3 analysis/review_diag.py --subgrid pilot   # reviewer diagnostics: TTC-anchoring,
                                                  # asymmetry, expected-notch, noise floor,
                                                  # fingerprint-FE robustness (works on any
                                                  # subgrid: use --subgrid full after the full run)
```
Read `pilot/PILOT_VERDICT.md`. It ends in exactly one of:
`PILOT: PASS → cleared for full run` / `PILOT: FAIL (...)` / `PILOT: KILL (...)`.

**Then stop. Do not run the full grid until you have read the verdict and said go.**

---

## (d) Full run — ONLY after PILOT: PASS and your explicit go-ahead
Separate `$40` cap (`budgets.full`), adds gpt-4o + xAI Grok (two more families), the
`v_stable` anchoring-control arm (4 variants), and the full 80-firm battery = 38,400
cells. Best run after your OpenAI daily cap resets so the OpenAI arm completes fast.
```bash
python3 capture/probe.py --subgrid full          # probe the full model set (incl. Grok);
                                                 # measures real gpt-4o/Grok price so preflight is grounded
PARALLEL=1 SUBGRID=full CONC=8 ./run_all.sh       # ledger-gated at $40 (real projection ~$28-37)
python3 analysis/run.py --subgrid full
python3 pilot/verdict.py
python3 analysis/review_diag.py --subgrid full    # TTC-anchoring incl. v_ttc vs v_stable,
                                                 # asymmetry, expected-notch, fingerprint FE
```

---

### Notes
- Reset the offline dry-run any time: `PILOT_MOCK=1 ./run_all.sh` re-mints its own
  (mock) CSVs. Never resets REAL captures unless you pass `RESET=1`.
- Git: commit after each stage locally. (In the Cowork sandbox the mounted `.git`
  can't unlink lock files, so commits are best done from your machine.)

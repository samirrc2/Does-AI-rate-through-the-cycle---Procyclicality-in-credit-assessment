#!/usr/bin/env bash
# P5 end-to-end runner.
#   SUBGRID=pilot|full   which grid (default pilot)
#   PILOT_MOCK=1         offline deterministic fake rater, $0 (default 0 = live)
#   CONC=N               worker concurrency PER capture (default 5)
#   PARALLEL=1           run provider tracks (OpenAI / Gemini / xAI) CONCURRENTLY,
#                        each with its own ledger + an equal share of the cap so the
#                        aggregate spend still cannot cross the global budget. Default
#                        0 = sequential (single global ledger, exact cap — the
#                        defensible pilot path).
#
# Pipeline: build firm battery -> capture each (model,variant), freeze on landing ->
# analysis (frozen only) -> pilot verdict. The ledger enforces the budget cap; a
# budget stop aborts before freezing that CSV.
#
#   PILOT_MOCK=1 ./run_all.sh                 # offline dry-run (validate for $0)
#   ./run_all.sh                              # real pilot (<=$10, ledger-gated)
#   PARALLEL=1 SUBGRID=full CONC=8 ./run_all.sh   # full run, provider tracks in parallel
set -euo pipefail
cd "$(dirname "$0")"
PY="${PY:-python3}"
SUBGRID="${SUBGRID:-pilot}"
CONC="${CONC:-5}"
MOCK="${PILOT_MOCK:-0}"
PARALLEL="${PARALLEL:-0}"
MODE=$([ "$MOCK" = "1" ] && echo MOCK || echo REAL)
mkdir -p logs

echo "== P5 run_all: subgrid=$SUBGRID mode=$MODE conc=$CONC parallel=$PARALLEL =="

# 1. firm battery (deterministic, offline, $0)
if [ ! -f "data/firms/${SUBGRID}.jsonl" ]; then
  $PY capture/build_firms.py
fi

MODELS=$($PY -c "import sys;sys.path.insert(0,'config');import loader as C;print(' '.join(C.subgrid(C.load_all(),'$SUBGRID').models))")
VARIANTS=$($PY -c "import sys;sys.path.insert(0,'config');import loader as C;print(' '.join(C.subgrid(C.load_all(),'$SUBGRID').variants))")
echo "   models  : $MODELS"
echo "   variants: $VARIANTS"

# RESET=1 clears prior raw CSVs, freeze receipts and ledgers for a fresh start —
# e.g. before the FIRST real run (to drop the offline dry-run's MOCK artifacts,
# which otherwise trigger a MOCK/REAL mode-mismatch refusal). REAL data is only
# cleared when you explicitly ask via RESET=1.
if [ "${RESET:-0}" = "1" ]; then
  echo "   RESET=1: clearing raw CSVs, freeze receipts, ledgers for subgrid=$SUBGRID"
  for m in $MODELS; do for v in $VARIANTS; do
    for f in "data/raw/runs_${SUBGRID}_${m}_${v}.csv" "data/frozen/${SUBGRID}_${m}_${v}.freeze.json"; do
      [ -f "$f" ] && { chmod u+w "$f" 2>/dev/null || true; : > "$f"; rm -f "$f"; }
    done
  done; done
  for L in manifest/ledger_${SUBGRID}_MOCK*.json manifest/ledger_${SUBGRID}_REAL*.json; do
    [ -f "$L" ] && { chmod u+w "$L" 2>/dev/null || true; rm -f "$L"; }
  done
fi

# MOCK is a repeatable dry-run: reset prior mock CSVs + ledger so re-runs are clean.
if [ "$MOCK" = "1" ]; then
  for m in $MODELS; do for v in $VARIANTS; do
    f="data/raw/runs_${SUBGRID}_${m}_${v}.csv"
    [ -f "$f" ] && { chmod u+w "$f" 2>/dev/null || true; rm -f "$f"; }
    fr="data/frozen/${SUBGRID}_${m}_${v}.freeze.json"; [ -f "$fr" ] && rm -f "$fr"
  done; done
  for L in manifest/ledger_${SUBGRID}_MOCK*.json; do [ -f "$L" ] && rm -f "$L"; done
fi

# provider of a model key (for parallel track grouping + cap splitting)
provider_of () { $PY -c "import sys;sys.path.insert(0,'config');import loader as C;print(C.load_all().models.cfg('$1').provider)"; }

capture_one () {   # args: model variant [suffix] [capflag]
  local m="$1" v="$2" suf="${3:-}" capflag="${4:-}"
  set +e
  PILOT_MOCK=$MOCK $PY capture/orchestrator.py --subgrid "$SUBGRID" --model "$m" \
      --variant "$v" --concurrency "$CONC" ${suf:+--ledger-suffix "$suf"} $capflag
  local rc=$?
  set -e
  if [ $rc -eq 0 ]; then
    $PY capture/freeze.py --subgrid "$SUBGRID" --model "$m" --variant "$v"
  fi
  return $rc
}

if [ "$PARALLEL" = "1" ]; then
  # Group models by provider; run one background track per provider. Split the cap
  # equally across tracks (each track gets its own ledger suffix + --spend-cap), so
  # the SUM across tracks still cannot exceed the global budget.
  # NOTE: bash 3.2 compatible (macOS default) — NO associative/`declare -A` arrays.
  PROVIDERS=""
  for m in $MODELS; do
    p=$(provider_of "$m")
    case " $PROVIDERS " in *" $p "*) ;; *) PROVIDERS="$PROVIDERS $p" ;; esac
  done
  NTRACKS=$(echo $PROVIDERS | wc -w | tr -d ' ')
  CAP=$($PY -c "import sys;sys.path.insert(0,'config');import loader as C;print(getattr(C.load_all().grid.budgets,'$SUBGRID'))")
  SUBCAP=$($PY -c "print(round($CAP/$NTRACKS,4))")
  echo "   PARALLEL: $NTRACKS provider tracks, per-track cap \$$SUBCAP (global \$$CAP)"
  PIDS=""; TRACKS=""
  for p in $PROVIDERS; do
    pm=""
    for m in $MODELS; do [ "$(provider_of "$m")" = "$p" ] && pm="$pm $m"; done
    ( trc=0
      for m in $pm; do
        for v in $VARIANTS; do
          capture_one "$m" "$v" "_$p" "--spend-cap $SUBCAP" || trc=$?
        done
      done
      exit $trc
    ) >"logs/${SUBGRID}_${p}.log" 2>&1 &
    PIDS="$PIDS $!"; TRACKS="$TRACKS $p"
    echo "     -> $p track PID $! -> logs/${SUBGRID}_${p}.log"
  done
  fail=0
  set -- $TRACKS
  for pid in $PIDS; do
    tname="$1"; shift
    if wait "$pid"; then echo "   track $tname DONE";
    else echo "   track $tname stopped/failed (see logs/${SUBGRID}_${tname}.log)"; fail=1; fi
  done
  [ "$fail" = 1 ] && echo "!! a track stopped early (budget or error) — analysis runs on what landed."
else
  # Sequential: one global ledger, exact cap guarantee.
  for m in $MODELS; do
    for v in $VARIANTS; do
      set +e; capture_one "$m" "$v"; rc=$?; set -e
      if [ $rc -eq 3 ]; then
        echo "!! budget stop during $m/$v — resume by re-running. Aborting."; exit 3
      elif [ $rc -eq 6 ]; then
        echo "!! preflight budget refusal for $m/$v — aborting."; exit 6
      elif [ $rc -ne 0 ]; then
        echo "!! capture error rc=$rc for $m/$v"; exit $rc
      fi
    done
  done
fi

# 3. analysis (pure, $0, frozen CSVs only)
$PY analysis/run.py --subgrid "$SUBGRID"

# 4. pilot verdict (report + stop; never starts the full run)
$PY pilot/verdict.py

echo "== done: see claims.json and pilot/PILOT_VERDICT.md =="

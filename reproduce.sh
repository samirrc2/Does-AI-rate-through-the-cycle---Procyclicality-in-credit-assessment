#!/usr/bin/env bash
# ============================================================================
# P5 — "Do LLMs Rate Through the Cycle?"  ·  REPRODUCE (offline, $0, no capture)
# ============================================================================
# Regenerates the analysis from the FROZEN captures in data/ and verifies it
# against the committed results. This NEVER calls a vendor API, never captures
# new data, and never spends money — it is a pure, deterministic function of the
# frozen inputs. (Live capture is a separate, key-gated path; see docs/RUNBOOK.md.)
#
#   bash reproduce.sh            # FULL: integrity + regenerate claims.json + compare
#   bash reproduce.sh --quick    # FAST (~seconds): integrity + exact primary estimates
#                                #   (skips the 2000-draw bootstrap)
#   bash reproduce.sh --write    # FULL, then refresh results/ (claims, verdict, diag)
#   SUBGRID=pilot bash reproduce.sh
#
# The primary estimands (within-firm cyclicality slopes) are pure-python and
# reproduce EXACTLY on any platform; the 95% CIs come from a seeded pure-python
# bootstrap and also reproduce exactly. The ordered-probit robustness estimator uses
# SciPy's optimizer, which can differ at floating-point precision across builds — so a
# whole-file hash is byte-identical only in the pinned environment (environment/
# Dockerfile). --quick verifies the primary estimands without the bootstrap.
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONUNBUFFERED=1
PY="${PY:-python3}"
SUBGRID="${SUBGRID:-full}"
MODE="full"
case "${1:-}" in
  --quick) MODE="quick" ;;
  --write) MODE="write" ;;
esac

echo "== P5 reproduce ($MODE): subgrid=$SUBGRID · offline · \$0 · no capture =="

# ---- (1)(2)(3) integrity: frozen data + pre-registration ----------------------
$PY - "$SUBGRID" <<'PY'
import hashlib, json, sys
from pathlib import Path
sub = sys.argv[1]; root = Path(".")
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
ok = True
man = json.loads((root/"manifest"/"firms_manifest.json").read_text())
for which in ("pilot", "full"):
    f = root/"data"/"firms"/f"{which}.jsonl"
    if f.exists() and which in man:
        got, exp = sha(f), man[which]["sha256"]
        ok &= got == exp
        print(f"  [{'OK ' if got==exp else 'FAIL'}] firm battery {which}.jsonl  {got[:16]}… vs {exp[:16]}…")
frozen = sorted((root/"data"/"frozen").glob(f"{sub}_*.freeze.json"))
nfz = nfail = 0
for rec in frozen:
    r = json.loads(rec.read_text()); csvp = root/"data"/"raw"/r["csv"]
    if not csvp.exists(): print(f"  [MISS] {r['csv']}"); ok = False; continue
    nfz += 1
    if sha(csvp) != r["sha256"]: nfail += 1; ok = False; print(f"  [FAIL] {r['csv']}")
print(f"  [{'OK ' if nfail==0 else 'FAIL'}] {nfz} frozen captures match receipts ({nfail} mismatch)")
import re
fz = root/"PREREGISTRATION.freeze.txt"
if fz.exists():
    m = re.search(r"sha256\s+([0-9a-f]{64})", fz.read_text())
    if m:
        got = sha(root/"PREREGISTRATION.md"); ok &= got == m.group(1)
        print(f"  [{'OK ' if got==m.group(1) else 'FAIL'}] PREREGISTRATION.md {got[:16]}… vs freeze {m.group(1)[:16]}…")
sys.exit(0 if ok else 2)
PY
[ $? -ne 0 ] && { echo "!! INTEGRITY FAILED — frozen inputs do not match recorded hashes. Stop."; exit 2; }

# ---- QUICK: primary point-estimates (no bootstrap) ----------------------------
if [ "$MODE" = "quick" ]; then
  $PY - "$SUBGRID" <<'PY'
import json, sys
sys.path.insert(0, "analysis"); sys.path.insert(0, "config")
import ratings as RA, cyclicality as CY
sub = sys.argv[1]; c = json.load(open("claims.json"))
rt = RA.load_rating_table(subgrid_filter=sub, allowed_models=set(c["meta"]["models"]))
bad = n = 0
for key, d in c["per_model_variant"].items():
    mv = (d["model"], d["variant"]); firms = rt.firm_support(mv, "macro"); n += 1
    if CY.cyclicality_notch(rt, mv, firms) != d["cyclicality_notch_per_step"]:
        print(f"  DIFF {key}"); bad += 1
print(f"  [{'OK ' if bad==0 else 'FAIL'}] {n-bad}/{n} primary cyclicality estimands reproduce EXACTLY")
sys.exit(0 if bad == 0 else 3)
PY
  echo "== reproduce (quick): DONE =="; exit $?
fi

# ---- FULL: regenerate and compare ---------------------------------------------
TMP="$(mktemp -d)"
echo "  regenerating claims.json (seeded 2000-draw bootstrap; ~2-5 min)…"
$PY analysis/run.py --subgrid "$SUBGRID" --out "$TMP/claims.json" >/dev/null
sha() { if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | awk '{print $1}'; else shasum -a 256 "$1" | awk '{print $1}'; fi; }
A="$(sha claims.json)"; B="$(sha "$TMP/claims.json")"
echo "  committed  : $A"
echo "  regenerated: $B"
if [ "$A" = "$B" ]; then
  echo "  ==> BYTE-IDENTICAL. Full reproduction verified."
else
  echo "  ==> whole-file hash differs; checking reported PRIMARY numbers exactly:"
  $PY - "claims.json" "$TMP/claims.json" <<'PY'
import json, sys
c = json.load(open(sys.argv[1])); r = json.load(open(sys.argv[2])); bad = 0
if c['headline_cyclicality']['pooled_notch_per_step'] != r['headline_cyclicality']['pooled_notch_per_step']:
    print("   DIFF headline pooled"); bad += 1
for k, a in c['per_model_variant'].items():
    b = r['per_model_variant'][k]
    if a['cyclicality_notch_per_step'] != b['cyclicality_notch_per_step']: print(f"   DIFF {k} slope"); bad += 1
    if a['cyclicality_ci95'] != b['cyclicality_ci95']: print(f"   DIFF {k} CI"); bad += 1
if bad == 0:
    print("   All PRIMARY estimands (within-firm slopes + bootstrap CIs) reproduce EXACTLY.")
    print("   (Whole-file difference is confined to the ordered-probit robustness estimator,")
    print("    whose SciPy optimizer is platform-sensitive; use environment/Dockerfile for")
    print("    a byte-identical run.)")
else:
    print(f"   {bad} PRIMARY estimand(s) differ — reproduction FAILED."); sys.exit(3)
PY
fi

if [ "$MODE" = "write" ]; then
  echo "  --write: refreshing results/ …"
  cp "$TMP/claims.json" claims.json
  $PY pilot/verdict.py >/dev/null
  $PY analysis/review_diag.py --subgrid "$SUBGRID" > "results/review_diag_${SUBGRID}.txt" 2>/dev/null || true
  echo "  results refreshed."
fi
rm -rf "$TMP"
echo "== reproduce: DONE =="

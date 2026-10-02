#!/usr/bin/env bash
# ============================================================================
# P5 — "Does AI rate through the cycle?"  ·  REPRODUCE (offline, $0, no capture)
# ============================================================================
# Regenerates the analysis from the FROZEN captures in data/ and verifies it
# against the committed results. This NEVER calls a vendor API, never captures
# new data, and never spends money — it is a pure, deterministic function of the
# frozen inputs. (Live capture is a separate, key-gated path; see docs/RUNBOOK.md.)
#
#   bash reproduce.sh            # FULL: integrity + regenerate claims.json + SHA match
#   bash reproduce.sh --quick    # FAST (~seconds): integrity + primary estimates
#                                #   (skips the 2000-draw bootstrap)
#   bash reproduce.sh --write    # FULL, then refresh results/ (claims, verdict, diag)
#   SUBGRID=pilot bash reproduce.sh
#
# claims.json floats are integer-quantized (12 decimals) before write, so the
# whole-file SHA-256 matches across platforms. --quick checks primary slopes
# against the committed file within 0.5 ULP of that quantization.
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
"$PY" - "$SUBGRID" <<'PY'
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

# ---- canonicalize unit test (same dict → same bytes) -------------------------
"$PY" -m unittest tests.test_canonicalize -q
[ $? -ne 0 ] && { echo "!! canonicalize unit tests FAILED. Stop."; exit 4; }
echo "  [OK ] canonicalize dumps_claims unit tests"

# ---- QUICK: primary point-estimates (no bootstrap) ----------------------------
if [ "$MODE" = "quick" ]; then
  "$PY" - "$SUBGRID" <<'PY'
import json, sys
sys.path.insert(0, "analysis"); sys.path.insert(0, "config")
import ratings as RA, cyclicality as CY, canonicalize as CAN
TOL = 0.5 * 10 ** (-CAN.CLAIMS_FLOAT_DECIMALS)
def same(a, b):
    return a is not None and b is not None and abs(a - b) <= TOL
sub = sys.argv[1]; c = json.load(open("claims.json"))
rt = RA.load_rating_table(subgrid_filter=sub, allowed_models=set(c["meta"]["models"]))
bad = n = 0
for key, d in c["per_model_variant"].items():
    mv = (d["model"], d["variant"]); firms = rt.firm_support(mv, "macro"); n += 1
    got = CAN.quantize(CY.cyclicality_notch(rt, mv, firms))
    if not same(got, d["cyclicality_notch_per_step"]):
        print(f"  DIFF {key}: got={got} committed={d['cyclicality_notch_per_step']}"); bad += 1
print(f"  [{'OK ' if bad==0 else 'FAIL'}] {n-bad}/{n} primary cyclicality estimands match (quantized {CAN.CLAIMS_FLOAT_DECIMALS} dp)")
sys.exit(0 if bad == 0 else 3)
PY
  echo "== reproduce (quick): DONE =="; exit $?
fi

# ---- FULL: regenerate and require byte-identical claims.json ------------------
TMP="$(mktemp -d)"
echo "  regenerating claims.json (seeded 2000-draw bootstrap; ~2-5 min)…"
"$PY" analysis/run.py --subgrid "$SUBGRID" --out "$TMP/claims.json" >/dev/null

if [ "$MODE" = "write" ]; then
  echo "  --write: refreshing claims.json + results/ …"
  cp "$TMP/claims.json" claims.json
  "$PY" pilot/verdict.py >/dev/null
  "$PY" analysis/review_diag.py --subgrid "$SUBGRID" > "results/review_diag_${SUBGRID}.txt" 2>/dev/null || true
  echo "  results refreshed."
fi

sha() { if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | awk '{print $1}'; else shasum -a 256 "$1" | awk '{print $1}'; fi; }
A="$(sha claims.json)"; B="$(sha "$TMP/claims.json")"
echo "  committed  : $A"
echo "  regenerated: $B"
if [ "$A" = "$B" ]; then
  echo "  ==> BYTE-IDENTICAL. Full reproduction verified."
else
  echo "  ==> HASH MISMATCH — claims.json did not reproduce byte-identically."
  "$PY" - "claims.json" "$TMP/claims.json" <<'PY'
import json, sys
sys.path.insert(0, "analysis")
import canonicalize as CAN
c = json.load(open(sys.argv[1])); r = json.load(open(sys.argv[2]))
def walk(a, b, path="$"):
    if type(a) != type(b) and not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
        print(f"   TYPE {path}: {type(a).__name__} vs {type(b).__name__}"); return 1
    if isinstance(a, dict):
        keys = set(a) | set(b); n = 0
        for k in sorted(keys):
            if k not in a: print(f"   MISS committed {path}.{k}"); n += 1
            elif k not in b: print(f"   MISS regenerated {path}.{k}"); n += 1
            else: n += walk(a[k], b[k], f"{path}.{k}")
        return n
    if isinstance(a, list):
        if len(a) != len(b):
            print(f"   LEN {path}: {len(a)} vs {len(b)}"); return 1
        return sum(walk(x, y, f"{path}[{i}]") for i, (x, y) in enumerate(zip(a, b)))
    if isinstance(a, bool) or a is None or isinstance(a, str):
        if a != b: print(f"   DIFF {path}: {a!r} vs {b!r}"); return 1
        return 0
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        qa, qb = CAN.quantize(float(a)), CAN.quantize(float(b))
        if qa != qb:
            print(f"   DIFF {path}: {a!r} vs {b!r} (q {qa} vs {qb})"); return 1
        return 0
    if a != b:
        print(f"   DIFF {path}: {a!r} vs {b!r}"); return 1
    return 0
n = walk(c, r)
print(f"   {n} leaf mismatch(es) after quantization.")
sys.exit(3)
PY
fi
rm -rf "$TMP"
echo "== reproduce: DONE =="

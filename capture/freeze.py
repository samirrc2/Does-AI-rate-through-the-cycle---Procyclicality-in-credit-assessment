"""Freeze-on-landing: hash + lock one capture CSV the moment it completes. Writes
data/frozen/<subgrid>_<model>_<variant>.freeze.json with the SHA-256 of the raw CSV
and makes the CSV read-only. Analysis reads only frozen CSVs."""
from __future__ import annotations
import argparse, csv, hashlib, json, os, stat, sys
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_RAW = _HERE.parent / "data" / "raw"
_FROZEN = _HERE.parent / "data" / "frozen"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stats(path: Path):
    n = n_err = 0
    for r in csv.DictReader(path.open()):
        n += 1
        if r.get("ok") != "True":
            n_err += 1
    return n, n_err


def freeze_one(subgrid: str, model: str, variant: str) -> int:
    csv_path = _RAW / f"runs_{subgrid}_{model}_{variant}.csv"
    if not csv_path.exists():
        print(f"[freeze] ERROR: {csv_path.name} not found — capture first."); return 2
    n, n_err = _stats(csv_path)
    err_rate = n_err / max(1, n)
    if err_rate > 0.02:
        print(f"[freeze] REFUSING: {csv_path.name} ERROR rate {err_rate*100:.2f}% > 2% "
              f"— NON-AUTHORITATIVE. Re-run to <=2% before freezing."); return 7
    _FROZEN.mkdir(parents=True, exist_ok=True)
    digest = sha256(csv_path)
    receipt = {
        "subgrid": subgrid, "model": model, "variant": variant, "csv": csv_path.name,
        "sha256": digest, "n_rows": n, "n_error": n_err,
        "error_rate": round(err_rate, 4),
        "frozen_utc": datetime.now(timezone.utc).isoformat(),
    }
    (_FROZEN / f"{subgrid}_{model}_{variant}.freeze.json").write_text(json.dumps(receipt, indent=2))
    try:
        os.chmod(csv_path, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
    except OSError:
        pass
    print(f"[freeze] {csv_path.name} sha256={digest[:16]}... rows={n} err={n_err} -> receipt")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--subgrid", default="pilot")
    ap.add_argument("--model", required=True)
    ap.add_argument("--variant", required=True)
    args = ap.parse_args()
    return freeze_one(args.subgrid, args.model, args.variant)


if __name__ == "__main__":
    sys.exit(main())

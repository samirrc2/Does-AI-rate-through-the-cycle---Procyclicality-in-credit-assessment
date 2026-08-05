"""Live capture progress — counts rows landed in data/raw against the expected cell
count for a subgrid. $0, read-only. Handy while a parallel run is in flight.

  python status.py --subgrid pilot           # one snapshot
  python status.py --subgrid pilot --watch    # refresh every few seconds
"""
from __future__ import annotations
import argparse, csv, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "config"))
import loader as C  # noqa: E402

_RAW = Path(__file__).resolve().parent / "data" / "raw"


def snapshot(subgrid: str) -> str:
    cfg = C.load_all()
    sg = C.subgrid(cfg, subgrid)
    n_firms = cfg.firms.sizes.pilot if sg.firms == "pilot" else cfg.firms.sizes.full
    n_states = len(sg.macro_states) + len(getattr(sg, "placebo_states", []))
    per_mv = len(sg.seed_indices) * n_firms * n_states
    total = per_mv * len(sg.models) * len(sg.variants)
    done = err = 0
    for m in sg.models:
        for v in sg.variants:
            p = _RAW / f"runs_{subgrid}_{m}_{v}.csv"
            if not p.exists():
                continue
            for r in csv.DictReader(p.open()):
                done += 1
                if r.get("ok") != "True":
                    err += 1
    pct = 100.0 * done / total if total else 0.0
    return (f"[status] {subgrid}: {done}/{total} cells ({pct:.1f}%), {err} ERROR "
            f"| {len(sg.models)} models x {len(sg.variants)} var x {per_mv} cells/mv")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--subgrid", default="pilot")
    ap.add_argument("--watch", action="store_true")
    args = ap.parse_args()
    if not args.watch:
        print(snapshot(args.subgrid)); return 0
    try:
        while True:
            print(snapshot(args.subgrid)); time.sleep(5)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())

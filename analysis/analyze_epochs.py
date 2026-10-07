"""Replication stability and version drift (referee 1 comment 7). Offline, $0.

The comment asks about two things -- repeated API calls AND model updates -- and the
revision's extra seeds happened to separate them, because they were collected 2.5 months
after the original grid. So the same nominal models were measured in two epochs, and the
two sources can be decomposed instead of conflated:

  within-epoch  : replicate seeds inside one collection date  -> pure decoding noise
  across-epoch  : the same cell in July vs September          -> served-version drift

Both are reported per model, together with the drift in the COEFFICIENT itself, which is
the quantity the paper actually claims. Emits results/seeds_epochs.json.
"""
from __future__ import annotations
import argparse, collections, csv, json, os, statistics as st, sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE)); sys.path.insert(0, str(_HERE.parent / "config"))
import cyclicality as CY   # noqa: E402

SEV = {"boom": -2, "expansion": -1, "neutral": 0, "slowdown": 1, "severe_recession": 2}
MODELS = ["openai_4o_mini", "openai_41_mini", "openai_4o", "gemini_flash"]
# pinned snapshot vs unpinned alias -- the distinction the drift result turns on
PINNED = {"openai_4o_mini": True, "openai_41_mini": True, "openai_4o": True,
          "gemini_flash": False}
RAW = _HERE.parent / "data" / "raw"


def cells(path: Path, macro_only=False):
    c = collections.defaultdict(list)
    if not path.exists():
        return c
    for r in csv.DictReader(path.open()):
        if r.get("ok") != "True":
            continue
        if macro_only and r["macro_kind"] != "macro":
            continue
        v = r.get("rating_notch")
        if v:
            c[(r["firm_id"], r["macro_state"])].append(float(v))
    return c


def noise(c):
    m = [v for v in c.values() if len(v) > 1]
    if not m:
        return None
    return {"mean_within_cell_sd": sum(st.pstdev(v) for v in m) / len(m),
            "pct_cells_disagreeing": 100 * sum(1 for v in m if len(set(v)) > 1) / len(m),
            "n_cells": len(m)}


def beta(path: Path):
    c = cells(path, macro_only=True)
    byfirm = collections.defaultdict(dict)
    for (f, s), vs in c.items():
        if s in SEV:
            byfirm[f][s] = st.median(vs)
    sl = []
    for f, states in byfirm.items():
        sev = [float(SEV[s]) for s in states]; val = [states[s] for s in states]
        if len(sev) >= 4:
            v = CY._within_firm_slope(sev, val)
            if v is not None:
                sl.append(v)
    return (-(sum(sl) / len(sl)) if sl else None), len(sl)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results/seeds_epochs.json")
    a = ap.parse_args()
    out = {"epochs": {"july": "runs_full_*_v_terse.csv (seeds 0,1)",
                      "september": "runs_seeds_*_v_terse.csv (seeds 2,3,4)"},
           "models": {}}
    print(f"{'model':18}{'within Jul':>22}{'within Sep':>22}{'cells moved':>13}{'beta drift':>12}")
    for m in MODELS:
        pj = RAW / f"runs_full_{m}_v_terse.csv"
        ps = RAW / f"runs_seeds_{m}_v_terse.csv"
        if not ps.exists():
            continue
        cj, cs = cells(pj), cells(ps)
        nj, ns = noise(cj), noise(cs)
        both = [k for k in cj if k in cs and cj[k] and cs[k]]
        shifts = [st.median(cs[k]) - st.median(cj[k]) for k in both]
        moved = 100 * sum(1 for x in shifts if abs(x) > 1e-9) / max(1, len(shifts))
        mad = sum(abs(x) for x in shifts) / max(1, len(shifts))
        bj, njf = beta(pj); bs, nsf = beta(ps)
        rec = {"pinned_snapshot": PINNED[m], "within_epoch_july": nj,
               "within_epoch_september": ns,
               "across_epoch": {"pct_cells_moved": moved, "mean_abs_shift_notch": mad,
                                "n_cells": len(both)},
               "beta_july": bj, "beta_september": bs, "beta_drift": bs - bj,
               "n_firms_july": njf, "n_firms_september": nsf}
        out["models"][m] = rec
        print(f"  {m:16}SD {nj['mean_within_cell_sd']:.4f}/{nj['pct_cells_disagreeing']:4.1f}%"
              f"   SD {ns['mean_within_cell_sd']:.4f}/{ns['pct_cells_disagreeing']:4.1f}%"
              f"{moved:>11.1f}%{bs-bj:>+12.3f}")
    # the headline: cells churn, the estimand does not
    d = [abs(r["beta_drift"]) for r in out["models"].values()]
    out["max_abs_beta_drift"] = max(d) if d else None
    out["max_pct_cells_moved_pinned"] = max(
        (r["across_epoch"]["pct_cells_moved"] for r in out["models"].values()
         if r["pinned_snapshot"]), default=None)
    out["pct_cells_moved_unpinned_alias"] = next(
        (r["across_epoch"]["pct_cells_moved"] for r in out["models"].values()
         if not r["pinned_snapshot"]), None)
    print(f"\nmax |beta drift| = {out['max_abs_beta_drift']:.3f} notches; "
          f"pinned cells moved <= {out['max_pct_cells_moved_pinned']:.1f}%, "
          f"unpinned alias {out['pct_cells_moved_unpinned_alias']:.1f}%")
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=2, sort_keys=True))
    print(f"-> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

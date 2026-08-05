"""Review-response diagnostics (2026-07-15 reviewer). Pure, $0, reads the FROZEN
pilot captures only. Answers, on the real data:

  1. PD-divergence under v_ttc  — is TTC genuine rating-philosophy (rating flat, PD
     still moves PIT) or generic anchoring (both flat)?
  2. Estimator range + noise floor — small TTC coefficients shown next to the probit
     estimate and the within-cell seed noise floor (does the coef clear the floor?).
  3. Residual reframing — per-model residual procyclicality that SURVIVES the TTC
     instruction (notch/step and boom->severe-recession swing).
  4a. Asymmetry — downside slope (neutral->severe recession) vs upside slope
      (boom->neutral); the financially dangerous margin.
  4b. Expected-notch slope (OpenAI logprobs) surfaced in the main table.
  obs. Per-model parse/format check + fingerprint-stratified stability (severity
      coefficient with vs without system_fingerprint fixed effects).

  python3 analysis/review_diag.py --subgrid pilot
"""
from __future__ import annotations
import argparse, csv, sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "config"))
import ratings as RA          # noqa: E402
import cyclicality as CY      # noqa: E402
import probit as PB           # noqa: E402
import loader as C            # noqa: E402

_HERE = Path(__file__).resolve().parent
_RAW = _HERE.parent / "data" / "raw"


def _f(x, nd=3):
    return f"{x:.{nd}f}" if isinstance(x, (int, float)) else "n/a"


def half_slope(rt, mv, firms, lo_side: bool):
    """Mean within-firm downgrade-notches per step on one half of the macro axis.
    lo_side=True -> upside (severity <= 0: boom..neutral); False -> downside
    (severity >= 0: neutral..severe recession)."""
    order = rt.macro_order()
    sel = [s for s in order if (rt.state_sev[s] <= 0 if lo_side else rt.state_sev[s] >= 0)]
    slopes = []
    for fr in firms:
        pts = [(rt.state_sev[s], rt.notch[mv][fr].get(s)) for s in sel]
        pts = [(sv, v) for sv, v in pts if v is not None]
        if len(pts) < 2:
            continue
        sv = [p[0] for p in pts]; vv = [p[1] for p in pts]
        sl = CY._within_firm_slope(sv, vv)
        if sl is not None:
            slopes.append(sl)
    return -(sum(slopes) / len(slopes)) if slopes else None


def per_model_format(subgrid: str):
    """Per-model parse/error/format check straight from the raw CSVs."""
    rows = defaultdict(lambda: {"n": 0, "err": 0, "ratings": set(), "out_tok": [],
                                "fps": set()})
    for p in sorted(_RAW.glob(f"runs_{subgrid}_*.csv")):
        for r in csv.DictReader(p.open()):
            m = r["model_key"]; d = rows[m]
            d["n"] += 1
            if r.get("ok") != "True":
                d["err"] += 1
            else:
                d["ratings"].add(r["rating"])
                try:
                    d["out_tok"].append(int(r["output_tokens"]))
                except ValueError:
                    pass
            if r.get("system_fingerprint"):
                d["fps"].add(r["system_fingerprint"])
    out = {}
    for m, d in rows.items():
        ot = d["out_tok"]
        out[m] = {"n": d["n"], "err": d["err"],
                  "parse_rate": (d["n"] - d["err"]) / max(1, d["n"]),
                  "distinct_ratings": len(d["ratings"]),
                  "mean_out_tok": (sum(ot) / len(ot)) if ot else None,
                  "n_fingerprints": len(d["fps"])}
    return out


def fingerprint_fe_check(subgrid: str, model: str, variant: str):
    """Severity coefficient (procyclical-positive) WITH vs WITHOUT system_fingerprint
    fixed effects, on the macro rows for one (model, variant). If the coefficient is
    stable, the effect is not infrastructure/batch drift. Uses numpy OLS on
    firm + (optionally) fingerprint dummies."""
    p = _RAW / f"runs_{subgrid}_{model}_{variant}.csv"
    if not p.exists():
        return None
    sev, notch, firm, fp = [], [], [], []
    for r in csv.DictReader(p.open()):
        if r.get("ok") != "True" or r.get("macro_kind") != "macro":
            continue
        try:
            sev.append(float(r["macro_severity"])); notch.append(float(r["rating_notch"]))
        except ValueError:
            continue
        firm.append(r["firm_id"]); fp.append(r.get("system_fingerprint") or "NA")
    if len(sev) < 20:
        return None
    try:
        import numpy as np
    except Exception:
        return None

    def _coef(with_fp: bool):
        cols = [np.array(sev, float)]
        # firm dummies (drop first)
        firms = sorted(set(firm))
        for fu in firms[1:]:
            cols.append(np.array([1.0 if x == fu else 0.0 for x in firm]))
        if with_fp:
            fps = sorted(set(fp))
            for fu in fps[1:]:
                cols.append(np.array([1.0 if x == fu else 0.0 for x in fp]))
        X = np.column_stack([np.ones(len(sev))] + cols)
        y = np.array(notch, float)
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        return -float(beta[1])   # procyclical-positive (downgrade per +1 severity)

    return {"n": len(sev), "coef_firm_fe": _coef(False),
            "coef_firm_plus_fp_fe": _coef(True),
            "n_fingerprints": len(set(fp))}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--subgrid", default="pilot")
    args = ap.parse_args()
    cfg = C.load_all()
    sg = C.subgrid(cfg, args.subgrid)
    rt = RA.load_rating_table(subgrid_filter=args.subgrid, allowed_models=set(sg.models))
    models = rt.models
    variants = sorted(sg.variants)

    L = []
    P = print
    P(f"\n=== P5 REVIEW DIAGNOSTICS ({rt.mode}) — {args.subgrid} ===\n")

    # ---- obs: per-model format/parse ----
    fmt = per_model_format(args.subgrid)
    P("## Per-model parse / format check")
    P(f"{'model':18s} {'n':>5} {'err':>4} {'parse':>6} {'distinctR':>9} {'out_tok':>8} {'#fps':>5}")
    for m in models:
        d = fmt[m]
        P(f"{m:18s} {d['n']:>5} {d['err']:>4} {_f(d['parse_rate'],3):>6} "
          f"{d['distinct_ratings']:>9} {_f(d['mean_out_tok'],1):>8} {d['n_fingerprints']:>5}")

    # ---- main table: linear / probit / expnotch / noise / pd ----
    P("\n## Cyclicality per model x variant  (notch/step, procyclical-positive)")
    P(f"{'model':18s} {'var':7s} {'linear':>7} {'probit':>7} {'expNotch':>8} "
      f"{'noiseSD':>7} {'clrs?':>5} {'pd_logodds':>10} {'down':>6} {'up':>6}")
    rowsout = []
    for m in models:
        for v in variants:
            mv = (m, v)
            if mv not in rt.notch:
                continue
            firms = rt.firm_support(mv, "macro")
            lin = CY.cyclicality_notch(rt, mv, firms)
            pb = PB.ordered_probit(rt, mv, firms).get("notch_per_step")
            ef = rt.firm_support(mv, "macro", table="expnotch")
            exp = CY.cyclicality_notch(rt, mv, ef, "macro", "expnotch") if ef else None
            nz = rt.noise_sd.get(mv)
            clears = (abs(lin) > nz) if (lin is not None and nz is not None) else None
            pds = CY.cyclicality_pd(rt, mv, firms)
            down = half_slope(rt, mv, firms, lo_side=False)
            up = half_slope(rt, mv, firms, lo_side=True)
            rowsout.append((m, v, lin, pb, exp, nz, clears, pds, down, up))
            P(f"{m:18s} {v:7s} {_f(lin):>7} {_f(pb):>7} {_f(exp):>8} {_f(nz):>7} "
              f"{str(clears):>5} {_f(pds):>10} {_f(down):>6} {_f(up):>6}")

    # ---- 1. PD-divergence TTC diagnostic ----
    P("\n## TTC diagnostic — genuine rating philosophy vs generic anchoring")
    P("   (rating slope should COLLAPSE under ttc; if PD slope is RETAINED, the model")
    P("    holds the TTC rating flat while its PIT default view still moves = genuine)")
    P(f"{'model':18s} {'rat_terse':>9} {'rat_ttc':>8} {'pd_terse':>9} {'pd_ttc':>8} "
      f"{'pd_retain':>9} {'verdict':>12}")
    for m in models:
        f_t = rt.firm_support((m, "v_terse"), "macro")
        f_c = rt.firm_support((m, "v_ttc"), "macro")
        rt_t = CY.cyclicality_notch(rt, (m, "v_terse"), f_t)
        rt_c = CY.cyclicality_notch(rt, (m, "v_ttc"), f_c)
        pd_t = CY.cyclicality_pd(rt, (m, "v_terse"), f_t)
        pd_c = CY.cyclicality_pd(rt, (m, "v_ttc"), f_c)
        retain = (pd_c / pd_t) if (pd_t not in (None, 0) and pd_c is not None) else None
        # classify
        if rt_c is None:
            verd = "n/a"
        elif abs(rt_c) < 0.20 and retain is not None and retain > 0.6:
            verd = "GENUINE-TTC"
        elif abs(rt_c) < 0.20 and retain is not None and retain < 0.4:
            verd = "ANCHORING"
        elif abs(rt_c) >= 0.20:
            verd = "weak-effect"
        else:
            verd = "mixed"
        P(f"{m:18s} {_f(rt_t):>9} {_f(rt_c):>8} {_f(pd_t):>9} {_f(pd_c):>8} "
          f"{_f(retain):>9} {verd:>12}")

    # ---- 3. residual-TTC reframing (range across estimators) ----
    P("\n## Residual procyclicality that SURVIVES the ttc instruction")
    P(f"{'model':18s} {'ttc_lin':>8} {'ttc_probit':>10} {'range':>14} {'boom->rec swing':>16}")
    for m in models:
        mv = (m, "v_ttc"); firms = rt.firm_support(mv, "macro")
        lin = CY.cyclicality_notch(rt, mv, firms)
        pb = PB.ordered_probit(rt, mv, firms).get("notch_per_step")
        vals = [x for x in (lin, pb) if x is not None]
        rng = f"[{min(vals):.2f}, {max(vals):.2f}]" if vals else "n/a"
        swing = CY.endpoint_swing(rt, mv, firms)
        P(f"{m:18s} {_f(lin):>8} {_f(pb):>10} {rng:>14} {_f(swing):>16}")

    # ---- obs: fingerprint stability (OpenAI) ----
    P("\n## Fingerprint-stability — severity coef WITH vs WITHOUT system_fingerprint FE")
    for m in models:
        if not m.startswith("openai"):
            continue
        r = fingerprint_fe_check(args.subgrid, m, "v_terse")
        if r:
            P(f"{m:18s} v_terse  firmFE={_f(r['coef_firm_fe'])}  "
              f"firm+fpFE={_f(r['coef_firm_plus_fp_fe'])}  "
              f"(n={r['n']}, {r['n_fingerprints']} fps)")
    P("")
    return 0


if __name__ == "__main__":
    sys.exit(main())

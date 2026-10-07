"""Joint specification for the placebo-adjusted net effect (referee 3 comment 3).

The manuscript reports the net effect by SUBTRACTING slopes (pooled macro minus pooled
placebo). The referee asks which construction is used; we say subtraction, and also claim
a joint specification agrees. This computes that joint specification so the claim is a
result rather than an assertion.

Specification, estimated WITHIN firm and then averaged over firms (the same clustering
unit as everything else):

    notch_ijk = a_i + d * sev_k + t * (sev_k * is_macro_k) + e

Every cell carries a severity in -2..+2, whether it sits on the macro axis or the matched
placebo axis. `d` is the sensitivity common to both axes -- the frame-compliance or
demand-effect floor -- and `t` is the ADDITIONAL sensitivity of the macro axis over the
placebo axis. That `t` is the net effect, obtained as a single coefficient instead of as a
difference of two separately estimated slopes.

Sign convention matches CY.cyclicality_notch: reported as DOWNGRADE notches per +1 step,
so the fitted coefficients are negated (a higher notch is a better rating).

  python analysis/joint_spec.py [--draws 2000]
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE)); sys.path.insert(0, str(_HERE.parent / "config"))
import ratings as RA      # noqa: E402
import cyclicality as CY  # noqa: E402
import stats as S         # noqa: E402

MODELS_FULL = ["openai_4o_mini", "openai_41_mini", "openai_4o",
               "gemini_flash_lite", "gemini_flash"]


def _ols3(rows):
    """Least squares for notch ~ 1 + sev + sev*is_macro on one firm's 10 cells.
    Returns (d, t) or None. Solved with explicit normal equations on a 3x3 system so the
    module needs no numpy."""
    n = len(rows)
    if n < 4:
        return None
    X = [(1.0, s, s * m) for s, m, _ in rows]
    y = [v for _, _, v in rows]
    A = [[sum(X[i][a] * X[i][b] for i in range(n)) for b in range(3)] for a in range(3)]
    B = [sum(X[i][a] * y[i] for i in range(n)) for a in range(3)]
    # Gauss-Jordan with partial pivoting
    M = [A[r][:] + [B[r]] for r in range(3)]
    for c in range(3):
        p = max(range(c, 3), key=lambda r: abs(M[r][c]))
        if abs(M[p][c]) < 1e-12:
            return None
        M[c], M[p] = M[p], M[c]
        pv = M[c][c]
        M[c] = [v / pv for v in M[c]]
        for r in range(3):
            if r != c and abs(M[r][c]) > 0:
                f = M[r][c]
                M[r] = [M[r][k] - f * M[c][k] for k in range(4)]
    return M[1][3], M[2][3]          # d, t


def firm_rows(rt, mv, firm):
    tab = rt.notch.get(mv, {}).get(firm, {})
    out = []
    for st, v in tab.items():
        if v is None or st not in rt.state_sev:
            continue
        kind = rt.state_kind.get(st)
        if kind not in ("macro", "placebo"):
            continue
        out.append((float(rt.state_sev[st]), 1.0 if kind == "macro" else 0.0, float(v)))
    return out


def pooled(rt, models, firms):
    """Mean over firms and models of the within-firm (d, t), sign-flipped to downgrades."""
    ds, ts = [], []
    for m in models:
        mv = (m, "v_terse")
        if mv not in rt.notch:
            continue
        for f in firms:
            r = _ols3(firm_rows(rt, mv, f))
            if r is None:
                continue
            ds.append(-r[0]); ts.append(-r[1])
    if not ts:
        return None, None
    return sum(ds) / len(ds), sum(ts) / len(ts)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--draws", type=int, default=2000)
    ap.add_argument("--out", default="results/joint_spec.json")
    a = ap.parse_args()
    rt = RA.load_rating_table(subgrid_filter="full")
    firms = sorted({f for m in MODELS_FULL
                    for f in rt.notch.get((m, "v_terse"), {})})
    print(f"[joint] models={len(MODELS_FULL)} firms={len(firms)}")

    d, t = pooled(rt, MODELS_FULL, firms)
    ci = S.cluster_bootstrap(rt, firms,
                             lambda x: pooled(rt, MODELS_FULL, x)[1],
                             draws=a.draws, seed=4242)

    # the subtraction construction the manuscript reports, recomputed here
    CY.clear_cache()
    macro, plac = [], []
    for m in MODELS_FULL:
        mv = (m, "v_terse")
        fs = rt.firm_support(mv, "macro", "notch")
        macro.append(CY.cyclicality_notch(rt, mv, fs))
        plac.append(CY.placebo_cyclicality(rt, mv, fs))
    pm = sum(macro) / len(macro); pp = sum(plac) / len(plac)
    sub = pm - pp

    print(f"[joint] SUBTRACTION : pooled macro {pm:.3f} - pooled placebo {pp:.3f} = {sub:.3f}")
    print(f"[joint] JOINT SPEC  : common-axis d = {d:.3f}, macro EXCESS t = {t:.3f} "
          f"CI[{ci['ci_low']:.3f},{ci['ci_high']:.3f}]")
    agree = abs(sub - t) <= 0.02
    print(f"[joint] agreement within 0.02 notches/step? {agree}  (difference {abs(sub-t):.4f})")
    blob = {"subtraction": {"pooled_macro": pm, "pooled_placebo": pp, "net": sub},
            "joint": {"common_axis_slope": d, "macro_excess_net": t,
                      "ci95": [ci["ci_low"], ci["ci_high"]]},
            "agree_within_0.02": agree, "difference": abs(sub - t),
            "n_firms": len(firms), "models": MODELS_FULL}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(blob, indent=2, sort_keys=True))
    print(f"[joint] -> {a.out}")
    return 0 if agree else 1


if __name__ == "__main__":
    raise SystemExit(main())

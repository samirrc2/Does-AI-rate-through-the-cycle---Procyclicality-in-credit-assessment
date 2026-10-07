"""OFAT macro-factor decomposition (referee 1 comment 3). Offline, $0, frozen data only.

Which macro signal drives the rating change? The joint states move all five indicators
together, so this arm moves ONE at a time across the identical -2..+2 severity range with
the other four held NEUTRAL. Each factor's slope is therefore directly comparable to the
joint slope from the main design, and to the other factors.

The per-firm estimator is CY._within_firm_slope, the SAME one the joint coefficient uses,
so a factor slope and the joint slope are not two different statistics. The five states of
a factor plus the shared `ofat_neutral` cell give the severity-0 point.

  python analysis/analyze_ofat.py [--draws 2000] [--out results/ofat.json]
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE)); sys.path.insert(0, str(_HERE.parent / "config"))
import ratings as RA            # noqa: E402
import cyclicality as CY        # noqa: E402
import stats as S               # noqa: E402

FACTORS = ["gdp", "unemp", "spread", "deflt", "standards"]
LABEL = {"gdp": "GDP growth", "unemp": "unemployment", "spread": "credit spread",
         "deflt": "default rate", "standards": "lending standards"}
MODELS = ["openai_4o_mini", "openai_4o", "gemini_flash", "openai_astra"]
# the joint (all-five-together) terse coefficient, recomputed here rather than quoted, so
# the comparison cannot drift from the frozen data
JOINT_SUBGRID = {"openai_4o_mini": "full", "openai_4o": "full",
                 "gemini_flash": "full", "openai_astra": "frontier"}


def factor_states(rt, factor):
    """(state, severity) for one factor: its four off-neutral cells plus the shared
    all-neutral cell, ordered by severity."""
    want = {f"ofat_{factor}_n2": -2, f"ofat_{factor}_n1": -1,
            "ofat_neutral": 0, f"ofat_{factor}_p1": 1, f"ofat_{factor}_p2": 2}
    return [(s, v) for s, v in sorted(want.items(), key=lambda kv: kv[1])
            if s in rt.state_sev]


def firm_slope(rt, mv, firm, states):
    tab = rt.notch.get(mv, {}).get(firm, {})
    sev, val = [], []
    for s, v in states:
        if s in tab and tab[s] is not None:
            sev.append(float(v)); val.append(float(tab[s]))
    if len(sev) < 3:
        return None
    return CY._within_firm_slope(sev, val)


def factor_slope(rt, mv, firms, states):
    """Mean within-firm DOWNGRADE-notches per +1 severity step, sign-matched to
    CY.cyclicality_notch, which returns -(mean raw slope) because a higher notch is a
    BETTER rating. Without the negation these slopes would carry the opposite sign from
    the joint coefficient they exist to be compared against."""
    vals = [v for f in firms if (v := firm_slope(rt, mv, f, states)) is not None]
    return -(sum(vals) / len(vals)) if vals else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--draws", type=int, default=2000)
    ap.add_argument("--out", default="results/ofat.json")
    a = ap.parse_args()
    rt = RA.load_rating_table(subgrid_filter="ofat")
    rtf = RA.load_rating_table(subgrid_filter="full")
    rtr = RA.load_rating_table(subgrid_filter="frontier")

    out = {"draws": a.draws, "models": {}}
    print(f"[ofat] states present: {sum(1 for s in rt.state_sev if s.startswith('ofat'))}")
    for m in MODELS:
        mv = (m, "v_terse")
        if mv not in rt.notch:
            print(f"[ofat] {m}: absent"); continue
        firms = sorted(rt.notch[mv])
        # joint slope from the main design, same estimator, for the comparison row
        jrt = rtf if JOINT_SUBGRID[m] == "full" else rtr
        CY.clear_cache()
        jf = jrt.firm_support((m, "v_terse"), "macro", "notch")
        joint = CY.cyclicality_notch(jrt, (m, "v_terse"), jf)
        rec = {"n_firms": len(firms), "joint_slope_all_five": joint, "factors": {}}
        tot = 0.0
        for fac in FACTORS:
            states = factor_states(rt, fac)
            if len(states) < 3:
                continue
            pt = factor_slope(rt, mv, firms, states)
            ci = S.cluster_bootstrap(rt, firms,
                                     lambda x, st=states: factor_slope(rt, mv, x, st),
                                     draws=a.draws, seed=4242)
            rec["factors"][fac] = {"slope": pt, "ci95": [ci["ci_low"], ci["ci_high"]],
                                   "n_states": len(states),
                                   "excludes_zero": ci["ci_low"] is not None and
                                                    (ci["ci_low"] > 0 or ci["ci_high"] < 0)}
            if pt: tot += pt
        rec["sum_of_factor_slopes"] = tot
        # additivity: do the five one-at-a-time slopes add up to the joint slope? A sum
        # BELOW the joint slope means the indicators reinforce one another when moved
        # together; above means they substitute.
        rec["additivity_ratio_sum_over_joint"] = (tot / joint) if joint else None
        out["models"][m] = rec
        print(f"[ofat] {m:16} joint={joint:.3f}  sum-of-factors={tot:.3f}  "
              f"ratio={rec['additivity_ratio_sum_over_joint']:.2f}  n={len(firms)}")
        for fac in FACTORS:
            d = rec["factors"].get(fac)
            if d:
                print(f"         {LABEL[fac]:20}{d['slope']:+.3f} "
                      f"[{d['ci95'][0]:+.3f},{d['ci95'][1]:+.3f}]  "
                      f"{'sig' if d['excludes_zero'] else '  -'}")
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=2, sort_keys=True))
    print(f"[ofat] -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

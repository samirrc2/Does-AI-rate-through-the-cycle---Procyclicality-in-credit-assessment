"""Round-1 reviewer-revision analyses. Offline, $0, FROZEN data only.

Each block below answers one numbered referee comment and prints its own coverage
count, so a silently-empty analysis cannot masquerade as a pass.

  R3#2  formal pairwise tests for model and framing differences (overlapping
        marginal CIs establish nothing either way, so every contrast is bootstrapped
        as a PAIRED difference on the SAME resampled firms)
  R3#4  per-model DOWNSIDE/UPSIDE half-slope CIs -- Figure 2 currently plots bare bars
  R1#6  capital-mapping sensitivity: LGD x maturity x alternative notch->PD map,
        plus the verbalised-PD anchoring already implemented as source='pd'
  R1#5  calibration diagnostics on the verbalised PDs, and point-in-time sensitivity
        measures that do NOT depend on them

Usage:  python analysis/reviewer_revision.py [--draws 2000] [--out results/reviewer_revision.json]

The 7-model set spans two frozen subgrids -- the 5 incumbents in `full`, the 2 frontier
models in `frontier` -- over the SAME 80-firm battery, so firm ids are shared and a
paired resample is well defined across them.
"""
from __future__ import annotations
import argparse, json, sys
from itertools import combinations
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent / "config"))

import ratings as RA          # noqa: E402
import cyclicality as CY      # noqa: E402
import stats as S             # noqa: E402
import capital as CAP         # noqa: E402

INCUMBENTS = ["openai_4o_mini", "openai_41_mini", "openai_4o",
              "gemini_flash_lite", "gemini_flash"]
FRONTIER = ["gemini_pro", "openai_astra"]
FRAMINGS = ["v_pit", "v_terse", "v_stable", "v_ttc"]
# gpt-6-astra REFUSES temperature=0 (measured); every other arm ran at t=0. Recorded so
# no contrast involving it is read as temperature-matched.
TEMP = {m: 0.0 for m in INCUMBENTS + ["gemini_pro"]}
TEMP["openai_astra"] = 1.0


def load():
    """Frozen tables for both subgrids, plus the model -> table routing."""
    rti = RA.load_rating_table(subgrid_filter="full")
    rtf = RA.load_rating_table(subgrid_filter="frontier")
    route = {m: rti for m in INCUMBENTS}
    route.update({m: rtf for m in FRONTIER})
    return rti, rtf, route


def _support(rt, m, v):
    return set(rt.firm_support((m, v), "macro", "notch"))


def common_firms(route, pairs):
    """Firms estimable in EVERY (model, framing) cell involved in a contrast."""
    sets = [_support(route[m], m, v) for m, v in pairs]
    return sorted(set.intersection(*sets)) if sets else []


# ── R3#2a  pairwise MODEL contrasts on the terse coefficient ────────────────
def model_contrasts(route, strat_rt, draws):
    out = []
    models = INCUMBENTS + FRONTIER
    for a, b in combinations(models, 2):
        fs = common_firms(route, [(a, "v_terse"), (b, "v_terse")])
        if len(fs) < 20:
            continue
        ra, rb = route[a], route[b]
        def stat(x, ra=ra, rb=rb, a=a, b=b):
            va = CY.cyclicality_notch(ra, (a, "v_terse"), x)
            vb = CY.cyclicality_notch(rb, (b, "v_terse"), x)
            return None if (va is None or vb is None) else va - vb
        ci = S.cluster_bootstrap(strat_rt, fs, stat, draws=draws, seed=4242)
        d = ci["point"]
        sig = (ci["ci_low"] is not None and (ci["ci_low"] > 0 or ci["ci_high"] < 0))
        out.append({"a": a, "b": b, "n_firms": len(fs), "diff": d,
                    "ci95": [ci["ci_low"], ci["ci_high"]], "excludes_zero": sig,
                    "temperature_matched": TEMP[a] == TEMP[b]})
    return out


# ── R3#2b  pairwise FRAMING contrasts within each model ────────────────────
def framing_contrasts(route, strat_rt, draws):
    out = []
    for m in INCUMBENTS + FRONTIER:
        rt = route[m]
        for va, vb in combinations(FRAMINGS, 2):
            fs = common_firms(route, [(m, va), (m, vb)])
            if len(fs) < 20:
                continue
            def stat(x, rt=rt, m=m, va=va, vb=vb):
                p = CY.cyclicality_notch(rt, (m, va), x)
                q = CY.cyclicality_notch(rt, (m, vb), x)
                return None if (p is None or q is None) else p - q
            ci = S.cluster_bootstrap(strat_rt, fs, stat, draws=draws, seed=4242)
            sig = (ci["ci_low"] is not None and (ci["ci_low"] > 0 or ci["ci_high"] < 0))
            out.append({"model": m, "a": va, "b": vb, "n_firms": len(fs),
                        "diff": ci["point"], "ci95": [ci["ci_low"], ci["ci_high"]],
                        "excludes_zero": sig})
    return out


# ── R3#4  per-model half-slope CIs (Figure 2 needs error bars) ─────────────
def half_slope_cis(route, strat_rt, draws):
    out = {}
    for m in INCUMBENTS + FRONTIER:
        rt = route[m]
        fs = sorted(_support(rt, m, "v_terse"))
        if len(fs) < 20:
            continue
        rec = {"n_firms": len(fs), "temperature": TEMP[m]}
        for side in ("down", "up"):
            ci = S.cluster_bootstrap(strat_rt, fs,
                                     lambda x, rt=rt, m=m, side=side:
                                         CY.half_slope(rt, (m, "v_terse"), x, side),
                                     draws=draws, seed=4242)
            rec[side] = {"point": ci["point"], "ci95": [ci["ci_low"], ci["ci_high"]]}
        # the ratio is bootstrapped as a UNIT -- its denominator is small, so two
        # marginal CIs eyeballed together would misstate its uncertainty badly
        cir = S.cluster_bootstrap(strat_rt, fs,
                                  lambda x, rt=rt, m=m: (
                                      (lambda d, u: (d / u) if (u not in (None, 0) and d is not None) else None)(
                                          CY.half_slope(rt, (m, "v_terse"), x, "down"),
                                          CY.half_slope(rt, (m, "v_terse"), x, "up"))),
                                  draws=draws, seed=4242)
        rec["ratio_down_over_up"] = {"point": cir["point"],
                                     "ci95": [cir["ci_low"], cir["ci_high"]]}
        out[m] = rec
    return out


# ── R1#6  capital-mapping sensitivity ──────────────────────────────────────
def _alt_map(kind, base):
    """Alternative notch->PD maps. 'half' halves every PD, 'double' doubles it (both
    clipped to <1), 'shift_down' moves the whole ladder one notch. A result that
    survives these is not an artefact of the particular stylised map.

    `base` is passed in explicitly: deriving it from CAP.NOTCH_PD is a trap, because
    the caller clears that dict before installing the new map, and Python evaluates
    the clear() before the _alt_map() argument -- so the map was built from an empty
    dict and every notch lookup after the first cell raised KeyError.
    """
    base = dict(base)
    if kind == "baseline":
        return base
    if kind == "half":
        return {k: min(0.99, v * 0.5) for k, v in base.items()}
    if kind == "double":
        return {k: min(0.99, v * 2.0) for k, v in base.items()}
    if kind == "shift_down":
        return {k: base.get(min(21, k + 1), base[21]) for k in base}
    raise ValueError(kind)


def capital_sensitivity(route, draws):
    rows = []
    orig_map = dict(CAP.NOTCH_PD)
    orig_irb = CAP.irb_capital
    for m in INCUMBENTS + FRONTIER:
        rt = route[m]
        fs = sorted(_support(rt, m, "v_terse"))
        if len(fs) < 20:
            continue
        for mp in ("baseline", "half", "double", "shift_down"):
            for lgd in (0.30, 0.45, 0.60):
                for M in (1.0, 2.5, 5.0):
                    _new = _alt_map(mp, orig_map)
                    CAP.NOTCH_PD.clear(); CAP.NOTCH_PD.update(_new)
                    CAP.irb_capital = (lambda pd, lgd=lgd, M=M, _f=orig_irb:
                                       _f(pd, lgd=lgd, M=M))
                    try:
                        sw = CAP.mean_capital_swing(rt, (m, "v_terse"), fs, source="rating")
                    finally:
                        CAP.irb_capital = orig_irb
                    rows.append({"model": m, "map": mp, "lgd": lgd, "M": M,
                                 "mean_capital_swing_pp": sw})
        # verbalised-PD anchoring, already implemented upstream as source='pd'
        CAP.NOTCH_PD.clear(); CAP.NOTCH_PD.update(orig_map)
        rows.append({"model": m, "map": "baseline", "lgd": 0.45, "M": 2.5,
                     "source": "pd",
                     "mean_capital_swing_pp":
                         CAP.mean_capital_swing(rt, (m, "v_terse"), fs, source="pd")})
    CAP.NOTCH_PD.clear(); CAP.NOTCH_PD.update(orig_map)
    CAP.irb_capital = orig_irb
    return rows


# ── R1#5  PD calibration + PD-free point-in-time sensitivity ───────────────
def pd_diagnostics(route, strat_rt, draws):
    out = {}
    for m in INCUMBENTS + FRONTIER:
        rt = route[m]
        for v in FRAMINGS:
            fs = sorted(_support(rt, m, v))
            if len(fs) < 20:
                continue
            ci = S.cluster_bootstrap(strat_rt, fs,
                                     lambda x, rt=rt, m=m, v=v: CY.cyclicality_pd(rt, (m, v), x),
                                     draws=draws, seed=4242)
            entry = {"pd_logodds_slope": ci["point"],
                     "ci95": [ci["ci_low"], ci["ci_high"]], "n_firms": len(fs)}
            # PD-FREE point-in-time measure: the log-probability expected-notch slope,
            # which does not depend on the verbalised PD at all (referee 1 comment 5).
            # The table is `expnotch` and it has its OWN firm support -- it exists only
            # where the provider returns rating-token logprobs: the three older OpenAI
            # arms. Gemini never exposes logprobs, and gpt-6-astra REFUSES the parameter
            # (measured). Reported where it exists, explicitly null elsewhere, with the
            # covered firm count, so absence is visible rather than silent.
            ef = sorted(set(rt.firm_support((m, v), "macro", table="expnotch")))
            if len(ef) >= 20:
                entry["expected_notch_slope"] = CY.cyclicality_notch(
                    rt, (m, v), ef, "macro", "expnotch")
                entry["expected_notch_n_firms"] = len(ef)
            else:
                entry["expected_notch_slope"] = None
                entry["expected_notch_n_firms"] = len(ef)
            out.setdefault(m, {})[v] = entry
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--draws", type=int, default=2000)
    ap.add_argument("--out", default="results/reviewer_revision.json")
    a = ap.parse_args()
    rti, rtf, route = load()
    strat = rti      # tier metadata is identical across subgrids (same battery)

    print(f"[rev] models={len(INCUMBENTS+FRONTIER)} framings={len(FRAMINGS)} draws={a.draws}")
    CY.clear_cache()
    mc = model_contrasts(route, strat, a.draws)
    print(f"[rev] R3#2a model pairs tested   : {len(mc)}")
    fc = framing_contrasts(route, strat, a.draws)
    print(f"[rev] R3#2b framing pairs tested : {len(fc)}")
    hs = half_slope_cis(route, strat, a.draws)
    print(f"[rev] R3#4  half-slope CIs       : {len(hs)} models")
    cs = capital_sensitivity(route, a.draws)
    print(f"[rev] R1#6  capital cells        : {len(cs)}")
    pdd = pd_diagnostics(route, strat, a.draws)
    print(f"[rev] R1#5  PD diagnostic cells  : {sum(len(v) for v in pdd.values())}")

    blob = {"draws": a.draws, "temperature_by_model": TEMP,
            "model_contrasts_terse": mc, "framing_contrasts": fc,
            "half_slopes": hs, "capital_sensitivity": cs, "pd_diagnostics": pdd}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(blob, indent=2, sort_keys=True))
    print(f"[rev] -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

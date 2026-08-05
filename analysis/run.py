"""SINGLE analysis entrypoint — pure, deterministic, $0. Reads frozen capture CSVs
and emits claims.json: every number the paper will cite, each with its CI and the
config/firms hash that produced it. Also computes the three pilot-gate booleans.

  python analysis/run.py --subgrid pilot [--draws 2000] [--seed 4242] [--allow-unfrozen]
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "config"))

import ratings as RA        # noqa: E402
import cyclicality as CY    # noqa: E402
import probit as PB         # noqa: E402
import stats as S           # noqa: E402
import loader as C          # noqa: E402

_HERE = Path(__file__).resolve().parent
_MANI = _HERE.parent / "manifest"
_OUT = _HERE.parent / "claims.json"

# pilot-gate thresholds (see PREREGISTRATION §5)
PARSE_MIN = 0.90
NOTCH_BAND = (4.0, 18.0)     # interior mean so both up/down moves are possible
DISTINCT_MIN = 6
SD_MIN = 1.5


def _read_ledger(subgrid: str) -> dict:
    # sum any per-track ledgers (parallel provider streams) for the true spend
    total = 0.0; mode = None; per_model = {}
    for p in sorted(_MANI.glob(f"ledger_{subgrid}_*.json")):
        try:
            d = json.loads(p.read_text())
        except (ValueError, OSError):
            continue
        total += float(d.get("cum_usd", 0.0))
        for k, v in d.get("per_model", {}).items():
            per_model[k] = v
        mode = "REAL" if "REAL" in p.name else (mode or "MOCK")
    return {"mode": mode, "cum_usd": total, "per_model": per_model}


def _firms_hash() -> dict:
    p = _MANI / "firms_manifest.json"
    if p.exists():
        d = json.loads(p.read_text())
        return {k: d[k]["sha256"] for k in ("pilot", "full") if k in d}
    return {}


def analyse(subgrid: str, draws: int, seed: int, allow_unfrozen: bool) -> dict:
    cfg = C.load_all()
    sg = C.subgrid(cfg, subgrid)
    allowed = set(sg.models)
    rt = RA.load_rating_table(subgrid_filter=subgrid, allow_unfrozen=allow_unfrozen,
                              allowed_models=allowed)
    CY.clear_cache()   # fresh per-firm slope cache for this RatingTable
    ledger = _read_ledger(subgrid)
    disp = RA.dispersion(rt)

    has_placebo = bool(rt.placebo_order())
    has_expnotch = rt.n_expnotch > 0

    # ── per (model, variant) cyclicality block ──────────────────────────────
    per_mv = {}
    for m in rt.models:
        for v in sorted(sg.variants):
            mv = (m, v)
            if mv not in rt.notch:
                continue
            firms = rt.firm_support(mv, "macro")
            cyc_ci = S.cluster_bootstrap(rt, firms, lambda fs: CY.cyclicality_notch(rt, mv, fs),
                                         draws=draws, seed=seed)
            swing_ci = S.cluster_bootstrap(rt, firms, lambda fs: CY.endpoint_swing(rt, mv, fs),
                                           draws=draws, seed=seed)
            block = {
                "model": m, "variant": v, "family": rt.family[m], "n_firms": len(firms),
                "cyclicality_notch_per_step": CY.cyclicality_notch(rt, mv, firms),
                "cyclicality_ci95": [cyc_ci["ci_low"], cyc_ci["ci_high"]],
                "ci_excludes_0": S.ci_excludes(cyc_ci, 0.0, "either"),
                "endpoint_swing_notches": CY.endpoint_swing(rt, mv, firms),
                "endpoint_swing_ci95": [swing_ci["ci_low"], swing_ci["ci_high"]],
                "cyclicality_pd_logodds_per_step": CY.cyclicality_pd(rt, mv, firms),
                "monotonic_dose_response": CY.monotonic(rt, mv, firms),
                "churn": CY.churn(rt, mv, firms),
                "state_means": CY.state_means(rt, mv, firms),
                "ordered_probit": PB.ordered_probit(rt, mv, firms),
                "noise_floor_notch_sd": rt.noise_sd.get(mv),
            }
            if has_placebo:
                net_ci = S.cluster_bootstrap(rt, firms, lambda fs: CY.net_cyclicality(rt, mv, fs),
                                             draws=draws, seed=seed)
                block["placebo_cyclicality_notch_per_step"] = CY.placebo_cyclicality(rt, mv, firms)
                block["net_cyclicality_notch_per_step"] = CY.net_cyclicality(rt, mv, firms)
                block["net_cyclicality_ci95"] = [net_ci["ci_low"], net_ci["ci_high"]]
                block["net_ci_excludes_0"] = S.ci_excludes(net_ci, 0.0, "either")
            if has_expnotch:
                ef = rt.firm_support(mv, "macro", table="expnotch")
                block["expected_notch_cyclicality_per_step"] = CY.cyclicality_notch(
                    rt, mv, ef, "macro", "expnotch")
                block["expected_notch_n_firms"] = len(ef)
            # asymmetry (downside vs upside half-slopes) — deterministic point estimates
            ds = CY.half_slope(rt, mv, firms, side="down")
            us = CY.half_slope(rt, mv, firms, side="up")
            block["downside_slope"] = ds
            block["upside_slope"] = us
            block["asymmetry_ratio"] = (ds / us) if (ds is not None and us not in (None, 0)) else None
            # PD-retention vs this model's terse PD slope (anchoring diagnostic)
            terse_pd = CY.cyclicality_pd(rt, (m, "v_terse"),
                                         rt.firm_support((m, "v_terse"), "macro"))
            this_pd = block["cyclicality_pd_logodds_per_step"]
            block["pd_retention_vs_terse"] = (
                (this_pd / terse_pd) if (terse_pd not in (None, 0) and this_pd is not None) else None)
            per_mv[f"{m}|{v}"] = block

    # ── pooled-across-models cyclicality per variant + TTC contrast ──────────
    per_variant = {}
    all_firms = sorted(rt.firms_meta)
    for v in sorted(sg.variants):
        vfirms = sorted({f for m in rt.models
                         for f in rt.firm_support((m, v), "macro")}) or all_firms
        pooled_ci = S.cluster_bootstrap(
            rt, vfirms, lambda fs: CY.pooled_across_models(rt, v, fs, CY.cyclicality_notch),
            draws=draws, seed=seed)
        entry = {
            "pooled_cyclicality_notch_per_step":
                CY.pooled_across_models(rt, v, vfirms, CY.cyclicality_notch),
            "pooled_cyclicality_ci95": [pooled_ci["ci_low"], pooled_ci["ci_high"]],
            "ci_excludes_0": S.ci_excludes(pooled_ci, 0.0, "either"),
            "pooled_endpoint_swing":
                CY.pooled_across_models(rt, v, vfirms, CY.endpoint_swing),
        }
        if has_placebo:
            net_ci = S.cluster_bootstrap(
                rt, vfirms, lambda fs: CY.pooled_across_models(rt, v, fs, CY.net_cyclicality),
                draws=draws, seed=seed)
            entry["pooled_placebo_cyclicality"] = CY.pooled_across_models(
                rt, v, vfirms, CY.placebo_cyclicality)
            entry["pooled_net_cyclicality"] = CY.pooled_across_models(
                rt, v, vfirms, CY.net_cyclicality)
            entry["pooled_net_ci95"] = [net_ci["ci_low"], net_ci["ci_high"]]
            entry["net_ci_excludes_0"] = S.ci_excludes(net_ci, 0.0, "either")
        per_variant[v] = entry

    # instruction-effect contrasts (does an explicit TTC instruction dampen it?)
    def _pv(v):
        return per_variant.get(v, {}).get("pooled_cyclicality_notch_per_step")
    contrasts = {}
    if "v_terse" in per_variant and "v_ttc" in per_variant:
        a, b = _pv("v_terse"), _pv("v_ttc")
        contrasts["terse_minus_ttc"] = (a - b) if (a is not None and b is not None) else None
    if "v_pit" in per_variant and "v_ttc" in per_variant:
        a, b = _pv("v_pit"), _pv("v_ttc")
        contrasts["pit_minus_ttc"] = (a - b) if (a is not None and b is not None) else None
    if "v_terse" in per_variant and "v_stable" in per_variant:
        a, b = _pv("v_terse"), _pv("v_stable")
        contrasts["terse_minus_stable"] = (a - b) if (a is not None and b is not None) else None
    if "v_stable" in per_variant and "v_ttc" in per_variant:
        a, b = _pv("v_stable"), _pv("v_ttc")
        contrasts["stable_minus_ttc"] = (a - b) if (a is not None and b is not None) else None

    # ── pooled asymmetry (v_terse across models) with bootstrap CIs ───────────
    tfirms = sorted({f for m in rt.models for f in rt.firm_support((m, "v_terse"), "macro")}) \
        or all_firms
    _down = lambda rt_, mv_, ff: CY.half_slope(rt_, mv_, ff, side="down")   # noqa: E731
    _up = lambda rt_, mv_, ff: CY.half_slope(rt_, mv_, ff, side="up")       # noqa: E731
    down_ci = S.cluster_bootstrap(
        rt, tfirms, lambda fs: CY.pooled_across_models(rt, "v_terse", fs, _down),
        draws=draws, seed=seed)
    up_ci = S.cluster_bootstrap(
        rt, tfirms, lambda fs: CY.pooled_across_models(rt, "v_terse", fs, _up),
        draws=draws, seed=seed)
    d0 = CY.pooled_across_models(rt, "v_terse", tfirms, _down)
    u0 = CY.pooled_across_models(rt, "v_terse", tfirms, _up)
    asymmetry = {
        "variant": "v_terse",
        "pooled_downside_slope": d0, "pooled_downside_ci95": [down_ci["ci_low"], down_ci["ci_high"]],
        "pooled_upside_slope": u0, "pooled_upside_ci95": [up_ci["ci_low"], up_ci["ci_high"]],
        "ratio": (d0 / u0) if (d0 is not None and u0 not in (None, 0)) else None,
        "note": "downside = neutral->severe recession; upside = boom->neutral (notches/step)",
    }

    # ── headline: the primary arm (v_terse pooled) for the gate ─────────────
    primary_variant = "v_terse" if "v_terse" in per_variant else sorted(per_variant)[0]
    primary = per_variant.get(primary_variant, {})
    primary_ci = primary.get("pooled_cyclicality_ci95", [None, None])

    # ── pilot gate ───────────────────────────────────────────────────────────
    err = RA.error_rate(rt)
    cap = float(getattr(cfg.grid.budgets, subgrid, cfg.grid.budgets.pilot))
    ran_clean = (err <= 0.02) and (ledger["cum_usd"] <= cap)
    ratings_ok = (disp["parse_rate"] is not None and disp["parse_rate"] >= PARSE_MIN
                  and disp["mean_notch"] is not None
                  and NOTCH_BAND[0] <= disp["mean_notch"] <= NOTCH_BAND[1]
                  and disp["distinct_notches"] >= DISTINCT_MIN
                  and disp["sd_notch"] is not None and disp["sd_notch"] >= SD_MIN)
    coef = primary.get("pooled_cyclicality_notch_per_step")
    estimable = (coef is not None and primary_ci[0] is not None and primary_ci[1] is not None)
    probit_estimable = any(
        v.get("ordered_probit", {}).get("severity_coef") is not None
        for v in per_mv.values())

    claims = {
        "meta": {
            "subgrid": subgrid, "mode": rt.mode, "config_hash": cfg.config_hash(),
            "firms_sha256": _firms_hash(), "analysis_seed": seed, "bootstrap_draws": draws,
            "models": rt.models, "families": {m: rt.family[m] for m in rt.models},
            "prompt_variants": sorted(sg.variants),
            "macro_states": {s: rt.state_sev[s] for s in rt.macro_order()},
            "seed_indices": sorted(rt.seed_indices),
            "n_rows": rt.n_rows, "n_error": rt.n_error, "error_rate": round(err, 4),
            "n_firms": len(rt.firms_meta), "spend_usd": ledger["cum_usd"],
            "budget_cap_usd": cap, "primary_variant": primary_variant,
            "placebo_states": rt.placebo_order(), "has_placebo": has_placebo,
            "has_expected_notch": has_expnotch, "n_expected_notch": rt.n_expnotch,
            "system_fingerprints": RA.fingerprint_summary(rt),
        },
        "ratings_dispersion": disp,
        "headline_cyclicality": {
            "primary_variant": primary_variant,
            "pooled_notch_per_step": coef,
            "pooled_ci95": primary_ci,
            "ci_excludes_0": primary.get("ci_excludes_0"),
            "pooled_endpoint_swing": primary.get("pooled_endpoint_swing"),
            "pooled_placebo_cyclicality": primary.get("pooled_placebo_cyclicality"),
            "pooled_net_cyclicality": primary.get("pooled_net_cyclicality"),
            "pooled_net_ci95": primary.get("pooled_net_ci95"),
            "net_ci_excludes_0": primary.get("net_ci_excludes_0"),
            "interpretation": ("positive => procyclical (downgrades as macro worsens); "
                               "~0 with tight CI => through-the-cycle (TTC null holds). "
                               "NET = macro - placebo is the demand-effect-adjusted value."),
        },
        "per_variant_pooled": per_variant,
        "asymmetry": asymmetry,
        "instruction_effect_contrasts": contrasts,
        "per_model_variant": per_mv,
        "pilot_gate": {
            "criterion_1_ran_clean": ran_clean,
            "criterion_2_ratings_measurable": ratings_ok,
            "criterion_3_cyclicality_estimable": estimable and probit_estimable,
            "parse_rate": disp["parse_rate"], "mean_notch": disp["mean_notch"],
            "sd_notch": disp["sd_notch"], "distinct_notches": disp["distinct_notches"],
            "error_rate": round(err, 4), "spend_usd": ledger["cum_usd"],
            "primary_cyclicality": coef, "primary_ci95": primary_ci,
            "probit_estimable": probit_estimable,
        },
    }
    return claims


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--subgrid", default="pilot")
    ap.add_argument("--draws", type=int, default=None)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--allow-unfrozen", action="store_true")
    ap.add_argument("--out", default=str(_OUT))
    args = ap.parse_args()
    cfg = C.load_all()
    draws = args.draws if args.draws is not None else 2000
    seed = args.seed if args.seed is not None else int(cfg.grid.analysis_seed)
    claims = analyse(args.subgrid, draws, seed, args.allow_unfrozen)
    Path(args.out).write_text(json.dumps(claims, indent=2, sort_keys=True))
    g = claims["pilot_gate"]
    h = claims["headline_cyclicality"]

    def _f(x, nd=3):
        return f"{x:.{nd}f}" if isinstance(x, (int, float)) else "n/a"
    print(f"[analysis] mode={claims['meta']['mode']} models={len(claims['meta']['models'])} "
          f"firms={claims['meta']['n_firms']} err={claims['meta']['error_rate']}")
    print(f"[analysis] dispersion: mean notch={_f(g['mean_notch'],1)} sd={_f(g['sd_notch'],2)} "
          f"distinct={g['distinct_notches']} parse={_f(g['parse_rate'],3)}")
    print(f"[analysis] headline cyclicality ({h['primary_variant']}) = "
          f"{_f(h['pooled_notch_per_step'],3)} notch/step CI{h['pooled_ci95']} "
          f"(excludes 0: {h['ci_excludes_0']})")
    if claims['meta']['has_placebo']:
        print(f"[analysis] placebo={_f(h['pooled_placebo_cyclicality'],3)} -> NET "
              f"(demand-adjusted)={_f(h['pooled_net_cyclicality'],3)} "
              f"CI{h['pooled_net_ci95']} (excludes 0: {h['net_ci_excludes_0']})")
    if claims['meta']['has_expected_notch']:
        print(f"[analysis] expected-notch (logprobs) cyclicality available for "
              f"{claims['meta']['n_expected_notch']} OpenAI cells")
    print(f"[analysis] pilot gate: clean={g['criterion_1_ran_clean']} "
          f"ratings={g['criterion_2_ratings_measurable']} "
          f"estimable={g['criterion_3_cyclicality_estimable']} -> claims.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Build claims_revision.json: the frozen claims.json extended to all SEVEN models.

claims.json is the ORIGINAL confirmatory artifact for the five-model grid and is left
byte-identical -- its hash is cited in the reproducibility receipts. The revision adds two
frontier models whose arms live in the `frontier` subgrid, so the revised tables need a
claims file spanning both. Rather than mutate the frozen one, this merges:

    claims.json (5 models, `full` subgrid)  +  the frozen `frontier` arms (2 models)

into a new artifact with the SAME schema, so analysis/make_tables.py consumes it unchanged
via its existing --claims flag. Every frontier value is recomputed here from frozen
receipts with the same estimators claims.json used, not copied from a transcript.

  python analysis/make_revision_claims.py
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE)); sys.path.insert(0, str(_HERE.parent / "config"))
import ratings as RA      # noqa: E402
import cyclicality as CY  # noqa: E402
import stats as S         # noqa: E402
import probit as PB       # noqa: E402  Amato--Furfine ordered probit

FRONTIER = ["gemini_pro", "openai_astra"]
VARIANTS = ["v_terse", "v_ttc", "v_pit", "v_stable"]


def block(rt, m, v, draws, seed):
    mv = (m, v)
    CY.clear_cache()
    fs = rt.firm_support(mv, "macro", "notch")
    if len(fs) < 20:
        return None
    b = CY.cyclicality_notch(rt, mv, fs)
    ci = S.cluster_bootstrap(rt, fs, lambda x: CY.cyclicality_notch(rt, mv, x),
                             draws=draws, seed=seed)
    dn = CY.half_slope(rt, mv, fs, "down"); up = CY.half_slope(rt, mv, fs, "up")
    out = {"cyclicality_notch_per_step": b,
           "cyclicality_ci95": [ci["ci_low"], ci["ci_high"]],
           "endpoint_swing_notches": CY.endpoint_swing(rt, mv, fs),
           "downside_slope": dn, "upside_slope": up,
           "asymmetry_ratio": (dn / up) if up else None,
           "cyclicality_pd_logodds_per_step": CY.cyclicality_pd(rt, mv, fs),
           "placebo_cyclicality_notch_per_step": CY.placebo_cyclicality(rt, mv, fs),
           "net_cyclicality_notch_per_step": CY.net_cyclicality(rt, mv, fs),
           # Table 3's Noise SD column was blank for the frontier rows without this: the
           # RatingTable carries the within-cell dispersion, so there is no reason to leave
           # a computable cell empty and invite the reader to think it is zero.
           "noise_floor_notch_sd": rt.noise_sd.get(mv),
           "ordered_probit": PB.ordered_probit(rt, mv, fs),
           "n_firms": len(fs)}
    # PD retention is defined against this model's OWN terse arm, exactly as in run.py
    CY.clear_cache()
    tfs = rt.firm_support((m, "v_terse"), "macro", "notch")
    pt = CY.cyclicality_pd(rt, (m, "v_terse"), tfs)
    pv = out["cyclicality_pd_logodds_per_step"]
    out["pd_retention_vs_terse"] = (pv / pt) if (pt not in (None, 0) and pv is not None) else None
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--claims", default="claims.json")
    ap.add_argument("--out", default="claims_revision.json")
    ap.add_argument("--draws", type=int, default=2000)
    a = ap.parse_args()
    base = json.loads(Path(a.claims).read_text())
    seed = int(base.get("meta", {}).get("analysis_seed", 4242)) if isinstance(base.get("meta"), dict) else 4242
    rt = RA.load_rating_table(subgrid_filter="frontier")
    added = 0
    for m in FRONTIER:
        for v in VARIANTS:
            blk = block(rt, m, v, a.draws, seed)
            if blk is None:
                print(f"  [skip] {m}|{v} (insufficient firms)"); continue
            base["per_model_variant"][f"{m}|{v}"] = blk
            added += 1
            if v == "v_terse":
                print(f"  {m:14} beta={blk['cyclicality_notch_per_step']:.3f} "
                      f"CI[{blk['cyclicality_ci95'][0]:.3f},{blk['cyclicality_ci95'][1]:.3f}] "
                      f"swing={blk['endpoint_swing_notches']:.2f} "
                      f"D:U={blk['asymmetry_ratio']:.1f} "
                      f"PDret(ttc)={base['per_model_variant'][f'{m}|v_ttc']['pd_retention_vs_terse'] if f'{m}|v_ttc' in base['per_model_variant'] else float('nan'):.3f}")
    # per-model revision quantities, so make_tables can put them beside beta in Table 1
    for name, path, key in (("real", "results/real_arm.json", None),
                            ("epochs", "results/seeds_epochs.json", None)):
        f = Path(path)
        if not f.exists():
            print(f"  [skip] {path} absent"); continue
        d = json.loads(f.read_text())
        if name == "real":
            for m, r in d.get("replication", {}).items():
                blk = base["per_model_variant"].get(f"{m}|v_terse")
                if blk is not None:
                    blk["real_beta"] = r["real_beta"]
                    blk["real_net"] = r["real_net"]
        else:
            for m, r in d.get("models", {}).items():
                blk = base["per_model_variant"].get(f"{m}|v_terse")
                if blk is not None:
                    blk["beta_drift_epoch"] = r["beta_drift"]
                    blk["pct_cells_moved_epoch"] = r["across_epoch"]["pct_cells_moved"]
    base.setdefault("revision", {})
    base["revision"] = {"source": "claims.json + frozen `frontier` subgrid",
                        "frontier_models": FRONTIER, "blocks_added": added,
                        "note": "claims.json itself is unmodified; this is a derived superset."}
    Path(a.out).write_text(json.dumps(base, indent=2, sort_keys=True))
    print(f"[revclaims] {added} blocks added -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

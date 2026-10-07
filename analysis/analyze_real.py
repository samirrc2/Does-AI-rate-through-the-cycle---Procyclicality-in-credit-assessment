"""Real-fundamentals arm (referee 1 comments 1 and 2). Offline, $0, frozen data only.

Two questions, both answered with data rather than argument:

  (a) does the effect REPLICATE when the synthetic fundamentals are replaced by actual
      de-identified SEC XBRL filings?
  (b) the contamination test showed GPT-6 Astra can identify ~15-18% of the de-identified
      firms (against a 0/39 synthetic negative control), so does that recall BIAS THE
      ESTIMAND? Recognition can anchor the rating LEVEL, but the design identifies the
      within-firm SLOPE across macro states with fundamentals held byte-identical. This
      splits the battery by whether Astra named the firm and compares slopes.

Emits results/real_arm.json.
"""
from __future__ import annotations
import argparse, json, random, sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE)); sys.path.insert(0, str(_HERE.parent / "config"))
import ratings as RA      # noqa: E402
import cyclicality as CY  # noqa: E402
import stats as S         # noqa: E402

PAIRS = {"openai_4o_mini": "full", "openai_4o": "full",
         "gemini_flash": "full", "openai_astra": "frontier"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--draws", type=int, default=2000)
    ap.add_argument("--out", default="results/real_arm.json")
    a = ap.parse_args()
    rr = RA.load_rating_table(subgrid_filter="real", allow_unfrozen=True)
    _frozen = {json.loads(p.read_text())["csv"]
               for p in (_HERE.parent / "data" / "frozen").glob("*.freeze.json")}
    _unfrozen_used = [f"runs_real_{m}_v_terse.csv" for m in PAIRS
                      if f"runs_real_{m}_v_terse.csv" not in _frozen]
    if _unfrozen_used:
        raise SystemExit(f"[real] these arms are READ by this analysis but not frozen: "
                         f"{_unfrozen_used}. Freeze them or drop the model.")
    tabs = {"full": RA.load_rating_table(subgrid_filter="full"),
            "frontier": RA.load_rating_table(subgrid_filter="frontier")}
    out = {"replication": {}, "contamination_slope_test": {}}

    print(f"{'model':16}{'synthetic':>24}{'REAL':>24}{'diff':>8}")
    for m, sg in PAIRS.items():
        mv = (m, "v_terse")
        srt = tabs[sg]
        CY.clear_cache(); sf = srt.firm_support(mv, "macro", "notch")
        CY.clear_cache(); rf = rr.firm_support(mv, "macro", "notch")
        if len(sf) < 80 or len(rf) < 40:
            print(f"  {m:14} incomplete (syn {len(sf)}, real {len(rf)})"); continue
        CY.clear_cache(); sb = CY.cyclicality_notch(srt, mv, sf)
        sci = S.cluster_bootstrap(srt, sf,
                                  lambda x, srt=srt, mv=mv: CY.cyclicality_notch(srt, mv, x),
                                  draws=a.draws, seed=4242)
        CY.clear_cache(); rb = CY.cyclicality_notch(rr, mv, rf)
        rci = S.cluster_bootstrap(rr, rf,
                                  lambda x, mv=mv: CY.cyclicality_notch(rr, mv, x),
                                  draws=a.draws, seed=4242)
        CY.clear_cache()
        out["replication"][m] = {
            "synthetic_beta": sb, "synthetic_ci95": [sci["ci_low"], sci["ci_high"]],
            "real_beta": rb, "real_ci95": [rci["ci_low"], rci["ci_high"]],
            "real_placebo": CY.placebo_cyclicality(rr, mv, rf),
            "real_net": CY.net_cyclicality(rr, mv, rf),
            "real_excludes_zero": rci["ci_low"] is not None and rci["ci_low"] > 0,
            "n_firms_real": len(rf)}
        print(f"  {m:14}{sb:>8.3f} [{sci['ci_low']:.3f},{sci['ci_high']:.3f}]"
              f"{rb:>11.3f} [{rci['ci_low']:.3f},{rci['ci_high']:.3f}]{rb-sb:>8.3f}")

    # ── (b) does identification move the slope? ────────────────────────────
    cp = _HERE.parent / "results" / "contamination_openai_astra.json"
    if cp.exists():
        con = json.loads(cp.read_text())
        # Only the firms actually PUT TO the model can be classified. The sweep covers 40
        # of the 80-firm battery, so the untested 40 are neither identified nor
        # not-identified -- treating them as not-identified would silently inflate the
        # comparison group with firms that were never asked about.
        tested = {r["firm_id"] for r in con["real"]}
        ident = {r["firm_id"] for r in con["real"] if r.get("claimed_identification")}
        mv = ("openai_astra", "v_terse")
        CY.clear_cache(); allf = set(rr.firm_support(mv, "macro", "notch"))
        A = sorted(allf & ident)
        B = sorted((allf & tested) - ident)          # tested AND not identified
        rec = {"n_identified": len(A), "n_not_identified": len(B),
               "n_tested": len(allf & tested), "n_battery": len(allf),
               "n_untested_excluded": len(allf - tested)}
        for lbl, fs in (("identified", A), ("not_identified", B), ("all", sorted(allf))):
            if len(fs) < 3:
                continue
            CY.clear_cache(); b = CY.cyclicality_notch(rr, mv, fs)
            ci = S.cluster_bootstrap(rr, fs,
                                     lambda x, mv=mv: CY.cyclicality_notch(rr, mv, x),
                                     draws=a.draws, seed=4242)
            rec[lbl] = {"beta": b, "ci95": [ci["ci_low"], ci["ci_high"]], "n": len(fs)}
        if "identified" in rec and "not_identified" in rec:
            rec["difference"] = rec["identified"]["beta"] - rec["not_identified"]["beta"]
            # A CI on the DIFFERENCE, not two marginal CIs. Referee 3 is right that
            # overlapping marginal intervals establish nothing about a contrast: the
            # difference has its own sampling distribution, and comparing the gap to the
            # width of one group's interval -- which is what this code used to do -- is the
            # same error the paper is criticised for elsewhere. The two groups are disjoint
            # firm sets, so each bootstrap draw resamples firms with replacement INSIDE each
            # group independently and recomputes the difference.
            rngd = random.Random(4242)
            diffs = []
            for _ in range(a.draws):
                da = CY.cyclicality_notch(rr, mv, [rngd.choice(A) for _ in A])
                CY.clear_cache()
                db = CY.cyclicality_notch(rr, mv, [rngd.choice(B) for _ in B])
                CY.clear_cache()
                if da is not None and db is not None:
                    diffs.append(da - db)
            if diffs:
                diffs.sort()
                lo = diffs[int(0.025 * len(diffs))]
                hi = diffs[int(0.975 * len(diffs)) - 1]
                rec["difference_ci95"] = [lo, hi]
                rec["difference_excludes_0"] = not (lo <= 0 <= hi)
                rec["difference_draws"] = len(diffs)
        out["contamination_slope_test"] = rec
        print(f"\n  astra real: identified n={rec['n_identified']} beta="
              f"{rec.get('identified',{}).get('beta',float('nan')):.3f}  "
              f"not-identified n={rec['n_not_identified']} beta="
              f"{rec.get('not_identified',{}).get('beta',float('nan')):.3f}  "
              f"difference {rec.get('difference',float('nan')):+.3f}")
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=2, sort_keys=True))
    print(f"-> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

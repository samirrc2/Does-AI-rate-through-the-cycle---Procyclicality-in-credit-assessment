"""Computations the revision needs beyond claims_revision.json, for the letter and the archive.

Each block answers one reviewer-facing question and writes its numbers to
results/revision_extras.json so the response letter can be bound to them rather than quoting
figures that live only in prose.

  python3 analysis/revision_extras.py            # all blocks
  python3 analysis/revision_extras.py --only tost,holm

Blocks: frontier_gradient, stable_vs_ttc, stable_pd_retention, threshold_robustness, tost,
holm, per_model_placebo, flash_real_vs_synth, pd_calibration, ttc_rationales, basel_floor,
assessment_accounting, failed_calls.
"""
from __future__ import annotations
import argparse, collections, csv, glob, json, math, random, re, statistics, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(ROOT / "config"))
import ratings as RA      # noqa: E402
import cyclicality as CY  # noqa: E402
import stats as S         # noqa: E402
import capital as CAP     # noqa: E402

MODELS = ["openai_4o_mini", "openai_41_mini", "openai_4o", "gemini_flash",
          "gemini_flash_lite", "gemini_pro", "openai_astra"]
DISP = {"openai_4o_mini": "GPT-4o-mini", "openai_41_mini": "GPT-4.1-mini",
        "openai_4o": "GPT-4o", "gemini_flash": "Gemini Flash",
        "gemini_flash_lite": "Gemini Flash-Lite", "gemini_pro": "Gemini Pro",
        "openai_astra": "GPT-6 Astra"}
VARIANTS = ["v_pit", "v_terse", "v_stable", "v_ttc"]
DRAWS, SEED = 2000, 4242


def tables():
    return {"full": RA.load_rating_table(subgrid_filter="full"),
            "frontier": RA.load_rating_table(subgrid_filter="frontier")}


def table_for(tabs, m):
    for sg in ("full", "frontier"):
        if m in tabs[sg].models:
            return tabs[sg]
    return None


def ci(rt, firms, fn):
    d = S.cluster_bootstrap(rt, firms, fn, draws=DRAWS, seed=SEED)
    return {"point": d["point"], "ci95": [d["ci_low"], d["ci_high"]], "n_firms": d["n_firms"]}


# ── 4. frontier framing gradients ──────────────────────────────────────────────
def frontier_gradient(tabs):
    out = {}
    for m in ("gemini_pro", "openai_astra"):
        rt = table_for(tabs, m)
        out[m] = {}
        for v in VARIANTS:
            CY.clear_cache()
            fs = rt.firm_support((m, v), "macro", "notch")
            if len(fs) < 20:
                out[m][v] = None; continue
            out[m][v] = ci(rt, fs, lambda x, mv=(m, v): CY.cyclicality_notch(rt, mv, x))
    return {"quantity": "rating slope, notches of downgrade per +1 macro-severity step",
            "models": out}


# ── 5. "be stable" vs through-the-cycle contrast ───────────────────────────────
def stable_vs_ttc(tabs):
    out = {}
    for m in MODELS:
        rt = table_for(tabs, m)
        CY.clear_cache()
        a = set(rt.firm_support((m, "v_stable"), "macro", "notch"))
        b = set(rt.firm_support((m, "v_ttc"), "macro", "notch"))
        fs = sorted(a & b)
        if len(fs) < 20:
            out[m] = None; continue

        def diff(x, m=m):
            CY.clear_cache()
            s = CY.cyclicality_notch(rt, (m, "v_stable"), x)
            t = CY.cyclicality_notch(rt, (m, "v_ttc"), x)
            return None if (s is None or t is None) else s - t
        out[m] = ci(rt, fs, diff)
    return {"quantity": "RATING slope under 'be stable' minus the rating slope under the "
                        "explicit through-the-cycle instruction, in notches per severity step. "
                        "It is not a PD-retention contrast.",
            "models": out}


# ── 6. "be stable" PD retention ────────────────────────────────────────────────
def stable_pd_retention(tabs):
    out = {}
    for m in MODELS:
        rt = table_for(tabs, m)
        CY.clear_cache()
        a = set(rt.firm_support((m, "v_terse"), "macro"))
        b = set(rt.firm_support((m, "v_stable"), "macro"))
        fs = sorted(a & b)
        if len(fs) < 20:
            out[m] = None; continue

        def ratio(x, m=m):
            CY.clear_cache()
            t = CY.cyclicality_pd(rt, (m, "v_terse"), x)
            s = CY.cyclicality_pd(rt, (m, "v_stable"), x)
            return None if (t in (None, 0) or s is None) else s / t
        out[m] = ci(rt, fs, ratio)
    return {"quantity": "log-odds PD slope under 'be stable' divided by the same model's terse "
                        "slope, recomputed inside each bootstrap draw on the same firms",
            "models": out}


# ── 7. threshold robustness ────────────────────────────────────────────────────
def threshold_robustness(tabs, bands=(0.05, 0.10), retentions=(0.75, 0.50),
                         arm="v_ttc"):
    rows = {}
    for m in MODELS:
        rt = table_for(tabs, m)
        CY.clear_cache()
        fs = rt.firm_support((m, arm), "macro", "notch")
        resid = CY.cyclicality_notch(rt, (m, arm), fs)
        rci = S.cluster_bootstrap(rt, fs, lambda x, mv=(m, arm): CY.cyclicality_notch(rt, mv, x),
                                  draws=DRAWS, seed=SEED)
        CY.clear_cache()
        tfs = rt.firm_support((m, "v_terse"), "macro")
        pt = CY.cyclicality_pd(rt, (m, "v_terse"), tfs)
        pv = CY.cyclicality_pd(rt, (m, arm), fs)
        ret = (pv / pt) if (pt not in (None, 0) and pv is not None) else None
        rows[m] = {"residual_slope": resid, "residual_ci95": [rci["ci_low"], rci["ci_high"]],
                   "pd_retention": ret}
    grid = {}
    for band in bands:
        for keep in retentions:
            passes = []
            for m, r in rows.items():
                lo, hi = r["residual_ci95"]
                in_band = lo is not None and lo >= -band and hi <= band
                keeps = r["pd_retention"] is not None and r["pd_retention"] >= keep
                if in_band and keeps:
                    passes.append(m)
            grid[f"band_{band}_retention_{keep}"] = {"n_pass": len(passes), "models": passes}
    return {"criterion": "rating-stability interval entirely inside +/-band AND PD retention "
                         "at or above the threshold",
            "arm": arm, "per_model": rows, "grid": grid}


# ── 8. TOST equivalence for the non-significant pairs ──────────────────────────
def tost(tabs, margin=0.05):
    rev = json.loads((ROOT / "results" / "reviewer_revision.json").read_text())
    pairs = [(r["a"], r["b"]) for r in rev["model_contrasts_terse"] if not r["excludes_zero"]]
    out = {}
    for a, b in pairs:
        rta, rtb = table_for(tabs, a), table_for(tabs, b)
        # both arms must be resampled on the same firms for a paired contrast
        CY.clear_cache()
        fa = set(rta.firm_support((a, "v_terse"), "macro", "notch"))
        fb = set(rtb.firm_support((b, "v_terse"), "macro", "notch"))
        fs = sorted(fa & fb)
        rt = rta

        def diff(x, a=a, b=b, rta=rta, rtb=rtb):
            CY.clear_cache()
            va = CY.cyclicality_notch(rta, (a, "v_terse"), x)
            vb = CY.cyclicality_notch(rtb, (b, "v_terse"), x)
            return None if (va is None or vb is None) else va - vb
        d = S.cluster_bootstrap(rt, fs, diff, draws=DRAWS, seed=SEED)
        lo, hi = d["ci_low"], d["ci_high"]
        # TOST at level 0.05 is equivalent to the 90% interval lying inside +/-margin; the
        # 95% interval is the conservative version, so report both verdicts explicitly.
        equiv95 = lo is not None and lo > -margin and hi < margin
        out[f"{DISP[a]} vs {DISP[b]}"] = {
            "difference": d["point"], "ci95": [lo, hi],
            "margin": margin, "equivalent_at_95ci": equiv95, "n_firms": d["n_firms"]}
    return {"test": "two one-sided tests, read off the firm-clustered bootstrap interval of the "
                    "paired difference: equivalence is declared only if the whole interval lies "
                    "inside the margin",
            "margin_notches": margin, "pairs": out}


# ── 9. Holm correction on the 21 pairwise tests ────────────────────────────────
def holm(_tabs):
    rev = json.loads((ROOT / "results" / "reviewer_revision.json").read_text())
    rows = rev["model_contrasts_terse"]
    # the bootstrap gives intervals, not p-values; invert the interval to a normal-approx p
    out = []
    for r in rows:
        lo, hi = r["ci95"]
        se = (hi - lo) / (2 * 1.96) if (lo is not None and hi is not None) else None
        z = abs(r["diff"]) / se if se else None
        p = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2)))) if z else None
        out.append({"a": r["a"], "b": r["b"], "diff": r["diff"], "ci95": r["ci95"],
                    "p_normal_approx": p, "excludes_zero": r["excludes_zero"]})
    ordered = sorted([o for o in out if o["p_normal_approx"] is not None],
                     key=lambda o: o["p_normal_approx"])
    k = len(ordered)
    rejected, still = 0, True
    for i, o in enumerate(ordered):
        thresh = 0.05 / (k - i)
        o["holm_threshold"] = thresh
        if still and o["p_normal_approx"] <= thresh:
            o["holm_significant"] = True; rejected += 1
        else:
            still = False; o["holm_significant"] = False
    return {"n_tests": k, "n_significant_uncorrected": sum(1 for o in out if o["excludes_zero"]),
            "n_significant_holm": rejected,
            "note": "the bootstrap produces intervals; p-values here are a normal "
                    "approximation from the interval width, used only for the Holm ordering",
            "tests": ordered}


# ── 10. per-model placebo slope ────────────────────────────────────────────────
def per_model_placebo(tabs):
    out = {}
    for m in MODELS:
        rt = table_for(tabs, m)
        CY.clear_cache()
        fs = rt.firm_support((m, "v_terse"), "placebo", "notch")
        if len(fs) < 20:
            out[m] = None; continue
        out[m] = ci(rt, fs, lambda x, mv=(m, "v_terse"): CY.placebo_cyclicality(rt, mv, x))
    return {"quantity": "slope on the matched credit-irrelevant placebo axis, notches per step",
            "models": out}


# ── 11. Gemini Flash real vs synthetic ─────────────────────────────────────────
def flash_real_vs_synth(_tabs):
    m = "gemini_flash"
    rt_r = RA.load_rating_table(subgrid_filter="real", allowed_models={m})
    rt_s = RA.load_rating_table(subgrid_filter="full", allowed_models={m})
    CY.clear_cache()
    fr = rt_r.firm_support((m, "v_terse"), "macro", "notch")
    fs = rt_s.firm_support((m, "v_terse"), "macro", "notch")
    real = CY.cyclicality_notch(rt_r, (m, "v_terse"), fr)
    synth = CY.cyclicality_notch(rt_s, (m, "v_terse"), fs)
    # the two arms use DIFFERENT firms, so the difference is a two-sample bootstrap: resample
    # each battery independently within each draw and difference inside the draw
    rng = random.Random(SEED)
    by_r, by_s = {}, {}
    for f in fr:
        by_r.setdefault(rt_r.firms_meta[f]["tier"], []).append(f)
    for f in fs:
        by_s.setdefault(rt_s.firms_meta[f]["tier"], []).append(f)
    vals = []
    for _ in range(DRAWS):
        ra = [grp[rng.randrange(len(grp))] for t in sorted(by_r) for grp in [by_r[t]]
              for _i in range(len(grp))]
        sa = [grp[rng.randrange(len(grp))] for t in sorted(by_s) for grp in [by_s[t]]
              for _i in range(len(grp))]
        CY.clear_cache()
        a = CY.cyclicality_notch(rt_r, (m, "v_terse"), ra)
        b = CY.cyclicality_notch(rt_s, (m, "v_terse"), sa)
        if a is not None and b is not None:
            vals.append(a - b)
    vals.sort()
    lo = vals[int(0.025 * len(vals))] if len(vals) >= 20 else None
    hi = vals[int(0.975 * len(vals)) - 1] if len(vals) >= 20 else None
    return {"model": DISP[m], "real_beta": real, "synthetic_beta": synth,
            "difference_real_minus_synthetic": (real - synth) if (real is not None and synth is not None) else None,
            "difference_ci95": [lo, hi], "draws": DRAWS,
            "excludes_zero": (lo is not None and (lo > 0 or hi < 0)),
            "n_real_firms": len(fr), "n_synthetic_firms": len(fs),
            "note": "two-sample bootstrap: the arms use different firm batteries, so each is "
                    "resampled independently and the difference taken inside the draw"}


# ── 12. verbalised-PD calibration against the stylised ladder ──────────────────
def pd_calibration(_tabs):
    byr = collections.defaultdict(lambda: collections.defaultdict(list))
    for f in glob.glob(str(ROOT / "data" / "raw" / "runs_*_v_terse.csv")):
        with open(f) as fh:
            for r in csv.DictReader(fh):
                if (r.get("ok") or "").lower() in ("false", "0"):
                    continue
                try:
                    n = int(float(r["rating_notch"])); pd = float(r["pd_1yr"])
                except (TypeError, ValueError, KeyError):
                    continue
                if pd <= 0:
                    continue
                byr[r["model_key"]][n].append(pd)
    out = {}
    for m, d in byr.items():
        rows = {}
        for n in sorted(d, reverse=True):
            vals = d[n]
            if len(vals) < 5 or n not in CAP.NOTCH_PD:
                continue
            med = statistics.median(vals)
            rows[n] = {"n_obs": len(vals), "median_verbalised_pd": med,
                       "ladder_pd": CAP.NOTCH_PD[n],
                       "ratio_verbalised_over_ladder": med / CAP.NOTCH_PD[n]}
        if rows:
            rr = [v["ratio_verbalised_over_ladder"] for v in rows.values()]
            out[m] = {"by_notch": rows, "median_ratio": statistics.median(rr),
                      "min_ratio": min(rr), "max_ratio": max(rr), "n_notches": len(rows)}
    return {"quantity": "median verbalised one-year PD at each rating notch, against the "
                        "stylised S&P-anchored ladder in analysis/capital.py",
            "models": out}


# ── 13. do the TTC rationales mention the macro state? ─────────────────────────
def ttc_rationales(_tabs):
    TERMS = re.compile(r"recession|downturn|spread|cycle|cyclical|macro|contraction|"
                       r"slowdown|stress|unemploy", re.I)
    out = {}
    for f in glob.glob(str(ROOT / "data" / "raw" / "runs_*_v_ttc.csv")):
        with open(f) as fh:
            for r in csv.DictReader(fh):
                if (r.get("macro_kind") or "") != "macro":
                    continue
                m, st = r["model_key"], r["macro_state"]
                txt = r.get("rationale") or ""
                d = out.setdefault(m, {}).setdefault(st, {"n": 0, "mentions": 0,
                                                          "severity": r.get("macro_severity")})
                d["n"] += 1
                if TERMS.search(txt):
                    d["mentions"] += 1
    for m, states in out.items():
        for st, d in states.items():
            d["mention_rate"] = d["mentions"] / d["n"] if d["n"] else None
    return {"terms": TERMS.pattern,
            "quantity": "share of through-the-cycle rationales naming the macro state, by "
                        "severity state. A model that names the recession while holding its PD "
                        "flat is anchoring rather than ignoring the cycle.",
            "models": out}


# ── 14. Basel PD floor ─────────────────────────────────────────────────────────
def basel_floor(tabs, floor=0.0005):
    """Rerun the capital translation with the Basel 0.05% corporate PD floor applied.

    The first version of this block used a hand-rolled per-model average at 400 draws and
    produced [1.72, 2.01] where claims.json prints [1.73, 2.00]. That was this block's error,
    not the manuscript's: run.py bootstraps CAP.pooled_capital_swing over the union firm set at
    2000 draws. Both arms below now use exactly that estimator, so baseline and floored are
    comparable to each other and to the frozen artifact.
    """
    rt = tabs["full"]
    tfirms = sorted({f for m in rt.models for f in rt.firm_support((m, "v_terse"), "macro")})
    orig = dict(CAP.NOTCH_PD)
    out = {}
    try:
        for label, mapping in (("baseline", orig),
                               ("floored", {k: max(floor, v) for k, v in orig.items()})):
            CAP.NOTCH_PD.clear(); CAP.NOTCH_PD.update(mapping)
            CY.clear_cache()
            pooled = CAP.pooled_capital_swing(rt, "v_terse", tfirms, "rating")
            d = S.cluster_bootstrap(
                rt, tfirms,
                lambda fs: CAP.pooled_capital_swing(rt, "v_terse", fs, "rating"),
                draws=DRAWS, seed=SEED)
            per = {m: CAP.mean_capital_swing(rt, (m, "v_terse"),
                                             rt.firm_support((m, "v_terse"), "macro"), "rating")
                   for m in rt.models}
            halves = [CAP.mean_capital_halves(rt, (m, "v_terse"),
                                              rt.firm_support((m, "v_terse"), "macro"), "rating")
                      for m in rt.models]
            cd = [x[0] for x in halves if x[0] is not None]
            cu = [x[1] for x in halves if x[1] is not None]
            out[label] = {
                "pooled_swing_pp": pooled,
                "pooled_swing_ci95": [d["ci_low"], d["ci_high"]],
                "per_model_swing_pp": per,
                "max_per_model_swing_pp": max(v for v in per.values() if v is not None),
                "ratio_max_over_pooled": max(v for v in per.values() if v is not None) / pooled,
                "pooled_downside_pp": sum(cd) / len(cd) if cd else None,
                "pooled_upside_pp": sum(cu) / len(cu) if cu else None,
                "capital_asymmetry_ratio": ((sum(cd) / len(cd)) / (sum(cu) / len(cu)))
                                           if (cd and cu and sum(cu)) else None,
                "draws": DRAWS,
            }
        # the 259-cell sensitivity grid, recomputed under the floor
        import importlib
        rr = importlib.import_module("reviewer_revision")
        CAP.NOTCH_PD.clear(); CAP.NOTCH_PD.update({k: max(floor, v) for k, v in orig.items()})
        route = {m: table_for(tabs, m) for m in MODELS}
        cells = rr.capital_sensitivity(route, 0)
        vals = [c["mean_capital_swing_pp"] for c in cells]
        by_all, by_grid = collections.defaultdict(list), collections.defaultdict(list)
        for c in cells:
            by_all[c["model"]].append(c["mean_capital_swing_pp"])
            if c.get("source") != "pd":
                by_grid[c["model"]].append(c["mean_capital_swing_pp"])
        g = [max(v) / min(v) for v in by_grid.values()]
        a_ = [max(v) / min(v) for v in by_all.values()]
        out["grid_under_floor"] = {
            "n_cells": len(cells), "all_positive": all(v > 0 for v in vals),
            "min_swing_pp": min(vals), "max_swing_pp": max(vals),
            "rating_anchored_spread": [min(g), max(g)],
            "including_verbalised_spread": [min(a_), max(a_)]}
    finally:
        CAP.NOTCH_PD.clear(); CAP.NOTCH_PD.update(orig)
    out["floor"] = floor
    out["notches_below_floor"] = sorted(k for k, v in orig.items() if v < floor)
    out["note"] = ("the floor binds only on the four notches whose stylised PD is under 5 bp, "
                   "AA- and above, so it compresses the boom end of the severity axis")
    return out


# ── 15. how the arms sum to the study total ────────────────────────────────────
def assessment_accounting(_tabs):
    rows, errs = collections.Counter(), collections.Counter()
    for f in glob.glob(str(ROOT / "data" / "frozen" / "*.freeze.json")):
        d = json.loads(Path(f).read_text())
        rows[d["subgrid"]] += d["n_rows"]; errs[d["subgrid"]] += d.get("n_error", 0)
    arms = {}
    for k in sorted(rows):
        arms[k] = {"rows": rows[k], "errors": errs[k], "retained": rows[k] - errs[k]}
    counted = [k for k in rows if k != "pilot"]
    return {"arms": arms,
            "counted_in_study_total": sorted(counted),
            "excluded": ["pilot"],
            "study_total_retained": sum(arms[k]["retained"] for k in counted),
            "study_total_attempted": sum(arms[k]["rows"] for k in counted),
            "errors_in_counted_arms": sum(arms[k]["errors"] for k in counted),
            "original_confirmatory_grid": arms["full"]["retained"]}


# ── 16. the failed calls, and the real battery by tier ─────────────────────────
def failed_calls(_tabs):
    """Where the 101 excluded calls are, and which captures never cleared the freeze gate.

    Counting every raw CSV gives 2,949 failures, which does not match the receipts: four
    captures were never frozen, so the analysis never sees them. freeze_one() refuses any
    capture whose error rate exceeds 2%, and that is what happened to all four.
    """
    per_tier = collections.Counter()
    for line in (ROOT / "data" / "firms" / "real.jsonl").read_text().splitlines():
        if line.strip():
            per_tier[json.loads(line)["tier"]] += 1

    frozen = {}
    for f in glob.glob(str(ROOT / "data" / "frozen" / "*.freeze.json")):
        d = json.loads(Path(f).read_text()); frozen[d["csv"]] = d

    counted, failed_in_counted, byfile, unfrozen = 0, 0, {}, {}
    for f in sorted(glob.glob(str(ROOT / "data" / "raw" / "runs_*.csv"))):
        name = Path(f).name
        rows = list(csv.DictReader(open(f)))
        bad = [r for r in rows if (r.get("ok") or "") != "True"]
        rate = len(bad) / len(rows) if rows else 0.0
        causes = collections.Counter((r.get("error") or "")[:48] for r in bad)
        rec = {"rows": len(rows), "failed": len(bad), "error_rate": rate,
               "distinct_failed_cells": len({(r.get("firm_id"), r.get("macro_state"),
                                              r.get("seed_index")) for r in bad}),
               "top_cause": (causes.most_common(1)[0][0] if causes else None)}
        if name in frozen:
            if frozen[name]["subgrid"] != "pilot":
                counted += len(rows); failed_in_counted += len(bad)
            if bad:
                byfile[name] = rec
        else:
            rec["refused_by_freeze_gate_2pct"] = rate > 0.02
            unfrozen[name] = rec
    return {"real_firms_per_tier": dict(per_tier),
            "counted_rows": counted, "counted_failed": failed_in_counted,
            "counted_retained": counted - failed_in_counted,
            "frozen_files_with_failures": byfile,
            "captures_never_frozen": unfrozen,
            "note": "a failed call leaves its (firm, state, seed) cell one replicate short; it "
                    "was not retried, so the cell is the median over the replicates that "
                    "landed. The four unfrozen captures are excluded wholesale, which is why "
                    "three models carry two replicates rather than five."}


def threshold_robustness_stable(tabs):
    return threshold_robustness(tabs, arm="v_stable")


BLOCKS = {
    "threshold_robustness_stable": threshold_robustness_stable,
    "frontier_gradient": frontier_gradient, "stable_vs_ttc": stable_vs_ttc,
    "stable_pd_retention": stable_pd_retention, "threshold_robustness": threshold_robustness,
    "tost": tost, "holm": holm, "per_model_placebo": per_model_placebo,
    "flash_real_vs_synth": flash_real_vs_synth, "pd_calibration": pd_calibration,
    "ttc_rationales": ttc_rationales, "basel_floor": basel_floor,
    "assessment_accounting": assessment_accounting, "failed_calls": failed_calls,
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "results" / "revision_extras.json"))
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    want = [x.strip() for x in a.only.split(",") if x.strip()] or list(BLOCKS)
    tabs = tables()
    out = {"meta": {"draws": DRAWS, "seed": SEED,
                    "models": MODELS, "display": DISP}}
    for name in want:
        if name not in BLOCKS:
            print(f"[extras] unknown block {name!r}", file=sys.stderr); return 1
        print(f"  [extras] {name} ...", flush=True)
        out[name] = BLOCKS[name](tabs)
    p = Path(a.out)
    if p.exists() and want != list(BLOCKS):
        prev = json.loads(p.read_text()); prev.update(out); out = prev
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=2, sort_keys=True, default=str) + "\n")
    print(f"-> {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

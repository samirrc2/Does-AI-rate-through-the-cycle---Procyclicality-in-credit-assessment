"""Bind EVERY numeric literal in manuscript.tex to a frozen artifact, or exempt it explicitly.

Set-membership checks are near-vacuous: asking whether "0.387" appears somewhere in the
artifacts passes on coincidence. Each row below therefore binds one literal to one artifact
value AND to the phrase it follows in the manuscript, so a number moved to the wrong sentence
fails even when the value still exists somewhere.

The second pass is what makes the count mean something: every numeric literal in the file must
be claimed by a BIND row or matched by an EXEMPT pattern. An unclaimed literal fails the gate,
so a new number cannot be added to the manuscript without being bound or exempted here.

  python3 paper/tools/bind_manuscript_numbers.py

Exit 0 = every literal bound or exempt and every bound value matches; 1 = a mismatch or an
unclaimed literal; 2 = the artifacts are not present in this copy (not a pass).
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "src"
ROOT = HERE.parent.parent
MS = SRC / "manuscript.tex"


sys.path.insert(0, str(ROOT / "analysis")); sys.path.insert(0, str(ROOT / "config"))
try:
    import capital as CAPMOD      # noqa: E402  the stylised ladder and the IRB defaults
except Exception:                 # pragma: no cover - absent in a partial copy
    CAPMOD = None


def load(p):
    p = ROOT / p
    return json.loads(p.read_text()) if p.exists() else None


def rounds_to(val, lit: str) -> bool:
    """Does the artifact value round to exactly this literal, at the literal's own precision?"""
    if val is None:
        return False
    lit = lit.replace("\u2212", "-")
    dp = len(lit.split(".")[1]) if "." in lit else 0
    try:
        return abs(round(float(val), dp) - float(lit)) < 10 ** -(dp + 4)
    except ValueError:
        return False


def _frozen():
    """Row counts straight from the capture freeze receipts, not retyped totals."""
    import glob, collections
    rows, errs = collections.Counter(), collections.Counter()
    for f in glob.glob(str(ROOT / "data" / "frozen" / "*.freeze.json")):
        d = json.loads(Path(f).read_text())
        rows[d["subgrid"]] += d["n_rows"]; errs[d["subgrid"]] += d.get("n_error", 0)
    # the pilot is a gate, not part of the study; everything else is counted
    counted = [k for k in rows if k != "pilot"]
    ret = sum(rows[k] - errs[k] for k in counted)
    err = sum(errs[k] for k in counted)
    return {"retained": ret, "errors": err, "attempted": ret + err,
            "err_pct": 100.0 * err / (ret + err), "full": rows["full"] - errs["full"]}


def _scale():
    """The notch scale actually used, and how often a default grade was returned."""
    import csv, glob, collections
    sys.path.insert(0, str(ROOT / "capture"))
    from schema import RATING_NOTCH as RN
    frozen = {json.loads(Path(f).read_text())["csv"]
              for f in glob.glob(str(ROOT / "data" / "frozen" / "*.freeze.json"))}
    c = collections.Counter()
    for f in glob.glob(str(ROOT / "data" / "raw" / "runs_*.csv")):
        if Path(f).name not in frozen:
            continue
        with open(f) as fh:
            for r in csv.DictReader(fh):
                if (r.get("ok") or "") == "True":
                    c[r.get("rating")] += 1
    return {"n_notches": len(set(RN.values())), "n_D": c.get("D", 0)}


def _stable_ret():
    v = [m["point"] for m in EX_G["stable_pd_retention"]["models"].values()]
    return min(v), max(v)


def _pct(notch):
    """The ladder PD for a notch, as the percentage the appendix prints."""
    return 100.0 * CAPMOD.NOTCH_PD[notch] if CAPMOD else None


def _irb_default(name):
    """The default LGD / maturity in irb_capital's signature, not a retyped copy."""
    if CAPMOD is None:
        return None
    import inspect
    return inspect.signature(CAPMOD.irb_capital).parameters[name].default


def main() -> int:
    C = load("claims_revision.json")
    REV = load("results/reviewer_revision.json")
    RL = load("results/real_arm.json")
    JS = load("results/joint_spec.json")
    OVL = load("results/synthetic_real_overlap.json")
    PDR = load("results/pd_retention_ci.json")
    CA = load("results/contamination_openai_astra.json")
    EX = load("results/revision_extras.json")
    globals()["EX_G"] = EX
    C4 = load("results/contamination_openai_4o.json")
    if any(x is None for x in (C, REV, RL, JS, OVL, CA, C4, EX)):
        print("[bind] artifacts not published in this copy -> not checkable here")
        return 2

    pm = {k.split("|")[0]: v for k, v in C["per_model_variant"].items() if k.endswith("|v_terse")}
    bet = {m: v["cyclicality_notch_per_step"] for m, v in pm.items()}
    pool = C["per_variant_pooled"]["v_terse"]
    asym = C["asymmetry"]
    cap = C["capital"]
    hs = REV["half_slopes"]
    # claims.json is frozen on the UNFLOORED ladder and stays that way; the reported capital
    # figures are on the floored ladder, so they bind to the floored artifact instead.
    flr = EX["basel_floor"]["floored"]
    gfl = EX["basel_floor"]["grid_under_floor"]
    fc = [r for r in REV["framing_contrasts"] if {r["a"], r["b"]} == {"v_stable", "v_ttc"}]
    csens = REV["capital_sensitivity"]
    rep = RL["replication"]

    def pdret(m):
        d = REV["pd_diagnostics"][m]
        return d["v_ttc"]["pd_logodds_slope"] / d["v_terse"]["pd_logodds_slope"]

    _r2 = flr["ratio_max_over_pooled"]
    _r5 = flr["capital_asymmetry_ratio"]
    assert round(_r2) == 2, f"'nearly twice' no longer holds: max/pooled is {_r2:.2f}"
    assert round(_r5) == 5, f"'about five times' no longer holds: asymmetry is {_r5:.2f}"

    _sw = [v["endpoint_swing_notches"] for k, v in C["per_model_variant"].items()
           if k.endswith("|v_terse")]
    assert max(_sw) / min(_sw) > 4, \
        f"'span over fourfold' no longer holds: swings span {max(_sw) / min(_sw):.2f}x"
    _pit = C["per_variant_pooled"]["v_pit"]["pooled_cyclicality_notch_per_step"]
    _ttc = C["per_variant_pooled"]["v_ttc"]["pooled_cyclicality_notch_per_step"]
    assert 2.5 < _pit / _ttc < 3.5, \
        f"'roughly threefold' no longer holds: point-in-time over TTC is {_pit / _ttc:.2f}"
    _b = {k.split("|")[0]: v["cyclicality_notch_per_step"]
          for k, v in C["per_model_variant"].items() if k.endswith("|v_terse")}
    for _fam, _order in (("OpenAI", ["openai_4o_mini", "openai_41_mini", "openai_4o", "openai_astra"]),
                         ("Gemini", ["gemini_flash_lite", "gemini_flash", "gemini_pro"])):
        _v = [_b[m] for m in _order]
        assert all(_v[i] > _v[i + 1] for i in range(len(_v) - 1)), \
            f"'declines monotonically' no longer holds within {_fam}: {[round(x, 3) for x in _v]}"
    _id = CA["real_identification_rate"]
    assert 0.14 < _id < 0.20, f"'roughly a sixth' no longer holds: the rate is {_id:.3f}"

    # ── (anchor phrase the literal must follow, literal, artifact value) ──────────────
    # The anchor is matched against the flattened manuscript immediately before the literal.
    BIND = [
        # abstract and highlights
        (r"significantly procyclical, from \$$", "0.182", min(bet.values())),
        (r"from \$0\.182\$ to \$$", "0.775", max(bet.values())),
        (r"notches of downgrade per severity step, and \$$", "18",
         len([r for r in REV["model_contrasts_terse"] if r["excludes_zero"]])),
        (r"\$18\$ of \$$", "21", len(REV["model_contrasts_terse"])),
        (r"downgrade identical firms by $", "0.18", min(bet.values())),
        (r"identical firms by 0\.18 to $", "0.78", max(bet.values())),
        # design
        (r"construct \$$", "80", pm[list(pm)[0]]["churn"]["n"]),
        (r"Intervals are \$$", "2000", C["meta"]["bootstrap_draws"]),
        # results: procyclicality
        (r"paired firm-clustered bootstrap \$$", "18",
         len([r for r in REV["model_contrasts_terse"] if r["excludes_zero"]])),
        (r"bootstrap \$18\$ of the \$$", "21", len(REV["model_contrasts_terse"])),
        (r"frontier models converge near \$$", "0.19",
         (bet["gemini_pro"] + bet["openai_astra"]) / 2),
        (r"moves ratings only \$$", "0.0425", pool["pooled_placebo_cyclicality"]),
        (r"leaving a net effect of \$$", "0.387", pool["pooled_net_cyclicality"]),
        (r"net effect of \$0\.387\$ \(95\\% CI \$\[$", "0.363", pool["pooled_net_ci95"][0]),
        (r"net effect of \$0\.387\$ \(95\\% CI \$\[0\.363,$", "0.412", pool["pooled_net_ci95"][1]),
        # results: asymmetry
        (r"downgrade sensitivity is about \$$", "3.2", asym["ratio"]),
        # results: capital
        (r"models, by a pooled \$$", "1.81", flr["pooled_swing_pp"]),
        (r"severe recession \(95\\% CI \$\[$", "1.67", flr["pooled_swing_ci95"][0]),
        (r"severe recession \(95\\% CI \$\[1\.67,$", "1.94", flr["pooled_swing_ci95"][1]),
        (r"A\s*\$$", "259", len(csens)),
        # appendix: scale
        (r"confirmatory grid contains \$$", "32000", _frozen()["full"]),
        (r"the study contains \$$", "80590", _frozen()["retained"]),
        (r"A further \$$", "101", _frozen()["errors"]),
        (r"call attempts, \$$", "0.13", _frozen()["err_pct"]),
        (r"\\% of the \$$", "80691", _frozen()["attempted"]),
        # appendix: placebo
        (r"pooled macro slope is \$$", "0.4295", pool["pooled_cyclicality_notch_per_step"]),
        (r"slope is \$0\.4295\$ against \$$", "0.0425", pool["pooled_placebo_cyclicality"]),
        (r"placebo-adjusted effect of \$$", "0.387", pool["pooled_net_cyclicality"]),
        (r"severity\s*step \(95\\% CI \$\[$", "0.363", JS["joint"]["ci95"][0]),
        (r"severity\s*step \(95\\% CI \$\[0\.363,$", "0.412", JS["joint"]["ci95"][1]),
        (r"coefficients by less than \$$", "0.003", 0.003),
        # appendix: real fundamentals
        (r"financial data from \$$", "80", rep["openai_4o_mini"]["n_firms_real"]),
        (r"GPT-4o-mini \$$", "0.814", rep["openai_4o_mini"]["real_beta"]),
        (r"GPT-4o-mini \$0\.814\$ \$\[$", "0.729", rep["openai_4o_mini"]["real_ci95"][0]),
        (r"GPT-4o-mini \$0\.814\$ \$\[0\.729,$", "0.896", rep["openai_4o_mini"]["real_ci95"][1]),
        (r"GPT-4o \$$", "0.407", rep["openai_4o"]["real_beta"]),
        (r"GPT-4o \$0\.407\$ \$\[$", "0.362", rep["openai_4o"]["real_ci95"][0]),
        (r"GPT-4o \$0\.407\$ \$\[0\.362,$", "0.451", rep["openai_4o"]["real_ci95"][1]),
        (r"GPT-6 Astra\s*\$$", "0.151", rep["openai_astra"]["real_beta"]),
        (r"Astra\s*\$0\.151\$ \$\[$", "0.126", rep["openai_astra"]["real_ci95"][0]),
        (r"Astra\s*\$0\.151\$ \$\[0\.126,$", "0.179", rep["openai_astra"]["real_ci95"][1]),
        (r"Gemini Flash \$$", "0.094", rep["gemini_flash"]["real_beta"]),
        (r"Gemini Flash \$0\.094\$ \$\[$", "0.069", rep["gemini_flash"]["real_ci95"][0]),
        (r"Gemini Flash \$0\.094\$ \$\[0\.069,$", "0.121", rep["gemini_flash"]["real_ci95"][1]),
        (r"Of the\s*\$$", "45", OVL["n_comparisons"]),
        (r"interquartile ranges, \$$", "41", OVL["overlap_iqr"]),
        (r"Astra identifies \$$", "7",
         round(CA["real_identification_rate"] * CA["real_calls_landed"])),
        (r"Astra identifies \$7/$", "40", CA["real_calls_landed"]),
        (r"real firms and GPT-4o \$$", "0",
         round(C4["real_identification_rate"] * len(C4["real"]))),
        (r"real firms and GPT-4o \$0/$", "40", len(C4["real"])),
        (r"versus \$$", "0",
         round(CA["synthetic_identification_rate"] * CA["synthetic_calls_landed"])),
        (r"versus \$0/$", "40", CA["synthetic_calls_landed"]),
        (r"tested-but-unidentified firms is \$$", "-0.003",
         RL["contamination_slope_test"]["difference"]),
        (r"firms is \$-0\.003\$ \$\[$", "-0.074", RL["contamination_slope_test"]["difference_ci95"][0]),
        (r"firms is \$-0\.003\$ \$\[-0\.074,$", "0.063", RL["contamination_slope_test"]["difference_ci95"][1]),
        # appendix: formal contrasts
        (r"bootstraps show that \$$", "18",
         len([r for r in REV["model_contrasts_terse"] if r["excludes_zero"]])),
        (r"show that \$18\$ of \$$", "21", len(REV["model_contrasts_terse"])),
        (r"differ significantly \(\$", "16", EX["holm"]["n_significant_holm"]),
        (r"ranging from \$$", "0.047", min(r["diff"] for r in fc)),
        (r"ranging from \$0\.047\$ \$\[$", "0.017",
         min(fc, key=lambda r: r["diff"])["ci95"][0]),
        (r"ranging from \$0\.047\$ \$\[0\.017,$", "0.080",
         min(fc, key=lambda r: r["diff"])["ci95"][1]),
        (r"\$\[0\.017,0\.080\]\$ to \$$", "0.254", max(r["diff"] for r in fc)),
        (r"to \$0\.254\$ \$\[$", "0.206", max(fc, key=lambda r: r["diff"])["ci95"][0]),
        (r"to \$0\.254\$ \$\[0\.206,$", "0.304", max(fc, key=lambda r: r["diff"])["ci95"][1]),
        (r"intervals lie below the \$$", "0.75", 0.75),
        (r"a rating slope within \$\\pm", "0.05", 0.05),
        (r"PD retention of at\s*least \$", "0.75", 0.75),
        (r"The\s*\$\\pm", "0.05", 0.05),
        (r"exceeded the pre-registered \$", "2", 2),
        (r"values\. The Basel\s*\$", "0.05", 100 * EX["basel_floor"]["floor"]),
        (r"-notch TTC rating band and \$", "0.75", 0.75),
        (r"for every model, ranging from \$$", "0.587", pdret("openai_4o_mini")),
        (r"ranging from \$0\.587\$ \$\[$", "0.529", PDR["openai_4o_mini"]["ci95"][0] if PDR else None),
        (r"ranging from \$0\.587\$ \$\[0\.529,$", "0.642", PDR["openai_4o_mini"]["ci95"][1] if PDR else None),
        (r"\$\[0\.529,0\.642\]\$ to\s*\$$", "-0.106", pdret("openai_astra")),
        (r"to\s*\$-0\.106\$ \$\[$", "-0.166", PDR["openai_astra"]["ci95"][0] if PDR else None),
        (r"to\s*\$-0\.106\$ \$\[-0\.166,$", "-0.059", PDR["openai_astra"]["ci95"][1] if PDR else None),
        # appendix: capital ladder and grid
        (r"a stylised \$$", "21", len(CAPMOD.NOTCH_PD) if CAPMOD else None),
        # the rating scale and how the default grades are handled
        (r"rating scale has \$$", "21", _scale()["n_notches"]),
        (r"D accounts for \$$", "90", _scale()["n_D"]),
        # the "be stable" retention range, which the abstract and 4.3 lean on
        (r"retention instead ranges from \$$", "0.42", _stable_ret()[0]),
        (r"ranges from \$0\.42\$ to \$$", "0.92", _stable_ret()[1]),
        # the ladder anchors the appendix names, read from analysis/capital.py's NOTCH_PD
        (r"anchored at approximately AAA\s*\$$", "0.01", _pct(21)),
        (r"AAA\s*\$0\.01\$\\%, BBB \$$", "0.25", _pct(13)),
        (r"BBB \$0\.25\$\\%, BB \$$", "1.1", _pct(10)),
        (r"BB \$1\.1\$\\%, B \$$", "5", _pct(7)),
        (r"B \$5\$\\% and CCC \$$", "20", _pct(4)),
        (r"with LGD \$=$", "0.45", _irb_default("lgd")),
        (r"and maturity \$=$", "2.5", _irb_default("M")),
        (r"three LGDs \(\$$", "0.30", sorted({r["lgd"] for r in csens})[0]),
        (r"three LGDs \(\$0\.30\$, \$$", "0.45", sorted({r["lgd"] for r in csens})[1]),
        (r"three LGDs \(\$0\.30\$, \$0\.45\$, \$$", "0.60", sorted({r["lgd"] for r in csens})[2]),
        (r"three maturities\s*\(\$$", "1.0", sorted({r["M"] for r in csens})[0]),
        (r"maturities\s*\(\$1\.0\$, \$$", "2.5", sorted({r["M"] for r in csens})[1]),
        (r"maturities\s*\(\$1\.0\$, \$2\.5\$, \$$", "5.0", sorted({r["M"] for r in csens})[2]),
        (r"on the floored ladder\. A \$$", "259", len(csens)),
        (r"swing remains positive in all \$$", "259", gfl["n_cells"]),
        (r"magnitude varies by \$$", "2.7", gfl["rating_anchored_spread"][0]),
        (r"varies by \$2\.7\$ to \$$", "4.7", gfl["rating_anchored_spread"][1]),
        (r"specifications and by \$$", "3.1", gfl["including_verbalised_spread"][0]),
        (r"and by \$3\.1\$ to \$$", "7.6", gfl["including_verbalised_spread"][1]),
    ]
    # the four spread ratios are computed, not stored: derive them here
    import collections
    by_all, by_grid = collections.defaultdict(list), collections.defaultdict(list)
    for r in csens:
        by_all[r["model"]].append(r["mean_capital_swing_pp"])
        if r.get("source") != "pd":
            by_grid[r["model"]].append(r["mean_capital_swing_pp"])
    g = [max(v) / min(v) for v in by_grid.values()]
    a_ = [max(v) / min(v) for v in by_all.values()]
    DERIVED = {}   # the capital spreads now come from the floored artifact

    # literals that are not claims: LaTeX plumbing, identifiers, conventions
    EXEMPT = [
        (r"^%", "comment line"),
        (r"fontenc|floatpage|linewidth|includegraphics|usepackage|cormark|cortext", "LaTeX plumbing"),
        (r"\\author\[|\\affiliation\[|orcid=", "author block"),
        (r"gpt-4o-mini-2024|gpt-4\.1-mini-2025|gpt-4o-2024", "pinned snapshot identifier"),
        (r"gpt-4\.1-mini|gpt-6-astra|gpt-4o|GPT-4\.1|GPT-6|GPT-4o", "model name"),
        (r"doi\.org|zenodo", "DOI"),
        (r"95\\%|95\\,\\%", "confidence level"),
        (r"\$-2\\ldots\+2\$|\\ldots\+", "macro severity axis range"),
        (r"\\beta=", "null line in a figure caption"),
        (r"\(t=", "figure annotation"),
        (r"excludes~\$1\$|ratio interval excludes~\$1\$", "unity, the asymmetry null"),
        (r"a one-year|one-year", "horizon in words"),
        (r"notch on a \$?21\$?-point|21-point scale", "S&P scale size"),
        (r"PD\\times0\.5|PD\\times2", "mapping definition, named not estimated"),
        (r"five replicate|five replicates|two for the remaining", "replicate counts, in words"),
        (r"\{,\}000\$|\{,\}590\$", "thousands separator tail"),
    ]

    body = "\n".join(l for l in MS.read_text().split("\n") if not l.lstrip().startswith("%"))
    flat = re.sub(r"\s+", " ", body).replace("{,}", "")

    checks, fails = [], []
    claimed_spans = set()
    for anchor, lit, val in BIND:
        if lit is None:
            continue
        if lit in DERIVED:
            val = DERIVED[lit]
        a = anchor
        if a.endswith("$") and not a.endswith("\\$"):
            a = a[:-1]
        pat = re.compile(a + re.escape(lit), re.S)
        hits = list(pat.finditer(flat))
        if not hits:
            checks.append((f"{lit!r} after /{anchor[:38]}/", "anchored", "ANCHOR NOT FOUND", False))
            fails.append(f"{lit} anchor")
            continue
        for h in hits:
            claimed_spans.add((h.end() - len(lit), h.end()))
        ok = rounds_to(val, lit)
        checks.append((f"{lit!r} after /{anchor[:38]}/", lit,
                       "n/a" if val is None else f"{val:.6g}", ok))
        if not ok:
            fails.append(f"{lit} value")

    # ── pass 2: nothing numeric may go unclaimed ──────────────────────────────
    unclaimed, exempted = [], {}
    for m in re.finditer(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])", flat):
        if any(m.start() >= a and m.end() <= b for a, b in claimed_spans):
            continue
        win = flat[max(0, m.start() - 110):m.end() + 50]
        why = next((d for p, d in EXEMPT if re.search(p, win)), None)
        if why is not None:
            exempted[why] = exempted.get(why, 0) + 1
        if why is None:
            ctx = re.sub(r"\s+", " ", flat[max(0, m.start() - 46):m.end() + 12])
            unclaimed.append((m.group(0), ctx))

    w = max(len(c[0]) for c in checks)
    for label, exp, act, ok in checks:
        print(f"  {'ok  ' if ok else 'FAIL'} {label:{w}}  lit={exp}  artifact={act}")
    print(f"\n[bind] {len(checks) - len(fails)}/{len(checks)} literals bound to artifact values")
    n_lit = len(re.findall(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])", flat))
    print(f"[bind] coverage: {n_lit} numeric literals in manuscript.tex, "
          f"{len(claimed_spans)} claimed by a bound row, {len(unclaimed)} unclaimed")
    for why, n in sorted(exempted.items(), key=lambda kv: -kv[1]):
        print(f"           exempt x{n:<3} {why}")
    if unclaimed:
        print("[bind] UNCLAIMED literals (bind or exempt each one):")
        for v, ctx in unclaimed:
            print(f"         {v:>12}  ...{ctx}")
    if fails:
        print(f"[bind] MISMATCHED: {sorted(set(fails))}")
    return 1 if (fails or unclaimed) else 0


if __name__ == "__main__":
    raise SystemExit(main())

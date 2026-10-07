"""Bind every numeric claim in OUR text of the response letter to a frozen artifact.

verify_response_numbers.py compares artifacts against constants written into that file, which
does not detect the letter being reworded, and after the letter was rewritten most of those
constants no longer appeared in it at all. This reads the numbers OUT OF THE LETTER, anchored to
the phrase each follows, and compares them with the artifacts.

Reviewer comment blocks are skipped: those are the referees' words, including any figure they
quote from the submitted version, and must not be edited to match a revised artifact.

  python3 paper/tools/bind_letter_numbers.py

Exit 0 = every literal bound or exempt and matching; 1 = a mismatch or an unclaimed literal;
2 = the artifacts are not present in this copy (not a pass).
"""
from __future__ import annotations
import collections, glob, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "src"
ROOT = HERE.parent.parent
LETTER = SRC / "response_to_reviewers.txt"


def jload(rel):
    p = ROOT / rel
    return json.loads(p.read_text()) if p.exists() else None


def rounds_to(val, lit: str) -> bool:
    if val is None:
        return False
    lit = lit.replace("−", "-").rstrip("%")
    dp = len(lit.split(".")[1]) if "." in lit else 0
    try:
        return abs(round(float(val), dp) - float(lit)) < 10 ** -(dp + 4)
    except ValueError:
        return False


def ours(text: str) -> str:
    """Only Author response / Author action blocks. Reviewer comments are their words."""
    keep, mode = [], None
    for line in text.split("\n"):
        st = line.strip()
        if st.startswith("Reviewer comment:"):
            mode = "rev"
        elif st.startswith(("Author response:", "Author action:")):
            mode = "ours"
        elif st.startswith(("Reviewer #", "Response to", "Editor")):
            mode = None
        if mode == "ours":
            keep.append(line)
    return re.sub(r"\s+", " ", " ".join(keep))


def frozen():
    rows, errs = collections.Counter(), collections.Counter()
    for f in glob.glob(str(ROOT / "data" / "frozen" / "*.freeze.json")):
        d = json.loads(Path(f).read_text())
        rows[d["subgrid"]] += d["n_rows"]; errs[d["subgrid"]] += d.get("n_error", 0)
    counted = [k for k in rows if k != "pilot"]
    ret = sum(rows[k] - errs[k] for k in counted)
    err = sum(errs[k] for k in counted)
    return {"retained": ret, "errors": err, "attempted": ret + err,
            "err_pct": 100.0 * err / (ret + err),
            "frontier": rows["frontier"] - errs["frontier"],
            "full": rows["full"] - errs["full"]}


def main() -> int:
    if not LETTER.exists():
        print("[lbind] letter absent -> not checkable here"); return 2
    C = jload("claims_revision.json"); REV = jload("results/reviewer_revision.json")
    RL = jload("results/real_arm.json"); OVL = jload("results/synthetic_real_overlap.json")
    PDR = jload("results/pd_retention_ci.json"); OF = jload("results/ofat.json")
    CA = jload("results/contamination_openai_astra.json")
    EX = jload("results/revision_extras.json")
    C4 = jload("results/contamination_openai_4o.json")
    if any(x is None for x in (C, REV, RL, OVL, PDR, OF, CA, C4, EX)):
        print("[lbind] artifacts not published in this copy -> not checkable here"); return 2

    pm, pv = C["per_model_variant"], C["per_variant_pooled"]
    rep = RL["replication"]
    cst = RL["contamination_slope_test"]
    mc = REV["model_contrasts_terse"]
    fc = [r for r in REV["framing_contrasts"] if {r["a"], r["b"]} == {"v_stable", "v_ttc"}]
    csens = REV["capital_sensitivity"]
    FZ = frozen()

    def pdret(m):
        d = REV["pd_diagnostics"][m]
        return d["v_ttc"]["pd_logodds_slope"] / d["v_terse"]["pd_logodds_slope"]

    by_all, by_grid = collections.defaultdict(list), collections.defaultdict(list)
    for r in csens:
        by_all[r["model"]].append(r["mean_capital_swing_pp"])
        if r.get("source") != "pd":
            by_grid[r["model"]].append(r["mean_capital_swing_pp"])
    spread_grid = [max(v) / min(v) for v in by_grid.values()]
    spread_all = [max(v) / min(v) for v in by_all.values()]

    pdc = EX["pd_calibration"]["models"]
    spr = EX["stable_pd_retention"]["models"]
    svt = EX["stable_vs_ttc"]["models"]
    plc = EX["per_model_placebo"]["models"]
    thr = EX["threshold_robustness"]
    tos = EX["tost"]["pairs"]
    hlm = EX["holm"]
    rat = EX["ttc_rationales"]["models"]
    EXS = EX["threshold_robustness_stable"]
    gfl = EX["basel_floor"]["grid_under_floor"]
    EP = jload("results/seeds_epochs.json") or {"models": {}}
    drift = [v["beta_september"] - v["beta_july"]
             for v in EP["models"].values() if "beta_july" in v]
    ttc_ret = {m: thr["per_model"][m]["pd_retention"] for m in thr["per_model"]}
    other5 = [v["point"] for m, v in spr.items() if m not in ("openai_astra", "gemini_pro")]
    holm_p = sorted(t["p_normal_approx"] for t in hlm["tests"] if not t["holm_significant"])

    _nf = EX["failed_calls"]["captures_never_frozen"]
    assert len(_nf) == 4, f"the letter and README say four refusals; the artifact lists {len(_nf)}"
    _astra_ttc = _nf["runs_real_openai_astra_v_ttc.csv"]["error_rate"] * 100

    BIND = [
        # ── R1.1 real fundamentals and issuer recall ──────────────────────────
        (r"financial data for ", "80", rep["openai_4o_mini"]["n_firms_real"]),
        (r"zero: GPT-4o-mini ", "0.814", rep["openai_4o_mini"]["real_beta"]),
        (r"GPT-4o-mini 0\.814 GPT-4o ", "0.407", rep["openai_4o"]["real_beta"]),
        (r"GPT-6 Astra ", "0.151", rep["openai_astra"]["real_beta"]),
        (r"and Gemini Flash ", "0.094", rep["gemini_flash"]["real_beta"]),
        (r"GPT-4o identifies ", "0", round(C4["real_identification_rate"] * len(C4["real"]))),
        (r"GPT-4o identifies 0/", "40", len(C4["real"])),
        (r"GPT-6 Astra ", "7", round(CA["real_identification_rate"] * CA["real_calls_landed"])),
        (r"GPT-6 Astra 7/", "40", CA["real_calls_landed"]),
        (r"against ", "0", round(CA["synthetic_identification_rate"] * CA["synthetic_calls_landed"])),
        (r"against 0/", "40", CA["synthetic_calls_landed"]),
        (r"unidentified\s*firms is ", "−0.003", cst["difference"]),
        (r"firms is −0\.003 \[", "−0.074", cst["difference_ci95"][0]),
        (r"\[−0\.074 ", "0.063", cst["difference_ci95"][1]),
        # ── R1.2 the generation specification against real filings ────────────
        (r"In 41 of the ", "45", OVL["n_comparisons"]),
        (r"sample\. In ", "41", OVL["overlap_iqr"]),
        # ── R1.4 and R2.1 the two frontier arms ───────────────────────────────
        (r"procyclical, at ", "0.198", pm["openai_astra|v_terse"]["cyclicality_notch_per_step"]),
        (r"at 0\.198 \[", "0.18", pm["openai_astra|v_terse"]["cyclicality_ci95"][0]),
        (r"0\.198 \[0\.18 ", "0.22", pm["openai_astra|v_terse"]["cyclicality_ci95"][1]),
        (r"0\.22\] and ", "0.182", pm["gemini_pro|v_terse"]["cyclicality_notch_per_step"]),
        (r"and 0\.182 \[", "0.15", pm["gemini_pro|v_terse"]["cyclicality_ci95"][0]),
        (r"0\.182 \[0\.15 ", "0.22", pm["gemini_pro|v_terse"]["cyclicality_ci95"][1]),
        (r"intervals\. 18 of ", "21", len(mc)),
        (r"intervals\. ", "18", len([r for r in mc if r["excludes_zero"]])),
        (r"significantly or ", "16", hlm["n_significant_holm"]),
        (r"bootstrap contrasts\. - ", "18", len([r for r in mc if r["excludes_zero"]])),
        (r"contrasts\. - 18 of ", "21", len(mc)),
        # ── R1.5 PD retention ─────────────────────────────────────────────────
        (r"scale lies below ", "0.75", 0.75),
        (r"model ranging from ", "0.587", max(ttc_ret.values())),
        (r"ranging from 0\.587 to ", "−0.106", min(ttc_ret.values())),
        # ── R1.6 the capital grid and the Basel floor ─────────────────────────
        (r"analysis to a ", "259", len(csens)),
        (r"the Basel ", "0.05%", 100 * EX["basel_floor"]["floor"]),
        (r"swing is positive in all ", "259", len(csens)),
        (r"varies by ", "2.7", gfl["rating_anchored_spread"][0]),
        (r"varies by 2\.7 to\s*", "4.7", gfl["rating_anchored_spread"][1]),
        (r"specifications and by ", "3.1", gfl["including_verbalised_spread"][0]),
        (r"and by 3\.1 to ", "7.6", gfl["including_verbalised_spread"][1]),
        (r"paragraph\s*CRE32\.", "4", 4),
        (r"CRE32\.4 sets the ", "0.05%", 100 * EX["basel_floor"]["floor"]),
        # ── R1.7 replicates and drift ─────────────────────────────────────────
        (r"exceeded the ", "2%", 2.0),
        (r"which is SHA-", "256", 256),
        (r"Flash-Lite returned ", "400", 400),
        (r"GPT-6 Astra hit ", "429", 429),
        (r"credit quota with ", "402", 402),
        (r"through-the-cycle run at a ", "10.6%", _astra_ttc),
        (r"Re-measurement ", "2.5", 2.5),
        (r"with Δβ from ", "−0.037", min(drift)),
        (r"from −0\.037 to \+", "0.002", max(drift)),
        # ── R3.2 the framing contrast ─────────────────────────────────────────
        (r"models\s*ranging from ", "0.047", min(v["point"] for v in svt.values())),
        (r"ranging from 0\.047 \[", "0.017",
         min(svt.values(), key=lambda v: v["point"])["ci95"][0]),
        (r"0\.047 \[0\.017 ", "0.080", min(svt.values(), key=lambda v: v["point"])["ci95"][1]),
        (r"0\.080\] to ", "0.254", max(v["point"] for v in svt.values())),
        (r"to 0\.254 \[", "0.206", max(svt.values(), key=lambda v: v["point"])["ci95"][0]),
        (r"0\.254 \[0\.206 ", "0.304", max(svt.values(), key=lambda v: v["point"])["ci95"][1]),
        # ── R3.1 the joint benchmark thresholds ───────────────────────────────
        (r"within ±", "0.05", 0.05),
        (r"retention of at least ", "0.75", 0.75),
        # ── R3.3 the placebo-adjusted construction ────────────────────────────
        (r"placebo slope:\s*", "0.4295", pv["v_terse"]["pooled_cyclicality_notch_per_step"]),
        (r"0\.4295 − ", "0.0425", pv["v_terse"]["pooled_placebo_cyclicality"]),
        (r"− 0\.0425 = ", "0.387", pv["v_terse"]["pooled_net_cyclicality"]),
        (r"The earlier ", "0.042", 0.042),
        (r"a truncation of ", "0.0425", pv["v_terse"]["pooled_placebo_cyclicality"]),
        (r"Its interval \[", "0.363", pv["v_terse"]["pooled_net_ci95"][0]),
        (r"interval \[0\.363 ", "0.412", pv["v_terse"]["pooled_net_ci95"][1]),
        # ── R3.4 the table notes and the parse disclosure ─────────────────────
        (r"Flash-Lite[’']s ", "0.000",
         pm["gemini_flash_lite|v_terse"]["noise_floor_notch_sd"]),
        (r"states that all ", "80590", FZ["retained"]),
        (r"discloses the ", "101", FZ["errors"]),
    ]

    # An exemption must CONTAIN the literal, not merely sit near it. A window test let the
    # pattern for model names excuse any number within 100 characters of "GPT-4o", which is
    # most of the letter: the exempt count for it jumped from 20 to 56 as soon as per-model
    # results were added, and real claims were being waved through.
    EXEMPT_SPANS = [
        (r"(?:GPT|gpt)-[\w.]+(?:-mini|-Lite)?|[Gg]emini[- ](?:Flash|Pro)(?:-Lite)?"
         r"|gemini-[\w.-]+|v_[a-z]+", "model name"),
        (r"Sections?\s+\d+(?:\.\d+)?(?:\s+and\s+\d+(?:\.\d+)?)?", "section locator"),
        (r"Tables?\s+\d+", "table locator"),
        (r"Figures?\s+\d+(?:\([a-z]\))?", "figure locator"),
        (r"Appendix\s+[A-Z]", "appendix locator"),
        (r"Panel\s+[AB]", "panel locator"),
        (r"(?:Moody\u2019s|S&P Global(?: Ratings)?|et al\.?),?\s*\(?\d{4}[ab]?(?:,\s*\d{4}[ab]?)?\)?",
         "citation year"),
        (r"95%", "confidence level"),
        (r"0\.000 Noise SD", "a table cell quoted as text"),
        (r"FY\d{4}", "fiscal year"),
    ]

    flat = ours(LETTER.read_text())
    nocomma0 = flat.replace(",", "")
    checks, fails, claimed = [], [], set()
    for anchor, lit, val in BIND:
        if lit is None:
            continue
        a = anchor[:-1] if anchor.endswith("$") and not anchor.endswith("\\$") else anchor
        forms = [lit, lit.replace("-", "\u2212"), lit.replace("\u2212", "-")]
        hits = []
        for form in dict.fromkeys(forms):
            hits = list(re.finditer(a.replace(",", "") + re.escape(form.replace(",", "")),
                                    nocomma0))
            if hits:
                lit = form; break
        if not hits:
            hits = list(re.finditer(a + re.escape(lit), flat))
        if not hits:
            checks.append((f"{lit!r} after /{anchor[:34]}/", "anchored", "ANCHOR NOT FOUND", False))
            fails.append(f"{lit} anchor"); continue
        for h in hits:
            claimed.add((h.end() - len(lit), h.end()))
        ok = rounds_to(val, lit)
        checks.append((f"{lit!r} after /{anchor[:34]}/", lit,
                       "n/a" if val is None else f"{val:.6g}", ok))
        if not ok:
            fails.append(f"{lit} value")

    nocomma = flat.replace(",", "")
    unclaimed, exempted = [], {}
    for m in re.finditer(r"(?<![\w.])(?:−|-)?\d+(?:\.\d+)?%?(?![\w])", nocomma):
        if any(m.start() >= a and m.end() <= b for a, b in claimed):
            continue
        why = None
        for pat, desc in EXEMPT_SPANS:
            for em in re.finditer(pat, nocomma):
                if em.start() <= m.start() and m.end() <= em.end():
                    why = desc; break
            if why:
                break
        if why:
            exempted[why] = exempted.get(why, 0) + 1
        else:
            ctx = nocomma[max(0, m.start() - 86):m.end() + 34]
            unclaimed.append((m.group(0), re.sub(r"\s+", " ", ctx)))

    w = max(len(c[0]) for c in checks)
    for label, exp, act, ok in checks:
        print(f"  {'ok  ' if ok else 'FAIL'} {label:{w}}  letter={exp}  artifact={act}")
    n_lit = len(re.findall(r"(?<![\w.])(?:−|-)?\d+(?:\.\d+)?%?(?![\w])", nocomma))
    print(f"\n[lbind] {len(checks) - len(fails)}/{len(checks)} letter literals read from the "
          f"letter and bound to artifacts")
    print(f"[lbind] coverage: {n_lit} numeric literals in our own text, {len(claimed)} claimed "
          f"by a bound row, {len(unclaimed)} unclaimed")
    for why, n in sorted(exempted.items(), key=lambda kv: -kv[1]):
        print(f"          exempt x{n:<3} {why}")
    if unclaimed:
        print("[lbind] UNCLAIMED (bind or exempt each one):")
        for v, ctx in unclaimed:
            print(f"          {v:>10}  ...{ctx}")
    if fails:
        print(f"[lbind] MISMATCHED: {sorted(set(fails))}")
    return 1 if (fails or unclaimed) else 0


if __name__ == "__main__":
    raise SystemExit(main())

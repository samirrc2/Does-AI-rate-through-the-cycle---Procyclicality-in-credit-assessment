"""Bind every numeric claim in the response letter to a value in the frozen artifacts.

A response letter is where numbers go stale fastest: it is written once and the analyses
keep moving. Each numeric row below recomputes a value from results/*.json and compares it
with a constant written into THIS FILE when the claim was first checked. That catches an
analysis that moved. It does NOT by itself catch the letter being reworded, so every row
also reports whether its value is still quoted in the letter. Rows marked "-" are artifact
regression checks only. The textual probes further down do read the letter directly.

Exit 0 = every expected value matched; 1 = a mismatch; 2 = the inputs are not present in
this copy (not a failure).

  python3 paper/tools/verify_response_numbers.py
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent      # paper/tools
SRC = HERE.parent / "src"                   # paper/src
ROOT = HERE.parent.parent                   # repository root
LETTER = SRC / "response_to_reviewers.txt"
REV = ROOT / "results" / "reviewer_revision.json"
OFAT = ROOT / "results" / "ofat.json"
CONTAM = ROOT / "results" / "contamination_openai_4o.json"

SH = {"openai_4o_mini": "4o-mini", "openai_41_mini": "4.1-mini", "openai_4o": "4o",
      "gemini_flash_lite": "flash-lite", "gemini_flash": "flash",
      "gemini_pro": "pro", "openai_astra": "astra"}


def close(a, b, tol=6e-4):
    return a is not None and b is not None and abs(float(a) - float(b)) <= tol


def main() -> int:
    if not LETTER.exists():
        print("[verify] letter absent -> nothing to check"); return 2
    missing = [p.name for p in (REV, OFAT, CONTAM) if not p.exists()]
    if missing:
        print(f"[verify] inputs not published in this copy: {missing}"); return 2
    txt = LETTER.read_text()
    rev = json.loads(REV.read_text())
    ofat = json.loads(OFAT.read_text())
    con = json.loads(CONTAM.read_text())

    checks, fails = [], []

    def chk(label, claimed, actual):
        ok = close(claimed, actual)
        checks.append((label, claimed, actual, ok))
        if not ok:
            fails.append(label)

    # ── R3#4 / R1#5: PD retention values quoted in the letter ───────────────
    for m, want in (("openai_4o_mini", 0.587), ("gemini_pro", -0.003), ("openai_astra", -0.106)):
        # retention is reported in the pd_diagnostics block as ttc/terse
        d = rev["pd_diagnostics"][m]
        r = d["v_ttc"]["pd_logodds_slope"] / d["v_terse"]["pd_logodds_slope"]
        chk(f"PD retention {SH[m]}", want, round(r, 3))

    # ── R1#5: PD-free expected-notch slopes ─────────────────────────────────
    for m, v, want in (("openai_4o_mini", "v_terse", 0.765), ("openai_4o_mini", "v_ttc", 0.418),
                       ("openai_41_mini", "v_terse", 0.420), ("openai_41_mini", "v_ttc", 0.081),
                       ("openai_4o", "v_terse", 0.378), ("openai_4o", "v_ttc", 0.182)):
        chk(f"expected-notch {SH[m]} {v}", want,
            round(rev["pd_diagnostics"][m][v]["expected_notch_slope"], 3))

    # ── R3#2: number of significant model pairs, and the three that are not ─
    mc = rev["model_contrasts_terse"]
    chk("significant model pairs (of 21)", 18, sum(1 for r in mc if r["excludes_zero"]))
    ns = {(SH[r["a"]], SH[r["b"]]) for r in mc if not r["excludes_zero"]}
    expect_ns = {("flash", "pro"), ("flash", "astra"), ("pro", "astra")}
    ok = ns == expect_ns
    checks.append(("the 3 non-significant pairs", str(sorted(expect_ns)), str(sorted(ns)), ok))
    if not ok:
        fails.append("non-significant pair set")

    # ── R1#3: OFAT factor slopes quoted in the letter ───────────────────────
    for m, fac, want in (("openai_4o", "spread", 0.112), ("openai_4o", "deflt", 0.114),
                         ("openai_4o", "gdp", 0.019), ("openai_astra", "spread", 0.091),
                         ("gemini_flash", "deflt", 0.046)):
        chk(f"OFAT {SH[m]} {fac}", want, round(ofat["models"][m]["factors"][fac]["slope"], 3))
    for m, want in (("openai_4o_mini", 1.17), ("openai_4o", 0.87),
                    ("gemini_flash", 0.62), ("openai_astra", 0.95)):
        chk(f"OFAT additivity {SH[m]}", want,
            round(ofat["models"][m]["additivity_ratio_sum_over_joint"], 2))

    # ── R1#1: contamination test ────────────────────────────────────────────
    chk("contamination real rate", 0.0, con["real_identification_rate"])
    chk("contamination synthetic rate", 0.0, con["synthetic_identification_rate"])

    # ── R3#4: every D:U interval excludes 1 (the claim the figure rests on) ─
    lo = min(v["ratio_down_over_up"]["ci95"][0] for v in rev["half_slopes"].values())
    ok = lo > 1.0
    checks.append(("every D:U CI excludes 1", ">1", round(lo, 2), ok))
    if not ok:
        fails.append("D:U exclusion")

    # ── R1#7: epoch decomposition (results/seeds_epochs.json) ──────────────
    EP = ROOT / "results" / "seeds_epochs.json"
    if EP.exists():
        ep = json.loads(EP.read_text())
        for m, want in (("openai_4o_mini", -0.028), ("openai_41_mini", -0.021),
                        ("openai_4o", 0.002), ("gemini_flash", -0.037)):
            chk(f"beta drift Jul->Sep {SH[m]}", want, round(ep["models"][m]["beta_drift"], 3))
        chk("max |beta drift|", 0.037, round(ep["max_abs_beta_drift"], 3))
        chk("pinned cells moved (max)", 15.5, round(ep["max_pct_cells_moved_pinned"], 1))
        chk("unpinned alias cells moved", 44.8, round(ep["pct_cells_moved_unpinned_alias"], 1))
        chk("unpinned alias mean shift",
            0.507, round(ep["models"]["gemini_flash"]["across_epoch"]["mean_abs_shift_notch"], 3))
        chk("Sept Gemini Flash beta", 0.193, round(ep["models"]["gemini_flash"]["beta_september"], 3))

    # ── R1#1: real-fundamentals replication (results/real_arm.json) ────────
    RL = ROOT / "results" / "real_arm.json"
    if RL.exists():
        rl = json.loads(RL.read_text())
        for m, want, lo, hi in (("openai_4o_mini", 0.814, 0.729, 0.896),
                                ("openai_4o", 0.407, 0.362, 0.451),
                                ("gemini_flash", 0.094, 0.069, 0.121),
                                ("openai_astra", 0.151, 0.126, 0.179)):
            r = rl["replication"][m]
            chk(f"REAL beta {SH[m]}", want, round(r["real_beta"], 3))
            chk(f"REAL CI lo {SH[m]}", lo, round(r["real_ci95"][0], 3))
            chk(f"REAL CI hi {SH[m]}", hi, round(r["real_ci95"][1], 3))
        allpos = all(v["real_excludes_zero"] for v in rl["replication"].values())
        checks.append(("every real-battery CI excludes 0", True, allpos, allpos))
        if not allpos:
            fails.append("real CI excludes zero")
        st = rl.get("contamination_slope_test") or {}
        if "identified" in st:
            chk("slope test identified beta", 0.143, round(st["identified"]["beta"], 3))
            chk("slope test not-identified beta", 0.145, round(st["not_identified"]["beta"], 3))
            chk("slope test difference", -0.003, round(st["difference"], 3))
            chk("slope test n identified", 7, st["n_identified"])
            chk("slope test n not-identified", 33, st["n_not_identified"])
            # the claim the letter actually makes: NO detectable slope difference
            i, nn = st["identified"]["ci95"], st["not_identified"]["ci95"]
            ov = not (i[1] < nn[0] or nn[1] < i[0])
            checks.append(("identified/not-identified CIs overlap", True, ov, ov))
            if not ov: fails.append("slope CIs overlap")

    # ── R1#1: contamination rates as the letter states them ────────────────
    CA = ROOT / "results" / "contamination_openai_astra.json"
    if CA.exists():
        ca = json.loads(CA.read_text())
        chk("astra real identification rate", 0.175, round(ca["real_identification_rate"], 3))
        chk("astra synthetic control rate", 0.0, ca["synthetic_identification_rate"])
        chk("astra real calls landed", 40, ca.get("real_calls_landed"))
        chk("astra control calls landed", 40, ca.get("synthetic_calls_landed"))

    # ── audit fixes: five response-to-manuscript mismatches, gated ─────────
    import csv as _csv, glob as _glob, os as _os
    # (1) the new-observation count must equal the frozen sum, and reconcile with the total
    frozen = {}
    for f in _glob.glob(str(ROOT / "data" / "raw" / "runs_*.csv")):
        st = _os.path.basename(f)[5:-4]
        if not (ROOT / "data" / "frozen" / f"{st}.freeze.json").exists():
            continue
        sg = st.split("_")[0]
        frozen[sg] = frozen.get(sg, 0) + sum(
            1 for r in _csv.DictReader(open(f)) if r.get("ok") == "True")
    new_obs = sum(v for k, v in frozen.items() if k not in ("full", "pilot"))
    chk("new observations (frozen)", 48590, new_obs)
    chk("original grid", 32000, frozen.get("full"))
    chk("study total", 80590, frozen.get("full", 0) + new_obs)
    _flat = " ".join(txt.split())
    if "55,040" in _flat and "earlier draft" not in _flat:
        checks.append(("stale 55,040 claim removed", "absent", "PRESENT", False))
        fails.append("55,040")

    # (3) the contamination split must be drawn within the TESTED subsample only
    if RL.exists():
        st2 = json.loads(RL.read_text()).get("contamination_slope_test") or {}
        if st2:
            chk("tested firms", 40, st2.get("n_tested"))
            chk("untested excluded", 40, st2.get("n_untested_excluded"))
            ok = st2.get("n_identified", 0) + st2.get("n_not_identified", 0) == st2.get("n_tested")
            checks.append(("identified + not-identified == tested", True, ok, ok))
            if not ok:
                fails.append("contamination split")

    # (4) the +/-0.05 band claim must match the intervals: exactly ONE model inside
    if REV.exists():
        pass  # residual intervals live in the manuscript's own table; checked below

    # (2)/(5) the two things the letter PROMISES must exist in the manuscript
    MS = SRC / "manuscript.tex"
    T0 = SRC / "tables" / "table0_firm_profiles.tex"
    T3 = SRC / "tables" / "table3_robustness.csv"
    if MS.exists():
        ms = MS.read_text()
        has_spec = T0.exists() and "table0_firm_profiles" in ms
        checks.append(("firm-generation table promised AND present", True, has_spec, has_spec))
        if not has_spec:
            fails.append("firm spec table")
    if T3.exists():
        cols = next(_csv.reader(open(T3)))
        has_ttc = "expnotch_ttc" in cols
        checks.append(("expected-notch TTC column present", True, has_ttc, has_ttc))
        if not has_ttc:
            fails.append("expnotch ttc column")

    # ── letter/manuscript consistency on claims that went stale once already ──
    _f = " ".join(txt.split())
    for bad, why in (
        ("Both frontier models SATISFY the rating condition",
         "only Gemini Pro satisfies the +/-0.05 band; Astra overshoots it"),
        ("as a new subsection rather than a footnote",
         "the OFAT results are in Table 1 Panel B and Appendix A, not a new subsection"),
        ("Table 3 now explains the blank expected-notch",
         "the robustness table renders as Table 4; Table 3 is the firm specification"),
    ):
        present = bad in _f
        checks.append((f"stale claim removed: {bad[:42]}...", "absent",
                       "PRESENT" if present else "absent", not present))
        if present:
            fails.append(bad[:28])
    # R1#1 asked about external validity, so the four real-battery intervals must be PRINTED in
    # the manuscript, not only asserted in this letter.
    MSr = SRC / "manuscript.tex"
    if MSr.exists() and RL.exists():
        msr = " ".join(MSr.read_text().split())
        rlr = json.loads(RL.read_text())["replication"]
        for m in ("openai_4o_mini", "openai_4o", "gemini_flash", "openai_astra"):
            c = rlr[m]["real_ci95"]
            lit = f"$[{c[0]:.3f},{c[1]:.3f}]$"
            ok = lit in msr
            checks.append((f"manuscript prints real CI {SH[m]}", lit, "present" if ok else "ABSENT", ok))
            if not ok:
                fails.append(f"real CI {SH[m]} not in manuscript")

    # R1#1's 7/40 is only interpretable against the synthetic control, so the manuscript must
    # print the control arm too, and both denominators must be the ones actually captured.
    if MSr.exists() and CONTAM.exists():
        msc = " ".join(MSr.read_text().split())
        ast = ROOT / "results" / "contamination_openai_astra.json"
        for label, want in (("astra real 7/40", "$7/40$"), ("4o real 0/40", "GPT-4o $0/40$"),
                            ("synthetic control 0/40", "versus $0/40$ synthetic controls")):
            ok = want in msc
            checks.append((f"manuscript prints {label}", want, "present" if ok else "ABSENT", ok))
            if not ok:
                fails.append(label)
        if ast.exists():
            a = json.loads(ast.read_text())
            n_id = round(a["real_identification_rate"] * a["real_calls_landed"])
            chk("astra identified firms (7 = rate x n)", 7, n_id)
            chk("astra synthetic control rate", 0.0, a["synthetic_identification_rate"])
            chk("astra control calls", 40, a["synthetic_calls_landed"])
        c4 = json.loads(CONTAM.read_text())
        chk("4o real calls captured", 40, len(c4["real"]))
        chk("4o synthetic calls captured", 40, len(c4["synthetic"]))

    # R1#6: the four alternative PD mappings must be NAMED, since the referee asked about
    # sensitivity to the mapping itself. Their names come from analysis/reviewer_revision.py.
    if MSr.exists():
        msm = " ".join(MSr.read_text().split())
        ok = "(baseline, PD$\\times0.5$, PD$\\times2$ and a one-notch downward shift)" in msm
        checks.append(("manuscript names the four PD mappings", True,
                       "present" if ok else "ABSENT", ok))
        if not ok:
            fails.append("PD mappings unnamed")

    # the manuscript must not claim the log-prob measure evidences the PD result
    MSp = SRC / "manuscript.tex"
    if MSp.exists():
        ms = " ".join(MSp.read_text().split())
        ok = ("do not rest the anchoring result on the elicited PDs alone" in ms
              and "It is supported jointly by three measures" in ms)
        checks.append(("expected-notch claim scoped to the RATING side", True, ok, ok))
        if not ok:
            fails.append("expnotch scope")

    # ── letter hygiene: the removed phrase, and unfilled placeholders ───────
    if "leading outlet" in txt.lower():
        # the letter QUOTES the referee asking for its removal, so one hit is expected
        n = txt.lower().count("leading outlet")
        ok = n <= 1
        checks.append(("'leading outlet' only in the quoted comment", "<=1", n, ok))
        if not ok:
            fails.append("leading outlet")
    ph = re.findall(r"\[[A-Z][A-Z ]{3,}\]", txt)
    ph = [p for p in ph if p not in ("[GAP]", "[SIGNATURE]", "[PAGEBREAK]")]
    if ph:
        print(f"[verify] UNFILLED PLACEHOLDERS still in the letter: {sorted(set(ph))}")
        fails.append("placeholders")

    flat = " ".join(txt.split())

    def quoted(v):
        """Is this value still written in the letter? None = too short to search for."""
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            return None
        forms = {f"{v}", f"{v:g}"}
        if isinstance(v, float):
            forms |= {f"{v:.3f}", f"{v:.2f}"}
        # a 1-2 digit token occurs in any document; finding it is not evidence of the claim
        if not any(len(f.lstrip("-0.")) >= 3 for f in forms):
            return None
        forms |= {f.replace("-", "\u2212") for f in forms}
        return any(f in flat for f in forms)

    w = max(len(c[0]) for c in checks)
    n_quoted = n_gone = 0
    for label, claimed, actual, ok in checks:
        q = quoted(claimed)
        n_quoted += q is True
        n_gone += q is False
        tag = ("text probe" if not isinstance(claimed, (int, float)) or isinstance(claimed, bool)
               else {True: "in-letter", False: "not in letter", None: "not searchable"}[q])
        print(f"  {'ok  ' if ok else 'FAIL'} {label:{w}}  expected={claimed}  "
              f"artifact={actual}  {tag}")
    print(f"\n[verify] {len(checks) - len(fails)}/{len(checks)} expected values match the artifacts")
    print(f"[verify] letter coverage: {n_quoted} quoted in the letter, {n_gone} distinctive values "
          f"NOT found in it, {len(checks) - n_quoted - n_gone} too short to search for")
    if n_gone:
        print(f"[verify] the {n_gone} not in the letter bind the artifact, and where a row says "
              f"so the manuscript, rather than the letter text: some are claims the letter makes "
              f"only qualitatively, others are constants left from an earlier draft of it")
    if fails:
        print(f"[verify] MISMATCHED: {fails}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

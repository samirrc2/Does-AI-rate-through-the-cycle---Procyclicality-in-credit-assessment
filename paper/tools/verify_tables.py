"""Re-derive every cell of every table from the frozen artifacts.

The generators read claims_revision.json, so a table is reproducible by construction. That is
not the same as correct: a generator can read the wrong key, or print at a precision that loses
the value it claims to report. This parses the generated .tex files and recomputes each cell
from the artifacts independently of the generator that wrote it. It found one real defect --
the EBITDA/interest row printed at 0 dp, so the generator's 1.6-3.2 band read as "2 to 3" and
0.4-1.6 as "0 to 2".

  python3 paper/tools/verify_tables.py

Exit 0 = every cell matches; 1 = a mismatch; 2 = artifacts absent (not a pass).
"""
import json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "src"
ROOT = HERE.parent.parent
TBL = SRC / "tables"
sys.path.insert(0, str(ROOT / "capture")); sys.path.insert(0, str(ROOT / "config"))


def jload(rel):
    p = ROOT / rel
    return json.loads(p.read_text()) if p.exists() else None


def main() -> int:
    C = jload("claims_revision.json"); REV = jload("results/reviewer_revision.json")
    RL = jload("results/real_arm.json"); EP = jload("results/seeds_epochs.json")
    OF = jload("results/ofat.json")
    if any(x is None for x in (C, REV, RL, EP, OF)) or not TBL.exists():
        print("[tables] artifacts or tables absent -> not checkable here"); return 2
    try:
        import build_firms as BF
    except Exception as e:
        print(f"[tables] cannot import build_firms ({e}) -> not checkable here"); return 2

    pm, pv = C["per_model_variant"], C["per_variant_pooled"]
    state = {"ok": 0, "fails": []}

    def chk(what, lit, val, dp):
        if lit is None and val is None:
            state["ok"] += 1; return
        good = (lit is not None and val is not None
                and abs(round(val, dp) - lit) < 10 ** -(dp + 3))
        if good:
            state["ok"] += 1
        else:
            state["fails"].append(what)
            print(f"  FAIL {what}: table={lit} artifact={val}")

    def eq(what, got, want):
        if str(got).strip() == str(want).strip():
            state["ok"] += 1
        else:
            state["fails"].append(what)
            print(f"  FAIL {what}: table={got} artifact={want}")

    def num(s):
        s = re.sub(r"\$|\^\{\\dagger\}|\\dagger|\{|\}", "", s).strip()
        return None if s in ("", "--") else float(s)

    def rowmap(text, labels):
        out = {}
        for line in text.split("\n"):
            for lb in labels:
                if line.startswith(lb + " &"):
                    out[lb] = [c.strip() for c in line.rstrip().rstrip("\\\\").split("&")]
        return out

    DISP = {"gemini_pro": "Gemini Pro", "openai_astra": "GPT-6 Astra",
            "gemini_flash": "Gemini Flash", "gemini_flash_lite": "Gemini Flash-Lite",
            "openai_4o": "GPT-4o", "openai_41_mini": "GPT-4.1-mini",
            "openai_4o_mini": "GPT-4o-mini"}
    FACTORS = ["gdp", "unemp", "spread", "deflt", "standards"]

    # ── Table 1: per-model, two panels, same row labels in each ──────────────
    allt = (TBL / "table1_per_model.tex").read_text()
    parts = allt.split(r"\emph{Panel B")
    PA, PB = parts[0], parts[-1]
    ra = rowmap(PA, list(DISP.values()))
    for m, d in DISP.items():
        c = ra.get(d)
        if not c:
            state["fails"].append(f"T1 row {d} missing"); print(f"  FAIL T1 row {d} missing"); continue
        t = pm[f"{m}|v_terse"]
        chk(f"T1 {d} beta", num(c[1].split(" [")[0]), t["cyclicality_notch_per_step"], 3)
        lo, hi = [float(x) for x in c[1].split("[")[1].rstrip("]").split(",")]
        chk(f"T1 {d} CI lo", lo, t["cyclicality_ci95"][0], 2)
        chk(f"T1 {d} CI hi", hi, t["cyclicality_ci95"][1], 2)
        chk(f"T1 {d} swing", num(c[2]), t["endpoint_swing_notches"], 2)
        chk(f"T1 {d} D:U", num(c[3]), REV["half_slopes"][m]["ratio_down_over_up"]["point"], 1)
        tt = pm.get(f"{m}|v_ttc", {})
        chk(f"T1 {d} resid", num(c[4].split(" [")[0]), tt.get("cyclicality_notch_per_step"), 3)
        pdd = REV["pd_diagnostics"][m]
        chk(f"T1 {d} PD-ret", num(c[5]),
            pdd["v_ttc"]["pd_logodds_slope"] / pdd["v_terse"]["pd_logodds_slope"], 2)
        rb = RL["replication"].get(m)
        chk(f"T1 {d} beta real", num(c[6]), rb["real_beta"] if rb else None, 3)
        em = (EP.get("models") or {}).get(m)
        drift = (em["beta_september"] - em["beta_july"]) if em and "beta_july" in em else None
        chk(f"T1 {d} drift", num(c[7]), drift, 3)
    rb_ = rowmap(PB, list(DISP.values()))
    for m, d in DISP.items():
        c = rb_.get(d)
        if not c:
            continue
        o = OF["models"][m]
        for i, key in enumerate(FACTORS, start=1):
            f = o["factors"].get(key, {})
            chk(f"T1B {d} {key}", num(c[i]), f.get("slope"), 3)
            # the dagger must mark exactly the intervals that include zero
            eq(f"T1B {d} {key} dagger", "dagger" in c[i], not f.get("excludes_zero"))
        chk(f"T1B {d} additivity", num(c[6]), o["additivity_ratio_sum_over_joint"], 2)

    # ── Table 2: instruction gradient ────────────────────────────────────────
    VAR = {"Point-in-time": "v_pit", "Terse": "v_terse", '"Be stable"': "v_stable",
           "Through-the-cycle": "v_ttc"}
    r2 = rowmap((TBL / "table2_instruction_gradient.tex").read_text(), list(VAR))
    for lb, v in VAR.items():
        c = r2.get(lb)
        if not c:
            state["fails"].append(f"T2 row {lb} missing"); print(f"  FAIL T2 row {lb} missing"); continue
        p = pv[v]
        chk(f"T2 {lb} beta", num(c[1]), p["pooled_cyclicality_notch_per_step"], 3)
        lo, hi = [float(x) for x in c[2].split("[")[1].rstrip("]").split(",")]
        chk(f"T2 {lb} lo", lo, p["pooled_cyclicality_ci95"][0], 2)
        chk(f"T2 {lb} hi", hi, p["pooled_cyclicality_ci95"][1], 2)
        eq(f"T2 {lb} excl0", c[3], "Yes" if p["ci_excludes_0"] else "No")

    # ── Table 4 (file table3_robustness.tex) ─────────────────────────────────
    r4 = rowmap((TBL / "table3_robustness.tex").read_text(), list(DISP.values()))
    for m, d in DISP.items():
        c = r4.get(d)
        if not c:
            state["fails"].append(f"T4 row {d} missing"); print(f"  FAIL T4 row {d} missing"); continue
        t = pm[f"{m}|v_terse"]
        tt = pm.get(f"{m}|v_ttc", {})
        chk(f"T4 {d} beta", num(c[1]), t["cyclicality_notch_per_step"], 3)
        chk(f"T4 {d} net", num(c[2]), t.get("net_cyclicality_notch_per_step"), 3)
        chk(f"T4 {d} expn terse", num(c[3]), t.get("expected_notch_cyclicality_per_step"), 3)
        chk(f"T4 {d} expn ttc", num(c[4]), tt.get("expected_notch_cyclicality_per_step"), 3)
        chk(f"T4 {d} noise SD", num(c[5]), t.get("noise_floor_notch_sd"), 3)
        chk(f"T4 {d} probit", num(c[6]),
            (t.get("ordered_probit") or {}).get("notch_per_step"), 3)

    # ── Table 2's caption points outside the paper: verify what it promises ──
    t2 = (TBL / "table2_instruction_gradient.tex").read_text()
    if "frontier models' framing gradients are reported in the replication" in t2:
        EX = jload("results/revision_extras.json") or {}
        fg = (EX.get("frontier_gradient") or {}).get("models") or {}
        for m in ("gemini_pro", "openai_astra"):
            got = fg.get(m) or {}
            have = [v for v in ("v_pit", "v_terse", "v_stable", "v_ttc")
                    if (got.get(v) or {}).get("ci95")]
            eq(f"T2 caption: archive holds {m} framing gradient", len(have), 4)

    # ── Table 3 (file table0_firm_profiles.tex): the generation spec ─────────
    P = BF._TIER_PROFILE
    TIERS = ["high_ig", "low_ig", "crossover", "high_yield", "distressed"]
    LBL = {"Revenue (USD m)": "revenue_musd", "Revenue growth (\\%)": "rev_growth_pct",
           "EBITDA margin (\\%)": "ebitda_margin_pct",
           "Net debt / EBITDA ($\\times$)": "net_debt_to_ebitda",
           "EBITDA / interest ($\\times$)": "ebitda_to_interest",
           "FCF margin (\\%)": "fcf_margin_pct", "Current ratio": "current_ratio",
           "Retained earnings / assets": "retained_earn_to_assets",
           "Working capital / assets": "wc_to_assets"}
    t0 = (TBL / "table0_firm_profiles.tex").read_text()
    for lb, key in LBL.items():
        line = next((l for l in t0.split("\n") if l.startswith(lb + " &")), None)
        if line is None:
            state["fails"].append(f"T3 row {key} missing"); print(f"  FAIL T3 row {key} missing"); continue
        cs = [c.strip() for c in line.rstrip().rstrip("\\\\").split("&")][1:]
        for tier, cell in zip(TIERS, cs):
            spec = P[tier].get(key)
            if spec is None:
                eq(f"T3 {key}/{tier} absent", cell, "--"); continue
            got = [float(x.replace("$-$", "-").replace("$", "")) for x in cell.split(" to ")]
            for g, w in zip(got, spec):
                nd = len(str(g).split(".")[1]) if "." in str(g) else 0
                chk(f"T3 {key}/{tier}", g, float(w), nd)

    n = state["ok"] + len(state["fails"])
    print(f"\n[tables] {state['ok']}/{n} table cells re-derived from the artifacts and matched")
    if state["fails"]:
        print(f"[tables] MISMATCHED: {state['fails'][:12]}")
    return 1 if state["fails"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Pilot verdict writer. Reads claims.json (produced by analysis/run.py) and writes
pilot/PILOT_RESULTS.md (the numbers) and pilot/PILOT_VERDICT.md (the three
pre-registered PASS criteria, each GREEN/RED, ending in exactly one verdict line).
Never decides to run the full grid — it only reports and stops.

  python pilot/verdict.py [--claims ../claims.json]
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_CLAIMS = _HERE.parent / "claims.json"


def _fmt(x, nd=3):
    if x is None:
        return "n/a"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


def _ci(pair, nd=2):
    if not pair or pair[0] is None or pair[1] is None:
        return "[n/a]"
    return f"[{pair[0]:.{nd}f}, {pair[1]:.{nd}f}]"


def build(claims: dict) -> tuple[str, str, str]:
    m = claims["meta"]
    g = claims["pilot_gate"]
    h = claims["headline_cyclicality"]
    disp = claims["ratings_dispersion"]
    pv = claims["per_variant_pooled"]
    con = claims["instruction_effect_contrasts"]

    # Criterion 1 = the PRE-REGISTERED threshold: error_rate <= 2% (freeze.py enforces
    # this per capture, so every frozen CSV is already <= 2%) AND spend <= cap. A single
    # stray 429 in thousands of live calls is exactly the noise the 2% tolerance exists
    # for; requiring literally 0 errors is unachievable in live capture (DECISIONS D17).
    c1 = bool(g["criterion_1_ran_clean"])
    c2 = bool(g["criterion_2_ratings_measurable"])
    c3 = bool(g["criterion_3_cyclicality_estimable"])

    # verdict precedence: degenerate-ratings KILL > operational FAIL > estimability FAIL > PASS
    if not c2:
        verdict = (f"PILOT: KILL (criterion 2 — ratings degenerate/censored: mean notch "
                   f"{_fmt(disp['mean_notch'],1)}, sd {_fmt(disp['sd_notch'],2)}, "
                   f"{disp['distinct_notches']} distinct, parse {_fmt(disp['parse_rate'],2)}; "
                   f"no dispersion for a macro shift to move -> nothing to measure)")
    elif not c1:
        verdict = (f"PILOT: FAIL (criterion 1 — did not run clean: "
                   f"error_rate={_fmt(m['error_rate'])}, spend=${_fmt(g['spend_usd'],4)}/"
                   f"cap ${_fmt(m['budget_cap_usd'],2)})")
    elif not c3:
        verdict = ("PILOT: FAIL (criterion 3 — cyclicality coefficient not estimable: "
                   "no finite bootstrap CI, or the ordered-probit null did not fit)")
    else:
        verdict = "PILOT: PASS → cleared for full run"

    # scientific read (does not gate PASS; a well-measured TTC null is a result)
    coef = h["pooled_notch_per_step"]
    excl0 = h["ci_excludes_0"]
    if coef is None:
        finding = "cyclicality not estimated"
    elif excl0 and coef > 0:
        finding = (f"PROCYCLICAL: {_fmt(coef)} notches downgraded per +1 macro-severity "
                   f"step (CI {_ci(h['pooled_ci95'])} excludes 0)")
    elif excl0 and coef < 0:
        finding = f"COUNTERCYCLICAL: {_fmt(coef)} notch/step (CI {_ci(h['pooled_ci95'])})"
    else:
        finding = (f"THROUGH-THE-CYCLE consistent: {_fmt(coef)} notch/step, CI "
                   f"{_ci(h['pooled_ci95'])} includes 0 (no procyclicality detected)")

    # demand-effect-adjusted (net of placebo) read
    net_line = ""
    if m.get("has_placebo"):
        nc = h.get("pooled_net_cyclicality"); pc = h.get("pooled_placebo_cyclicality")
        net_line = (f"Demand-effect control: placebo slope **{_fmt(pc)}** notch/step "
                    f"(frame-compliance floor) → **NET {_fmt(nc)}** notch/step, CI "
                    f"{_ci(h.get('pooled_net_ci95'))} (excludes 0: {h.get('net_ci_excludes_0')}). "
                    f"The net is the procyclicality that survives after removing pure "
                    f"suggestibility to a matched, credit-irrelevant frame.")

    def mark(ok): return "🟢 GREEN" if ok else "🔴 RED"

    verdict_md = f"""# PILOT_VERDICT — P5 (Do LLMs Rate Through the Cycle?)

**Subgrid:** `{m['subgrid']}`  ·  **Mode:** `{m['mode']}`  ·  **Config hash:** `{m['config_hash']}`
**Models:** {', '.join(m['models'])}
**Macro axis:** {m['macro_states']}
**Firms:** pilot sha256 `{m['firms_sha256'].get('pilot','n/a')[:16]}...`  ·  **Analysis seed:** {m['analysis_seed']}  ·  **Bootstrap draws:** {m['bootstrap_draws']}

> Pre-registered pilot gate (PREREGISTRATION §5). All three must hold to clear the
> full run. This file only reports; it never starts the full run. Note: PASS gates
> on the design being able to MEASURE the coefficient — it does NOT require a
> particular sign. A tight CI around 0 (a genuine TTC null) is a valid result.

## Criterion 1 — Ran clean  {mark(c1)}
End-to-end, resumable, **{m['n_error']} ERROR** / {m['n_rows']} rows
({_fmt(m['error_rate'])} rate, threshold ≤ 0.02), total spend
**${_fmt(g['spend_usd'],4)}** ≤ cap **${_fmt(m['budget_cap_usd'],2)}**.
Every declared capture froze (freeze.py enforces ≤ 2% ERROR per CSV).

## Criterion 2 — Ratings measurable & dispersed  {mark(c2)}
Pooled rating notch: mean **{_fmt(disp['mean_notch'],1)}** (target interior band [4, 18]),
sd **{_fmt(disp['sd_notch'],2)}** (≥1.5), **{disp['distinct_notches']}** distinct notches (≥6),
parse rate **{_fmt(disp['parse_rate'],3)}** (≥0.90).
{'Dispersed & interior — a macro shift has room to move in either direction.' if c2 else 'DEGENERATE — no dispersion for a shift to register → KILL.'}

## Criterion 3 — Cyclicality coefficient estimable  {mark(c3)}
Headline pooled cyclicality ({h['primary_variant']}) = **{_fmt(coef)}** notches/step,
95% CI **{_ci(h['pooled_ci95'])}**; ordered-probit null estimable: **{g['probit_estimable']}**.
Scientific read: **{finding}**.
{net_line}

---

## {verdict}
"""

    # per-variant table
    var_rows = "\n".join(
        f"| {v} | {_fmt(d['pooled_cyclicality_notch_per_step'])} | "
        f"{_ci(d['pooled_cyclicality_ci95'])} | {d['ci_excludes_0']} | "
        f"{_fmt(d['pooled_endpoint_swing'])} |"
        for v, d in pv.items())

    con_rows = "\n".join(f"| {k} | {_fmt(val)} |" for k, val in con.items()) or "| (none) | — |"

    if m.get("has_placebo"):
        plac_rows = "\n".join(
            f"| {v} | {_fmt(d.get('pooled_cyclicality_notch_per_step'))} | "
            f"{_fmt(d.get('pooled_placebo_cyclicality'))} | "
            f"{_fmt(d.get('pooled_net_cyclicality'))} | {_ci(d.get('pooled_net_ci95'))} | "
            f"{d.get('net_ci_excludes_0')} |"
            for v, d in pv.items())
    else:
        plac_rows = "| (placebo arm not run) | — | — | — | — | — |"

    fps = m.get("system_fingerprints", {})
    fp_summary = ", ".join(f"{mk}={v.get('n_distinct')}" for mk, v in fps.items()) or "n/a"

    # per-(model,variant) headline
    pmv = claims["per_model_variant"]
    pmv_rows = "\n".join(
        f"| {d['model']} | {d['variant']} | {d['family']} | "
        f"{_fmt(d['cyclicality_notch_per_step'])} | {_ci(d['cyclicality_ci95'])} | "
        f"{_fmt(d['endpoint_swing_notches'])} | "
        f"{_fmt(d['ordered_probit'].get('notch_per_step'))} | "
        f"{d['ordered_probit'].get('estimator')} |"
        for d in pmv.values())

    results_md = f"""# PILOT_RESULTS — P5  (mode={m['mode']})

Config hash `{m['config_hash']}` · firms(pilot) `{m['firms_sha256'].get('pilot','n/a')[:16]}...` · seed {m['analysis_seed']} · draws {m['bootstrap_draws']}.
{m['n_rows']} rows, {m['n_error']} ERROR ({_fmt(m['error_rate'])}), spend ${_fmt(g['spend_usd'],4)}.
Firms: {m['n_firms']} · macro axis: {m['macro_states']}.

**Headline (primary arm `{h['primary_variant']}`, pooled across models):**
cyclicality = **{_fmt(coef)} notches downgraded per +1 macro-severity step**,
95% CI {_ci(h['pooled_ci95'])}; endpoint (boom→severe recession) swing =
{_fmt(h['pooled_endpoint_swing'])} notches. → **{finding}**

## Pooled cyclicality by prompt variant
| variant | notch/step | 95% CI | excludes 0 | endpoint swing |
|---|---|---|---|---|
{var_rows}

## Instruction-effect contrasts (does an explicit TTC instruction dampen procyclicality?)
| contrast | Δ notch/step |
|---|---|
{con_rows}

> A positive `terse_minus_ttc` / `pit_minus_ttc` means the explicit through-the-cycle
> instruction REDUCED procyclicality relative to the terse / point-in-time framing.

## Per model × variant
| model | variant | family | cyclicality (notch/step) | 95% CI | endpoint swing | probit notch/step | estimator |
|---|---|---|---|---|---|---|---|
{pmv_rows}

## Demand-effect control (placebo arm)
| variant | macro slope | placebo slope | NET (macro−placebo) | net CI | net excl. 0 |
|---|---|---|---|---|---|
{plac_rows}

> The placebo axis is a matched-format, credit-irrelevant gradient (regional
> weather/traffic). Movement across it is pure frame-compliance (suggestibility);
> the NET coefficient is the procyclicality that survives it — the number a referee
> can't dismiss as a demand effect.

## Robustness & determinism controls
- Cyclicality reported four ways: within-firm notch slope (primary), boom→recession
  endpoint swing, Amato–Furfine ordered-probit macro term, and — for OpenAI models —
  the **logprobs expected-notch** slope (continuous, ~many-seeds-from-one-call).
  {'Expected-notch available for ' + str(m.get('n_expected_notch',0)) + ' OpenAI cells.' if m.get('has_expected_notch') else 'Expected-notch: none captured (mock/Gemini-only run).'}
- PD is elicited in **basis points** and analyzed as **log-odds** + rank-correlation
  across states (ordinal-robust); PD is secondary and does not gate the pilot.
- **Noise floor** (within-cell seed dispersion of the notch) is reported per model×
  variant so the cyclicality signal can be read against residual non-determinism —
  vendor determinism is best-effort (seed omits macro state by design).
- **system_fingerprint** is logged per call; a mid-run change is a batch-effect
  covariate. Distinct fingerprints per model: {fp_summary}.

> {'MOCK data — pipeline validation only, NOT a scientific result (DECISIONS D1).' if m['mode']=='MOCK' else 'REAL capture.'}
"""
    return verdict, verdict_md, results_md


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--claims", default=str(_CLAIMS))
    args = ap.parse_args()
    claims = json.loads(Path(args.claims).read_text())
    verdict, verdict_md, results_md = build(claims)
    (_HERE / "PILOT_VERDICT.md").write_text(verdict_md)
    (_HERE / "PILOT_RESULTS.md").write_text(results_md)
    print(verdict_md)
    print("\n" + "=" * 70)
    print(verdict)
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())

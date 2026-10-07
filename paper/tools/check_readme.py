"""Bind the headline numbers in README.md to the artifacts that produce them.

A README is where a stale number survives longest: nothing builds it, so nothing catches it.
This one carried "32,000 ratings" after the study grew to 80,590, a pooled PD retention of
0.38 that no artifact had produced since the revision, and a capital figure from before the
Basel floor was applied.

  python3 paper/tools/check_readme.py

Exit 0 = every bound figure matches; 1 = a mismatch or a missing anchor; 2 = artifacts absent.
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
README = ROOT / "README.md"


WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
         "seven": 7, "eight": 8, "nine": 9, "ten": 10}


def _as_number(lit: str):
    """A bound literal may be written as digits, a percentage, or an English word."""
    t = lit.replace(",", "").rstrip("%")
    try:
        return float(t)
    except ValueError:
        return WORDS.get(t.lower())


def jload(rel):
    p = ROOT / rel
    return json.loads(p.read_text()) if p.exists() else None


def main() -> int:
    if not README.exists():
        print("[readme] README.md absent -> not checkable here"); return 2
    C = jload("claims_revision.json"); REV = jload("results/reviewer_revision.json")
    EX = jload("results/revision_extras.json")
    if any(x is None for x in (C, REV, EX)):
        print("[readme] artifacts not published in this copy -> not checkable here"); return 2

    pv = C["per_variant_pooled"]["v_terse"]
    flr = EX["basel_floor"]["floored"]

    def pdret(m):
        d = REV["pd_diagnostics"][m]
        return d["v_ttc"]["pd_logodds_slope"] / d["v_terse"]["pd_logodds_slope"]
    rets = [pdret(m) for m in REV["pd_diagnostics"]]

    import collections, glob
    rows, errs = collections.Counter(), collections.Counter()
    for f in glob.glob(str(ROOT / "data" / "frozen" / "*.freeze.json")):
        d = json.loads(Path(f).read_text())
        rows[d["subgrid"]] += d["n_rows"]; errs[d["subgrid"]] += d.get("n_error", 0)
    counted = [k for k in rows if k != "pilot"]
    retained = sum(rows[k] - errs[k] for k in counted)
    n_receipts = len(glob.glob(str(ROOT / "data" / "frozen" / "*.freeze.json")))

    ms = (ROOT / "paper" / "src" / "manuscript.tex").read_text()
    cited = set()
    for m in re.finditer(r"\\cite[a-z]*\*?(?:\[[^\]]*\])*\{([^}]*)\}", ms):
        cited |= {k.strip() for k in m.group(1).split(",") if k.strip()}
    bib = (ROOT / "paper" / "src" / "refs.bib").read_text()
    n_frl = len(re.findall(r"journal\s*=\s*\{Finance Research Letters\}", bib))
    n_amend = len(re.findall(r"^## AMENDMENT #", (ROOT / "PREREGISTRATION_AMENDMENTS.md").read_text(), re.M))

    # the gate threshold is owned by freeze.py; the README must not restate it independently
    _fz = (ROOT / "capture" / "freeze.py").read_text()
    _m = re.search(r"err_rate\s*>\s*([0-9.]+)", _fz)
    _gate_pct = float(_m.group(1)) * 100 if _m else None
    # and the pre-registration must agree with freeze.py, or the README cites a section that
    # no longer says what it claims
    _pre = (ROOT / "PREREGISTRATION.md").read_text()
    _rule = re.search(r"error_rate\s*(?:≤|<=|<)\s*([0-9.]+)\s*%", _pre)
    if _gate_pct is not None and (not _rule or abs(float(_rule.group(1)) - _gate_pct) > 1e-9):
        print(f"[readme] FAIL PREREGISTRATION.md does not state error_rate <= {_gate_pct:g}% "
              f"(found: {_rule.group(0) if _rule else 'no error_rate bound at all'})")
        return 1
    # a version string is not a float: compare it as text against the recorded environment
    _env = jload("results/environment.json") or {}
    _env_lit = {"python": _env.get("python"), "python_floor": _env.get("python_floor"),
                **(_env.get("packages") or {})}
    if not all(_env_lit.values()):
        print(f"[readme] FAIL results/environment.json is missing entries: "
              f"{[k for k, v in _env_lit.items() if not v]}")
        return 1

    # the floor the README states must be the floor reproduce.sh actually enforces
    _rs = (ROOT / "reproduce.sh").read_text()
    _g = re.search(r"sys\.version_info\s*>=\s*\((\d+),\s*(\d+)\)", _rs)
    _enforced = f"{_g.group(1)}.{_g.group(2)}" if _g else None
    if _enforced != _env_lit["python_floor"]:
        print(f"[readme] FAIL reproduce.sh enforces Python {_enforced}, "
              f"environment.json says the floor is {_env_lit['python_floor']}")
        return 1

    _never_frozen = (jload("results/revision_extras.json") or {}).get(
        "failed_calls", {}).get("captures_never_frozen", {})
    _n_seed_refused = sum(1 for k in _never_frozen if k.startswith("runs_seeds_"))

    txt = re.sub(r"\s+", " ", README.read_text())

    # (phrase the figure must follow, literal as printed, artifact value, decimals)
    BIND = [
        (r"frozen ", "80,590", retained, 0),
        (r"captures \(", "80,590", retained, 0),
        (r"Deposit contents:.{0,60}?", "80,590", retained, 0),
        (r"Pooled effect:\*\* ", "0.429", pv["pooled_cyclicality_notch_per_step"], 3),
        (r"95% CI \[", "0.41", pv["pooled_cyclicality_ci95"][0], 2),
        (r"95% CI \[0\.41, ", "0.45", pv["pooled_cyclicality_ci95"][1], 2),
        (r"a ", "1.76", pv["pooled_endpoint_swing"], 2),
        (r"recessions is ≈ ", "3.2", C["asymmetry"]["ratio"], 1),
        (r"retention runs from ", "0.587", max(rets), 3),
        (r"down to −", "0.106", abs(min(rets)), 3),
        (r"below the ", "0.75", 0.75, 2),
        (r"capital swings ≈ ", "1.81", flr["pooled_swing_pp"], 2),
        (r"\(95% CI \[", "1.67", flr["pooled_swing_ci95"][0], 2),
        (r"CI \[1\.67, ", "1.94", flr["pooled_swing_ci95"][1], 2),
        (r"Basel ", "0.05", 100 * EX["basel_floor"]["floor"], 2),
        (r"and all ", "57", n_receipts, 0),
        (r"refs\.bib\) \| ", "29", len(cited), 0),
        (r"29 references \(", "5", n_frl, 0),
        (r"post-freeze changes \(", "8", n_amend, 0),
        # ── capture-level error gate: the README restates numbers owned elsewhere ──
        (r"exceeds the ", "2%", _gate_pct, 2),
        (r"so ", "four", len(_never_frozen), 0),
        (r"rather than trimmed\. ", "Three", _n_seed_refused, 0),
    ] + [
        # ── environment: every version in the README comes from the receipt ──
        (anchor, _env_lit[k], _env_lit[k], None) for anchor, k in (
            (r"byte-for-byte under Python ", "python"),
            (r"with numpy ", "numpy"),
            (r"scipy ", "scipy"),
            (r"pydantic ", "pydantic"),
            (r"PyYAML ", "PyYAML"),
            (r"matplotlib ", "matplotlib"),
            (r"pymupdf ", "pymupdf"),
            (r"may also work; Python ", "python_floor"),
            (r"activate # Python ", "python_floor"),
        )
    ]
    fails, ok = [], 0
    for anchor, lit, val, dp in BIND:
        m = re.search(anchor + re.escape(lit), txt)
        if not m:
            fails.append(f"{lit} (anchor /{anchor[:28]}/ not found)"); continue
        if dp is None:                      # a version string, compared verbatim
            if lit != val:
                fails.append(f"{lit} != recorded environment {val}")
            else:
                ok += 1
            continue
        got = _as_number(lit)
        if got is None:
            fails.append(f"{lit} (not a number this gate can compare)"); continue
        if val is None or abs(round(val, dp) - got) > 10 ** -(dp + 3):
            fails.append(f"{lit} != artifact {val}")
        else:
            ok += 1
    print(f"[readme] {ok}/{len(BIND)} headline figures bound to the artifacts")
    for f in fails:
        print(f"  FAIL {f}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())

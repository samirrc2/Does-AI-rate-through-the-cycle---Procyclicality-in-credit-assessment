"""Mint the REAL-fundamentals firm battery from SEC XBRL — deterministic, offline, $0.

Referee 1 comments 1 and 2 ask for validation on real firms or historical financial
statements, and for evidence that the synthetic ratio distributions are representative.
This builds the same 80-firm battery shape from ACTUAL FY2024 filings, so the
fundamentals distribution is real by construction rather than argued for.

IDENTIFICATION, and why real *firms* would break it: if a model recognises the issuer it
can recall that issuer's actual rating, and the issuer's identity also implies a time
period -- which entangles firm identity with the macro state and destroys the
byte-identical counterfactual the whole design rests on. That objection attaches to
IDENTITY, not to the numbers. So this arm keeps the real ratios and strips the identity:

  * no company name, no ticker, no CIK, no SIC text reaches the serialized block
  * no calendar dates -- the block says "most recent fiscal year", exactly as the
    synthetic battery does
  * the serializer is IMPORTED from build_firms.py, so a real block and a synthetic
    block are byte-identical in FORM and differ only in the numbers
  * whether de-identification actually worked is MEASURED, not assumed: see
    capture/contamination_test.py, which asks each model to name the firm and reports
    the identification rate

Financials (SIC 6000-6499) are EXCLUDED: for a bank, EBITDA/interest and net
debt/EBITDA are not meaningful corporate-credit metrics, so including them would
corrupt the tier assignment.

  python capture/fetch_sec.py            # once, populates data/sec_cache/
  python capture/build_real_firms.py     # -> data/firms/real.jsonl + manifest
"""
from __future__ import annotations
import argparse, hashlib, json, random, sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent / "config"))
import build_firms as BF          # noqa: E402  -- serializer reused verbatim
import loader as C                # noqa: E402

_CACHE = _HERE.parent / "data" / "sec_cache"
_FIRMS = _HERE.parent / "data" / "firms"
_MANI = _HERE.parent / "manifest"

# ── SIC -> the eight sectors already in the synthetic battery ───────────────
_SIC_RANGES = [
    ((1200, 1399), "energy"), ((2900, 2999), "energy"), ((4600, 4699), "energy"),
    ((4900, 4999), "utilities"),
    ((6500, 6599), "real_estate"), ((6798, 6798), "real_estate"),
    ((2833, 2836), "healthcare"), ((3841, 3851), "healthcare"), ((8000, 8099), "healthcare"),
    ((3570, 3579), "technology"), ((3600, 3699), "technology"), ((7370, 7379), "technology"),
    ((2000, 2199), "consumer_staples"), ((5400, 5499), "consumer_staples"),
    ((2300, 2399), "consumer_discretionary"), ((5600, 5999), "consumer_discretionary"),
    ((7000, 7099), "consumer_discretionary"),
    ((1500, 1799), "industrials"), ((3400, 3599), "industrials"),
    ((3700, 3799), "industrials"), ((4000, 4599), "industrials"),
    # broadened after an initial build dropped 59 otherwise-usable filers for want of a
    # bucket. The sector label feeds ONLY stratification and the generic sector_note --
    # it enters no estimate -- so a coarse but exhaustive mapping is the right trade.
    ((2200, 2299), "consumer_discretionary"),          # textiles / carpets
    ((2800, 2899), "industrials"),                     # chemicals (no materials sector)
    ((3000, 3099), "industrials"),                     # rubber & plastics
    ((3100, 3399), "industrials"),                     # leather, stone, primary metals
    ((3900, 3999), "industrials"),                     # misc manufacturing
    ((4800, 4829), "technology"),                      # communications services
    ((4830, 4899), "consumer_discretionary"),          # broadcasting / media
    ((5000, 5199), "industrials"),                     # wholesale distribution
    ((5200, 5399), "consumer_discretionary"),          # general merchandise
    ((7300, 7369), "technology"),                      # business / IT services
    ((7380, 7399), "technology"),
    ((7800, 7999), "consumer_discretionary"),          # entertainment / recreation
    ((8100, 8299), "consumer_discretionary"),          # legal / educational services
    ((8700, 8799), "technology"),                      # consulting / engineering
]
_SECTOR_CODE = {"industrials": "IND", "consumer_staples": "CST",
                "consumer_discretionary": "CDI", "technology": "TEC",
                "utilities": "UTL", "healthcare": "HLT", "energy": "ENE",
                "real_estate": "RES"}
# generic sector prose, matched in style to the synthetic blocks; carries no identity
_SECTOR_NOTE = {
    "industrials": "diversified industrial manufacturer",
    "consumer_staples": "packaged consumer staples producer",
    "consumer_discretionary": "consumer discretionary retailer",
    "technology": "enterprise technology provider",
    "utilities": "regulated utility operator",
    "healthcare": "healthcare products and services provider",
    "energy": "integrated energy producer",
    "real_estate": "commercial real-estate operator",
}


def _sector_of(sic) -> str | None:
    try:
        s = int(sic)
    except (TypeError, ValueError):
        return None
    if 6000 <= s <= 6499:
        return None                      # financials excluded, see module docstring
    for (lo, hi), name in _SIC_RANGES:
        if lo <= s <= hi:
            return name
    return None


# ── tier assignment: interest coverage x net leverage, the two dominant metrics ──
# Thresholds mirror the SYNTHETIC tier profiles in build_firms._TIER_PROFILE, so a real
# firm lands in the band whose fundamentals it actually resembles. Stated explicitly
# rather than fitted, so the assignment is auditable.
def _tier_of(cov: float, lev: float) -> str:
    if cov >= 14 and lev <= 1.3:
        return "high_ig"
    if cov >= 6 and lev <= 3.0:
        return "low_ig"
    if cov >= 3.5 and lev <= 4.5:
        return "crossover"
    if cov >= 1.5 and lev <= 7.0:
        return "high_yield"
    return "distressed"


def _frame(concept: str, period: str) -> dict:
    p = _CACHE / f"{concept}_{period}.json"
    if not p.exists():
        return {}
    return {r["cik"]: r["val"] for r in json.loads(p.read_text())["data"]}


def candidates() -> list[dict]:
    F = lambda c: _frame(c, "CY2024")
    I = lambda c: _frame(c, "CY2024Q4I")
    rev, rev2 = F("Revenues"), F("RevenueFromContractWithCustomerExcludingAssessedTax")
    revp = _frame("Revenues", "CY2023")
    revp2 = _frame("RevenueFromContractWithCustomerExcludingAssessedTax", "CY2023")
    oi, da, ie = F("OperatingIncomeLoss"), F("DepreciationDepletionAndAmortization"), F("InterestExpense")
    cfo, capex = F("NetCashProvidedByUsedInOperatingActivities"), F("PaymentsToAcquirePropertyPlantAndEquipment")
    A, AC, LC = I("Assets"), I("AssetsCurrent"), I("LiabilitiesCurrent")
    RE, CASH = I("RetainedEarningsAccumulatedDeficit"), I("CashAndCashEquivalentsAtCarryingValue")
    LTD, LTDC = I("LongTermDebtNoncurrent"), I("LongTermDebtCurrent")

    def pick(c, *ds):
        for d in ds:
            if c in d and d[c] is not None:
                return d[c]
        return None

    out = []
    base = set(A) & set(AC) & set(LC) & set(RE) & set(CASH) & set(oi) & set(da) & set(ie) & set(cfo) & set(capex)
    for cik in sorted(base):
        R, Rp = pick(cik, rev, rev2), pick(cik, revp, revp2)
        if not R or not Rp or R <= 0 or Rp <= 0:
            continue
        if cik not in LTD and cik not in LTDC:
            continue
        E = (oi[cik] or 0) + (da[cik] or 0)
        if E <= 0 or not ie[cik] or ie[cik] <= 0:
            continue
        if not A[cik] or A[cik] <= 0 or not LC[cik] or LC[cik] <= 0 or not AC[cik]:
            continue
        sub = _CACHE / "submissions" / f"CIK{cik:010d}.json"
        if not sub.exists():
            continue
        sector = _sector_of(json.loads(sub.read_text()).get("sic"))
        if sector is None:
            continue
        debt = (LTD.get(cik) or 0) + (LTDC.get(cik) or 0)
        nd = debt - (CASH[cik] or 0)
        cov, lev = E / ie[cik], nd / E
        # Scale floor: the synthetic battery spans $2bn-$180bn of revenue. Micro-caps
        # would widen the real distribution on a dimension the synthetic arm never
        # covered, confounding a real-vs-synthetic contrast with a size effect.
        if R < 5e8:
            continue
        out.append({
            "cik": cik, "sector": sector, "tier": _tier_of(cov, lev),
            "fundamentals": {
                "sector_note": _SECTOR_NOTE[sector],
                "revenue_musd": R / 1e6,
                "rev_growth_pct": 100.0 * (R - Rp) / Rp,
                "ebitda_musd": E / 1e6,
                "ebitda_margin_pct": 100.0 * E / R,
                "interest_expense_musd": ie[cik] / 1e6,
                "ebitda_to_interest": cov,
                "net_debt_musd": nd / 1e6,
                "net_debt_to_ebitda": lev,
                "fcf_musd": ((cfo[cik] or 0) - (capex[cik] or 0)) / 1e6,
                "current_ratio": AC[cik] / LC[cik],
                "retained_earn_to_assets": RE[cik] / A[cik],
                "wc_to_assets": (AC[cik] - LC[cik]) / A[cik],
            }})
    return out


def stratified(pool: list[dict], n: int, seed: int) -> list[dict]:
    """Spread the draw across tier x sector as evenly as the pool allows, so the real
    battery has the same dispersion role as the synthetic one (a macro-induced shift
    must be observable rather than censored at a rail)."""
    rng = random.Random(seed)
    buckets = {}
    for f in pool:
        buckets.setdefault((f["tier"], f["sector"]), []).append(f)
    for k in buckets:
        buckets[k].sort(key=lambda f: f["cik"])
        rng.shuffle(buckets[k])
    picked, keys = [], sorted(buckets)
    while len(picked) < n:
        progressed = False
        for k in keys:
            if buckets[k] and len(picked) < n:
                picked.append(buckets[k].pop()); progressed = True
        if not progressed:
            break
    return picked


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=80)
    ap.add_argument("--seed", type=int, default=None)
    a = ap.parse_args()
    cfg = C.load_all()
    seed = a.seed if a.seed is not None else int(cfg.firms.seed)

    pool = candidates()
    print(f"[real] candidate pool: {len(pool)} filers with all 9 ratios, non-financial, >=$0.5bn revenue")
    by_tier = {}
    for f in pool:
        by_tier[f["tier"]] = by_tier.get(f["tier"], 0) + 1
    print(f"[real] pool by tier: {dict(sorted(by_tier.items()))}")

    picked = stratified(pool, a.n, seed)
    print(f"[real] drawn: {len(picked)} (stratified over tier x sector, seed {seed})")

    rows, counts = [], {}
    for i, f in enumerate(sorted(picked, key=lambda x: (x["tier"], x["sector"], x["cik"]))):
        body = BF.serialize(f["fundamentals"])          # IMPORTED: identical form
        # firm_id carries tier+sector only -- never the CIK, so the id cannot re-identify
        idx = counts.get((f["tier"], f["sector"]), 0)
        counts[(f["tier"], f["sector"])] = idx + 1
        fid = f"R-{f['tier']}-{_SECTOR_CODE[f['sector']]}-{idx:03d}"
        rows.append({"firm_id": fid, "tier": f["tier"], "sector": f["sector"],
                     "stratum": f"{f['tier']}:{f['sector']}",
                     "fundamentals": f["fundamentals"], "serialized": body,
                     "content_sha256": hashlib.sha256(body.encode()).hexdigest()})
    # INTEGRITY GATE: no identifier may survive into anything the model will read.
    # Two precise checks, because a loose substring gate is worse than none: an earlier
    # version tested for "20" and flagged 14 blocks whose only sin was a number like
    # "+20.4%".
    #   (a) a standalone 4-digit year (\b(19|20)\d\d\b) -- catches a real date leak
    #       without matching digits inside a formatted figure
    #   (b) corporate-name suffixes as whole words
    #   (c) the LABEL SET must be byte-identical to a synthetic block, so a real and a
    #       synthetic block are indistinguishable in form
    import re as _re
    _year = _re.compile(r"\b(?:19|20)\d{2}\b")
    _name = _re.compile(r"\b(?:inc|corp|corporation|company|co|ltd|plc|llc|lp|holdings|group)\b",
                        _re.IGNORECASE)
    def _labels(block):
        return [ln.split(":")[0].strip() for ln in block.splitlines()]
    synth = BF.serialize({k: (0 if isinstance(v, (int, float)) else "x")
                          for k, v in rows[0]["fundamentals"].items()})
    ref_labels = _labels(synth)
    bad = []
    for r in rows:
        b = r["serialized"]
        if _year.search(b) or _name.search(b) or _labels(b) != ref_labels:
            bad.append(r["firm_id"])
    if bad:
        print(f"[real] !! integrity FAIL in {len(bad)} blocks: {bad[:5]}")
        return 1
    print(f"[real] integrity: {len(rows)}/{len(rows)} blocks carry no year and no "
          f"corporate-name token, and every label set matches a synthetic block")

    _FIRMS.mkdir(parents=True, exist_ok=True)
    out = _FIRMS / "real.jsonl"
    txt = "\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n"
    out.write_text(txt)
    h = hashlib.sha256(txt.encode()).hexdigest()
    _MANI.mkdir(parents=True, exist_ok=True)
    mp = _MANI / "real_firms_manifest.json"
    mp.write_text(json.dumps({"file": "data/firms/real.jsonl", "n_firms": len(rows),
                              "sha256": h, "seed": seed,
                              "source": "SEC XBRL frames FY2024 (public domain)",
                              "by_tier": dict(sorted(by_tier.items()))}, indent=2))
    print(f"[real] wrote {out} ({len(rows)} firms) sha256={h[:16]}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

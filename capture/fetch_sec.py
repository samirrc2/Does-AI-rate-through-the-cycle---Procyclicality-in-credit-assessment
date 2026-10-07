"""Fetch + CACHE the SEC XBRL frames needed for the real-fundamentals arm (referee 1
comments 1 and 2). Public-domain US government data, so the cache is redistributable
inside the reproducibility artifact and the build is offline-reproducible after one fetch.

  python capture/fetch_sec.py            # populate data/sec_cache/ (skips what exists)

Why frames and not companyfacts: one request per CONCEPT returns every filer for the
period, so the whole battery needs ~15 requests instead of one multi-MB document per
company. SEC asks for a descriptive User-Agent and <=10 requests/second.
"""
from __future__ import annotations
import json, time, urllib.request, urllib.error
from pathlib import Path

_CACHE = Path(__file__).resolve().parent.parent / "data" / "sec_cache"
UA = "samir.chincholikar@gmail.com academic research (credit-rating procyclicality artifact)"

# Flow concepts are annual (CY####); instantaneous balance-sheet concepts are period-end
# (CY####Q4I). FY2024 is the most recent complete year with broad coverage; FY2023 is
# fetched only for the revenue-growth line.
FLOWS = ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
         "OperatingIncomeLoss", "DepreciationDepletionAndAmortization",
         "InterestExpense", "NetCashProvidedByUsedInOperatingActivities",
         "PaymentsToAcquirePropertyPlantAndEquipment"]
INSTANTS = ["Assets", "AssetsCurrent", "LiabilitiesCurrent",
            "RetainedEarningsAccumulatedDeficit",
            "CashAndCashEquivalentsAtCarryingValue",
            "LongTermDebtNoncurrent", "LongTermDebtCurrent"]
PRIOR_FLOWS = ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"]
YEAR, PRIOR = 2024, 2023


def _get(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as f:
        return json.load(f)


def fetch_frame(concept: str, period: str) -> dict | None:
    _CACHE.mkdir(parents=True, exist_ok=True)
    out = _CACHE / f"{concept}_{period}.json"
    if out.exists():
        return json.loads(out.read_text())
    url = f"https://data.sec.gov/api/xbrl/frames/us-gaap/{concept}/USD/{period}.json"
    try:
        d = _get(url)
    except urllib.error.HTTPError as e:
        print(f"  [skip] {concept} {period}: HTTP {e.code}")
        return None
    out.write_text(json.dumps(d))
    time.sleep(0.15)                      # stay well under the 10 req/s ceiling
    return d


def fetch_submission(cik: int) -> dict | None:
    """Per-company metadata -- needed ONLY for the SIC code that maps a filer to one of
    the eight sectors. No name or identifier from here reaches the serialized block."""
    _CACHE.mkdir(parents=True, exist_ok=True)
    sub = _CACHE / "submissions"; sub.mkdir(exist_ok=True)
    out = sub / f"CIK{cik:010d}.json"
    if out.exists():
        return json.loads(out.read_text())
    try:
        d = _get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
    except urllib.error.HTTPError as e:
        print(f"  [skip] CIK {cik}: HTTP {e.code}")
        return None
    slim = {"cik": cik, "sic": d.get("sic"), "sicDescription": d.get("sicDescription"),
            "entityType": d.get("entityType")}
    out.write_text(json.dumps(slim))
    time.sleep(0.15)
    return slim


def main() -> int:
    n = 0
    for c in FLOWS:
        if fetch_frame(c, f"CY{YEAR}") is not None:
            n += 1
    for c in PRIOR_FLOWS:
        if fetch_frame(c, f"CY{PRIOR}") is not None:
            n += 1
    for c in INSTANTS:
        if fetch_frame(c, f"CY{YEAR}Q4I") is not None:
            n += 1
    print(f"[sec] {n} frames cached under {_CACHE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

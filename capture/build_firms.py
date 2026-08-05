"""Mint the synthetic firm battery — deterministic, offline, $0.

Each firm has FIXED fundamentals drawn from a credit-quality tier profile
(high_ig .. distressed) and a sector. The fundamentals are serialized ONCE into a
labelled financial-statement block and frozen; the orchestrator reuses that exact
text byte-identically under every macro state, so the macro context is the sole
perturbation. Firms are stratified across tiers x sectors so the fundamentals-
implied ratings span the scale (AAA..CCC) — dispersion is required so a macro-
induced shift is observable rather than censored at a rail.

Determinism: everything is seeded from firms.yaml `seed`. The full battery is
minted once; the pilot battery is a strict stratified SUBSAMPLE (pilot subset of
full). Output is frozen to data/firms/*.jsonl and SHA-256'd into a manifest.

INTEGRITY: no real company names; no calendar dates (relative 'most recent fiscal
year') -> nothing lets a model fingerprint a real issuer or historical period.
"""
from __future__ import annotations
import argparse, hashlib, json, random, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "config"))
import loader as C  # noqa: E402

_HERE = Path(__file__).resolve().parent
_FIRMS = _HERE.parent / "data" / "firms"
_MANI = _HERE.parent / "manifest"


# ── tier fundamental profiles (ranges chosen so the implied rating lands in band) ─
# Keys are financial ratios/scale lines. Values are (lo, hi) sampled uniformly.
_TIER_PROFILE = {
    "high_ig": {  # AAA-AA
        "revenue_musd": (40000, 180000), "rev_growth_pct": (2, 9),
        "ebitda_margin_pct": (22, 38), "net_debt_to_ebitda": (0.2, 1.3),
        "ebitda_to_interest": (14, 40), "fcf_margin_pct": (9, 18),
        "current_ratio": (1.4, 2.4), "retained_earn_to_assets": (0.35, 0.6),
        "wc_to_assets": (0.15, 0.32),
    },
    "low_ig": {  # A-BBB
        "revenue_musd": (8000, 60000), "rev_growth_pct": (1, 7),
        "ebitda_margin_pct": (15, 27), "net_debt_to_ebitda": (1.3, 2.8),
        "ebitda_to_interest": (6, 13), "fcf_margin_pct": (4, 10),
        "current_ratio": (1.1, 1.8), "retained_earn_to_assets": (0.18, 0.4),
        "wc_to_assets": (0.06, 0.2),
    },
    "crossover": {  # BBB-/BB+
        "revenue_musd": (2000, 20000), "rev_growth_pct": (-2, 6),
        "ebitda_margin_pct": (11, 20), "net_debt_to_ebitda": (2.8, 4.2),
        "ebitda_to_interest": (3.0, 6.0), "fcf_margin_pct": (0, 6),
        "current_ratio": (0.9, 1.4), "retained_earn_to_assets": (0.05, 0.22),
        "wc_to_assets": (-0.02, 0.12),
    },
    "high_yield": {  # BB-B
        "revenue_musd": (500, 8000), "rev_growth_pct": (-5, 6),
        "ebitda_margin_pct": (7, 16), "net_debt_to_ebitda": (4.2, 6.5),
        "ebitda_to_interest": (1.6, 3.2), "fcf_margin_pct": (-4, 3),
        "current_ratio": (0.7, 1.2), "retained_earn_to_assets": (-0.05, 0.1),
        "wc_to_assets": (-0.08, 0.06),
    },
    "distressed": {  # CCC and below
        "revenue_musd": (100, 3000), "rev_growth_pct": (-18, 2),
        "ebitda_margin_pct": (0, 9), "net_debt_to_ebitda": (6.5, 12.0),
        "ebitda_to_interest": (0.4, 1.6), "fcf_margin_pct": (-14, -1),
        "current_ratio": (0.4, 0.9), "retained_earn_to_assets": (-0.4, -0.02),
        "wc_to_assets": (-0.25, -0.02),
    },
}

_SECTOR_NOTE = {
    "industrials": "diversified industrial manufacturer",
    "consumer_staples": "packaged-goods / staples producer",
    "consumer_discretionary": "discretionary retail / consumer brand",
    "technology": "enterprise software & hardware",
    "utilities": "regulated electric & gas utility",
    "healthcare": "healthcare products & services",
    "energy": "oil, gas & energy operations",
    "real_estate": "commercial real-estate owner/operator",
}

# UNIQUE short codes for firm_ids (sector[:3] collides: staples/discretionary -> 'con').
_SECTOR_CODE = {
    "industrials": "IND", "consumer_staples": "CST", "consumer_discretionary": "CDI",
    "technology": "TEC", "utilities": "UTL", "healthcare": "HLT", "energy": "ENR",
    "real_estate": "RES",
}


def _rng(seed: int, *parts) -> random.Random:
    h = hashlib.sha256(("|".join([str(seed), *map(str, parts)])).encode()).hexdigest()
    return random.Random(int(h[:16], 16))


def _u(r: random.Random, lo, hi, nd=1):
    return round(r.uniform(lo, hi), nd)


def _fundamentals(r: random.Random, tier: str, sector: str) -> dict:
    p = _TIER_PROFILE[tier]
    rev = _u(r, *p["revenue_musd"], 0)
    m = _u(r, *p["ebitda_margin_pct"])
    ebitda = round(rev * m / 100.0, 0)
    cov = _u(r, *p["ebitda_to_interest"], 2)
    interest = round(ebitda / cov, 0) if cov > 0 else round(ebitda, 0)
    nde = _u(r, *p["net_debt_to_ebitda"], 2)
    net_debt = round(ebitda * nde, 0)
    fcf = round(rev * _u(r, *p["fcf_margin_pct"]) / 100.0, 0)
    return {
        "sector_note": _SECTOR_NOTE[sector],
        "revenue_musd": rev,
        "rev_growth_pct": _u(r, *p["rev_growth_pct"]),
        "ebitda_musd": ebitda,
        "ebitda_margin_pct": m,
        "interest_expense_musd": interest,
        "ebitda_to_interest": cov,
        "net_debt_musd": net_debt,
        "net_debt_to_ebitda": nde,
        "fcf_musd": fcf,
        "current_ratio": _u(r, *p["current_ratio"], 2),
        "retained_earn_to_assets": _u(r, *p["retained_earn_to_assets"], 3),
        "wc_to_assets": _u(r, *p["wc_to_assets"], 3),
    }


def serialize(f: dict) -> str:
    """Fixed labelled block. No firm name; no calendar dates."""
    return "\n".join([
        f"  Sector: {f['sector_note']}",
        f"  Revenue: {f['revenue_musd']:,.0f} musd  (YoY growth {f['rev_growth_pct']:+.1f}%)",
        f"  EBITDA: {f['ebitda_musd']:,.0f} musd  (margin {f['ebitda_margin_pct']:.1f}%)",
        f"  Interest expense: {f['interest_expense_musd']:,.0f} musd  "
        f"(EBITDA/interest {f['ebitda_to_interest']:.2f}x)",
        f"  Net debt: {f['net_debt_musd']:,.0f} musd  "
        f"(net debt/EBITDA {f['net_debt_to_ebitda']:.2f}x)",
        f"  Free cash flow: {f['fcf_musd']:,.0f} musd",
        f"  Current ratio: {f['current_ratio']:.2f}",
        f"  Retained earnings / total assets: {f['retained_earn_to_assets']:+.3f}",
        f"  Working capital / total assets: {f['wc_to_assets']:+.3f}",
    ])


def build_firm(tier: str, sector: str, idx: int, seed: int) -> dict:
    r = _rng(seed, tier, sector, idx)
    f = _fundamentals(r, tier, sector)
    body = serialize(f)
    firm_id = f"F-{tier}-{_SECTOR_CODE[sector]}-{idx:03d}"
    return {
        "firm_id": firm_id,
        "tier": tier,                       # clustering unit + dispersion axis
        "sector": sector,
        "stratum": f"{tier}:{sector}",
        "fundamentals": f,
        "serialized": body,                 # byte-identical across macro states
        "content_sha256": hashlib.sha256(body.encode()).hexdigest(),
    }


def _counts(total: int, tiers: list[str], sectors: list[str]) -> list[tuple[str, str, int]]:
    """Distribute `total` firms as evenly as possible across tier x sector cells."""
    cells = [(t, s) for t in tiers for s in sectors]
    base = total // len(cells)
    rem = total - base * len(cells)
    out = []
    for i, (t, s) in enumerate(cells):
        out.append((t, s, base + (1 if i < rem else 0)))
    return out


def mint_full(cfg) -> list[dict]:
    f = cfg.firms
    seed = f.seed
    firms = []
    for t, s, n in _counts(f.sizes.full, f.tiers, f.sectors):
        for i in range(n):
            firms.append(build_firm(t, s, i, seed))
    firms.sort(key=lambda c: c["firm_id"])
    return firms


def subsample_pilot(cfg, full: list[dict]) -> list[dict]:
    """Strict stratified subsample: pilot subset of full, proportional per tier."""
    f = cfg.firms
    want = f.sizes.pilot
    frac = want / len(full)
    by = {}
    for c in full:
        by.setdefault(c["tier"], []).append(c)
    chosen = []
    for k in sorted(by):
        grp = sorted(by[k], key=lambda c: c["firm_id"])
        take = max(1, int(round(len(grp) * frac)))
        r = _rng(f.seed, "pilot", k)
        chosen.extend(r.sample(grp, min(take, len(grp))))
    chosen.sort(key=lambda c: c["firm_id"])
    if len(chosen) > want:
        r = _rng(f.seed, "pilot_trim")
        drop = set(r.sample(range(len(chosen)), len(chosen) - want))
        chosen = [c for i, c in enumerate(chosen) if i not in drop]
    elif len(chosen) < want:
        pool = [c for c in full if c["firm_id"] not in {x["firm_id"] for x in chosen}]
        r = _rng(f.seed, "pilot_pad")
        chosen.extend(r.sample(pool, want - len(chosen)))
    chosen.sort(key=lambda c: c["firm_id"])
    return chosen


def _write(firms: list[dict], path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        for c in firms:
            fh.write(json.dumps(c, sort_keys=True) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _summary(firms: list[dict]) -> dict:
    from collections import Counter
    return {
        "n": len(firms),
        "by_tier": dict(Counter(c["tier"] for c in firms)),
        "by_sector": dict(Counter(c["sector"] for c in firms)),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--which", choices=["full", "pilot", "both"], default="both")
    args = ap.parse_args()

    cfg = C.load_all()
    full = mint_full(cfg)
    pilot = subsample_pilot(cfg, full)

    _MANI.mkdir(parents=True, exist_ok=True)
    receipts = {"config_hash": cfg.config_hash(), "seed": cfg.firms.seed}

    if args.which in ("full", "both"):
        h = _write(full, _FIRMS / "full.jsonl")
        receipts["full"] = {"sha256": h, **_summary(full)}
        print(f"[firms] full : {len(full)} firms  sha256={h[:16]}...")
    if args.which in ("pilot", "both"):
        h = _write(pilot, _FIRMS / "pilot.jsonl")
        receipts["pilot"] = {"sha256": h, **_summary(pilot)}
        print(f"[firms] pilot: {len(pilot)} firms  sha256={h[:16]}...")

    (_MANI / "firms_manifest.json").write_text(json.dumps(receipts, indent=2, sort_keys=True))
    print("[firms] manifest -> manifest/firms_manifest.json")
    return 0


def load_firms(which: str) -> list[dict]:
    path = _FIRMS / f"{which}.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"{path} missing — run capture/build_firms.py first")
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


if __name__ == "__main__":
    sys.exit(main())

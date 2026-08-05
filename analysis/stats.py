"""Inferential layer: a seeded CLUSTER BOOTSTRAP resampling the clustering unit =
FIRM. Because fundamentals are fixed per firm and each firm contributes a full
macro-state curve, the firm is the natural cluster. Any headline scalar is a
function of a list of firm_ids; the bootstrap resamples firms with replacement,
recomputes the scalar, and returns point + 95% percentile CI. Byte-stable given the
same frozen inputs and seed.
"""
from __future__ import annotations
import math
import random
from ratings import RatingTable


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float | None, float | None]:
    if n == 0:
        return (None, None)
    phat = k / n
    denom = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    half = (z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n))) / denom
    return (center - half, center + half)


def cluster_bootstrap(rt: RatingTable, firms: list[str], stat_fn, draws: int = 2000,
                      seed: int = 4242) -> dict:
    """stat_fn(firm_ids) -> float|None. Resamples FIRMS with replacement (optionally
    stratified within tier to preserve the credit-quality mix)."""
    point = stat_fn(firms)
    n = len(firms)
    if n == 0:
        return {"point": point, "ci_low": None, "ci_high": None, "n_firms": 0, "n_valid": 0}
    # stratify the resample by tier so every draw keeps the dispersion mix
    by_tier = {}
    for f in firms:
        by_tier.setdefault(rt.firms_meta[f]["tier"], []).append(f)
    tiers = sorted(by_tier)
    rng = random.Random(seed)
    vals = []
    for _ in range(draws):
        resampled = []
        for t in tiers:
            grp = by_tier[t]
            for _i in range(len(grp)):
                resampled.append(grp[rng.randrange(len(grp))])
        v = stat_fn(resampled)
        if v is not None and not (isinstance(v, float) and math.isnan(v)):
            vals.append(v)
    vals.sort()
    if len(vals) < 20:
        return {"point": point, "ci_low": None, "ci_high": None,
                "n_firms": n, "n_valid": len(vals)}
    return {"point": point,
            "ci_low": vals[int(0.025 * len(vals))],
            "ci_high": vals[int(0.975 * len(vals)) - 1],
            "n_firms": n, "n_valid": len(vals)}


def ci_excludes(ci: dict, value: float, side: str = "above") -> bool | None:
    """True if the CI lies strictly on one side of `value`. side='above' => whole CI
    > value; side='below' => whole CI < value; side='either' => excludes value."""
    lo, hi = ci.get("ci_low"), ci.get("ci_high")
    if lo is None or hi is None:
        return None
    if side == "above":
        return lo > value
    if side == "below":
        return hi < value
    return (lo > value) or (hi < value)

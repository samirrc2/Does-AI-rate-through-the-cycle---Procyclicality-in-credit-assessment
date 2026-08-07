"""Cyclicality layer: the core estimands. Pure functions of the RatingTable and a
list of firm_ids (the support / a bootstrap resample).

Convention: PROCYCLICAL means the rating is downgraded as the macro state worsens
(severity rises). The cyclicality coefficient = NOTCHES OF DOWNGRADE PER +1 SEVERITY
STEP (positive = procyclical, 0 = through-the-cycle null, negative = countercyclical).

Because fundamentals are byte-identical across states, the within-firm slope is a
clean estimate. Estimators are parametric over:
  kind  = 'macro' (economic axis) | 'placebo' (credit-irrelevant axis)
  table = 'notch' (sampled median) | 'expnotch' (logprobs expected-notch, OpenAI)
The NET coefficient (macro - placebo) is the demand-effect-adjusted cyclicality.
"""
from __future__ import annotations
import math
from ratings import RatingTable


def _within_firm_slope(sev, notch) -> float | None:
    n = len(sev)
    if n < 2:
        return None
    mx = sum(sev) / n; my = sum(notch) / n
    sxx = sum((x - mx) ** 2 for x in sev)
    if sxx <= 1e-12:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(sev, notch)) / sxx


def _order(rt, kind):
    return rt.placebo_order() if kind == "placebo" else rt.macro_order()


def _firm_curve(rt, mv, firm, kind, table):
    order = _order(rt, kind)
    d = getattr(rt, table).get(mv, {}).get(firm, {})
    sev = [rt.state_sev[s] for s in order]
    vals = [d.get(s) for s in order]
    if any(v is None for v in vals) or len(order) < 2:
        return None, None
    return sev, vals


# ── per-firm value cache ────────────────────────────────────────────────────
# The within-firm slope (and half-slope, PD slope, endpoint swing) for a given
# (mv, firm, kind, table) is CONSTANT. Memoizing it turns each bootstrap draw into a
# handful of dict lookups + a mean, instead of recomputing every firm's regression —
# mathematically identical results, ~100x faster (seconds, not minutes). Keyed by
# id(rt) so different RatingTables never collide within a process.
_MISS = object()
_CACHE: dict = {}


def clear_cache():
    _CACHE.clear()


def _firm_slope(rt, mv, firm, kind, table):
    key = (id(rt), "slope", mv, firm, kind, table)
    v = _CACHE.get(key, _MISS)
    if v is not _MISS:
        return v
    sev, vals = _firm_curve(rt, mv, firm, kind, table)
    s = _within_firm_slope(sev, vals) if sev is not None else None
    _CACHE[key] = s
    return s


def _firm_half_slope(rt, mv, firm, side, table):
    key = (id(rt), "half", mv, firm, side, table)
    v = _CACHE.get(key, _MISS)
    if v is not _MISS:
        return v
    order = rt.macro_order()
    sel = [s for s in order if (rt.state_sev[s] >= 0 if side == "down" else rt.state_sev[s] <= 0)]
    d = getattr(rt, table).get(mv, {}).get(firm, {})
    pts = [(rt.state_sev[s], d.get(s)) for s in sel if d.get(s) is not None]
    val = (_within_firm_slope([p[0] for p in pts], [p[1] for p in pts])
           if len(pts) >= 2 else None)
    _CACHE[key] = val
    return val


def _firm_swing(rt, mv, firm, kind, table):
    key = (id(rt), "swing", mv, firm, kind, table)
    v = _CACHE.get(key, _MISS)
    if v is not _MISS:
        return v
    order = _order(rt, kind)
    val = None
    if len(order) >= 2:
        d = getattr(rt, table).get(mv, {}).get(firm, {})
        a, b = d.get(order[0]), d.get(order[-1])
        val = (a - b) if (a is not None and b is not None) else None
    _CACHE[key] = val
    return val


def _firm_pd_slope(rt, mv, firm):
    key = (id(rt), "pd", mv, firm)
    v = _CACHE.get(key, _MISS)
    if v is not _MISS:
        return v
    order = rt.macro_order()
    pds = [rt.pd.get(mv, {}).get(firm, {}).get(s) for s in order]
    val = (_within_firm_slope([rt.state_sev[s] for s in order], [_logit(p) for p in pds])
           if all(p is not None for p in pds) else None)
    _CACHE[key] = val
    return val


def cyclicality_notch(rt: RatingTable, mv, firms, kind="macro", table="notch") -> float | None:
    """Mean within-firm downgrade-notches per +1 severity step (positive = procyclical)."""
    slopes = [s for f in firms if (s := _firm_slope(rt, mv, f, kind, table)) is not None]
    return -(sum(slopes) / len(slopes)) if slopes else None


def half_slope(rt: RatingTable, mv, firms, side="down", table="notch") -> float | None:
    """Mean within-firm downgrade-notches per +1 severity step on ONE half of the
    macro axis. side='down' => recession side (severity >= 0, neutral..severe
    recession); side='up' => expansion side (severity <= 0, boom..neutral). The
    asymmetry (down >> up) is the financially dangerous margin."""
    order = rt.macro_order()
    sel = [s for s in order if (rt.state_sev[s] >= 0 if side == "down" else rt.state_sev[s] <= 0)]
    if len(sel) < 2:
        return None
    slopes = [s for f in firms if (s := _firm_half_slope(rt, mv, f, side, table)) is not None]
    return -(sum(slopes) / len(slopes)) if slopes else None


def endpoint_swing(rt: RatingTable, mv, firms, kind="macro", table="notch") -> float | None:
    if len(_order(rt, kind)) < 2:
        return None
    diffs = [s for f in firms if (s := _firm_swing(rt, mv, f, kind, table)) is not None]
    return (sum(diffs) / len(diffs)) if diffs else None


def net_cyclicality(rt: RatingTable, mv, firms, table="notch") -> float | None:
    """Demand-effect-adjusted cyclicality = macro slope - placebo slope, over firms
    with a full curve on BOTH axes."""
    if not rt.placebo_order():
        return cyclicality_notch(rt, mv, firms, "macro", table)
    common = [f for f in firms
              if _firm_slope(rt, mv, f, "macro", table) is not None
              and _firm_slope(rt, mv, f, "placebo", table) is not None]
    if not common:
        return None
    econ = cyclicality_notch(rt, mv, common, "macro", table)
    plac = cyclicality_notch(rt, mv, common, "placebo", table)
    return None if (econ is None or plac is None) else econ - plac


def placebo_cyclicality(rt: RatingTable, mv, firms, table="notch") -> float | None:
    return cyclicality_notch(rt, mv, firms, "placebo", table)


def state_means(rt: RatingTable, mv, firms, kind="macro") -> dict:
    order = _order(rt, kind)
    out = {}
    for st in order:
        nv = [rt.notch[mv][f].get(st) for f in firms if rt.notch[mv].get(f, {}).get(st) is not None]
        pv = [rt.pd.get(mv, {}).get(f, {}).get(st) for f in firms
              if rt.pd.get(mv, {}).get(f, {}).get(st) is not None]
        out[st] = {"severity": rt.state_sev[st],
                   "mean_notch": (sum(nv) / len(nv)) if nv else None,
                   "mean_pd": (sum(pv) / len(pv)) if pv else None, "n": len(nv)}
    return out


def _logit(p):
    p = min(1 - 1e-6, max(1e-6, p))
    return math.log(p / (1 - p))


def cyclicality_pd(rt: RatingTable, mv, firms) -> float | None:
    """Mean within-firm slope of log-odds(PD) on macro severity (positive = procyclical)."""
    slopes = [s for f in firms if (s := _firm_pd_slope(rt, mv, f)) is not None]
    return (sum(slopes) / len(slopes)) if slopes else None


def pd_half_slope(rt: RatingTable, mv, firms, side="down") -> float | None:
    """Mean within-firm log-odds(PD) slope on one half of the macro axis (downside =
    neutral->severe recession; upside = boom->neutral). Used to test whether the TTC
    instruction suppresses DOWNSIDE PD movement specifically."""
    order = rt.macro_order()
    sel = [s for s in order if (rt.state_sev[s] >= 0 if side == "down" else rt.state_sev[s] <= 0)]
    if len(sel) < 2:
        return None
    slopes = []
    for f in firms:
        d = rt.pd.get(mv, {}).get(f, {})
        pts = [(rt.state_sev[s], d.get(s)) for s in sel if d.get(s) is not None]
        if len(pts) < 2:
            continue
        sl = _within_firm_slope([p[0] for p in pts], [_logit(p[1]) for p in pts])
        if sl is not None:
            slopes.append(sl)
    return (sum(slopes) / len(slopes)) if slopes else None


def churn(rt: RatingTable, mv, firms) -> dict:
    order = rt.macro_order()
    if len(order) < 2:
        return {"n": 0, "frac_moved_ge1": None, "frac_moved_ge2": None,
                "spearman_extremes": None, "pd_spearman_extremes": None}
    best, worst = order[0], order[-1]
    a, b, pa, pb = [], [], [], []
    m1 = m2 = n = 0
    for f in firms:
        x = rt.notch[mv][f].get(best); y = rt.notch[mv][f].get(worst)
        if x is None or y is None:
            continue
        n += 1; a.append(x); b.append(y)
        if abs(x - y) >= 1:
            m1 += 1
        if abs(x - y) >= 2:
            m2 += 1
        px = rt.pd.get(mv, {}).get(f, {}).get(best)
        py = rt.pd.get(mv, {}).get(f, {}).get(worst)
        if px is not None and py is not None:
            pa.append(px); pb.append(py)
    return {"n": n, "frac_moved_ge1": (m1 / n) if n else None,
            "frac_moved_ge2": (m2 / n) if n else None,
            "spearman_extremes": _spearman(a, b),
            "pd_spearman_extremes": _spearman(pa, pb)}


def _rank(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs); i = 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _spearman(a, b):
    if len(a) < 3:
        return None
    ra, rb = _rank(a), _rank(b); n = len(a)
    ma = sum(ra) / n; mb = sum(rb) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    da = math.sqrt(sum((x - ma) ** 2 for x in ra))
    db = math.sqrt(sum((y - mb) ** 2 for y in rb))
    return (num / (da * db)) if (da > 1e-12 and db > 1e-12) else None


def monotonic(rt: RatingTable, mv, firms, kind="macro") -> bool | None:
    sm = state_means(rt, mv, firms, kind)
    means = [sm[s]["mean_notch"] for s in _order(rt, kind)]
    if any(v is None for v in means):
        return None
    return all(means[i] >= means[i + 1] - 1e-9 for i in range(len(means) - 1))


def pooled_across_models(rt: RatingTable, variant, firms, fn) -> float | None:
    vals = []
    for m in rt.models:
        mv = (m, variant)
        if mv not in rt.notch:
            continue
        v = fn(rt, mv, firms)
        if v is not None:
            vals.append(v)
    return (sum(vals) / len(vals)) if vals else None

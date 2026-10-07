"""Basel IRB capital translation of the rating movements (referee Row 2).

A rating is what enters a credit pipeline, so we anchor the capital calculation
through the RATING, not the models' verbalised (and disclaimed-as-miscalibrated) PDs:
notch -> a stylised 1-year default probability calibrated to published agency average
default rates -> the Basel IRB corporate risk-weight formula. We report the CHANGE in
the capital requirement across the macro-severity axis (far more defensible than any
level). The raw-verbalised-PD version is provided as a robustness check.

This is a STYLISED PROXY for the core economic logic (LGD 0.45, maturity M 2.5,
the corporate asset-correlation formula), NOT the regulatory framework in full detail
(no SME or firm-size adjustment, no scaling factor).
"""
from __future__ import annotations
import math

# ── stylised notch -> 1-year PD, monotone, calibrated to published agency average
# one-year corporate default rates. The anchors below are the values ACTUALLY in the
# table and match the manuscript's Appendix A text:
#   AAA (21) 0.01%   BBB (13) 0.25%   BB (10) 1.10%   B (7) 5.00%   CCC (4) 20.00%
# (An earlier version of this comment quoted 0.0/0.2/0.8/4/27% -- wrong on four of the
# five anchors. The table and the manuscript were correct; only this comment drifted.
# It is the kind of error a replicator would read as a miscalibrated map.)
# Values interpolate smoothly across the 21-notch S&P scale. The reported result is the
# CHANGE in capital and is robust to the exact mapping (see the raw-PD robustness
# variant, and the LGD/M/alternative-map sensitivity grid in reviewer_revision.py).
NOTCH_PD = {
    21: 0.00010, 20: 0.00015, 19: 0.00025, 18: 0.00035, 17: 0.00050, 16: 0.00070,
    15: 0.00100, 14: 0.00150, 13: 0.00250, 12: 0.00400, 11: 0.00700, 10: 0.01100,
    9: 0.01700, 8: 0.03000, 7: 0.05000, 6: 0.08000, 5: 0.13000, 4: 0.20000,
    3: 0.27000, 2: 0.40000, 1: 0.50000,
}


def _phi(x):     # standard normal CDF
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _phinv(p):   # standard normal inverse CDF (Acklam's algorithm)
    if p <= 0.0:
        return -1e9
    if p >= 1.0:
        return 1e9
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
           (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def irb_capital(pd: float, lgd: float = 0.45, M: float = 2.5) -> float:
    """Basel IRB corporate capital requirement K (fraction of exposure).
    Capital requirement (% of EAD) = 100*K; risk weight (%) = 1250*K."""
    pd = min(max(pd, 1e-6), 0.9999)
    e = math.exp(-50 * pd)
    denom = 1 - math.exp(-50.0)
    R = 0.12 * (1 - e) / denom + 0.24 * (1 - (1 - e) / denom)
    b = (0.11852 - 0.05478 * math.log(pd)) ** 2
    cond = _phi((_phinv(pd) + math.sqrt(R) * _phinv(0.999)) / math.sqrt(1 - R))
    K = (lgd * cond - pd * lgd) * (1 - 1.5 * b) ** -1 * (1 + (M - 2.5) * b)
    return max(0.0, K)


def notch_to_capital(notch) -> float:
    """Capital requirement (% of exposure) from a rating notch, via the stylised
    notch->PD map and the IRB formula."""
    n = int(round(notch))
    n = max(1, min(21, n))
    return 100.0 * irb_capital(NOTCH_PD[n])


def pd_to_capital(pd) -> float:
    return 100.0 * irb_capital(pd)


# ── per-firm capital movements (referee: report the CHANGE across the axis) ───
def _firm_states(rt, mv):
    order = rt.macro_order()          # ascending severity: boom .. severe_recession
    return order[0], order[len(order) // 2], order[-1]   # boom, neutral, severe


def firm_capital_swing(rt, mv, firm, source="rating"):
    """Capital requirement (pp of exposure) at severe recession minus at boom, for one
    firm. source='rating' anchors through the notch (primary); 'pd' uses the verbalised
    PD (robustness). Returns None if the firm lacks a full curve."""
    boom, _, sev = _firm_states(rt, mv)
    if source == "rating":
        d = rt.notch.get(mv, {}).get(firm, {})
        a, b = d.get(boom), d.get(sev)
        if a is None or b is None:
            return None
        return notch_to_capital(b) - notch_to_capital(a)
    else:
        d = rt.pd.get(mv, {}).get(firm, {})
        a, b = d.get(boom), d.get(sev)
        if a is None or b is None:
            return None
        return pd_to_capital(b) - pd_to_capital(a)


def firm_capital_halves(rt, mv, firm, source="rating"):
    """(downside, upside) capital change in pp: severe_rec - neutral, and neutral - boom.
    The downside dominates because capital is convex in PD and the rating falls faster
    into recession (welds the asymmetry to the capital number)."""
    boom, neutral, sev = _firm_states(rt, mv)
    tbl = rt.notch if source == "rating" else rt.pd
    d = tbl.get(mv, {}).get(firm, {})
    a, m, b = d.get(boom), d.get(neutral), d.get(sev)
    if a is None or m is None or b is None:
        return None
    f = notch_to_capital if source == "rating" else pd_to_capital
    return (f(b) - f(m), f(m) - f(a))


def mean_capital_swing(rt, mv, firms, source="rating"):
    vals = [v for f in firms if (v := firm_capital_swing(rt, mv, f, source)) is not None]
    return (sum(vals) / len(vals)) if vals else None


def mean_capital_halves(rt, mv, firms, source="rating"):
    ds, us = [], []
    for f in firms:
        h = firm_capital_halves(rt, mv, f, source)
        if h is not None:
            ds.append(h[0]); us.append(h[1])
    down = (sum(ds) / len(ds)) if ds else None
    up = (sum(us) / len(us)) if us else None
    return down, up


def pooled_capital_swing(rt, variant, firms, source="rating"):
    vals = []
    for m in rt.models:
        mv = (m, variant)
        if mv in rt.notch:
            v = mean_capital_swing(rt, mv, firms, source)
            if v is not None:
                vals.append(v)
    return (sum(vals) / len(vals)) if vals else None

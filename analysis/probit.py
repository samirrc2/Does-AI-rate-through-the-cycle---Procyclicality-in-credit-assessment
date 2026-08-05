"""The Amato-Furfine ORDERED-PROBIT null. Fits an ordered probit of the rating
notch on macro severity, netting out firm-level creditworthiness with a Mundlak
device (the firm's mean notch as a continuous control — a correlated-random-effects
substitute for firm fixed effects that avoids the incidental-parameters problem
with 40-80 firms and ~20 ordinal categories).

Under the through-the-cycle NULL the macro coefficient is 0. A positive latent
coefficient on severity means the latent creditworthiness the model perceives falls
as the macro worsens even though fundamentals are byte-identical -> procyclicality.

Estimation is self-contained (numpy + scipy). If scipy is unavailable, it falls
back to the pooled within-firm OLS slope and records estimator='ols_fallback', so
the pipeline never breaks. Sign convention matches cyclicality.py: the reported
`procyclical_severity_coef` is POSITIVE when worse macro -> lower rating.
"""
from __future__ import annotations
from ratings import RatingTable


def _collect(rt: RatingTable, mv, firms: list[str]):
    """Return (sev, notch, firm_mean_notch) arrays over all (firm, macro) cells with
    a non-None notch, plus the raw per-firm mean used as the Mundlak control."""
    sev, notch, firm_mean = [], [], []
    order = rt.macro_order()
    for f in firms:
        row = rt.notch[mv].get(f, {})
        vals = [row.get(ms) for ms in order]
        present = [(rt.state_sev[ms], v) for ms, v in zip(order, vals) if v is not None]
        if len(present) < 2:
            continue
        fm = sum(v for _, v in present) / len(present)
        for s, v in present:
            sev.append(float(s)); notch.append(float(v)); firm_mean.append(fm)
    return sev, notch, firm_mean


def _ols_slope(rt: RatingTable, mv, firms: list[str]) -> float | None:
    """Pooled within-firm OLS slope of notch on severity (fallback estimator)."""
    from cyclicality import cyclicality_notch
    c = cyclicality_notch(rt, mv, firms)   # already = -(mean slope), procyclical-positive
    return c


def ordered_probit(rt: RatingTable, mv, firms: list[str]) -> dict:
    """Fit the ordered probit. Returns the severity coefficient (procyclical-positive
    sign), its implied notch effect per step, and the estimator used."""
    sev, notch, firm_mean = _collect(rt, mv, firms)
    if len(sev) < 8 or len(set(notch)) < 2:
        return {"estimator": "insufficient", "severity_coef": None,
                "notch_per_step": None, "n": len(sev), "n_categories": len(set(notch))}
    try:
        import numpy as np
        from scipy.optimize import minimize
        from scipy.stats import norm
    except Exception:
        c = _ols_slope(rt, mv, firms)
        return {"estimator": "ols_fallback", "severity_coef": c,
                "notch_per_step": c, "n": len(sev), "n_categories": len(set(notch))}

    y_raw = np.array(notch)
    cats = sorted(set(notch))
    cat_index = {c: i for i, c in enumerate(cats)}
    y = np.array([cat_index[v] for v in notch])
    K = len(cats)
    # standardize regressors for a stable optimizer
    X1 = np.array(sev); X2 = np.array(firm_mean)
    x1 = (X1 - X1.mean()) / (X1.std() + 1e-9)
    x2 = (X2 - X2.mean()) / (X2.std() + 1e-9)

    # params: K-1 increasing cutpoints (via first cut + log-gaps) + b1 + b2
    def unpack(p):
        c0 = p[0]
        gaps = np.exp(p[1:K - 1]) if K > 2 else np.array([])
        cuts = np.concatenate([[c0], c0 + np.cumsum(gaps)]) if K > 2 else np.array([c0])
        b1, b2 = p[K - 1], p[K]
        return cuts, b1, b2

    def negll(p):
        cuts, b1, b2 = unpack(p)
        eta = b1 * x1 + b2 * x2
        lo = np.where(y == 0, -np.inf, np.take(cuts, np.clip(y - 1, 0, K - 2)))
        hi = np.where(y == K - 1, np.inf, np.take(cuts, np.clip(y, 0, K - 2)))
        pr = norm.cdf(hi - eta) - norm.cdf(lo - eta)
        pr = np.clip(pr, 1e-12, 1.0)
        return -np.sum(np.log(pr))

    p0 = np.concatenate([[norm.ppf((np.arange(1, K) / K))[0]],
                         np.zeros(max(0, K - 2)), [0.0, 1.0]])
    try:
        res = minimize(negll, p0, method="Nelder-Mead",
                       options={"maxiter": 20000, "xatol": 1e-4, "fatol": 1e-4})
        _, b1, _ = unpack(res.x)
        # b1 is per-standardized-severity in latent SD units; convert back to per raw
        # severity step, then to an approximate notch effect via the average local
        # category width in latent units.
        coef_raw = b1 / (X1.std() + 1e-9)
        # latent span maps to (K-1) category boundaries over the observed notch range
        notch_span = (max(cats) - min(cats))
        cuts, _, _ = unpack(res.x)
        latent_span = (cuts[-1] - cuts[0]) if len(cuts) > 1 else 1.0
        notch_per_latent = (notch_span / latent_span) if latent_span > 1e-6 else 1.0
        notch_per_step = -coef_raw * notch_per_latent   # procyclical-positive sign
        return {"estimator": "ordered_probit", "severity_coef": float(-coef_raw),
                "notch_per_step": float(notch_per_step),
                "n": len(sev), "n_categories": K, "converged": bool(res.success)}
    except Exception as e:
        c = _ols_slope(rt, mv, firms)
        return {"estimator": "ols_fallback", "severity_coef": c, "notch_per_step": c,
                "n": len(sev), "n_categories": K, "error": str(e)[:120]}

"""Per-model PD-retention confidence intervals, bootstrapped as a RATIO.

Retention is pd_logodds_slope(v_ttc) / pd_logodds_slope(v_terse) for the same model. The response
letter quotes intervals for it, but no analysis in the artifact produced any: only a single pooled
interval existed. Differencing or dividing two separately drawn intervals is exactly the error
Referee 3 objected to, so the ratio is recomputed inside each draw on the SAME resampled firms.
"""
import json, random, sys
from pathlib import Path
H = Path("analysis").resolve(); sys.path.insert(0, str(H)); sys.path.insert(0, str(H.parent / "config"))
import ratings as RA, cyclicality as CY   # noqa: E402

MODELS = ["openai_4o_mini", "openai_41_mini", "openai_4o", "gemini_flash",
          "gemini_flash_lite", "gemini_pro", "openai_astra"]
DISP = {"openai_4o_mini": "GPT-4o-mini", "openai_41_mini": "GPT-4.1-mini", "openai_4o": "GPT-4o",
        "gemini_flash": "Gemini Flash", "gemini_flash_lite": "Gemini Flash-Lite",
        "gemini_pro": "Gemini Pro", "openai_astra": "GPT-6 Astra"}
DRAWS = 2000

def main():
    tabs = {"full": RA.load_rating_table(subgrid_filter="full"),
            "frontier": RA.load_rating_table(subgrid_filter="frontier")}
    out = {}
    for m in MODELS:
        for sg, rt in tabs.items():
            if m not in rt.models:
                continue
            mt, mv = (m, "v_terse"), (m, "v_ttc")
            CY.clear_cache()
            firms = sorted(set(rt.firm_support(mt, "macro")) & set(rt.firm_support(mv, "macro")))
            if len(firms) < 3:
                continue
            def ratio(fs):
                CY.clear_cache(); t = CY.cyclicality_pd(rt, mt, fs)
                CY.clear_cache(); k = CY.cyclicality_pd(rt, mv, fs)
                return (k / t) if (t not in (None, 0) and k is not None) else None
            point = ratio(firms)
            rng = random.Random(4242); draws = []
            for _ in range(DRAWS):
                r = ratio([rng.choice(firms) for _ in firms])
                if r is not None:
                    draws.append(r)
            draws.sort()
            lo = draws[int(0.025 * len(draws))]; hi = draws[int(0.975 * len(draws)) - 1]
            out[m] = {"retention": point, "ci95": [lo, hi], "n_firms": len(firms),
                      "draws": len(draws), "below_075": hi < 0.75}
            print(f"  {DISP[m]:20} {point:+.3f}  [{lo:+.3f}, {hi:+.3f}]  n={len(firms)}  "
                  f"interval entirely below 0.75: {hi < 0.75}")
            break
    Path("results").mkdir(exist_ok=True)
    Path("results/pd_retention_ci.json").write_text(json.dumps(out, indent=2, sort_keys=True))
    print(f"\n  wrote results/pd_retention_ci.json ({len(out)} models)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

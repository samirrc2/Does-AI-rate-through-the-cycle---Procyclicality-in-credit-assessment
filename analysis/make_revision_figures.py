"""Revision figures. Kept SEPARATE from make_figures.py so the as-submitted figures stay
byte-reproducible from claims.json; these read results/reviewer_revision.json and cover
all seven models.

Figure 2 (referee 3 comment 4): the submitted Figure 2 plots bare downside/upside bars
with no uncertainty at all. This version carries firm-clustered bootstrap 95% CIs, which
is what makes the asymmetry claim readable: every model's downside exceeds its upside,
but the per-model RANKING is not resolvable -- the D:U ratio CIs overlap heavily because
the ratio's denominator is small. Reporting the half-slopes with CIs as primary, and the
ratio as descriptive, is the honest presentation.

  python analysis/make_revision_figures.py [--out paper/src/figures]
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt      # noqa: E402
import numpy as np                   # noqa: E402

_HERE = Path(__file__).resolve().parent
DISP = {"openai_4o_mini": "GPT-4o-mini", "openai_41_mini": "GPT-4.1-mini",
        "openai_4o": "GPT-4o", "gemini_flash_lite": "Gemini Flash-Lite",
        "gemini_flash": "Gemini Flash", "gemini_pro": "Gemini Pro",
        "openai_astra": "GPT-6 Astra"}
# ascending terse beta, so the panel reads as a capability/magnitude ordering
ORDER = ["openai_4o_mini", "openai_41_mini", "openai_4o",
         "gemini_flash_lite", "gemini_flash", "openai_astra", "gemini_pro"]


def figure2r(rev: dict, out: Path):
    hs = rev["half_slopes"]
    models = [m for m in ORDER if m in hs]
    x = np.arange(len(models)); w = 0.38
    dn = [hs[m]["down"]["point"] for m in models]
    up = [hs[m]["up"]["point"] for m in models]
    dnerr = np.array([[hs[m]["down"]["point"] - hs[m]["down"]["ci95"][0] for m in models],
                      [hs[m]["down"]["ci95"][1] - hs[m]["down"]["point"] for m in models]])
    uperr = np.array([[hs[m]["up"]["point"] - hs[m]["up"]["ci95"][0] for m in models],
                      [hs[m]["up"]["ci95"][1] - hs[m]["up"]["point"] for m in models]])
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    ax.bar(x - w/2, dn, w, yerr=dnerr, capsize=3, label="Downside (neutral$\\to$severe recession)",
           color="#8c2d04", error_kw={"lw": 0.9, "ecolor": "0.25"})
    ax.bar(x + w/2, up, w, yerr=uperr, capsize=3, label="Upside (boom$\\to$neutral)",
           color="#4292c6", error_kw={"lw": 0.9, "ecolor": "0.25"})
    # mark the models whose temperature differs from the t=0 design default
    labels = []
    for m in models:
        t = rev["temperature_by_model"].get(m, 0.0)
        labels.append(DISP[m] + ("\n(t=1)" if t and float(t) != 0.0 else ""))
    ax.set_xticks(x); ax.set_xticklabels(labels, rotation=20, ha="right", fontsize=8)
    ax.set_ylabel("Half-slope  (notches / severity step)")
    ax.axhline(0, color="0.4", lw=0.8)
    ax.set_title("Asymmetry with 95% firm-clustered bootstrap CIs: every model downgrades "
                 "faster than it upgrades", fontsize=8.5, loc="left")
    ax.legend(frameon=False, fontsize=7.5, loc="upper right")
    fig.tight_layout()
    out.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(out / f"Figure_2.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)
    # the numbers the caption must state, printed so the caption cannot drift from them
    print("  Figure_2 models:", len(models))
    for m in models:
        d, u, r = hs[m]["down"], hs[m]["up"], hs[m]["ratio_down_over_up"]
        print(f"    {DISP[m]:18} down {d['point']:.3f} [{d['ci95'][0]:.3f},{d['ci95'][1]:.3f}]  "
              f"up {u['point']:.3f} [{u['ci95'][0]:.3f},{u['ci95'][1]:.3f}]  "
              f"D:U {r['point']:.2f} [{r['ci95'][0]:.2f},{r['ci95'][1]:.2f}]")
    lo = min(hs[m]["ratio_down_over_up"]["ci95"][0] for m in models)
    print(f"  every D:U CI excludes 1? {lo > 1.0}  (lowest lower bound {lo:.2f})")


def main() -> int:
    ap = argparse.ArgumentParser()
    # Resolve against the REPO ROOT, not the caller's cwd. build.sh runs from
    # paper/src, where a relative "results/..." does not exist -- the script then
    # raised FileNotFoundError and build.sh's `|| true` swallowed it, leaving the old
    # CI-less Figure 2 in place with no visible error.
    ap.add_argument("--rev", default=str(_HERE.parent / "results" / "reviewer_revision.json"))
    ap.add_argument("--out", default="paper/src/figures")
    a = ap.parse_args()
    rev = json.loads(Path(a.rev).read_text())
    figure2r(rev, Path(a.out))
    print(f"[revfig] wrote Figure_2.(pdf|png) -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

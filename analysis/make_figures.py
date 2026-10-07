"""Generate the paper figures from claims.json. Vector PDF + 300-dpi PNG. Pure, $0.

  Figure 1  per-model cyclicality beta with 95% CIs (forest) + instruction gradient
  Figure 2  downside vs upside asymmetry per model

  python3 analysis/make_figures.py --claims claims.json --out paper/src/figures
"""
from __future__ import annotations
import argparse, json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# The frontier arms were added in revision and these two tables were not extended with them, so
# panel (a) silently plotted five models while the manuscript described seven. The filter below
# keeps any model absent from the claims file out of the figure, which is why the omission was
# invisible: nothing errored, the panel just had two fewer rows than the text claimed.
DISP = {
    "gemini_flash": "Gemini Flash",
    "gemini_flash_lite": "Gemini Flash-Lite",
    "openai_41_mini": "GPT-4.1-mini",
    "openai_4o": "GPT-4o",
    "openai_4o_mini": "GPT-4o-mini",
    "gemini_pro": "Gemini Pro",
    "openai_astra": "GPT-6 Astra",
}
ORDER = ["gemini_flash", "gemini_flash_lite", "openai_41_mini", "openai_4o", "openai_4o_mini",
         "gemini_pro", "openai_astra"]
plt.rcParams.update({"font.size": 9, "font.family": "DejaVu Sans", "axes.linewidth": 0.8,
                     "pdf.fonttype": 42, "ps.fonttype": 42})  # embed TrueType (no Type-3)


def _pmv(c, m, v):
    return c["per_model_variant"].get(f"{m}|{v}", {})


def save(fig, out: Path, name: str):
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(out / f"{name}.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def figure1(c, out: Path):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.2, 3.2), gridspec_kw={"width_ratios": [1.05, 1]})

    # (a) per-model beta (terse) with 95% CI — forest
    models = [m for m in ORDER if _pmv(c, m, "v_terse")]
    ys = list(range(len(models)))[::-1]
    for m, y in zip(models, ys):
        d = _pmv(c, m, "v_terse")
        b = d["cyclicality_notch_per_step"]; lo, hi = d["cyclicality_ci95"]
        ax1.plot([lo, hi], [y, y], color="#333", lw=1.4, zorder=2)
        ax1.plot([b], [y], "o", color="#1f4e79", ms=6, zorder=3)
    ax1.axvline(0, color="#999", lw=0.8, ls="--")
    ax1.set_yticks(ys); ax1.set_yticklabels([DISP[m] for m in models])
    ax1.set_xlabel("Procyclicality β  (notches / severity step)")
    ax1.set_title(f"(a) Per-model, terse framing ({len(models)} models)", fontsize=9, loc="left")
    ax1.margins(y=0.15)

    # (b) instruction gradient (pooled) with CI
    order = ["v_pit", "v_terse", "v_stable", "v_ttc"]
    lab = {"v_pit": "Point-\nin-time", "v_terse": "Terse", "v_stable": "\"Be\nstable\"", "v_ttc": "Through-\nthe-cycle"}
    xs = list(range(len(order)))
    bs, los, his = [], [], []
    for v in order:
        d = c["per_variant_pooled"][v]
        bs.append(d["pooled_cyclicality_notch_per_step"])
        lo, hi = d["pooled_cyclicality_ci95"]; los.append(lo); his.append(hi)
    ax2.errorbar(xs, bs, yerr=[[b - l for b, l in zip(bs, los)], [h - b for b, h in zip(bs, his)]],
                 fmt="o-", color="#1f4e79", ecolor="#333", capsize=3, lw=1.4, ms=6)
    ax2.axhline(0, color="#999", lw=0.8, ls="--")
    ax2.set_xticks(xs); ax2.set_xticklabels([lab[v] for v in order])
    ax2.set_ylabel("Pooled β  (notches / step)")
    # Panel (b) reads per_variant_pooled, which pools the FIVE original models only -- the
    # pooled v_terse beta of 0.4295 is exactly their mean, against 0.3611 for all seven. The
    # title says so rather than leaving "pooled" to be read as all of them.
    ax2.set_title("(b) Instruction gradient (pooled, 5 original models)", fontsize=9,
                  loc="left")
    ax2.set_ylim(bottom=0)
    fig.tight_layout()
    save(fig, out, "Figure_1")


def figure2(c, out: Path):
    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    models = [m for m in ORDER if _pmv(c, m, "v_terse")]
    import numpy as np
    x = np.arange(len(models)); w = 0.38
    down = [_pmv(c, m, "v_terse")["downside_slope"] for m in models]
    up = [_pmv(c, m, "v_terse")["upside_slope"] for m in models]
    ax.bar(x - w / 2, down, w, label="Downside (into recession)", color="#8c2d04")
    ax.bar(x + w / 2, up, w, label="Upside (into boom)", color="#4292c6")
    ax.set_xticks(x); ax.set_xticklabels([DISP[m] for m in models], rotation=20, ha="right")
    ax.set_ylabel("Half-slope  (notches / step)")
    ax.set_title("Asymmetry: downgrades into recession vs upgrades into boom", fontsize=9, loc="left")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    save(fig, out, "Figure_2")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--claims", default="claims.json")
    ap.add_argument("--out", default="paper/src/figures")
    args = ap.parse_args()
    c = json.loads(Path(args.claims).read_text())
    out = Path(args.out)
    figure1(c, out)
    figure2(c, out)
    print(f"[figures] wrote Figure_1.(pdf|png), Figure_2.(pdf|png) -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

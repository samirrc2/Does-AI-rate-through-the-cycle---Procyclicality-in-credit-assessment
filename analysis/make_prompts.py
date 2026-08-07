"""Extract the prompt framings + macro/placebo blocks from capture/agent.py into a
LaTeX appendix (verbatim, exactly as executed). Pure, $0.  Referee Row 8: a prompt
appendix that differs from the executed prompt is worse than none.

  python3 analysis/make_prompts.py --out paper/latex/appendix_prompts.tex
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "capture"))
sys.path.insert(0, str(ROOT / "config"))
import agent  # noqa: E402


def _ascii(text: str) -> str:
    # transliterate the few non-ASCII glyphs so verbatim typesets under T1/lmodern;
    # the exact bytes live in the code/data deposit.
    return (text.replace("\u00b0", " deg").replace("\u2013", "-").replace("\u2014", "--")
            .replace("\u2018", "'").replace("\u2019", "'").replace("\u201c", '"')
            .replace("\u201d", '"').replace("\u2192", "->"))


def vb(text: str) -> str:
    return "\\begin{verbatim}\n" + _ascii(text) + "\n\\end{verbatim}"


def esc(s: str) -> str:
    return s.replace("_", r"\_")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="paper/latex/appendix_prompts.tex")
    args = ap.parse_args()
    L = ["% AUTO-GENERATED from capture/agent.py by analysis/make_prompts.py — do not edit.",
         r"\subsection{Prompt framings}\label{app:framings}",
         "The four instruction framings (system prompt), verbatim as executed:"]
    for v in ["v_terse", "v_ttc", "v_pit", "v_stable"]:
        L.append(r"\paragraph{\texttt{%s}}" % esc(v))
        L.append(vb(agent.system_prompt(v)))
    L.append(r"\subsection{Macro-environment blocks}\label{app:macro}")
    L.append("Prepended to the byte-identical fundamentals; only these five blocks differ across the "
             "severity axis:")
    for s in ["boom", "expansion", "neutral", "slowdown", "severe_recession"]:
        L.append(r"\paragraph{%s}" % esc(s))
        L.append(vb(agent.block_for(s, "macro")))
    L.append(r"\subsection{Placebo blocks (credit-irrelevant control)}\label{app:placebo}")
    L.append("Matched in structure and number density, on a credit-irrelevant axis:")
    for s in ["placebo_calm", "placebo_mild", "placebo_normal", "placebo_rough", "placebo_storm"]:
        L.append(r"\paragraph{%s}" % esc(s))
        L.append(vb(agent.block_for(s, "placebo")))
    Path(args.out).write_text("\n\n".join(L))
    print(f"[prompts] wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

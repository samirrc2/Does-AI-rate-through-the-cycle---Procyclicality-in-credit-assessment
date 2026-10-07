"""Is any paper deliverable older than the source it is built from?

Ported from the Paper 2 build_package.sh --check gate. It exists because a deliverable
silently going stale is the easiest failure to ship: the response letter was edited and
its PDF left unrebuilt for several exchanges, so the file on disk no longer said what the
source said.

Exit 0 = everything current; 1 = something is stale; 2 = sources not present in this copy.

  python3 paper/tools/check_stale.py
"""
from __future__ import annotations
import sys
from pathlib import Path

# The script lives in paper/tools/, so parent.parent is the PAPER directory and ROOT is the
# repository. After the restructure every path below pointed at paper/paper/latex, which does
# not exist, so the checker skipped all twelve pairs and printed "nothing to check here" -- a
# staleness checker that silently checks nothing is worse than none, and it is exactly why a
# stale response-letter PDF went unnoticed.
PAPER = Path(__file__).resolve().parent.parent
ROOT = PAPER.parent
SRC = PAPER / "src"
OUT = PAPER / "out"

# derived -> the sources it must be newer than
PAIRS = [
    (OUT / "FRL-Response-to-Reviewers.pdf",  [SRC / "response_to_reviewers.txt"]),
    (OUT / "FRL-Response-to-Reviewers.docx", [SRC / "response_to_reviewers.txt"]),
    (OUT / "manuscript.pdf",                 [SRC / "manuscript.tex"]),
    (OUT / "manuscript_anonymous.pdf",       [SRC / "manuscript.tex"]),
    (OUT / "manuscript_tracked.pdf",         [SRC / "manuscript.tex"]),
    (OUT / "title_page.pdf",                 [SRC / "title_page.tex"]),
    # the Word deliverables are the ones FRL requires, and they were not checked at all
    (OUT / "manuscript.docx",                [SRC / "manuscript.tex"]),
    (OUT / "highlights.docx",                [SRC / "manuscript.tex"]),
    (OUT / "title_page.docx",                [SRC / "title_page.tex"]),
    # tables and Figure 2 are DERIVED from the analysis artifacts, so a fresh analysis with
    # a stale table is the same class of error
    (SRC / "tables" / "table0_firm_profiles.tex",
     [ROOT / "results" / "synthetic_real_overlap.json"]),
    (ROOT / "results" / "synthetic_real_overlap.json", [ROOT / "data" / "firms" / "real.jsonl"]),
    (SRC / "tables" / "table1_per_model.tex", [ROOT / "claims_revision.json"]),
    (SRC / "tables" / "table3_robustness.tex", [ROOT / "claims_revision.json"]),
    (SRC / "figures" / "Figure_2.pdf",
     [ROOT / "results" / "reviewer_revision.json"]),
    (OUT / "manuscript.pdf", [SRC / "tables" / "table1_per_model.tex",
                              SRC / "figures" / "Figure_2.pdf"]),
]


def main() -> int:
    stale, missing = [], []
    for out, srcs in PAIRS:
        present = [s for s in srcs if s.exists()]
        if not present:
            missing.append(out.name); continue
        if not out.exists():
            stale.append(f"{out.name} MISSING"); continue
        for s in present:
            if out.stat().st_mtime < s.stat().st_mtime:
                stale.append(f"{out.name} older than {s.name}")
    for m in sorted(set(missing)):
        print(f"  [skip] sources for {m} not published in this copy")
    if stale:
        for s in stale:
            print(f"  STALE: {s}")
        print(f"\n[stale] {len(stale)} deliverable(s) out of date -- rebuild before submitting")
        return 1
    if missing and len(missing) == len(PAIRS):
        print("[stale] nothing to check here"); return 2
    print(f"[stale] all {len(PAIRS)} derived files are current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

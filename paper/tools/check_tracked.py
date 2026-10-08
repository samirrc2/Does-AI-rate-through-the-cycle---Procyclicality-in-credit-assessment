#!/usr/bin/env python3
"""Fail if manuscript_tracked.pdf is not actually a tracked-changes document.

The tracked build took its baseline from HEAD, so once the revision was committed latexdiff
compared the manuscript with itself: the PDF still rendered as a normal 15-page document with
no markup at all, and nothing in the build said so. Markup volume is the only thing that
distinguishes a real diff from that, so it is checked here.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAIRS = [("manuscript_tracked", "clean"), ("manuscript_tracked_anonymous", "blinded")]
MIN_ADD = 50          # the revision rewrote whole subsections; 15 was the broken-baseline value
MIN_DEL = 50


def main() -> int:
    rc = 0
    for stem, label in PAIRS:
        rc |= check(ROOT / "paper" / "src" / f"{stem}.tex",
                    ROOT / "paper" / "out" / f"{stem}.pdf", label)
    return rc


def check(TEX, PDF, label) -> int:
    if not TEX.exists() or not PDF.exists():
        print(f"[tracked] SKIP {label} tracked sources not built")
        return 2
    s = TEX.read_text(errors="replace")
    add, dele = len(re.findall(r"DIFadd", s)), len(re.findall(r"DIFdel", s))
    try:
        import pymupdf
    except ImportError:
        print("[tracked] SKIP pymupdf unavailable")
        return 2
    d = pymupdf.open(PDF)
    colours = set()
    for pg in d:
        for b in pg.get_text("dict")["blocks"]:
            for ln in b.get("lines", []):
                for sp in ln.get("spans", []):
                    colours.add(sp["color"])
    coloured = {c for c in colours if c != 0}
    ok = add >= MIN_ADD and dele >= MIN_DEL and coloured
    print(f"[tracked] {label}: {add} addition and {dele} deletion markers, "
          f"{len(coloured)} non-black text colour(s) in the PDF")
    if not ok:
        print(f"  FAIL this is not a tracked-changes document "
              f"(need >={MIN_ADD} additions, >={MIN_DEL} deletions and coloured text). "
              f"Check the latexdiff baseline is the as-submitted ref, not HEAD.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

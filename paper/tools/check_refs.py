"""Fail the build on an unresolved cross-reference.

An undefined \\ref renders as "??" in the PDF. LaTeX reports it as a warning among hundreds of
lines of log noise, and build.sh discards the log, so the only reliable place to catch it is the
rendered text.

  python3 paper/tools/check_refs.py

Exit 0 = no "??" in any deliverable; 1 = at least one; 2 = pymupdf unavailable (not a pass).
"""
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "out"
PDFS = ("manuscript", "manuscript_anonymous", "manuscript_tracked")

try:
    import pymupdf
except ImportError:
    print("[refs] pymupdf unavailable -> NOT CHECKED (declare it: see requirements.txt)")
    raise SystemExit(2)

bad = 0
for name in PDFS:
    p = OUT / f"{name}.pdf"
    if not p.exists():
        print(f"[refs] {name}.pdf absent -> not checked"); continue
    d = pymupdf.open(p)
    txt = "\n".join(pg.get_text() for pg in d)
    d.close()
    n = txt.count("??")
    bad += n
    print(f"[refs] {name}.pdf: {n} unresolved reference(s)")
raise SystemExit(1 if bad else 0)

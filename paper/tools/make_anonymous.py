#!/usr/bin/env python3
"""Generate manuscript_anonymous.tex from manuscript.tex.

It used to be a hand-maintained second copy, and it drifted: on 2026-10-05 the double-blind
version was six days and roughly fifteen content changes behind the real manuscript, still
carrying the old Introduction, the withdrawn "shifts the level, not the slope" claim and the
pre-rewrite Appendix A. A referee reading it would have reviewed a different paper.

Anonymisation is only a front-matter transformation, so the body can be taken verbatim:

  * \\shortauthors is emptied and the author blocks collapse to a single "Anonymous";
  * \\bibliography switches to refs_blind, which omits the authors' own cited work;
  * Data availability drops the DOI, which identifies the authors through the archive.

The script asserts afterwards that no author name, e-mail, ORCID or the archive DOI survives.
A silent leak in a double-blind submission is the failure mode worth guarding against.

  python3 paper/tools/make_anonymous.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

PAPER = Path(__file__).resolve().parent.parent
SRC = PAPER / "src" / "manuscript.tex"
DST = PAPER / "src" / "manuscript_anonymous.tex"

# Real identifiers, checked in the source. The bare word "orcid" is NOT here: the source
# legitimately contains \printorcid in the command that suppresses the label, so checking for
# it at source level flags our own fix. The rendered-PDF audit checks for it instead, which is
# where an empty "ORCID(s):" footnote would actually reach a referee.
IDENTIFIERS = ("Chincholikar", "Chawla", "samir.chincholikar", "robin.chawla", "0009-0007",
               "10.5281/zenodo.21864041", "10.5281/zenodo.21864042")

ANON_AUTHOR = "\\author[1]{Anonymous}\n"
ANON_DATA = """\\section*{Data availability}
All data and code required to reproduce every result are openly available in a public repository.
The citable archive (DOI) is withheld here to preserve author anonymity for double-blind review and
will be provided on acceptance \\citep{artifact2026}.
"""


def main() -> int:
    if not SRC.exists():
        print(f"[anon] {SRC} not present", file=sys.stderr)
        return 2
    s = SRC.read_text()

    # front matter: everything from the first \author to \cortext becomes one anonymous author
    s = re.sub(r"\\shortauthors\{[^}]*\}", r"\\shortauthors{}", s)
    first = s.find("\\author[")
    last = s.find("\\cortext[")
    if first < 0 or last < first:
        print("[anon] cannot find the author block; front matter has changed shape",
              file=sys.stderr)
        return 1
    end = s.find("\n", s.find("}", last))
    s = s[:first] + ANON_AUTHOR + s[end + 1:]

    # the blinded bibliography
    s = s.replace("\\bibliography{refs}", "\\bibliography{refs_blind}")

    # The CAS class always footnotes "ORCID(s):" whenever \printorcid runs, and with a single
    # anonymous author it printed the label with nothing after it. An empty ORCID line in a
    # double-blind PDF advertises that metadata was stripped, so the command is neutralised.
    s = s.replace("\\begin{document}",
                  "\\makeatletter\\renewcommand\\printorcid{}\\makeatother\n\\begin{document}", 1)

    # the archive DOI identifies the authors
    m = re.search(r"\\section\*\{Data availability\}.*?(?=\n\n)", s, re.S)
    if m:
        s = s[:m.start()] + ANON_DATA.rstrip() + s[m.end():]

    DST.write_text(s)

    leaked = [k for k in IDENTIFIERS if k.lower() in s.lower()]
    if leaked:
        print(f"[anon] IDENTITY LEAK in the blinded source: {leaked}", file=sys.stderr)
        return 1
    print(f"[anon] wrote {DST.relative_to(PAPER.parent)} "
          f"({len(s.splitlines())} lines, no identifier in the source)")
    return 0


def audit_pdf(pdf: Path) -> int:
    """Check the RENDERED pdf, which is where a leak actually reaches a referee.

    Checking only the .tex passed while the typeset page carried an empty "ORCID(s):" footnote
    the class had added on its own. A source-level check cannot see what the class emits.
    """
    try:
        import pymupdf
    except ImportError:
        print("[anon] pymupdf absent, cannot audit the rendered PDF", file=sys.stderr)
        return 2
    t = " ".join(" ".join(p.get_text().split()) for p in pymupdf.open(pdf))
    leaked = [k for k in IDENTIFIERS + ("orcid",) if k.lower() in t.lower()]
    if leaked:
        print(f"[anon] IDENTITY LEAK in {pdf.name}: {leaked}", file=sys.stderr)
        return 1
    print(f"[anon] {pdf.name} audited: no author name, e-mail, ORCID or archive DOI")
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--audit":
        raise SystemExit(audit_pdf(PAPER / "out" / "manuscript_anonymous.pdf"))
    raise SystemExit(main())

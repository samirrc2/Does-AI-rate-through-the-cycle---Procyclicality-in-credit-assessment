#!/usr/bin/env python3
"""Rewrite a latexdiff output so pandoc can carry its markup into Word.

pandoc does not know \\DIFadd and \\DIFdel. Converting a tracked source directly yields a
document with every revision mark silently dropped, which is worse than producing nothing: it
looks like a clean manuscript. The macros are mapped to underline and strikethrough, which is
how a reviewer expects tracked changes to read.

Usage: tracked_to_word.py <tracked.tex> <out.tex>
"""
import re
import sys
from pathlib import Path


def convert(s: str) -> tuple:
    # latexdiff's preamble defines the DIF macros. It must go as a block: stripping the macro
    # names first turned \providecommand{\DIFaddbegin}{} into \providecommand{}{} and pandoc
    # stopped at "unexpected }".
    s = "\n".join(l for l in s.split("\n") if "%DIF PREAMBLE" not in l)
    s = re.sub(r"^%DIFDELCMD.*$", "", s, flags=re.M)
    # latexdiff also emits DIF macro DEFINITIONS outside the marked preamble. Stripping
    # macro names first turned \newcommand{\DIFdelgraphicswidth}{0.5} into
    # \newcommand{}{0.5} and pandoc stopped at "unexpected }". Definitions therefore go as
    # whole lines, before any macro name is touched.
    s = re.sub(r"^[ \t]*\\(?:re)?newcommand\*?\s*\{?\s*\\DIF.*$", "", s, flags=re.M)
    s = re.sub(r"^[ \t]*\\providecommand\*?\s*\{?\s*\\DIF.*$", "", s, flags=re.M)
    s = re.sub(r"^[ \t]*\\(?:newlength|setlength)\s*\{?\s*\\DIF.*$", "", s, flags=re.M)

    # the markup itself, innermost first so FL (float) variants are not half-matched
    n_add = len(re.findall(r"\\DIFadd(?:FL)?\{", s))
    n_del = len(re.findall(r"\\DIFdel(?:FL)?\{", s))
    s = re.sub(r"\\DIFadd(?:FL)?\{", r"\\uline{", s)
    s = re.sub(r"\\DIFdel(?:FL)?\{", r"\\sout{", s)

    # the position markers carry no content
    s = re.sub(r"\\DIF(?:O)?(?:add|del|mod)(?:begin|end)(?:FL)?\b\s*", "", s)
    # graphics helpers latexdiff emits around figures
    s = re.sub(r"\\DIF(?:O)?(?:add|del)includegraphics\b", r"\\includegraphics", s)
    s = re.sub(r"\\DIFdelgraphics(?:width|height|box)\b\s*", "", s)
    s = re.sub(r"\\DIFscaledelfig\b\s*", "", s)
    # anything left over would reach pandoc as an unknown control sequence
    s = re.sub(r"\\DIF[a-zA-Z]*\b\s*", "", s)

    # Inline math must become ordinary text. pandoc renders $...$ as an OMML <m:oMath>
    # element rather than a <w:r> run, and a revision mark can only wrap runs: a deleted
    # "$0.429$" therefore survived "Accept All", leaving "procyclical0.429 , from 0.182 to
    # 0.775" in the accepted text. Every changed figure in a numbers paper would do the same.
    # A tracked review copy needs correct marking far more than it needs typeset math.
    SYM = {r"\\beta": "\u03b2", r"\\Delta": "\u0394", r"\\Sigma": "\u03a3",
           r"\\times": "\u00d7", r"\\approx": "\u2248", r"\\pm": "\u00b1",
           r"\\to": "\u2192", r"\\ldots": "\u2026", r"\\dagger": "\u2020",
           r"\\S": "\u00a7", r"\\%": "%", r"\\,": "\u2009", r"\\!": ""}

    def demath(m):
        t = m.group(1)
        for k, v in SYM.items():
            t = re.sub(k + r"(?![a-zA-Z])", v, t)
        t = re.sub(r"\\mathrm\{([^}]*)\}|\\text\{([^}]*)\}",
                   lambda mm: mm.group(1) or mm.group(2), t)
        t = re.sub(r"\^\{?([0-9n])\}?", lambda mm: {"2": "\u00b2", "3": "\u00b3",
                                                  "1": "\u00b9"}.get(mm.group(1), mm.group(1)), t)
        t = re.sub(r"_\{?([0-9a-zA-Z]+)\}?", r"\1", t)
        t = t.replace("{,}", ",").replace("{", "").replace("}", "")
        t = re.sub(r"\s+([,.;:%])", r"\1", t)      # no space before punctuation
        t = re.sub(r"(?<=\d)\s+(?=\d{3}\b)", ",", t)
        return t.strip()

    s = re.sub(r"\$([^$]{1,200}?)\$", demath, s)
    s = re.sub(r"(\\(?:uline|sout)\{)\s+", r"\1", s)

    if "\\usepackage{ulem}" not in s:
        s = s.replace("\\begin{document}", "\\usepackage[normalem]{ulem}\n\\begin{document}", 1)
    return s, n_add, n_del


if __name__ == "__main__":
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    out, a, d = convert(src.read_text())
    if a + d == 0:
        sys.exit(f"   {src}: no tracked markup found -- refusing to write a file that "
                 f"would look like a clean manuscript")
    left = re.findall(r"\\DIF[a-zA-Z]*", out)
    if left:
        sys.exit(f"   {src}: {len(left)} latexdiff macro(s) would reach pandoc: "
                 f"{sorted(set(left))[:4]}")
    dst.write_text(out)
    print(f"   {src.name}: {a} additions, {d} deletions mapped")

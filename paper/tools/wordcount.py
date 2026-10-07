"""FRL main-text word count. Prints the countable total and the margin to the 2,500 cap.

FRL counts main text INCLUDING in-text citations and footnotes, and EXCLUDING the abstract,
highlights, keywords, references, tables, figures, captions, declarations and appendices.
So this strips the exclusions from manuscript.tex, runs texcount on what remains, and adds
back an estimate for the citation commands, which texcount counts as zero but which render
as "(Author et al., Year)".

Two earlier attempts at this got it wrong in opposite directions and both were used to make
decisions: a hand-rolled regex counter silently included the abstract (because this template
uses \section*{Abstract}, not the abstract environment), and a PDF-extraction counter
reported the count RISING after text was deleted, because floating tables drifted in and out
of the measured span. Use texcount on a stripped copy; do not hand-roll it.

  python3 paper/tools/wordcount.py
"""
from __future__ import annotations
import re, shutil, subprocess, sys
from pathlib import Path

# The script lives in paper/tools/, so its parent.parent IS the paper directory.
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "manuscript.tex"
ABSTRACT_CAP = 250      # FRL: abstract cap
KEYWORD_CAP = 7         # FRL: 1-7 keywords
CAP = 2500
WORDS_PER_CITE = 3.5      # "(Author et al., 2024)" -- conservative

EXCLUDE = (r'\\begin\{abstract\}.*?\\end\{abstract\}',
           r'\\begin\{highlights\}.*?\\end\{highlights\}',
           r'\\begin\{keyword\}.*?\\end\{keyword\}',
           r'\\begin\{table\}.*?\\end\{table\}',
           r'\\begin\{figure\}.*?\\end\{figure\}',
           r'\\section\*\{Declaration.*?(?=\\section|\Z)',
           r'\\section\*\{Funding.*?(?=\\section|\Z)',
           r'\\section\*\{Data availability.*?(?=\\section|\Z)',
           r'\\input\{[^}]*\}')


def main() -> int:
    if not SRC.exists():
        print(f"[wc] {SRC} not present in this copy"); return 2
    tc = shutil.which("texcount") or str(Path.home() /
         "Library/TinyTeX/bin/universal-darwin/texcount")
    if not Path(tc).exists():
        print("[wc] texcount not installed (tlmgr install texcount)"); return 2
    s = SRC.read_text()
    m = re.search(r'\\begin\{document\}', s)
    body = s[m.end():] if m else s
    ap = re.search(r'\\appendix', body)
    if ap:
        body = body[:ap.start()]
    for pat in EXCLUDE:
        body = re.sub(pat, '', body, flags=re.S)
    n_cite = len(re.findall(r'\\cite[a-z]*\{', body))
    tmp = Path("/tmp/_frl_maintext.tex")
    tmp.write_text("\\documentclass{article}\\usepackage{natbib}\\begin{document}\n"
                   + body + "\n\\end{document}\n")
    out = subprocess.run([tc, "-brief", str(tmp)], capture_output=True, text=True).stdout
    mm = re.match(r'\s*(\d+)', out)
    if not mm:
        print(f"[wc] could not parse texcount output: {out[:120]}"); return 2
    words = int(mm.group(1))
    cites = int(round(n_cite * WORDS_PER_CITE))
    total = words + cites
    print(f"  texcount body        : {words}")
    print(f"  + {n_cite} citations       : {cites}")
    print(f"  FRL countable total  : {total}")
    print(f"  cap {CAP}             : {'OVER by ' + str(total-CAP) if total > CAP else 'under by ' + str(CAP-total)}")
    bad = total > CAP

    src = SRC.read_text()
    am = re.search(r'\\begin\{abstract\}(.*?)\\end\{abstract\}', src, flags=re.S)
    if am is None:
        print("  abstract             : NOT FOUND -- cap unchecked"); bad = True
    else:
        a = re.sub(r'\\[a-zA-Z]+\*?(\[[^\]]*\])?', ' ', am.group(1))
        a = re.sub(r'[{}$\\]', ' ', a)
        n_abs = len([x for x in a.split() if any(c.isalnum() for c in x)])
        over = n_abs > ABSTRACT_CAP
        bad |= over
        print(f"  abstract             : {n_abs}  cap {ABSTRACT_CAP} -> "
              f"{'OVER by ' + str(n_abs-ABSTRACT_CAP) if over else 'under by ' + str(ABSTRACT_CAP-n_abs)}")

    km = re.search(r'\\begin\{keywords?\}(.*?)\\end\{keywords?\}', src, flags=re.S)
    if km is None:
        print("  keywords             : NOT FOUND -- cap unchecked"); bad = True
    else:
        n_kw = len([x for x in km.group(1).split(r'\sep') if x.strip()])
        over = not (1 <= n_kw <= KEYWORD_CAP)
        bad |= over
        print(f"  keywords             : {n_kw}  allowed 1-{KEYWORD_CAP} -> "
              f"{'OUT OF RANGE' if over else 'ok'}")

    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())

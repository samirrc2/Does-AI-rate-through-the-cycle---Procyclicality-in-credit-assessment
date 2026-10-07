#!/usr/bin/env python3
"""Typeset paper/src/response_to_reviewers.txt as FRL-Response-to-Reviewers.{pdf,docx}.

Ported from the Paper 2 (IEEE Access) builder and retargeted at Finance Research
Letters. The letter STRUCTURE is deliberately unchanged -- covering letter on page 1,
then one section per concern quoting the referee in full before the response -- because
that structure is what makes a 16-concern reply auditable. Only the journal-facing
names change: FRL has no response .docx template of its own, so the reviewer-attribution
colour is retained as attribution rather than as template compliance.

The .txt is the source of truth. Elsevier accepts a response file on upload, so both formats are produced:
the DOCX for editing and the PDF for reading. Structure follows their template -- for each comment, the reviewer's concern, then
"Author response:", then "Author action:".

Page 1 is the covering letter, set as a block letter: the manuscript-identification fields and
the To/Re fields are aligned label-and-value rows rather than running text, separated by
whitespace, with the signature lines broken where they are written. Without that the fields join into
one paragraph and the manuscript ID runs into the article title. The item-by-item responses begin
on page 2, which is what the [PAGEBREAK] marker in the source does.

Three markers structure the letter: [GAP] opens vertical space between the letter's parts,
[SIGNATURE] starts the block where line breaks are kept as written, and [PAGEBREAK] ends page 1. Lines of the form "Label: value"
above the salutation become the aligned field rows.

Concern headings carry the reviewer and concern number only. The quoted comment immediately
below says what the concern is, so a summary title would only restate it.

Each concern quotes the reviewer's comment in full before the response. Those quoted paragraphs
are set in the template's green (008000), matching the colour the IEEE Access .docx template uses
for the "Reviewer#N, Concern # M (please list here)" lines. Nothing else is coloured, and the
green is confined to the reviewer's own words so it reads as attribution rather than decoration.

The letter uses two bullet levels, distinguished by indentation in the source: two spaces for
the first level and six for the second. Those become nested itemize environments.

Otherwise plain: no bold outside the headings, no italics, no rules.

Usage: python3 paper/tools/build_response.py
"""
import os
import re
import shutil
import zipfile
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# The tooling lives in paper/tools/, the letter source in paper/src/, the deliverables in
# paper/out/ -- one directory per role, so nothing generated sits next to a source.
PAPER = os.path.dirname(HERE)
SRC = os.path.join(PAPER, "src", "response_to_reviewers.txt")
OUT_DIR = os.path.join(PAPER, "out")
# The .txt keeps its working name; the generated deliverables carry the name the journal
# sees on upload.
OUT_STEM = "FRL-Response-to-Reviewers"
SPECIAL = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
           "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}",
           "^": r"\textasciicircum{}",
           # pasted from the decision letter, so it arrives with the reviewers' own glyphs
           "\u2192": r"$\rightarrow$", "\u2190": r"$\leftarrow$", "\u2212": r"$-$",
           "\u2033": r"$^{\prime\prime}$", "\u2032": r"$^{\prime}$", "\u2248": r"$\approx$",
           "\u2264": r"$\leq$", "\u2265": r"$\geq$", "\u00d7": r"$\times$",
           "\u2013": "--", "\u2014": "---", "\u2019": "'", "\u2018": "`", "\u2026": r"\ldots{}",
           # curly double quotes and the plus-minus sign arrive in pasted response text; with no
           # mapping pdflatex renders the wrong glyph or drops it silently
           "\u201c": "``", "\u201d": "''", "\u00b1": r"$\pm$",
           # Greek letters reach this file from the manuscript's notation. With no mapping,
           # pdflatex under T1 fontenc drops them silently: "(Table 1, \u0394\u03b2, and ..."
           # rendered as "(Table 1, , and ...", losing the symbol the sentence was about.
           "\u0394": r"$\Delta$", "\u03b2": r"$\beta$", "\u03ba": r"$\kappa$",
           "\u03c6": r"$\phi$", "\u03c3": r"$\sigma$", "\u03a3": r"$\Sigma$"}

PRE = r"""\documentclass[11pt]{article}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{mathptmx}
\usepackage[margin=1in]{geometry}
\usepackage[hidelinks]{hyperref}
\usepackage{enumitem}
\usepackage{microtype}
\usepackage{tabularx}
\usepackage[dvipsnames]{xcolor}
\definecolor{ReviewerGreen}{HTML}{008000}
\newcommand{\rvcomment}[1]{{\color{ReviewerGreen}#1}}
\newcommand{\concern}[1]{\textbf{\color{ReviewerGreen}#1}}
\setlength{\parindent}{0pt}
\setlength{\parskip}{6pt}
\setlist[itemize,1]{leftmargin=1.6em,labelsep=0.6em,itemsep=3pt,topsep=3pt,parsep=0pt,
                    label=\raisebox{-0.15ex}{\large\textbullet}}
\setlist[itemize,2]{leftmargin=1.4em,labelsep=0.5em,itemsep=2pt,topsep=3pt,parsep=0pt,
                    label=\textendash}
\pagestyle{plain}
\begin{document}
"""


GREEN = "008000"


def _style_runs(para, color=None, bold=False):
    """Push colour and weight onto every run in one Word paragraph.

    Word carries character formatting on the run, not the paragraph, so the properties have to
    be injected run by run. w:rPr must be the first child of w:r, and within rPr w:b precedes
    w:color; getting that order wrong makes Word treat the file as corrupt.
    """
    props = ("<w:b/>" if bold else "") + (f'<w:color w:val="{color}"/>' if color else "")
    if not props:
        return para

    def fix(m):
        run = m.group(0)
        if "<w:rPr>" in run:
            return run.replace("<w:rPr>", "<w:rPr>" + props, 1)
        return run.replace(m.group(1), m.group(1) + "<w:rPr>" + props + "</w:rPr>", 1)

    return re.sub(r"(<w:r(?: [^>]*)?>)(?:(?!</w:r>).)*</w:r>", fix, para, flags=re.S)


def colour_docx(path):
    """Set the reviewer's own words in the template's green, as the IEEE .docx template does.

    pandoc writes plain runs, so this is a post-pass over document.xml. Green covers the concern
    heading, the "Reviewer comment:" label and the quoted comment; it stops at "Author response:",
    so nothing we wrote ourselves is green.
    """
    z = zipfile.ZipFile(path)
    parts = {n: z.read(n) for n in z.namelist()}
    z.close()
    xml = parts["word/document.xml"].decode("utf-8")
    head, body = xml.split("<w:body>", 1)
    body, tail = body.rsplit("</w:body>", 1)

    out, green, n_green, n_bold = [], False, 0, 0
    for chunk in re.split(r"(<w:p(?: [^>]*)?>.*?</w:p>)", body, flags=re.S):
        if not chunk.startswith("<w:p"):
            out.append(chunk)
            continue
        text = re.sub(r"<[^>]+>", "", chunk).strip()
        if re.match(r"^Reviewer #\d+, Concern #\d+:?$", text):
            green = False
            out.append(_style_runs(chunk, GREEN, bold=True)); n_green += 1; n_bold += 1
        elif text == "Reviewer comment:":
            green = True
            out.append(_style_runs(chunk, GREEN, bold=True)); n_green += 1; n_bold += 1
        elif text in ("Author response:", "Author action:"):
            green = False
            out.append(_style_runs(chunk, bold=True)); n_bold += 1
        elif green and text:
            out.append(_style_runs(chunk, GREEN)); n_green += 1
        else:
            out.append(chunk)
    parts["word/document.xml"] = (head + "<w:body>" + "".join(out) + "</w:body>" + tail).encode("utf-8")

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as w:
        for n, d in parts.items():
            w.writestr(n, d)
    return n_green, n_bold


def esc(t):
    out, openq = [], True
    for ch in t:
        if ch == '"':
            out.append("``" if openq else "''")
            openq = not openq
        else:
            out.append(SPECIAL.get(ch, ch))
    # No digit-hyphen to en-dash substitution here. Every such string in this letter is an
    # identifier -- SR 11-7, SR 26-2, the manuscript ID -- and an en-dash would misprint it.
    return "".join(out)


def to_tex(txt):
    lines = txt.split("\n")
    blocks, para, depth = [], [], 0
    green = False   # inside a quoted reviewer comment
    fields = []     # consecutive "Label: value" rows of the letter head

    FIELD = re.compile(r"^(Original Manuscript ID|Original Article Title|To|Re|Date):\s*(.*)$")

    def flush_para():
        if para:
            body = esc(" ".join(para))
            blocks.append(r"\rvcomment{" + body + "}" if green else body)
            para.clear()

    def flush_fields():
        """Emit collected label/value rows as one aligned block.

        tabularx sizes the value column to whatever the label column needs, so the article
        title wraps under itself instead of pushing past the margin.
        """
        if not fields:
            return
        rows = " \\\\[3pt]\n".join(
            r"\textbf{" + esc(k + ":") + "} & " + esc(v) for k, v in fields)
        blocks.append(r"\noindent\begin{tabularx}{\textwidth}{@{}l@{\hspace{1.1em}}X@{}}"
                      + "\n" + rows + "\n" + r"\end{tabularx}")
        fields.clear()

    def close(to):
        nonlocal depth
        while depth > to:
            blocks.append(r"\end{itemize}")
            depth -= 1

    i = 0
    while i < len(lines):
        raw = lines[i]
        s = raw.strip()
        if not s:
            flush_para(); flush_fields()
            i += 1
            continue
        m = re.match(r"^(\s*)-\s+(.*)$", raw)
        if m:
            flush_para()
            want = 2 if len(m.group(1)) >= 5 else 1
            item = [m.group(2)]
            # gather continuation lines, which are indented further and not bullets
            while i + 1 < len(lines) and lines[i + 1].strip() \
                    and not re.match(r"^\s*-\s+", lines[i + 1]):
                i += 1
                item.append(lines[i].strip())
            if want > depth:
                while depth < want:
                    # \color inside the environment covers the \item LABELS too. Colouring only
                    # the item text left the bullet glyphs black while their text was green --
                    # which is what "Reviewer 2's comments are not in green" actually was.
                    blocks.append(r"\begin{itemize}" +
                                  (r"\color{ReviewerGreen}" if green else ""))
                    depth += 1
            else:
                close(want)
            # A bulleted line inside a reviewer comment must stay green like the rest of that
            # comment. Emitting a bare \item dropped the colour, so Reviewer 2's concerns 3 and 4
            # -- the only quoted comments that contain a bullet list -- rendered black in the PDF
            # while the other fourteen were green.
            txt = esc(" ".join(item))
            blocks.append(r"\item " + (r"\rvcomment{" + txt + "}" if green else txt))
            i += 1
            continue
        close(0)
        m = FIELD.match(s)
        if m:
            flush_para()
            fields.append((m.group(1), m.group(2)))
            i += 1
            continue
        if s == "[GAP]":
            flush_para(); flush_fields()
            # A block letter separates its parts by whitespace, not by a drawn rule.
            blocks.append(r"\vspace{18pt}")
            i += 1
            continue
        if s == "[SIGNATURE]":
            flush_para(); flush_fields()
            sig = []
            while i + 1 < len(lines) and lines[i + 1].strip():
                i += 1
                sig.append(esc(lines[i].strip()))
            # space for a signature between the closing and the names
            blocks.append(r"\vspace{14pt}" + "\n"
                          + (sig[0] + r" \\[22pt]" + "\n" if sig else "")
                          + (r" \\" + "\n").join(sig[1:]))
            i += 1
            continue
        if s.startswith("Dear ") and s.endswith(","):
            # separate the salutation from the field block above it, or the letter reads as
            # a continuous list rather than as a letter
            flush_para(); flush_fields()
            blocks.append(r"\vspace{16pt}" + "\n" + esc(s))
            i += 1
            continue
        if s == "[PAGEBREAK]":
            flush_para(); flush_fields()
            blocks.append(r"\newpage")
            i += 1
            continue
        if re.match(r"^Reviewer #\d+, Concern #\d+:?$", s):
            flush_para()
            green = False
            blocks.append(r"\vspace{12pt}" + "\n" + r"\concern{" + esc(s) + "}")
            i += 1
            continue
        if s == "Reviewer comment:":
            flush_para()
            green = True
            blocks.append(r"\concern{" + esc(s) + "}")
            i += 1
            continue
        if s in ("Author response:", "Author action:"):
            flush_para()
            green = False
            blocks.append(r"\textbf{" + esc(s) + "}")
            i += 1
            continue
        para.append(s)
        i += 1
    flush_para()
    flush_fields()
    close(0)
    return PRE + "\n\n".join(blocks) + "\n\n\\end{document}\n"


def main():
    txt = open(SRC, encoding="utf-8").read()
    stem = os.path.join(OUT_DIR, OUT_STEM)
    open(stem + ".tex", "w", encoding="utf-8").write(to_tex(txt))
    tex = shutil.which("pdflatex") or os.path.expanduser(
        "~/Library/TinyTeX/bin/universal-darwin/pdflatex")
    for _ in range(2):
        subprocess.run([tex, "-interaction=nonstopmode", OUT_STEM + ".tex"],
                       cwd=OUT_DIR, capture_output=True)
    pages = "?"
    log = stem + ".log"
    if os.path.exists(log):
        m = re.search(r"\((\d+) pages", open(log, encoding="utf-8", errors="replace").read())
        if m:
            pages = m.group(1)
    for ext in (".aux", ".log", ".out"):
        if os.path.exists(stem + ext):
            os.remove(stem + ext)
    print(f"   {OUT_STEM}.pdf  {pages} pages")
    if shutil.which("pandoc"):
        # pandoc reads the letter as markdown, so a reviewer comment opening "1. Please
        # justify..." becomes an ordered-list item and the reviewer's own numbering is
        # rewritten or dropped. Escaping the enumerator keeps the quoted text verbatim.
        md = re.sub(r"^(\d+)([.)])(\s)", r"\1\\\2\3",
                    open(SRC, encoding="utf-8").read(), flags=re.M)
        tmp = stem + "_pandoc.md"
        open(tmp, "w", encoding="utf-8").write(md)
        subprocess.run(["pandoc", "-f", "markdown", tmp, "-o", stem + ".docx"], check=True)
        os.remove(tmp)
        g, b = colour_docx(stem + ".docx")
        print(f"   {OUT_STEM}.docx  ({g} green paragraphs, {b} bold)")


if __name__ == "__main__":
    main()

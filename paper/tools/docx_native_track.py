#!/usr/bin/env python3
"""Turn underline/strikethrough markup in a DOCX into native Word tracked changes.

pandoc can only carry latexdiff's markup across as character formatting. That looks like a
tracked-changes document and is not one: Word's Review pane reads <w:ins> and <w:del>, so with
formatting alone a reviewer cannot accept or reject anything, cannot toggle the markup off to
read clean text, and the file reports no revisions at all.

Each underlined run becomes an insertion and each struck run a deletion, with the visual
formatting removed so Word draws its own revision marks.

Usage: docx_native_track.py <in.docx> <out.docx> [author]
"""
import re
import shutil
import sys
import zipfile
from pathlib import Path

DATE = "2026-10-07T00:00:00Z"


def convert(xml: str, author: str) -> tuple:
    out, n_ins, n_del = [], 0, 0
    pos, counter = 0, 1000
    for m in re.finditer(r"<w:r>(?:(?!</w:r>).)*</w:r>", xml, re.S):
        run = m.group(0)
        out.append(xml[pos:m.start()])
        pos = m.end()
        ins = "<w:u " in run
        dele = "<w:strike/>" in run or "<w:strike " in run
        if not (ins or dele) or not re.search(r"<w:t[^>]*>", run):
            out.append(run)
            continue
        # drop the visual markup: Word draws its own once the run is a revision
        body = re.sub(r"<w:u [^/>]*/>", "", run)
        body = re.sub(r"<w:strike[^/>]*/>", "", body)
        counter += 1
        attrs = f'w:id="{counter}" w:author="{author}" w:date="{DATE}"'
        if dele:
            # a deleted run carries w:delText, not w:t, or Word drops the text entirely
            body = re.sub(r"<w:t(\s[^>]*)?>", lambda mm: "<w:delText%s>" % (mm.group(1) or ""), body)
            body = body.replace("</w:t>", "</w:delText>")
            out.append(f"<w:del {attrs}>{body}</w:del>")
            n_del += 1
        else:
            out.append(f"<w:ins {attrs}>{body}</w:ins>")
            n_ins += 1
    out.append(xml[pos:])
    return "".join(out), n_ins, n_del


if __name__ == "__main__":
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    author = sys.argv[3] if len(sys.argv) > 3 else "Author"
    tmp = dst.with_suffix(".tmp.docx")
    with zipfile.ZipFile(src) as zin:
        names = zin.namelist()
        doc = zin.read("word/document.xml").decode("utf8")
        new, a, d = convert(doc, author)
        if a + d == 0:
            sys.exit(f"   {src.name}: no underline/strikethrough runs found -- refusing to "
                     f"write a file that would report zero revisions")
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
            for n in names:
                zout.writestr(n, new.encode("utf8") if n == "word/document.xml" else zin.read(n))
    shutil.move(tmp, dst)
    print(f"   {dst.name}: {a} insertions, {d} deletions as native Word revisions "
          f"(author '{author}')")

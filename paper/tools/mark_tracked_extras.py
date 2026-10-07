"""Add tracked-change markup that latexdiff cannot: table cells and reference entries.

latexdiff is configured with PICTUREENV=(...|tabular|thebibliography), which makes it leave
those interiors alone. That is forced, not a preference:

  * taking tabular out produces 45 "Missing \\cr" + 44 "Misplaced \\cr" and a fatal error,
    because booktabs' \\toprule expands to \\noalign, which cannot sit inside latexdiff's
    \\DIFaddbeginFL group. No PDF is produced at all.
  * taking thebibliography out produces 28 "Something's wrong--perhaps a missing \\item",
    because a wholly new \\bibitem ends up inside a \\DIFadd{} group.

So the markup is injected here instead, after latexdiff and before pdflatex, at a granularity
that compiles: whole cell contents, and whole reference entries. Both use \\TRKadd / \\TRKdel,
which are colour-only, so nothing is wrapped in \\uwave or \\sout where a \\url or a math group
could break it.

  python3 paper/tools/mark_tracked_extras.py <baseline-dir> [tracked.tex]

Exit 0 = markup injected; 1 = the tracked file or baseline is not where expected.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "src"

PREAMBLE = (
    "%DIF TRK PREAMBLE\n"
    "\\makeatletter\n"
    "\\long\\def\\TRKadd#1{{\\protect\\color{blue}#1}}\n"
    "\\long\\def\\TRKdel#1{{\\protect\\color{red}#1}}\n"
    "\\makeatother\n"
    "%DIF TRK PREAMBLE END\n"
)


def cells(row: str) -> list[str]:
    return [c.strip() for c in row.split("&")]


def _scan(tex: str):
    """Walk a tabular and return {(row label, column name): cell}, plus the column names seen.

    Columns must be matched by NAME, not position. Table 1's columns were restructured between
    submission and revision, so a positional comparison reported every cell as changed and
    printed things like "0.230 -> 0.230 [0.19, 0.27]", which is noise rather than a change.
    """
    m = re.search(r"\\begin\{tabular\}[^\n]*\n(.*?)\\end\{tabular\}", tex, re.S)
    if not m:
        return {}, set()
    cellmap, names, hdr = {}, set(), None
    for line in m.group(1).split("\n"):
        t = line.strip()
        if not t or t.startswith(("\\toprule", "\\midrule", "\\bottomrule", "\\cmidrule",
                                  "\\multicolumn", "%")):
            continue
        if "&" not in t:
            continue
        body = t.rstrip()
        body = body[:-2] if body.endswith("\\\\") else body
        c = cells(body)
        # a row whose first cell repeats the stub label starts a new panel header
        if hdr is None or c[0] == hdr[0]:
            hdr = c
            names |= {x for x in c[1:] if x}
            continue
        for name, val in zip(hdr[1:], c[1:]):
            if name:
                cellmap[(c[0], name)] = val
    return cellmap, names


def mark_table(cur_tex: str, base_tex: str):
    """Colour each current cell whose same-named column differs from the baseline."""
    base, base_cols = _scan(base_tex)
    changed = added = 0
    out, hdr = [], None
    for line in cur_tex.split("\n"):
        t = line.strip()
        if "&" not in t or t.startswith(("\\multicolumn", "%", "\\cmidrule")):
            out.append(line); continue
        tail = "\\\\" if t.rstrip().endswith("\\\\") else ""
        body = t.rstrip()[:-2] if tail else t.rstrip()
        c = cells(body)
        if hdr is None or c[0] == hdr[0]:
            hdr = c
            # a column name the submitted table did not have is itself an addition
            new_hdr = [c[0]]
            for name in c[1:]:
                if name and name not in base_cols:
                    added += 1
                    new_hdr.append(f"\\TRKadd{{{name}}}")
                else:
                    new_hdr.append(name)
            out.append(" & ".join(new_hdr) + tail)
            continue
        newrow = [c[0]]
        for name, val in zip(hdr[1:], c[1:]):
            key = (c[0], name)
            old = base.get(key)
            if old is None:
                if val.strip():
                    changed += 1
                    newrow.append(f"\\TRKadd{{{val}}}")
                else:
                    newrow.append(val)
            elif old == val:
                newrow.append(val)
            else:
                changed += 1
                piece = f"\\TRKadd{{{val}}}" if val.strip() else val
                if old.strip() and old.strip() != "--":
                    piece = f"\\TRKdel{{{old}}}~{piece}"
                newrow.append(piece)
        newrow += c[len(hdr):]
        out.append(" & ".join(newrow) + tail)
    return "\n".join(out), changed, added


def bibkeys(bbl: str) -> dict[str, str]:
    """Each entry's key -> its body text, from a .bbl."""
    out = {}
    parts = re.split(r"(\\bibitem(?:\[[^\]]*\])?\{[^}]+\})", bbl)
    for i in range(1, len(parts), 2):
        k = re.search(r"\{([^}]+)\}\s*$", parts[i]).group(1)
        out[k] = parts[i + 1] if i + 1 < len(parts) else ""
    return out


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__); return 1
    basedir = Path(sys.argv[1])
    trk = Path(sys.argv[2]) if len(sys.argv) > 2 else SRC / "manuscript_tracked.tex"
    if not trk.exists():
        print(f"[trk] {trk} absent"); return 1
    s = trk.read_text()
    if "%DIF TRK PREAMBLE" in s:
        print("[trk] already marked"); return 0

    # ── tables: match each tabular in the tracked file to its source table ──
    n_tab = n_cell = n_row = 0
    missed = []
    for f in sorted((SRC / "tables").glob("*.tex")):
        cur = f.read_text()
        lab = re.search(r"\\label\{([^}]+)\}", cur)
        if not lab:
            continue
        base_f = basedir / "tables" / f.name
        if not base_f.exists():
            continue                      # wholly new table: latexdiff already marks it added
        mt = re.search(r"\\begin\{tabular\}.*?\\end\{tabular\}", cur, re.S)
        if not mt:
            continue
        verbatim = mt.group(0)
        at = s.find(verbatim)
        if at < 0:
            print(f"[trk] FAIL {f.name}: its tabular is not present verbatim in the tracked "
                  f"file, so its cells cannot be marked", file=sys.stderr)
            missed.append(f.name)
            continue
        marked, ch, ad = mark_table(verbatim, base_f.read_text())
        if ch or ad:
            s = s[:at] + marked + s[at + len(verbatim):]
            n_tab += 1; n_cell += ch; n_row += ad

    # ── references: colour entries the baseline bibliography did not have ──
    n_ref = 0
    base_bbl = basedir / "manuscript.bbl"
    blocks = list(re.finditer(r"\\begin\{thebibliography\}.*?\\end\{thebibliography\}",
                               s, re.S))
    mb = blocks[-1] if blocks else None
    if base_bbl.exists() and mb:
        old = set(bibkeys(base_bbl.read_text()))
        block = mb.group(0)
        tailmark = "\\end{thebibliography}"
        cut = block.rindex(tailmark)
        block, closing = block[:cut], block[cut:]
        parts = re.split(r"(\\bibitem(?:\[[^\]]*\])?\{[^}]+\})", block)
        rebuilt = [parts[0]]
        for i in range(1, len(parts), 2):
            head, body = parts[i], parts[i + 1] if i + 1 < len(parts) else ""
            key = re.search(r"\{([^}]+)\}\s*$", head).group(1)
            if key not in old:
                n_ref += 1
                # colour the entry body; \TRKadd is colour-only so \url and \doi survive
                rebuilt.append(head + "\\TRKadd{%\n" + body.rstrip() + "\n}%\n")
            else:
                rebuilt.append(head + body)
        s = s[:mb.start()] + "".join(rebuilt) + closing + s[mb.end():]

    s = s.replace("\\begin{document}", PREAMBLE + "\\begin{document}", 1)
    trk.write_text(s)
    print(f"   table markup: {n_cell} changed cell(s) and {n_row} new row(s) across {n_tab} table(s)")
    print(f"   reference markup: {n_ref} added entry/entries")
    if missed:
        print(f"[trk] {len(missed)} table(s) could not be marked: {missed}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Check every locator the response letter gives against the manuscript's real structure.

A referee follows these pointers. A letter that says "Section 4.3" when the change landed in
4.4, or names an appendix paragraph that no longer exists, wastes a review cycle. Section
titles, table and figure counts, and the appendix paragraph leads are all read out of
manuscript.tex, so the check tracks the paper rather than a remembered layout.

  python3 paper/tools/verify_locators.py

Exit 0 = every locator resolves; 1 = one does not; 2 = sources absent (not a pass).
"""
from __future__ import annotations
import re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "src"
MS = SRC / "manuscript.tex"
LETTER = SRC / "response_to_reviewers.txt"


def strip_tex(s: str) -> str:
    s = s.replace("``", "\u201c").replace("''", "\u201d")
    s = re.sub(r"\\(?:emph|textbf|texttt|text)\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", "", s)
    return s.replace("{", "").replace("}", "").strip()


def _paragraphs(body: str, num: str, sections: dict) -> int:
    """How many paragraphs does this numbered section hold? Used to resolve
    positional locators such as "Section 1, second paragraph"."""
    title = sections.get(num)
    if not title:
        return 0
    heads = [m for m in re.finditer(r"\\(?:sub)?section\{", body)]
    start = None
    for m in heads:
        seg = body[m.start():m.start() + 200]
        if strip_tex(seg[seg.find("{"):seg.find("}") + 1]) == title:
            start = m.start(); break
    if start is None:
        return 0
    nxt = next((m.start() for m in heads if m.start() > start), len(body))
    chunk = body[start:nxt]
    return len([q for q in re.split(r"\n\s*\n", chunk) if q.strip()])


def main() -> int:
    if not MS.exists() or not LETTER.exists():
        print("[loc] manuscript or letter absent -> not checkable here"); return 2
    ms = MS.read_text()
    body = "\n".join(l for l in ms.split("\n") if not l.lstrip().startswith("%"))

    # ── number the sections exactly as LaTeX will ────────────────────────────
    sections, appendices = {}, {}
    sec = sub = 0
    in_appendix = False
    for m in re.finditer(r"\\(appendix)\b|\\(section|subsection)\{((?:[^{}]|\{[^}]*\})*)\}", body):
        if m.group(1):
            in_appendix = True
            sec = 0
            continue
        kind, title = m.group(2), strip_tex(m.group(3))
        if kind == "section":
            sec += 1; sub = 0
            if in_appendix:
                appendices[chr(ord("A") + sec - 1)] = title
            else:
                sections[str(sec)] = title
        else:
            sub += 1
            sections[f"{sec}.{sub}"] = title

    # ── count floats in order of appearance, as LaTeX numbers them ───────────
    n_tab = n_fig = 0
    order = []
    for m in re.finditer(r"\\input\{tables/([^}]+)\}|\\begin\{(table|figure)\}", body):
        if m.group(1):
            n_tab += 1; order.append(("Table", n_tab, m.group(1)))
        elif m.group(2) == "table":
            n_tab += 1; order.append(("Table", n_tab, "inline"))
        else:
            n_fig += 1; order.append(("Figure", n_fig, "inline"))

    # ── appendix paragraph leads, i.e. \emph{...} at a paragraph start ───────
    appx = body[body.find(r"\section{Robustness}"):] if r"\section{Robustness}" in body else ""
    leads = {strip_tex(x).rstrip(".") for x in re.findall(r"\\emph\{([^}]+)\}", appx)}

    flat = " ".join(LETTER.read_text().split())
    checks, fails = [], []

    def add(label, ok, detail=""):
        checks.append((label, ok, detail))
        if not ok:
            fails.append(label)

    def norm(x: str) -> str:
        """Compare titles ignoring quote style and trailing punctuation."""
        x = x.replace("\u201c", "").replace("\u201d", "").replace('"', "")
        return x.strip().rstrip(",.;:").strip().lower()

    # Section N / N.M, optionally followed by a quoted title and/or a paragraph position.
    # The letter's Author action bullets lead with the location, as "Section 3, "Design and
    # identification," was revised to ...", so the title is a quoted string, not free text.
    ORD = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5}
    for m in re.finditer(r"Section\s+(\d+(?:\.\d+)?)", flat):
        num = m.group(1)
        if num not in sections:
            add(f"Section {num}", False, f"no such section (have {sorted(sections)})"); continue
        real = sections[num]
        tail = flat[m.end():m.end() + 90]
        qt = re.match(r",\s*[\u201c\"]([^\u201d\"]{3,70})[\u201d\"]", tail)
        if qt:
            add(f"Section {num}, {qt.group(1)[:34]!r}", norm(qt.group(1)) == norm(real),
                f"manuscript title is {real!r}")
        pos = re.search(r"\b(first|second|third|fourth|fifth)\s+paragraph", tail)
        if pos:
            n_par = _paragraphs(body, num, sections)
            k = ORD[pos.group(1)]
            add(f"Section {num}, {pos.group(0)}", n_par >= k,
                f"section has {n_par} paragraphs")
        if not qt and not pos:
            add(f"Section {num} exists", True, real)

    for m in re.finditer(r"Table\s+(\d+)", flat):
        n = int(m.group(1))
        add(f"Table {n}", n <= n_tab, f"{n_tab} tables in the manuscript")
    for m in re.finditer(r"Figure\s+(\d+)", flat):
        n = int(m.group(1))
        add(f"Figure {n}", n <= n_fig, f"{n_fig} figures in the manuscript")

    # Appendix A, "<paragraph lead>" or "<the appendix's own title>"
    for m in re.finditer(r"Appendix\s+([A-Z])(?:,\s*[\u201c\"]([^\u201d\"]{3,70})[\u201d\"])?",
                         flat):
        letter, para = m.group(1), m.group(2)
        if letter not in appendices:
            add(f"Appendix {letter}", False, f"have {sorted(appendices)}"); continue
        if para:
            targets = {norm(x) for x in leads} | {norm(appendices[letter])}
            ok = norm(para) in targets
            add(f"Appendix {letter}, {para[:40]!r}", ok,
                "" if ok else f"not a paragraph lead or the appendix title: {sorted(leads)}")
        else:
            add(f"Appendix {letter} exists", True, appendices[letter])

    seen = set()
    for label, ok, detail in checks:
        if label in seen and ok:
            continue
        seen.add(label)
        print(f"  {'ok  ' if ok else 'FAIL'} {label:52}  {detail[:70]}")
    print(f"\n[loc] sections {sorted(sections)}")
    print(f"[loc] appendices {sorted(appendices)}  tables {n_tab}  figures {n_fig}")
    print(f"[loc] appendix paragraph leads: {sorted(leads)}")
    titled = sum(1 for lb, _, _ in checks if "'" in lb or "paragraph" in lb)
    print(f"[loc] {len(checks) - len(fails)}/{len(checks)} locator references resolve "
          f"({titled} assert a title or position, {len(checks) - titled} are number-only and "
          f"cannot detect a rename)")
    if fails:
        print(f"[loc] UNRESOLVED: {sorted(set(fails))}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())

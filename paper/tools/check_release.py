#!/usr/bin/env python3
"""Verify the release metadata against the repository it describes.

Minting a DOI is irreversible, so everything a deposit asserts is checked here first. The
failures this exists to stop were all real: the cited DOI was a per-version DOI that froze a
referee on the pre-revision V.1.0 archive; .zenodo.json and CITATION.cff still described a
"32,000-rating dataset" from five models; DATA_AVAILABILITY.md still said "No real firms or
real financial data are used" after an 80-firm SEC arm was added; and three files carried
unfilled <ID> placeholders.
"""
import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONCEPT = "10.5281/zenodo.21864041"
# V.1.0 minted 21864042 and V.2.0 minted 23224927; neither may be cited in place of
# the concept DOI above. The check below rejects any version DOI, named or not.

# Every file that states the DOI, and how many times it must appear.
DOI_FILES = {
    "paper/src/manuscript.tex": 1,
    "paper/src/refs.bib": 1,
    "README.md": 6,
    "CITATION.cff": 2,
    ".zenodo.json": 1,
    "DATA_AVAILABILITY.md": 1,
    "paper/src/cover_letter.tex": 1,
}


def fail(msg, out):
    out.append(f"  FAIL {msg}")


def main() -> int:
    out, checks = [], 0

    # ---- the DOI is the concept DOI, everywhere, and the old one is cited nowhere
    for rel, n in DOI_FILES.items():
        p = ROOT / rel
        if not p.exists():
            fail(f"{rel} is missing", out); continue
        s = p.read_text(errors="replace")
        got = s.count(CONCEPT)
        checks += 1
        if got != n:
            fail(f"{rel} states the concept DOI {got} time(s), expected {n}", out)
        # Reject ANY per-version DOI, not just the one already superseded: each new deposit
        # mints another, and pasting any of them back pins readers to a single version.
        checks += 1
        for other in set(re.findall(r"10\.5281/zenodo\.\d+", s)) - {CONCEPT}:
            fail(f"{rel} cites the per-version DOI {other}; cite the concept DOI {CONCEPT}, "
                 f"which resolves to the newest version", out)

    # ---- the deposit's own counts must match the repository
    raw = sorted(glob.glob(str(ROOT / "data/raw/*.csv")))
    raw_rows = sum(sum(1 for _ in open(f, errors="replace")) - 1 for f in raw)
    recs = glob.glob(str(ROOT / "data/frozen/*.freeze.json"))
    rec_rows = sum(json.loads(Path(f).read_text())["n_rows"] for f in recs)
    real_firms = sum(1 for _ in open(ROOT / "data/firms/real.jsonl"))
    fc = json.loads((ROOT / "results/revision_extras.json").read_text())["failed_calls"]

    def flat(t: str) -> str:
        return re.sub(r"\s+", " ", t)

    da = flat((ROOT / "DATA_AVAILABILITY.md").read_text())
    zn = flat(json.loads((ROOT / ".zenodo.json").read_text())["description"])
    cf = flat((ROOT / "CITATION.cff").read_text())

    def c(n):
        return f"{n:,}"

    for label, phrases in (
        ("raw capture files", [(da, f"{len(raw)} files"),
                               (zn, f"{len(raw)} capture files"),
                               (cf, f"{len(raw)} capture files")]),
        ("raw rows",          [(da, f"{c(raw_rows)} rows"),
                               (zn, f"{c(raw_rows)} rows"),
                               (cf, f"{c(raw_rows)} rows")]),
        ("freeze receipts",   [(da, f"{len(recs)} receipts")]),
        ("receipt rows",      [(da, f"{c(rec_rows)} rows")]),
        ("real firms",        [(da, f"{real_firms} firms"),
                               (zn, f"{real_firms} companies"),
                               (cf, f"{real_firms} companies")]),
        ("analysed rows",     [(da, f"{c(fc['counted_rows'])} of those rows")]),
        ("failed calls",      [(da, f"{c(fc['counted_failed'])} are recorded API failures")]),
        ("retained rows",     [(da, f"{c(fc['counted_retained'])} are retained")]),
    ):
        for text, phrase in phrases:
            checks += 1
            if phrase not in text:
                fail(f"{label}: the release metadata does not say {phrase!r}", out)

    # the pre-revision statement that the revision made false
    checks += 1
    if re.search(r"[Nn]o real (firms|financial data)", da):
        fail("DATA_AVAILABILITY.md still says no real firms are used, but the real-firm "
             "arm uses public SEC company facts", out)

    # ---- nothing may still be a placeholder
    for rel in list(DOI_FILES) + ["LICENSE"]:
        s = (ROOT / rel).read_text(errors="replace")
        checks += 1
        for bad in ("<ID>", "Insert the minted", "at deposit", "TODO", "FIXME"):
            if bad in s:
                fail(f"{rel} still contains the placeholder {bad!r}", out)

    # ---- the blind copy must not carry the DOI
    anon = ROOT / "paper/out/manuscript_anonymous.pdf"
    if anon.exists():
        try:
            import pymupdf
            t = "\n".join(pg.get_text() for pg in pymupdf.open(anon))
            checks += 1
            if "zenodo" in t.lower() or "2186404" in t:
                fail("manuscript_anonymous.pdf names the archive DOI", out)
        except ImportError:
            print("[release] NOTE pymupdf unavailable; blind-copy DOI check skipped")

    print(f"[release] {checks} release-metadata checks against the repository")
    for line in out:
        print(line)
    return 1 if out else 0


if __name__ == "__main__":
    sys.exit(main())

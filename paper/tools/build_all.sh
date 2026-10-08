#!/usr/bin/env bash
# Build EVERY deliverable, in dependency order. One command, so none can be left stale.
#
# The deliverables were built by three separate scripts, and twice a reviewer-facing edit was
# made, one script was run, and a PDF that still showed the old text went out: the tracked-changes
# PDF once, the response letter once. The cost is a wasted review cycle, so the entry point is
# now singular and the staleness check runs at the end rather than being remembered.
#
#   bash paper/tools/build_all.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
PY="${PY:-./.venv/bin/python}"
[[ -x "$PY" ]] || PY=python3

echo "== 1/4 manuscript + anonymous + tables + figures =="
bash paper/tools/build.sh

echo "== 2/4 tracked-changes manuscript =="
bash paper/tools/build_tracked.sh
bash paper/tools/build_tracked.sh --anon

echo "== 3/4 response to reviewers =="
"$PY" paper/tools/build_response.py

# The Word deliverables are what FRL actually requires at submission, and build_all.sh did
# not build them: manuscript.docx sat 22 minutes behind manuscript.pdf after an edit, which
# is exactly the failure this script exists to prevent. build_word.sh also enforces the
# 3-5 highlights at 85 characters, so skipping it skipped that gate too.
echo "== 4/4 Word deliverables (manuscript.docx, title_page.docx, highlights.docx) =="
bash paper/tools/build_word.sh
bash paper/tools/build_word_tracked.sh

echo "== cover letter =="
( cd paper/src && pdflatex -interaction=nonstopmode -halt-on-error \
    -output-directory=../out cover_letter.tex >/dev/null ) \
  && echo "   paper/out/cover_letter.pdf"

echo "== staleness and compliance =="
"$PY" paper/tools/check_stale.py || true
"$PY" paper/tools/wordcount.py | tail -4
# This gate was inert from the folder restructure until now (every path pointed at the old
# paper/latex layout, so it exited 2 and checked nothing). Run it here so it cannot go quiet
# again without the build saying so.
"$PY" paper/tools/verify_response_numbers.py | tail -3
# Full binding: every number in the manuscript and in our own letter text is read out of
# the document, anchored to the phrase it follows, and compared with a frozen artifact.
# Every table cell is re-derived independently of the generator that printed it. Every
# locator the letter gives is resolved against the real section and float numbering.
"$PY" paper/tools/bind_manuscript_numbers.py | grep -E "bound to artifact|coverage|UNCLAIMED|MISMATCH"
"$PY" paper/tools/bind_letter_numbers.py    | grep -E "bound to artifacts|coverage|UNCLAIMED|MISMATCH"
"$PY" paper/tools/verify_tables.py          | tail -1
"$PY" paper/tools/verify_locators.py        | tail -1
"$PY" paper/tools/check_readme.py
"$PY" paper/tools/check_refs.py
"$PY" paper/tools/check_tracked.py
"$PY" paper/tools/check_release.py

echo
echo "deliverables in paper/out:"
ls -1t paper/out/*.pdf paper/out/*.docx 2>/dev/null | while read -r f; do
  printf "   %-42s %s\n" "$(basename "$f")" "$(date -r "$f" '+%H:%M')"
done

#!/usr/bin/env bash
# Tracked-changes manuscript, against the as-submitted version in git.
#
# Every flag here was forced by a failure, so none of them is decorative:
#   --append-safecmd citep,citet,...  citation keys must stay ATOMIC. Passing them as
#       textcmd made latexdiff diff INSIDE \citep{...}, producing \citep{a\DIFadd{,b}} and
#       42 "extra }" errors.
#   --flatten  latexdiff must SEE the table environments to use its float-aware markup.
#       Without it a newly-\input'd table is wrapped in \DIFadd{}, and \begin{table} cannot
#       start a float inside a group ("Not in outer par mode").
#   PICTUREENV += tabular,thebibliography  --flatten pulls in the .bbl, and diffing inside
#       it corrupts natbib internals (\csname \DIFadd{natexlab}\endcsname). tabular is there
#       because \cmidrule cannot survive markup injected mid-row.
#   VERBATIMENV = lstlisting,...  markup inside lstlisting silently DROPS the content: the
#       prompts appendix came out empty, with only a Listings warning to show for it. Note
#       lstlisting must NOT go in PICTUREENV -- that yields \PICTUREBLOCKlstlisting undefined.
# It also needs settobox.sty, i.e. `tlmgr install oberdiek`.
set -euo pipefail
cd "$(dirname "$0")/../src"
ROOT="$(cd ../.. && pwd)"
# build.sh removes the figure copies it makes once the PDF is out, so this build has to bring
# its own: a tracked PDF that silently used draft boxes for both figures was the failure that
# made this explicit. They are removed again at the end.
cp -f figures/Figure_1.pdf figures/Figure_2.pdf ./ 2>/dev/null || true
export PATH="$HOME/Library/TinyTeX/bin/universal-darwin:$PATH"
# Which commit is the as-submitted version. Override with: build_tracked.sh <ref>
#
# This MUST be the as-submitted tag, not HEAD. It defaulted to HEAD, which worked only while
# the revision sat uncommitted: the moment the revision was committed, HEAD became the revised
# manuscript and latexdiff compared the file with itself, so the tracked PDF came out with
# essentially no markup and still looked like a normal 13-page document.
ANON=0
for a in "$@"; do [ "$a" = "--anon" ] && ANON=1; done
BASEREF="V.1.0"
for a in "$@"; do case "$a" in --*) ;; *) BASEREF="$a" ;; esac; done
OUTNAME="manuscript_tracked"
[ "$ANON" = 1 ] && OUTNAME="manuscript_tracked_anonymous"
if [ "$(git rev-parse "$BASEREF")" = "$(git rev-parse HEAD)" ]; then
  echo "!! baseline $BASEREF is the current HEAD -- the diff would be empty." >&2
  echo "!! Pass the as-submitted ref explicitly: build_tracked.sh <tag-or-commit>" >&2
  exit 2
fi
# The baseline needs its OWN \input'd tables and its own .bbl. --flatten resolves \input
# relative to the baseline FILE's directory, so writing the baseline next to the current
# manuscript made it expand TODAY's tables: both sides of the diff then held identical table
# bodies, and no table change could ever appear. The .bbl was worse -- it was literally
# `cp manuscript.bbl`, so the reference list was identical on both sides by construction.
BASEDIR="$ROOT/paper/.tracked_base"
BASE="$BASEDIR/manuscript.tex"
rm -rf "$BASEDIR"; mkdir -p "$BASEDIR/tables"
trap 'rm -rf "$BASEDIR"' EXIT
# The manuscript lived at paper/latex/ until the repository was restructured, so a baseline from
# any commit before that move is only reachable at the OLD path. Try the current path, then it.
FOUND=0
for PFX in paper/src paper/latex; do
  if git show "$BASEREF:$PFX/manuscript.tex" > "$BASE" 2>/dev/null; then
    git show "$BASEREF:$PFX/manuscript.bbl" > "$BASEDIR/manuscript.bbl" 2>/dev/null || true
    for T in $(grep -o '\\input{[^}]*}' "$BASE" | sed 's/.*{//;s/}//' | sort -u); do
      case "$T" in *.tex) ;; *) T="$T.tex" ;; esac
      mkdir -p "$BASEDIR/$(dirname "$T")"
      git show "$BASEREF:$PFX/$T" > "$BASEDIR/$T" 2>/dev/null || rm -f "$BASEDIR/$T"
    done
    FOUND=1; break
  fi
done
[ "$FOUND" = 1 ] || { echo "!! cannot read the baseline manuscript from $BASEREF at either" >&2
                      echo "!! paper/src/manuscript.tex or paper/latex/manuscript.tex" >&2; exit 2; }
echo "   baseline $BASEREF ($(git rev-parse --short "$BASEREF")) with $(find "$BASEDIR" -name '*.tex' ! -name manuscript.tex | wc -l | tr -d ' ') included file(s) and its own .bbl"
NEW="manuscript.tex"
if [ "$ANON" = 1 ]; then
  python3 "$ROOT/paper/tools/make_anonymous.py" "$BASE" "$BASEDIR/manuscript_anon.tex" \
    >/dev/null || { echo "!! could not blind the baseline" >&2; exit 2; }
  BASE="$BASEDIR/manuscript_anon.tex"
  if [ -f "$BASEDIR/manuscript.bbl" ]; then
    sed -e 's/Chincholikar, S\./Anonymous/g; s/Chawla, R\./Anonymous/g' \
        -e 's/Chincholikar and Chawla/Anonymous Authors/g' \
        -e 's#10\.5281/zenodo\.[0-9]*#withheld for review#g' \
        "$BASEDIR/manuscript.bbl" > "$BASEDIR/manuscript_anon.bbl"
  fi
  NEW="manuscript_anonymous.tex"
  [ -f "$NEW" ] || python3 "$ROOT/paper/tools/make_anonymous.py" >/dev/null
  echo "   blinding both sides of the diff"
fi
latexdiff --encoding=utf8 --flatten \
  --append-safecmd="citep,citet,citealp,citeauthor,ref,label,texttt,bibitem,natexlab" \
  --append-textcmd="emph,textbf" \
  --config="PICTUREENV=(?:picture|DIFnomarkup|tabular|thebibliography)[\w\d*@]*,VERBATIMENV=(?:lstlisting|verbatim|Verbatim|alltt)[\w\d*@]*" \
  "$BASE" "$NEW" > "$OUTNAME.tex"
python3 "$ROOT/paper/tools/mark_tracked_extras.py" "$BASEDIR" "$OUTNAME.tex"
for i in 1 2 3; do
  pdflatex -interaction=nonstopmode "$OUTNAME.tex" >/dev/null 2>&1 || true
  [ "$i" = 1 ] && (bibtex "$OUTNAME" >/dev/null 2>&1 || true)
done
err=$(grep -c '^! ' "$OUTNAME.log" || true)
drop=$(grep -c 'Text dropped after begin of listing' "$OUTNAME.log" || true)
mkdir -p "$ROOT/paper/out"
mv -f "$OUTNAME.pdf" "$ROOT/paper/out/$OUTNAME.pdf" 2>/dev/null || true
rm -f Figure_1.pdf Figure_2.pdf "$OUTNAME.aux" "$OUTNAME.out" \
      "$OUTNAME.abs" "$OUTNAME.blg"
echo "   paper/out/$OUTNAME.pdf  errors=$err  listing-drops=$drop"
[ "$err" = 0 ] && [ "$drop" = 0 ] || { echo "!! tracked build is not clean" >&2; exit 1; }

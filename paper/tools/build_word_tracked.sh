#!/usr/bin/env bash
# Word versions of the tracked-changes manuscripts, clean and blinded.
#
#   bash paper/tools/build_word_tracked.sh
#
# The latexdiff markup is mapped to underline and strikethrough by tracked_to_word.py, which
# refuses to write a file carrying no markup: a tracked document that silently lost its
# revisions looks exactly like a clean one.
set -euo pipefail
cd "$(dirname "$0")/../.."
command -v pandoc >/dev/null || { echo "build_word_tracked: pandoc not installed" >&2; exit 2; }
mkdir -p paper/out

for name in manuscript_tracked manuscript_tracked_anonymous; do
  src="paper/src/$name.tex"
  [ -f "$src" ] || { echo "   skipping $name (not built)"; continue; }
  tmp="paper/src/.$name.word.tex"
  python3 paper/tools/tracked_to_word.py "$src" "$tmp"
  case "$name" in
    *_anonymous) bib=refs_blind.bib ;;
    *)           bib=refs.bib ;;
  esac
  merged="refs_tracked_$(basename "$bib" .bib).bib"
  python3 paper/tools/merge_tracked_bib.py "paper/src/$bib" "paper/src/$merged"
  bib="$merged"
  ( cd paper/src && pandoc "$(basename "$tmp")" --citeproc --metadata reference-section-title=References --bibliography="$bib" \
        --resource-path=.:figures -o "$OLDPWD/paper/out/$name.docx" 2>/dev/null ) \
    || { rm -f "$tmp"; echo "build_word_tracked: $name conversion FAILED" >&2; exit 1; }
  rm -f "$tmp"
  case "$name" in
    *_anonymous) who="Anonymous Author" ;;
    *)           who="S. Chincholikar and R. Chawla" ;;
  esac
  python3 paper/tools/docx_native_track.py "paper/out/$name.docx" "paper/out/$name.docx" "$who"
done

# A blinded deliverable that still names its authors is the one failure that matters here.
python3 - <<'PY'
import re, sys, zipfile
from pathlib import Path
p = Path("paper/out/manuscript_tracked_anonymous.docx")
if not p.exists():
    sys.exit(0)
with zipfile.ZipFile(p) as z:
    xml = b"".join(z.read(n) for n in z.namelist() if n.endswith(".xml")).decode("utf8", "ignore")
text = re.sub(r"<[^>]+>", " ", xml)
bad = [k for k in ("Chincholikar", "Chawla", "samir.chincholikar", "robin.chawla",
                   "0009-0007", "zenodo") if k.lower() in text.lower()]
if bad:
    sys.exit(f"build_word_tracked: IDENTITY LEAK in the blinded DOCX: {bad}")
print("   manuscript_tracked_anonymous.docx audited: no author name, e-mail, ORCID or DOI")
PY

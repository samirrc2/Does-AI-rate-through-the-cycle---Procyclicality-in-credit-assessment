#!/usr/bin/env bash
# Word deliverables, GENERATED from the LaTeX sources.
#
# paper/manuscript.docx used to be written from scratch by build_manuscript.py with python-docx:
# a second, parallel document whose prose was maintained by hand while manuscript.tex moved on.
# By 2026-10-05 it was two months behind and described the pre-revision paper. Converting from
# manuscript.tex instead means the Word version cannot say anything the LaTeX does not.
#
#   bash paper/tools/build_word.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
command -v pandoc >/dev/null || { echo "build_word: pandoc not installed" >&2; exit 2; }
mkdir -p paper/out

# --citeproc resolves \citep against the .bib, otherwise the DOCX carries raw keys and no
# reference list at all.
( cd paper/src && pandoc manuscript.tex --citeproc --bibliography=refs.bib \
      --resource-path=.:figures -o "$OLDPWD/paper/out/manuscript.docx" 2>/dev/null ) \
  && echo "-> paper/out/manuscript.docx" \
  || { echo "build_word: manuscript conversion FAILED" >&2; exit 1; }

( cd paper/src && pandoc title_page.tex -o "$OLDPWD/paper/out/title_page.docx" 2>/dev/null ) \
  && echo "-> paper/out/title_page.docx" || echo "   WARNING: title_page.docx not refreshed"

# The highlights are the authoritative list inside manuscript.tex, so take them from there
# rather than keeping a separate copy that can drift.
python3 - <<'PY'
import re, subprocess, sys
from pathlib import Path
tex = Path("paper/src/manuscript.tex").read_text()
m = re.search(r"\\begin\{highlights\}(.*?)\\end\{highlights\}", tex, re.S)
if not m:
    print("build_word: no highlights environment in manuscript.tex", file=sys.stderr); raise SystemExit(1)
items = re.findall(r"\\item\s+(.*?)(?=\n\s*\\item|\Z)", m.group(1), re.S)
def clean(x):
    x = re.sub(r"\\%", "%", " ".join(x.split()))
    x = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?", "", x)
    return x.replace("$", "").replace("{", "").replace("}", "").replace("``", '"').replace("''", '"').strip()
bullets = [clean(i) for i in items if clean(i)]
over = [b for b in bullets if len(b) > 85]
md = "# Highlights\n\n" + "\n".join(f"- {b}" for b in bullets) + "\n"
Path("/tmp/_hl.md").write_text(md)
subprocess.run(["pandoc", "/tmp/_hl.md", "-o", "paper/out/highlights.docx"], check=True)
print(f"-> paper/out/highlights.docx ({len(bullets)} bullets, longest {max(len(b) for b in bullets)} chars)")
if not 3 <= len(bullets) <= 5 or over:
    print(f"build_word: FRL requires 3-5 bullets of <=85 chars; got {len(bullets)}, over-length: {over}",
          file=sys.stderr)
    raise SystemExit(1)
PY

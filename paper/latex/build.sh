#!/usr/bin/env bash
# Build the Elsevier CAS (cas-sc) manuscript PDF. Requires a TeX Live install
# (pdflatex, bibtex). Figures (Figure_1.pdf, Figure_2.pdf) and the claims-gated
# tables (tables/) are regenerated from claims.json by analysis/make_figures.py and
# analysis/make_tables.py; this script only typesets.
#
#   bash build.sh
set -euo pipefail
cd "$(dirname "$0")"
pdflatex -interaction=nonstopmode manuscript.tex >/dev/null
bibtex manuscript >/dev/null
pdflatex -interaction=nonstopmode manuscript.tex >/dev/null
pdflatex -interaction=nonstopmode manuscript.tex >/dev/null
echo "-> manuscript.pdf"

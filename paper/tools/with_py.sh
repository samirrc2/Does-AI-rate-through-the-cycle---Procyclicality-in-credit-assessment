#!/bin/sh
# Resolve the interpreter for a verification gate, then exec it.
#
# The gates need a Python 3.10+ interpreter, and there are three places it can come from.
# An explicit PY wins (con1's iterate.sh exports one). Otherwise the repository's own
# .venv, which is what `python3 -m venv .venv` in the README creates. Otherwise python3
# from PATH, which is correct on a machine whose python3 is new enough and gives a clear
# failure from reproduce.sh's floor check where it is not.
#
# This exists because .con1.json used to name an absolute interpreter path under one
# developer's home directory. Removing it fixed iterate.sh, which has its own fallback,
# but left inject.py expanding "$PY" to nothing and every gate exiting 127 -- a gate that
# cannot run is indistinguishable from a gate that passes unless something says so.
set -eu
cd "$(dirname "$0")/../.."
if [ -n "${PY:-}" ]; then
  P=$PY
elif [ -x ./.venv/bin/python ]; then
  P=./.venv/bin/python
else
  P=python3
fi
exec "$P" "$@"

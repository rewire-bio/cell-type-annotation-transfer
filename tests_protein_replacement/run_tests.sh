#!/bin/sh
# E7 unit tests for the replacement protein builder (synthetic data and mocks only; no network).
# Usage: sh tests_protein_replacement/run_tests.sh [PYTHON]
# PYTHON must provide the pinned stack (pyproject.toml / uv.lock); it is used read-only.
# All bytecode, temp files and library caches go to tests_protein_replacement/_tmp.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
PY=${1:-python3}
T="$HERE/_tmp"
mkdir -p "$T"
export PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="$T/pycache" TMPDIR="$T" MPLCONFIGDIR="$T/mpl" \
       NUMBA_CACHE_DIR="$T/numba" XDG_CACHE_HOME="$T/xdg"
cd "$HERE"
exec "$PY" -B -m unittest discover -s "$HERE" -p 'test_*.py' -v

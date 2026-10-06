#!/bin/sh
# Unit tests for scripts/make_paper_assets.py (tiny synthetic fixtures only; no real data, no network).
# Usage: sh tests_paper_assets/run_tests.sh [PYTHON]
# PYTHON must provide the pinned stack (matplotlib 3.9.2, numpy 1.26.4); it is used read-only.
# All temp files, bytecode and matplotlib caches go to tests_paper_assets/_tmp (git-ignored via the
# caller's cleanup; remove the directory after the run if desired).
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
PY=${1:-python3}
T="$HERE/_tmp"
mkdir -p "$T"
export PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="$T/pycache" TMPDIR="$T" MPLCONFIGDIR="$T/mpl" \
       XDG_CACHE_HOME="$T/xdg"
cd "$HERE"
exec "$PY" -B -m unittest discover -s "$HERE" -p 'test_*.py' -v

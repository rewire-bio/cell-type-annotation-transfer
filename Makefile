# Stage targets. `reproduce` is the harness clean-reproduction command (H, includes Mode F).
# Requires CELLTRANSFER_BASELINE_MANIFEST (Mode R comparison manifest, read only).
PY ?= .venv/bin/python
export UV_CACHE_DIR := $(CURDIR)/.cache-study/uv
export UV_PROJECT_ENVIRONMENT := $(CURDIR)/.venv
export PYTHONDONTWRITEBYTECODE := 1

.PHONY: env data full reproduce test paper
env:
	uv sync --frozen

data: env
	$(PY) scripts/acquire_inputs.py acquire --root .

full: env
	$(PY) scripts/experiment.py --config configs/full.json --output results/R

reproduce:
	python3 scripts/reproduce.py --config configs/full.json

test: env
	$(PY) -m unittest discover -s tests_pipeline -t .

paper: env
	$(PY) scripts/build_paper.py

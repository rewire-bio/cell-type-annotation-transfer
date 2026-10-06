# Pipeline integration (harness wiring) — implementation report

Status: **code integrated and tested with synthetic data and mocks only.** No real experiment, recovery, reproduction, scoring or paper build was run. No result exists. This report does not verify anything.

## Files
- `scripts/experiment.py` is the harness `experiment.command`. It runs `recover.main` (Mode R). The historical root is `$HISTORICAL_RUNS_ROOT`, defaulting to `<repo>/historical`. The manifest is `$CELLTRANSFER_HISTORICAL_MANIFEST` or `configs/full.json` `mode_r.historical_manifest`. The script then writes `results.json`, `comparison_manifest.json` (mode R) and `provenance.json`. Exit codes:
  - 3 if the historical manifest is missing.
  - The recovery exit code if recovery does not succeed.
  - 1 if any output is missing. In that case no `results.json` is written.
- `scripts/result_manifest.py`:
  - **Aggregation into `results.json`.** Keys are stable and the same in both modes. There is no mode, time or path key, and volatile column names are dropped or rejected. Floats are finite, or `None` when undefined. `cell_counts` values are exact integers. `*_ci95` columns are split into `_lo`/`_hi`.
  - **Arm assembly.** Each arm directory holds symlinks combining the fit and predict outputs. A duplicate prediction parquet is fatal. A non-identical duplicate JSON is fatal.
  - **Compare manifest writer** (`celltransfer-compare-manifest/1`). Paths are relative to the manifest directory. It enforces exactly one `M4/fit_info.json` per arm. `fresh_execution` is required for mode F. `d03_features` is marked `reference-check-only`.
  - **Optional exact-evidence discovery.** Expected names are `score/bootstrap_weights.npy`, `score/sampled_ids.csv` and `protein/protein_classes_<file>.{parquet,csv}`. These names are assumptions; see remaining need 2.
- `scripts/reproduce.py` is stage H, run by `make reproduce`. The step order, guards and budgets are in its docstring. Mode F has a 14 h ceiling inside the 15 h H budget. A step gets at most 2 attempts, and only infrastructure statuses are retried, within the budget. A generation receipt is written after every step to `runs/F-<UTC>/generation_receipt.json`. The baseline manifest:
  - is used only by `compare_runs.py`
  - must be mode R
  - must not lie under the reproduction output dirs.

  `results/full/results.json` or `paper/build/main.pdf` existing before the run is fatal. The comparison must exit 0, or the paper stage is not reached. A missing `scripts/make_paper_assets.py` or paper source fails at the paper stage.
- `study.json`:
  - Scientific inputs are now concrete: companion science code, label maps (`companion/src`), locks, `uv.lock`, `protocol/tolerances.json`, the experiment and recovery code, and `data/manifest.json`. They exclude `Makefile`, `reproduce.py`, the paper code and figure code.
  - Outputs and budgets are set.
  - Harness tolerance is abs 0.01, rel 0.
  - The tiered comparison is recorded as a required pass.
- `configs/full.json`: R/F ceilings, per-step ceilings, and guard settings (4 threads, 12 GiB, 7 GiB).
- `Makefile`: `env`, `data`, `full`, `reproduce`, `test` and `paper` targets.
- `tests_pipeline/`: 12 synthetic tests.

## Validation
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests_pipeline -t .`: 12 OK.
- `tests_comparison`: still OK (20 skipped without pandas).
- `make -n reproduce test`: OK.

## Remaining integration needs (not done; must be resolved before execution)
1. **Approval hash.** Editing `study.json` and `configs/full.json` changes the harness `protocol_hash`. Any earlier `.research/approval.json` will no longer match, so the coordinator must re-record approval of these exact files. The budgets match the recorded approval: 8 h R, 15 h H, 30 min paper, 7 GiB, 4 threads.
2. **Scoring and protein outputs.** The exact-evidence file names (bootstrap weights, protein classes, sampled ids) must be confirmed against the scoring worker's actual outputs. If they are absent, the comparison exits 3 and H fails honestly.
3. **Input layout.** `acquire_inputs.py --root runs/F-*/inputs` uses the `historical/...` prefix layout. The companion scripts take `--workspace <repo>`. The mapping between the acquired input paths and the paths `build_data.py`/`build_cite.py` read has **not** been verified. It may need a workspace argument or an env var. Also, the external cache fallback in `acquire_inputs.py` is item-agnostic. Restricting it to third-party model items (never data or trained models) needs a check in `acquire_inputs.py`, which this worker does not own.
4. **Recovery outputs.** `recover.py` is being changed by another worker (resume and method-specific caps). `experiment.py` relies on:
   - `main(argv)` and its flags
   - `recovery_manifest.json` with `status`, `historical_layout`, `cached`, and `steps[name,status,out_dir]`
   - step names `B_M{4,5,6}_{fit,predict}`, `cite_build`, `score` and `protein`.

   Resumed or duplicate ok attempts make `last_ok` fail closed. Re-check after that worker's change.
5. **Missing values.** `None` and NaN in score CSVs are indistinguishable. Both map to `None`.
6. **Gitignore.** `.venv`, `.cache-study` and `runs/` are not gitignored. `.gitignore` is not owned by this worker.
7. **Untested parts.** `RG.run_guarded` integration in `reproduce.py` is exercised only through a mock runner. It has not been tested with real processes, `uv sync` or the companion scripts. Arm A CITE predictions in F use the fresh Arm A fit dirs. The M6 checkpoint hash guard (`--expected-hashes`) is applied only in Mode R.
8. **Paper stage.** `scripts/make_paper_assets.py` (API `--score --protein --comparison --output paper`) is not implemented yet, so the paper stage will fail until a paper worker adds it.

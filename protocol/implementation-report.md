# Implementation report: recovery infrastructure and scoring fixes (2026-10-06, revision 2)

Worker: research-engineer. Snapshot `7ace3c7d`. Inputs: `protocol/resume-plan-reviewed.md` (PROPOSAL, not approved), `protocol/coordinator-execution-note.md`, `evidence/recovery-inputs.json`. Scientific design, tolerances, data, methods, seeds and metrics are unchanged. **No study experiment, recovery step, scoring of real data or prediction-vs-label inspection was run.** Every test uses synthetic fixtures. `historical/` is unchanged (`git diff -- historical` is empty), and earlier failure logs and worker records were not touched. Nothing was committed.

Revision 1 of this report, at snapshot `7dc729db`, described the first pass: the D-1a `--natural-unknown-scope` option in `score_all.py`, M6 checkpoint relocation with `--expected-hashes` in `run_matched.py`, the process-group watchdog in `resource_guard.py`, and the hash-verified Mode R driver. Those parts stand. This revision closes the integration gaps that revision 1 listed. `companion/scripts/score_all.py` and `run_matched.py` needed no further code change. Their existing behaviour is now covered by numerical tests (D-1a) and driver tests (B_M6 hashes).

## Changes in this revision

### `scripts/resource_guard.py`
- **Post-run `/usr/bin/time -l` check (OA-5 item 4).**
  - With `time_l=True` (or `--time-l`), the command runs as `/usr/bin/time -l <cmd>`.
  - After exit, `parse_time_l` reads `peak memory footprint`, `maximum resident set size` and `real` from `stderr.log`. The last occurrence wins, and malformed or missing lines give `None`.
  - `postrun_exceeds` flags only when the peak is **strictly greater than** the limit (default 12 GiB). An unknown peak never flags; it is recorded as `available: false`.
  - A flagged `ok` or `failed` attempt becomes `memory-stop-postrun`, with `status_before_postrun` kept. This status is in `MEMORY_STATUSES`, so it counts as infrastructure, one retry is allowed, and two memory stops are a blocker.
  - The parsed values and their scope ("direct child of time only; understates aggregate memory under n_jobs>1") go in `attempt.json`. `stdout.log`, `stderr.log` and `samples.jsonl` are kept.
- **Storage cap without double counting.**
  - `normalize_cap_paths` resolves real paths, removes duplicates, and drops any path nested inside another cap path.
  - `tree_usage` counts each `(st_dev, st_ino)` once, so a uv cache hard-linked into the venv is not counted twice. It does not follow symlinks, so historical runs linked into `armB/` stay outside the cap, as the plan says.
  - Per-path usage is recorded at the start and end of every attempt.
- `launch.json` (pid and pgid) is written at launch, so a resumed driver can detect an orphaned process group.

### `scripts/recover.py`
1. **Method-specific reviewed caps** (per attempt), from §6 of the reviewed plan:
   - B_M4: fit 20 min, predict 5 min. B_M5: fit 50 / 10. B_M6: fit 60 / 20.
   - cite_build 20, score 120, protein 15, preflight 30 (all minutes).
   - **R5 CITE predictions (A_M1…M6): one shared 30 min pool, a total, not 30 min each.** Each attempt's timeout is `min(step cap, remaining pool, remaining 8 h stage)`. Every A_M*_cite attempt, retries included, draws on the same pool. This is the conservative reading of "30 min total", so a retry cannot extend R5. Please confirm this reading at approval (open item below). All attempts and retries count toward the 8 h cumulative stage ceiling.
2. **Every real step is wrapped in `/usr/bin/time -l`** (on by default; `--no-time-l` exists for tests only). The post-run peak is copied into each manifest step entry, along with the stdout and stderr paths.
3. **B_M6 relocated predict has its own expected hashes.** The B_M6 fit receipt's `scanvi/*` sha256 values are written once to `armB_M6_scanvi_expected_sha256.json` and passed as `--expected-hashes` to B_M6 predict. Arm A M6 still uses the manifest hashes.
4. **Safe resume after an infrastructure interruption (`--resume`).**
   - After each `ok` attempt, the driver writes an immutable receipt (`receipts/<step>.json`, exclusive create, mode 0444) containing sha256 of every output file.
   - On resume, a step that has a receipt is reused only if its output still matches byte for byte. If it does not match, the run blocks; the step is not rerun.
   - Attempt counts are never reset. An earlier attempt with no `attempt.json`, or with `ok` but no receipt, counts as `driver-interrupted` (infrastructure). An earlier deterministic failure stays a blocker.
   - Attempts that were never recorded are charged to the stage time and the R5 pool, using start time (from the directory name) to newest file mtime.
   - Resume blocks in these cases:
     - the source git rev or the code sha256 differs from the original run;
     - the historical manifest differs;
     - the process group of an interrupted attempt is still running.
   - Symlinks and expected-hash files are checked for idempotence.
5. **Cap paths cover the full study.** For both `--workspace` and `--study-root`: `companion`, `runs`, `.cache-study`, `paper/build`, `.venv` and `.tools`. The run directory (for example under `.research/…`) and any `--cap-path` are added. Duplicates and nested paths are removed. The caches (`UV_CACHE_DIR`, `HF_HOME`, `XDG_CACHE_HOME`, `CELLTYPIST_FOLDER`, `MPLCONFIGDIR`) are placed under `<study-root>/.cache-study`. The coordinator reports a 1.3 GiB root `.venv` and a 1.2 GiB cache; this worker did not re-measure them. Note that walking a full venv at every 30 s disk poll costs some seconds of I/O.
6. **Arm assembly record** (`assembly.json`, also stored in the manifest):
   - Cached B M1–M3: historical predictions and fit directory, `fit_info.json`, sha256 of the source files, and the manifest sha256.
   - Recomputed B M4–M6: `fit_dir`, `fit_info.json` (for M4 this holds `chosen_C` and `validation_macro_f1_by_C`, needed for the T1 exact comparison; `fit_dir/model.pkl` is used for export), the fit and predict receipts with file hashes, and the source revision with code hashes.
   - A CITE: historical fit directory and the hashes of `model.pkl`, `fit_info.json` and `scanvi/`.
7. **R0 read-only preflight (`--preflight [--watchdog-selftest]`).** It writes only `<run-dir>/preflight.json` (and the self-test attempt directories). It records:
   - cap usage per path and in total against 7 GiB, free disk, and whether `/usr/bin/time` is present;
   - sha256 verification of the historical inputs;
   - the K and K_B lists and the sha256 of `features_and_classes.json`, which is reference-only, so no labels are read (`labels_read: false`);
   - the pinned interpreter's version and the sorted `name==version` list of distributions with its sha256 (run with `python -I`, without importing study packages);
   - a CELLTYPIST_FOLDER check against the installed package source.

   Data acquisition is left to the coordinator.
8. **1 GiB production-threshold self-test** (`watchdog_selftest_run`). Using the production `run_guarded` with `/usr/bin/time -l` on and a 1 GiB threshold:
   - a 1.5 GiB allocator must end as `memory-stop` (phys_footprint, on macOS) within 60 s;
   - a 256 MiB allocator must end `ok`.

**CELLTYPIST_FOLDER verified.** The installed celltypist 1.7.1 (`.venv/lib/python3.11/site-packages/celltypist/models.py:16`) contains `celltypist_path = os.getenv('CELLTYPIST_FOLDER', default = …/.celltypist)`. It is read at import time, and the driver sets it in the child environment. Note: `~/.celltypist/data` already existed on this machine when inspected. This worker's preflight does not import celltypist.

## Test evidence (executed 2026-10-06, macOS darwin 25.6)
`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests` ran **38 tests in about 41 s; all passed.** It used the system python3 for the stdlib tests and the pinned study venv `.venv/bin/python` (numpy 1.26.4, pandas 2.2.3, anndata 0.12.19, scvi-tools 1.4.1, celltypist 1.7.1) for the numerical scoring and preflight tests. Scratch files go under `tests/_tmp*` and are deleted afterwards. `git status` shows only the owned files.

- **Numerical D-1a** (`tests/test_scoring_numerical.py`, `tests/d1a_fixture.py`). This runs the real `companion/scripts/score_all.py` on a synthetic fixture: 10 natural neutrophils outside K at conf 0.99, 7 top-up erythroid cells outside K at conf 0.01, and B-removed types with 6 natural cells at 0.99 and 3 top-up cells at 0.01. Results:
  - **Primary natural scope** (Arm A M4, P1, P2): unknown_cells = 10, false-accept@OPcov = 1.0, unknown_auroc = 3/54 (the expected value, from ties with in-K cells). Per-class unknowns are {neutrophil} only.
  - **Arm B** in both scopes: unknown_cells = 9, false-accept = 6/9, so all strata are kept.
  - **Secondary file:** `unknowns_allstrata_secondary.csv` is labelled `secondary-sensitivity-all-strata`, with 17 cells and false-accept = 10/17.
  - **`--natural-unknown-scope all`** reproduces the historical all-strata definition (17 cells, 10/17).
  - Known-cell metrics are identical between scopes.
- **Post-run parser.** Boundaries were tested at limit − 1, limit and 0 (not flagged) and limit + 1 (flagged), with missing, malformed and last-wins input. With a fake `time` binary, a peak exactly at 12 GiB stays `ok` and 12 GiB + 1 becomes `memory-stop-postrun`. A real `/usr/bin/time -l` run of an 80 MiB allocation parsed a peak above 80 MiB and was not flagged.
- **Actual 1 GiB threshold.** Through the production CLI (`resource_guard.main --mem-limit-gib 1 --time-l`), a 1.5 GiB allocation gave rc 2 and `memory-stop`, with peak phys_footprint above 1 GiB, in under 30 s. The `watchdog_selftest_run` over and under cases passed.
- **Driver.**
  - Full step order and the reviewed per-step timeouts (1200/300/3000/600/3600/1200 s; cite_build 1200, score 7200, protein 900) are applied. The A CITE timeouts shrink from the shared pool.
  - B_M6 predict gets `--expected-hashes` equal to the fit checkpoint sha256. A M6 gets the manifest hashes.
  - Receipts exist for all steps. `assembly.json` carries the fit directory, fit hashes and source revision.
  - `/usr/bin/time -l` is the exec prefix, and a post-run peak is recorded.
- **R5 pool.** With a 1.5 s pool, the driver blocks with "cite_predict pool … exhausted" before all six predictions run.
- **Resume.** The driver was SIGKILLed during A_M3_cite. `--resume`:
  - reused every receipted step (no B refits);
  - reran only A_M3 to A_M6, with A_M3 as **attempt 2**;
  - charged the unrecorded attempt's time to the stage and the pool, and completed.

  Resume also blocks in three cases:
  - a receipted output was tampered with;
  - an earlier deterministic failure exists (attempts are not reset);
  - the interrupted process group is still alive.
- **Cap paths.** `.venv`, `.tools`, `runs`, `companion`, `.cache-study`, `paper/build` and the run directory are included with no duplicates. A nested `--cap-path` is dropped. A hard-linked 2 MiB file across `.venv` and `.tools` is counted once.
- **Preflight.** Run with the pinned venv it returns rc 0, `labels_read: false`, the K list is reported, the CELLTYPIST_FOLDER check passes, the historical files are byte-identical before and after, and no step is launched.
- The revision 1 tests (guard limits, retries, the stage ceiling, hash mismatch and unlisted-file blocking, M6 relocation, the historical score_all being preserved) still pass.

## Remaining items (not done here; none needs a scientific change)
1. **Open interpretation for approval:** the R5 30 min pool is charged across retries (the stricter reading). If the user intends 30 min per R5 attempt-round, `POOLS`/`STEP_POOL` must change, and that needs approval.
2. The resume logic was exercised only with synthetic steps and a SIGKILLed driver. Before `--resume`, the operator must make sure no orphaned step group is still running; the driver checks `launch.json` and blocks if one is.
3. The R0 preflight and the 1 GiB self-test are implemented and tested but have **not been run against the real `HISTORICAL_RUNS_ROOT`**. Data acquisition is the coordinator's job, and running it is part of the approved execution. `evidence/recovery-inputs.json` supplies `root_layout` plus the 613 hashes. The driver's whole-subtree check also requires that every file under the D05 and T01 directories, and under the T02 M1–M3 directories, is listed there.
4. The post-run `/usr/bin/time -l` figure covers only time's direct child (a measurement limitation under `n_jobs=4`). The watchdog's process-group phys_footprint remains the primary enforcement.
5. Still needed:
   - the sha256 of `companion/scripts/score_all.py` recorded in an amendment before R6;
   - `protocol/tolerances.json`;
   - `study.json` and Makefile integration (both stay disabled);
   - verification of the four 10x CITE file hashes inside `build_cite.py`, which is owned by another worker;
   - coordinator verification.
6. The protocol is still not approved. This report is not methods approval or scientific verification.

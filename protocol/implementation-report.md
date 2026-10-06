# Implementation report: recovery infrastructure and scoring fixes (2026-10-06)

Worker: research-engineer. Snapshot `7dc729db`. Authority: `protocol/amendments/2026-10-06-approved-resumption.md`. Scientific scope and tolerances are unchanged. No study experiment, queue, scoring run or prediction-vs-label inspection took place. `historical/` is unchanged: `git diff -- historical` is empty, and `scripts/verify_migration.py` reports `changed: 0`. It also reports `missing: 570`, which is expected because the public snapshot excludes large and binary files (coordinator note §7), so that check exits 1.

## Changes

### `companion/scripts/score_all.py` (D-1a)
- New argument `--natural-unknown-scope {natural,all}`, default `natural`. For Arm A and the practical track, the primary unknown set is now `mapped & target ∉ K & stratum == "natural"`. This feeds `unknown_false_accept@OP*`, `unknown_auroc`, the per-class unknown rows and the bootstrap `unknown_false_accept@OPcov`.
- Arm B simulated unknowns (`REMOVED_B`, all strata) are unchanged.
- The all-strata analysis is still produced, as point estimates only, in `unknowns_allstrata_secondary.csv`. Each row is labelled `secondary-sensitivity-all-strata`. `scoring_scope.json` records the scope used.
- `--natural-unknown-scope all` reproduces the historical behaviour. The historical code itself is kept in `historical/companion/scripts/score_all.py`.
- Still to do before R6: the amendment must record the sha256 of this file.

### `companion/scripts/run_matched.py` (M6 checkpoint path)
- The `ScanviTransfer` pickle stores an absolute `self.dir` from fit time (`methods.py` around lines 200 and 211: `lvae.save(self.dir)` and `prepare_query_anndata(q, self.dir)`). At predict time, `model.dir` is now rewritten to `<--model-dir>/scanvi`.
- sha256 values for `model.pkl` and every checkpoint file are recorded in `predict_info.json`. The info also keeps the pickled path, the path actually used, and whether hashes were verified.
- The optional `--expected-hashes JSON` turns any mismatch or missing file into a hard error, which counts as a deterministic failure. `celltransfer/methods.py` is not modified.

### `scripts/resource_guard.py` (standard library only)
- Runs one foreground attempt in a new, never-reused `attempt-<n>-<UTC>` directory. The child gets its own session/process group (`start_new_session`).
- Memory is the sum over the process group plus all descendants found through the ppid tree, which catches children that called `setsid`.
- The primary memory measure is macOS `phys_footprint`, read with `proc_pid_rusage` (RUSAGE_INFO_V0, via ctypes on libproc). When that is unavailable, the guard falls back to RSS from `ps`. A stop triggered by the fallback has status `memory-watchdog-rss`.
- Swap: the stop fires when growth in `sysctl vm.swapusage` used exceeds 4 GiB.
- Disk: needs ≥ 3 GiB free to start (the driver raises this to 4 GiB for fits) and stops below 1.5 GiB while running. A 7 GiB storage cap is measured with du-equivalent block counts over `companion/`, `runs/`, `.cache-study/` and `paper/build/`.
- The timeout kills the group with TERM, then KILL.
- Environment: `*_NUM_THREADS=4`. `TMPDIR`, `JOBLIB_TEMP_FOLDER`, `TMP` and `TEMP` point to a per-attempt scratch directory, which is deleted afterwards.
- Each attempt writes `attempt.json` (command, limits, environment overrides, peaks, measure used, wall time, status), `samples.jsonl`, `stdout.log` and `stderr.log`.
- Defaults: 12 GiB memory, 5 s memory polling, 30 s disk polling.
- Known limitation: post-run `/usr/bin/time -l` peak footprint is **not** implemented (OA-5 item 4).

### `scripts/recover.py` (Mode R driver, standard library only)
- Reads `$HISTORICAL_RUNS_ROOT` (or `--historical-root`) and a hash manifest that lists `root_layout` {data, armA, armB} and `files` [{path, sha256}].
- Before launching anything, it verifies sha256 for the data dir, all Arm A dirs and Arm B M1–M3. It blocks on a mismatch, a missing file, or any file not listed in the manifest. It also requires `receipt.json` and the Arm A `model.pkl` files.
- Order (step arguments follow `queue_main.sh`):
  1. B M4, M5, M6: fit, then predict (`--model-dir` = the fit output).
  2. `build_cite.py`.
  3. A M1–M6 CITE predict, with `--model-dir` = historical `TA/M*`. M6 also gets `--expected-hashes`, generated from the manifest.
  4. `score_all.py --matched A=<TA> B=<armB> --reps 1000 --natural-unknown-scope natural`.
  5. `protein_check.py --cite <ci> --matched A=<armA_cite> --thresholds <score>/thresholds_validation.csv`.
- Arm B and A-CITE are assembled as symlinks named exactly `M1`…`M6`. Cached B M1–M3 links point to the verified historical directories, so cached labelling is preserved and the manifest records them as `cached`. Recomputed steps are recorded as `recomputed`.
- Retry rules:
  - At most 2 attempts per step.
  - Only infrastructure statuses are retried: memory, swap, disk-running, timeout and launch-error. Two memory-stops are a blocker.
  - `failed`, `disk-start` and `storage-cap` stop immediately.
- Time accounting: the wall time of every attempt counts toward the 8 h stage ceiling. Each attempt's timeout is `min(step ceiling, remaining stage time)`. Hitting the ceiling stops the run as blocked.
- After every attempt, the driver atomically rewrites `recovery_manifest.json` (source git rev and dirty flag, environment, verified input hashes, steps with command, attempt directory, logs, timeout, wall time, status). `--dry-run` only verifies the historical inputs.

## Test evidence (executed)
`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests` ran 20 tests in about 18 s, all passing, on macOS (darwin 25.6) with the system python3. Scratch files go to `tests/_tmp/` and temporary directories inside `tests/`, and are removed afterwards. The tests cover:
- Low-limit allocator: a 400 MiB allocation against a 100 MiB threshold ends with `memory-stop` via phys_footprint.
- Descendants: a child that calls setsid and allocates 300 MiB is counted toward the group total and killed.
- Timeout: the group is killed, and the killed process's negative return code is preserved.
- Disk: start floor, running floor and storage cap.
- Attempts: a failed attempt and the next attempt get separate, preserved attempt directories.
- Environment: threads set to 4, temp directory points to the attempt scratch, scratch deleted.
- CLI: infrastructure statuses return exit code 2.
- Recovery driver: full step order and arguments (`1000` reps, natural scope, M6 `--expected-hashes` matching the manifest, historical `--model-dir`, `M1`…`M6` links).
- Retry behaviour: a deterministic failure is not retried and its attempt is kept; a timeout is retried once and both attempts are kept.
- Stage ceiling: the run stops at the ceiling and the retry time is counted.
- Historical inputs: a hash mismatch, or a file not in the manifest, blocks before any launch.
- M6 relocation: the supplied directory is used, a hash mismatch raises, and a missing directory raises.
- D-1a: static wiring checks only.

Because the tests use synthetic fixtures, the driver's fake interpreter records the argument lists but runs no science.

## Not done / remaining integration (blocking R execution)
1. **No numerical scoring test of D-1a.** It needs the companion venv (numpy, pandas, anndata) and a synthetic obs fixture run through the real `score_all.py`. Neither was run within this worker's 900 s budget.
2. **There is no historical runs hash manifest** in the format `recover.py` expects. `evidence/migration-manifest.json` covers `historical/` code only. Someone with local access must generate one over the preserved `runs/` (D05, T01, T02, including `T01/M6/scanvi/`), and the actual directory names must be filled into `root_layout`.
3. **R0 to R2 are not wired into `recover.py`:** venv/cache measurement, the K top-up report, and the 1 GiB synthetic watchdog check on the real launcher with the production threshold. The driver also does not yet use per-R-step ceilings (R3 ≤ 80 min over all fits, and so on). It applies per-kind caps plus the 8 h stage ceiling.
4. **OA-5 item 4 is missing:** the `/usr/bin/time -l` post-run peak check.
5. The `CELLTYPIST_FOLDER` environment variable name used for cache redirection has not been checked against the installed celltypist version.
6. `build_cite.py` fetches the four 10x files from the network. The driver does not pre-verify their hashes.
7. These items are still needed: the sha256 of `score_all.py` recorded in an amendment before R6, `protocol/tolerances.json`, the `study.json` and Makefile integration, and coordinator verification.

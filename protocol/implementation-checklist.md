# Implementation checklist (companion to `protocol/resume-plan.md`)

Status: **unexecuted proposal**. Each item lists its acceptance check. Ticking an item needs evidence in a run directory or a commit. Nothing below has been done. Items marked ⛔ wait for the user's recorded approval.

## 0. Path mapping (frozen protocol → this repo; `protocol.md` is not edited)

| Referenced in `protocol.md` | Location here |
|---|---|
| `companion/src/celltransfer/*.py`, `companion/scripts/*` | `historical/companion/...` (frozen) → runnable copy `companion/...` (OA-1) |
| `evidence/label-maps/*`, `evidence/protocol-deviations.md`, `evidence/protocol-freeze-receipt.txt`, `access-and-feasibility.md` | `historical/evidence/...` |
| `evidence/probes/P01-…` | `historical/evidence/probes/P01-census-blood-obs-20261005/` |
| `runs/…` (D05, T01, T02, R01, data/) | git-ignored, absent from worktree; `HISTORICAL_RUNS_ROOT` (OA-10) |

## A. Documentation and approval

- [ ] A1 Confirm `protocol.md` is byte-identical to the frozen original: `shasum -a 256 protocol.md historical/evidence/protocol-frozen-original.md`. Both must equal `9b4374d8…`, per the manifest. *Not yet checked by this worker; no shell available.* If they differ, stop and treat the frozen original as the source.
- [ ] A2 Verify every migrated file against `evidence/migration-manifest.json` (sha256 and bytes). Record the output in `runs/<ID>-preflight-<UTC>/hashes.txt`.
- [ ] A3 Record these discrepancies in the amendment for user decision. No silent resolution.
  - (a) Protocol table lists 4 CITE files; feasibility lists 5 (adds `5k_pbmc_protein_v3` 3.1.0). Use the protocol's 4 unless an amendment says otherwise.
  - (b) Disk floor: protocol 0.4 GiB vs feasibility 1.0 GiB vs deviation-1 wait rule. The plan proposes stop at 3/4 GiB.
  - (c) Released-model (P1/P2) predictions on CITE files: the protocol metric wording does not restrict them; the historical queue ran matched Arm A only. Check `build_cite.py` and report.
- [ ] A4 ⛔ User writes `protocol/amendments/<date>-resume-operational.md` approving OA-1 to OA-11, §6 ceilings and stopping rules, §7 tolerances, network fetches, and no paid compute. A worker must not author the approval.
- [ ] A5 Record the `score_all.py`, `evaluate.py` and `protein_check.py` hashes in the amendment *before* any scoring (blinding, plan §2).

## B. Scaffold replacements (default scaffold is a non-study π fixture and is disabled)

- [ ] B1 `study.json`: replace the `experiment` command, inputs and outputs with the real stage drivers. Replace `reproduction.abs_tolerance 1e-10 / rel 1e-8` with a pointer to the §7 tiered tolerances. Replace the budgets (120 s / 600 s / 900 s / 500 MB) with the §6 ceilings (Mode R 6 h, Mode F 12 h, storage cap 5 GiB). Keep `max_attempts: 2`. Needs A4.
- [ ] B2 `configs/smoke.json`, `configs/full.json`: `study_kind: unconfigured` and `seed 20261001` are scaffold values. Replace with configs naming the mode (R/F/smoke), Census LTS `2025-11-08`, sampling seed **20261005**, training seed **0**, reps 1000, and data/run roots. Smoke uses the D01/D04 smoke scope.
- [ ] B3 `Makefile`: keep it disabled until A4. Then add `preflight`, `resume` (Mode R stages R0–R7), `reproduce` (Mode F F0–F5), `compare` (§7) and `paper`. Each target runs in the foreground and creates new attempt directories.
- [ ] B4 `scripts/experiment.py`, `src/study/monte_carlo.py`, `scripts/analyse.py`, `tests/test_numerics.py`: remove the π fixture. Replace with the driver (OA-2 to OA-7), assembly (OA-9), comparison (§7) and table→LaTeX export. Add tests for guard, timeout and retry logic and the M6 path remap, using synthetic data only.
- [ ] B5 `scripts/data.py` and `data/manifest.json` (empty): list every external input with URL, pinned version or revision, sha256, licence, `licence_verified: false|true`, and `redistributable: false` until cleared.
- [ ] B6 `pyproject.toml` (no deps) and `uv.lock`: pin to `historical/companion/env/requirements-full.lock.txt` (Python 3.11.13, matching `.python-version`). Check with `uv pip freeze` diffed against the lock: zero differences.
- [ ] B7 `paper/main.tex`, `paper/references.bib`, `literature/sources.json`: remove the fixture text. Write the study paper (plan §9) with sources taken from `historical/research/` and retrieval dates.
- [ ] B8 `evidence/claims.json`, `evidence/reviews.json`: leave empty until results exist. They are filled by the coordinator or reviewer, not by this worker.
- [ ] B9 `.gitignore`: add `runs/` large artefacts, `companion/.venv/` and `**/scratch/`. Keep `historical/runs/` ignored.
- [ ] B10 `README.md`: update status only after verified completion.

## C. Environment and code (OA-1, OA-6)

- [ ] C1 Copy `historical/companion/{src,scripts,vendor,env,pyproject.toml}` to `companion/`. Every sha256 must equal the manifest.
- [ ] C2 Build `companion/.venv` from the lock. Record its size (expect ≈ 0.5 GiB) and the free disk before and after.
- [ ] C3 Implement OA-8 (M6 `dir` remap with `model.pt` hash check) as the only code delta, recorded in an amendment. Test: loading T01/M6 with the remap must not open any path under the original workspace (check with `fs_usage` or an `open` audit in the test).
- [ ] C4 Export the thread variables (=4) and point `JOBLIB_TEMP_FOLDER`/`TMPDIR` at the attempt scratch directory. Print them in each attempt record.

## D. Preflight inputs (Mode R)

- [ ] D1 Set `HISTORICAL_RUNS_ROOT` read-only. Verify D05, T01/M1–M6 and T02/M1–M3 files against the manifest; any mismatch stops the run.
- [ ] D2 Extract historical `/usr/bin/time -l` blocks from T01 stderr files (peak memory for M5/M6) and record them. Adjust nothing scientific.
- [ ] D3 Confirm the D05 `receipt.json` exists and that its `features_and_classes.json` is identical to D03's (determinism reference, deviation 10).
- [ ] D4 Confirm free disk ≥ 4 GiB and storage used by the study < 5 GiB.

## E. Mode R execution ⛔ (after A4)

- [ ] E1 R1 B_M4 fit → predict, in a new `runs/T02r-matched-armB-M4-<UTC>/`. Check: `fit_info.json` has `validation_macro_f1_by_C` for 3 values and `chosen_C`; 15 `predictions_*.parquet` files exist.
- [ ] E2 R2 B_M5, R3 B_M6, each in its own new attempt directory. Same checks.
- [ ] E3 OA-9 assembly `runs/T02-assembled-<UTC>/` with `ASSEMBLY.json` (cached/fresh labels and hashes).
- [ ] E4 R4 CITE build. If it fails after 2 attempts, record "protein check not completed" and continue to E6.
- [ ] E5 R5 A CITE predictions M1–M6 (OA-8 for M6).
- [ ] E6 R6 score with `--reps 1000`. Check: `score_info.json` lists 14 method tables (A:M1–M6, B:M1–M6, practical:P1, P2) and `test_donors` > 0. All CSVs listed in `score_all.py` are present.
- [ ] E7 R7 protein check (if E4 succeeded).
- [ ] E8 Post-hoc labelled outputs: practical track excluding HIHA, and the platform P1 circularity flag.
- [ ] E9 Keep every failed or timed-out attempt directory, and list them in the results summary.

## F. Mode F execution ⛔ (after E complete and verified)

- [ ] F1 Fresh venv; re-fetch external inputs; hash-compare against historical values (CL `ba24e243…`, Immune_All_Low `290874d3…`, scTab `573b911f…`). Label any cached fallback.
- [ ] F2 Full data build into a new `runs/DF-…`. `--resume` is allowed only within the same attempt.
- [ ] F3 Run Arms A and B M1–M6, then CITE, score and protein, each in new directories.
- [ ] F4 `compare` against Mode R per the §7 tiers. Write `runs/C-repro-compare-<UTC>/report.json` with per-tier pass/fail. Breaches are reported, not tuned.

## G. Paper and blog gating

- [ ] G1 Paper tables and figures are generated only from E6/E7 outputs and the F4 report, by script. No hand-entered numbers.
- [ ] G2 Paper includes all plan §9 caveats and the notrun or infeasible list from plan §3.
- [ ] G3 The coordinator independently verifies the work and a review is recorded in `evidence/reviews.json`. This is a gate, not a worker action.
- [ ] G4 Only after G3: short blog draft in `blog-handoff/`. No publishing, pushing or messaging by workers.
- [ ] G5 Licence clearance is recorded in `data/manifest.json` before any per-cell data, model or CITE file is placed in the public repo. Until then, only aggregate tables are included.

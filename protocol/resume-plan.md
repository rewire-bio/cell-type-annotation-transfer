# Resumption and full-reproduction plan (article 349, migrated study)

Status: **PROPOSAL. NOT APPROVED.** Drafted 2026-10-06 by the research-designer worker at snapshot `02091eaa`. Nothing in this file authorises execution. No experiment, download, training or scoring was run to prepare it. Execution needs the user's own recorded approval in `protocol/amendments/` (see §10).

The scientific source of truth is still the frozen protocol, `protocol.md` (v1.0, frozen 2026-10-05). Its copy and freeze receipt are at `historical/evidence/protocol-frozen-original.md` and `historical/evidence/protocol-freeze-receipt.txt`. Clarifications and caveats are in `historical/evidence/protocol-deviations.md` (items 1–4 and 1–10). This plan changes **no scientific choice**: data, sampling, seeds, features, methods, tuning budget, arms, operating points, metrics or uncertainty method. It proposes only the operational amendments listed in §4. If any of them is judged to affect science, it becomes a blocker that needs renewed approval.

## 1. Question, contribution and hypotheses (restated from the frozen protocol, unchanged)

- **Question.** For a new blood/PBMC cohort, how should a reference and an annotation workflow be chosen, and when should a label be accepted? Transfer is assessed by whole-study holdout.
- **Contribution.** Two kept-apart tracks (matched M1–M6 and practical P1–P2). Coverage-aware abstention with operating points tuned on validation only. Natural and simulated (Arm B) unknown-type false acceptance. Calibration. Donor-cluster bootstrap.
- **Hypotheses / estimands.** These are descriptive comparisons with M4 as the paired reference comparator, not directional hypotheses. Confirmatory scope means the primary metrics in protocol §§5–6 computed exactly as frozen. Platform (one donor) and protein check are descriptive.
- **Exploratory or post-hoc, and labelled as such:** practical track excluding HIHA (deviation caveat 1); scTab mirror-vs-official byte comparison (caveat 6); this reproduction comparison (§7), which is a reproducibility check and not a scientific result; and any analysis not named in protocol §§5–7.
- **Not run (frozen, retained):** Pan-Human Azimuth and scGPT. Reasons are in `historical/evidence/access-and-feasibility.md`. No human label adjudication.

## 2. Historical state (as recorded; not re-verified by this worker)

Sources: `evidence/migration-manifest.json` (byte sizes and sha256 values for every migrated file), and the original-workspace `runs/queue-main/queue.log` and `runs/T02-…/M4/B_M4_fit.stderr`, which this worker read without modifying them. The original workspace is at `/Users/timrichardson/Documents/projects/personal/blog/rewire.it/workbench/outputs/blog-post-cell-type-annotation-transfer-20261005-182352`. The manifest classifies the migration as "historical, incomplete, not independently reproduced".

| Run | Outcome (recorded) | Keep as |
|---|---|---|
| R01 scTab mirror tutorial reproduction | PASS (per protocol §3) | provenance evidence |
| D00 smoke | FAILED (`FAILED.txt`) | failure record |
| D01 smoke | complete | smoke / determinism reference |
| D02 full | ABORTED after first study; data unused | failure record |
| D03 full | stopped on 2 h disk-guard timeout; only `features_and_classes.json`, `gene_universe_G.csv` written | determinism reference for features (deviation 10) |
| D04 smoke resume | equivalence vs D01 PASS (per deviation 10) | resume-equivalence evidence |
| D05 full data build | complete (`receipt.json`, 15 query files: 2 validation, 4 test, 9 platform; 6 reference checkpoints; released predictions P1/P2) | **the data run used by T01/T02** |
| S01, S02 | smoke runs | smoke evidence |
| T01 Arm A M1–M6 | fit+predict complete, 2026-10-06 09:23:52–09:58:52 UTC | cached predictions, unscored |
| T02 Arm B M1–M3 | fit+predict complete, 09:58:52–09:59:30 UTC | cached predictions, unscored |
| T02 Arm B M4 fit | **FAILED** rc=1 at 09:59:36 UTC after 6.08 s, peak footprint 3.27 GB. Cause: `OSError: [Errno 28] No space left on device` while joblib memory-mapped the dense z-scored matrix to its temp folder inside `LogisticRegression.fit` (n_jobs=4), on the first C value | failure record, never overwritten |
| T02 Arm B M5, M6; CITE build; A CITE predictions; scoring; protein check | **not started** | — |

Historical wall times (from queue.log, 4 threads, Arm A, including data loading):

| Step | M1 | M2 | M3 | M4 (3 C values) | M5 | M6 |
|---|---|---|---|---|---|---|
| fit | 2 s | 5 s | 5 s | 184 s | 777 s | 882 s |
| predict | 1 s | 2 s | 23 s | 2 s | 5 s | 212 s |

Arm A total ≈ 35 min. B_M1–M3 timings were close to Arm A's. D05 took ≤ 43 min, an upper bound inferred from the gap between the directory timestamp (08:40:48Z) and the queue start (09:23:52Z), not from a time record.

**Blinding status.** Per deviation 10 and the queue log, no held-out metric has been computed. Arm A and B test predictions exist but have not been compared with labels. This plan keeps that state: no prediction-versus-label inspection before §4 amendments and §7 tolerances are approved and the scoring code hash is recorded. Any accidental inspection must be logged in a new amendment.

## 3. Feasibility on this machine (Apple M4, 16 GB RAM, ~11 GiB free, CPU only, local only, no paid compute)

| Work item | Feasible? | Basis / uncertainty |
|---|---|---|
| Rebuild env from `historical/companion/env/requirements-full.lock.txt` (Py 3.11.13) | Yes, ≈0.5 GiB | Historical cost 0.47 GiB. Needs network/uv cache. Lock may lack hashes (unverified). |
| B_M4 fit/predict | Yes | Failure was disk only, at ~3–3.5 GB free total. Memmapped matrix ≲ 2 GB (estimate from 3.27 GB peak footprint, *uncertain*). With ≥ 4 GiB guard and joblib temp on a guarded scratch, ample headroom. |
| B_M5, B_M6 fit/predict | Yes | Arm A took 13 min and 18 min. Memory not recorded in the queue log (read `/usr/bin/time` blocks from T01 stderr at preflight). |
| CITE build (10x CDN, 4 files × 17–33 MB) | Probably | Depends on the CDN still returning 200. Licence "to verify". Never redistributed. |
| Arm A CITE predictions | Yes, with path fix A2 | M6 needs path fix (§5). |
| Scoring, 1,000 donor bootstrap reps, 14 method tables | **Runtime unknown** | Loop is pure pandas per replicate; never timed on full data. Bounded by the §6 ceiling; if exceeded, stop and report (do not reduce reps without amendment). |
| Protein check | Yes | Small. |
| Clean data rebuild from Census LTS `2025-11-08` | Probably | Needs public S3 access via `cellxgene-census` 1.18.0. Historical build ≤ 43 min. D03 held six reference studies in memory without OOM. |
| Re-fetch released models (HF mirror rev `9d49621`, CellTypist models, CL obo) | Probably | Third-party hosts. If unavailable, a hash-verified cached copy may be used and is labelled `cached-third-party`. |
| Pan-Human Azimuth, scGPT | **No** (frozen notrun) | Environment conflicts and disk. Retained as notrun, not dropped. |
| scTab official-host byte comparison (caveat 6, added check) | Uncertain | Host previously served a bot challenge, then HTTP 206 on 2026-10-05. Streamed with no storage. Optional. Outcome recorded either way. |
| Study-level CIs; platform-level uncertainty; human adjudication | **No** (by design) | Four test studies; one donor; no adjudication. Report as limitations. |
| Bit-identical runtime/memory reproduction | **No** (not meaningful) | Runtimes are descriptive single runs. |
| Public redistribution of matrices, predictions per cell, checkpoints, CITE data | **Not until licence clearance** | Census "CC BY 4.0 to be verified"; 10x "to verify"; CellTypist "to verify"; scTab weights via third-party mirror. |
| Scaffold budgets in `study.json` (120 s experiment, 600 s reproduction, 500 MB storage) | **No** | scTab checkpoint alone is 503 MB and reproduction needs hours. Must be replaced (§9). |

Overall: the cached resume and the clean full reproduction are both expected to fit within 16 GB RAM and 11 GiB disk. The main uncertainties are external-service availability, scoring runtime, scANVI CPU determinism, and fluctuating free disk from other jobs (the original failure mode).

## 4. Required operational amendments (proposed, need user approval; no scientific change)

- **OA-1 Code location.** Do not execute from `historical/` (frozen evidence). Copy `historical/companion/{src,scripts,vendor,env,pyproject.toml}` to a new top-level `companion/`. Verify every copied file's sha256 equals the migration manifest before any run. Any later code edit goes through a new amendment.
- **OA-2 New queue driver.** Do not relaunch `historical/companion/scripts/queue_main.sh` or reuse `runs/queue-main/` state. Its `.dir`, `.done` and `current_data_dir.txt` files hold absolute original-workspace paths. Reusing them would skip steps based on stale markers or write into the original workspace, and rerunning B_M4 into the same `T02/M4` directory would overwrite `B_M4_fit.stderr`, breaking immutability. The new driver differs only in operation: foreground execution, no `nohup`, and new attempt directories (OA-3). It keeps the guards (OA-4), timeouts (OA-5) and retry policy (OA-6) and the same per-step commands and `/usr/bin/time -l` wrapping.
- **OA-3 Immutable attempt directories.** Each step attempt writes to `runs/<ID>-<name>-<UTC>/` and is never reused (frozen §8). Each records: command, env lock hash, `pip freeze`, input paths and sha256, git revision, start/end UTC, rc, stdout/stderr, `/usr/bin/time -l` output, free disk before/after, and a `STATUS` of `ok|failed|timeout|guard-stop`. Failed attempts are kept. Cached inputs are labelled `cached` with their manifest hash.
- **OA-4 Disk guard.** This replaces deviation-1 "wait up to 2 h" with **stop, do not wait**, at a stricter threshold. No step starts below **3 GiB** free; M4/M5/M6 fits need **4 GiB**. A step is aborted (killed) if free space drops below **1.5 GiB** during the run, checked every 30 s by the driver in the foreground. Study-created storage cap is **5 GiB** (`du` of `runs/`, `companion/.venv`, scratch). Exceeding the cap stops the stage. All thresholds are stricter than the frozen 0.4 GiB floor.
- **OA-5 Wall-time and memory ceilings per step** (§6). Enforced by a foreground subprocess timeout. Peak memory footprint above **12 GiB** counts as failure.
- **OA-6 Threads and temp.** Set `OMP_NUM_THREADS=MKL_NUM_THREADS=OPENBLAS_NUM_THREADS=VECLIB_MAXIMUM_THREADS=4`, as historically, and the code's `n_jobs=4` and `torch.set_num_threads(4)` stay unchanged so runtimes stay comparable with Arm A. `JOBLIB_TEMP_FOLDER` and `TMPDIR` go to `runs/<attempt>/scratch/`, on the guarded volume. Scratch is deleted after the step with its peak size recorded, and is not evidence. This is the direct fix for the B_M4 failure and needs no code change.
- **OA-7 Retry policy.** At most **2 attempts per step**, matching `study.json` `max_attempts`. Retries are allowed only for infrastructure causes: ENOSPC, network timeout or HTTP 5xx, external kill or timeout. Downloads may also retry 3× with backoff inside one attempt, each logged. Deterministic exceptions in scientific code are **not** retried: stop and report as a blocker.
- **OA-8 M6 path remap.** `ScanviTransfer.save` pickles `self.dir` as an absolute path into the original workspace. At load time the new driver overrides `model.dir` to `<model-dir>/scanvi`, after checking that `scanvi/model.pt` sha256 matches its manifest or attempt record. This keeps any run from silently reading the original workspace. It is a loader-side change to `run_matched.py` or a small wrapper, and is recorded as a code amendment.
- **OA-9 Mixed-run assembly for scoring.** `score_all.py` expects one directory per arm containing `M*/`. For the cached resume, an assembly directory `runs/T02-assembled-<UTC>/` holds relative symlinks to historical `T02/M1–M3` and the new `M4–M6` attempts, plus `ASSEMBLY.json` with source paths, hashes and `cached|fresh` labels. `score_all.py` stays byte-identical.
- **OA-10 Historical-run access.** `historical/runs/` is git-ignored and **absent from this worktree**. The cached resume reads it through one configured root (`HISTORICAL_RUNS_ROOT`), read-only, and verifies every file used against the migration manifest. Paths are never hard-coded.
- **OA-11 Path privacy for the public repo.** Historical logs contain `/Users/timrichardson/...` paths. Historical files are not edited. Any public copy is a separately generated, redacted derivative with a path mapping, or is withheld.

## 5. Absolute-path risks (inventory)

1. `runs/queue-main/*.dir`, `*.done`, `current_data_dir.txt` hold absolute T01/T02/D05 paths. Mitigation: OA-2.
2. M6 `model.pkl` holds an absolute `self.dir`. A CITE predict with `--model-dir T01/M6` would load the original workspace's `scanvi/`. Mitigation: OA-8.
3. `fit_info.json` and `predict_info.json` (`data`, `model_dir`) and every queue.log line hold absolute paths. These are provenance only; record the mapping old→new in the attempt record.
4. `run_matched.py` and `score_all.py` import from `<workspace>/companion/src`. The new repo has code under `historical/companion`. Mitigation: OA-1, with `--workspace` set to the repo root.
5. `migration-manifest.json` `source_workspace` and the venv paths in tracebacks are informational. The venv was excluded from migration and must be rebuilt.
6. The root `protocol.md` refers to `companion/…` and `evidence/…` paths that now live under `historical/`. Use the mapping table in the checklist and do not edit `protocol.md`.

## 6. Two execution modes

The modes are kept separate in directories, labels and reporting. **Mode R** must finish before **Mode F** starts. Mode F results never overwrite Mode R results.

### Mode R: cached resume (completes the historical study)

Inputs: D05, T01 (A M1–M6) and T02 (B M1–M3), read-only via OA-10 and hash-verified. Everything new runs on D05.

| Step | Command (unchanged script and arguments, new out dir) | Ceiling | Guard |
|---|---|---|---|
| R0 preflight | env build; hash checks; `pip freeze` vs lock; read T01 `/usr/bin/time` blocks | 30 min | 3 GiB |
| R1 B_M4 fit / predict | `run_matched.py --data D05 --arm B --method M4 --stage fit|predict` | 20 min / 5 min | 4 / 3 GiB |
| R2 B_M5 fit / predict | same, M5 | 50 min / 10 min | 4 / 3 GiB |
| R3 B_M6 fit / predict | same, M6 | 60 min / 20 min | 4 / 3 GiB |
| R4 CITE build | `build_cite.py --data D05` | 20 min | 3 GiB |
| R5 A CITE predict M1–M6 | `run_matched.py --arm A --data <CITE> --model-dir T01/<m>` (OA-8 for M6) | 30 min total | 3 GiB |
| R6 score | `score_all.py --data D05 --matched A=T01 B=T02-assembled --reps 1000` | 120 min | 3 GiB |
| R7 protein | `protein_check.py --thresholds R6/thresholds_validation.csv` | 15 min | 3 GiB |

Expected ≈ 2–2.5 h. Ceiling for the whole stage: **6 h** wall. Each row is run as a separate foreground invocation, so no background processes are needed. As in the historical queue, a CITE build failure (R4) does not block R6; it is reported as "protein check not completed" with the reason.

### Mode F: clean full reproduction (independent re-derivation)

No derived historical outputs are reused (no D05, T01, T02 or scoring). External immutable inputs are re-fetched and hash-checked against the historical values (CL obo `ba24e243…`, Immune_All_Low `290874d3…`, scTab ckpt `573b911f…`). If a re-fetch fails, a hash-identical cached copy may be used and the run is labelled `clean-with-cached-third-party`.

| Step | Ceiling |
|---|---|
| F0 fresh env (separate venv) + preflight | 30 min |
| F1 data build (`build_data.py`, Census LTS `2025-11-08`, seed 20261005, `--resume` permitted *within* this F1 attempt only) | 2 h |
| F2 Arm A M1–M6 fit/predict | 2.5 h |
| F3 Arm B M1–M6 fit/predict | 2.5 h |
| F4 CITE build + A CITE predict | 1 h |
| F5 score (1,000 reps) + protein | 2.5 h |

Expected ≈ 3.5–4.5 h. Ceiling: **12 h**, and stages may run on separate days. Peak extra storage is ≈ 2 GiB (env 0.5, scTab 0.5, data ≈ 0.35, two arms ≈ 0.5, transient joblib scratch ≤ 2) within the 5 GiB cap.

### Stopping rules (both modes)

Stop the stage and return **blocked** with the attempt directory if any of these occurs:

- a frozen-input or code hash mismatch;
- a disk guard trips, or the 5 GiB storage cap is exceeded;
- a step reaches its ceiling or memory exceeds 12 GiB on both attempts;
- a non-infrastructure exception occurs;
- Census LTS `2025-11-08` or a released model is unavailable with no hash-identical copy;
- any step would need a scientific change (method, seed, data, threshold rule, number of reps);
- the stage wall ceiling is reached.

Never substitute values, shorten training, cut bootstrap reps or drop methods to meet a budget.

## 7. Reproduction tolerances (fixed now, before any scoring; need approval)

These compare Mode F with Mode R on the same quantities. The tiers follow the source of nondeterminism. Same lock and same arm64 machine are assumed; multithreaded BLAS/Accelerate reductions are not guaranteed to be bitwise identical, and scANVI CPU training is not guaranteed deterministic.

| Tier | Quantity | Tolerance | Justification |
|---|---|---|---|
| T1 exact | sampled `soma_joinid` per study/role/stratum; `features_and_classes.json` (F_A, F_B, K, K_B, markers; also equal to D03's); cell counts; M4 chosen C (A and B); P1 labels; bootstrap donor weights | identical | Seeded `default_rng` + fixed inputs; D04 already showed resume-equivalence |
| T2 numeric | M1–M5 and P2 per-cell predictions | label agreement ≥ 99.9% per study; `conf` abs diff ≤ 1e-5 on agreeing cells; τ_cov, τ_err rel diff ≤ 1e-4 | float32 paths with threaded reductions; flips should be limited to near-ties |
| T3 stochastic | M6 per-cell predictions | label agreement ≥ 97% per study | scANVI/PyTorch CPU training with seed 0 is not guaranteed deterministic; 50-epoch query adaptation amplifies differences |
| M metric | for every arm × method: coverage, accepted error, unassigned at OP-cov/OP-err; macro-F1; unknown false acceptance; cross-lineage rate | abs diff ≤ 0.01 (AURC ≤ 0.005; Brier/ECE ≤ 0.01) | 1 percentage point is below the resolution at which the 90% coverage and 5% error operating points are interpreted |
| S sign | paired differences vs M4 whose 95% CI excludes 0 in either mode | same sign in both | Protects headline comparisons |
| — | runtime, peak memory | not toleranced; flag > 2× | descriptive single runs |

Outcome rules. All tiers within tolerance means "reproduced within pre-specified tolerance". Any breach is reported as a failed or partial reproduction for that method, with both results kept. Tolerances are never widened after seeing the comparison. Mode R stays the primary result of record, because it is the run defined by the historical data build. If T1 fails, the study is reported as not reproduced at the data level, and the coordinator decides whether to request an amendment.

## 8. Uncertainty reporting (unchanged)

Donor-cluster bootstrap within test studies: 1,000 reps, seed 20261005, 95% percentile intervals, paired against M4. Per-study estimates are given without study-level intervals. Cell counts are never the unit of uncertainty. Per-cell label disagreement between modes (§7) is reported as a reproducibility statistic, not folded into the CIs.

## 9. Repository, paper and blog gating

- **Fresh public study repo.** The repo contains code, protocol, amendments, attempt receipts (redacted per OA-11), aggregate result tables and the paper. Kept out until licence clearance is recorded in `data/manifest.json`: Census-derived h5ad/parquet per-cell files, released model files, the scTab checkpoint, 10x CITE matrices, and the `historical/research/automated-research/` source copies. `runs/` large artefacts are git-ignored; small receipts go to `evidence/archive/`.
- **Paper first.** `paper/main.tex` is replaced with the study paper, generated from Mode R tables plus the Mode F comparison. It must state these caveats: HIHA labels partly derived from CellTypist (P1 circular; HIHA-excluded sensitivity is post-hoc); platform-panel labels are a CellTypist/Seurat consensus (descriptive and circular for P1; pre- or post-relabel status unverified); the CVID reference includes stimulated and cultured cells; Hao 2021 includes post-vaccination timepoints; multi-valued `disease` may omit healthy cells; the scTab weights come from a third-party mirror; there was no human adjudication; the matched and practical tracks are not architecture comparisons; the platform comparison is one donor. Azimuth and scGPT are notrun, with reasons.
- **Blog only after verification.** No `blog-handoff/` is created until the coordinator has independently verified Mode R, and Mode F or a recorded reason it is infeasible, and the review is recorded in `evidence/reviews.json`. The blog is short and restates the same caveats. Nothing is published, pushed or sent by workers.

## 10. Approval required (not given)

The user must record in `protocol/amendments/<date>-resume-operational.md`:

1. acceptance of OA-1 to OA-11;
2. the §6 ceilings and stopping rules;
3. the §7 tolerances;
4. the §3 infeasible and notrun items;
5. permission for network fetches from Census S3, Hugging Face, CellTypist, the 10x CDN and GitHub;
6. confirmation that no paid compute is used.

Until then, `Makefile` targets stay disabled.

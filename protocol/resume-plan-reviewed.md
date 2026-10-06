# Resumption and full-reproduction plan, reviewed (article 349)

Status: **PROPOSAL, NOT APPROVED.** This is the methods-reviewer's corrected version of `protocol/resume-plan.md` (2026-10-06, snapshot `b9be7835`). The findings behind each correction are in `protocol/preexecution-review.md` (B1–B6 and numbered items). Nothing in this file authorises execution or certifies the methods. No scientific choice changes: data, sampling, seeds, features, methods, tuning budget, arms, operating points, metrics and the uncertainty method all stay as in the frozen `protocol.md` v1.0.

Sections of the original plan that carry over **unchanged**: §1 (question and hypotheses), §2 (historical state and blinding status), §5 (absolute-path inventory), §8 (uncertainty) and the §9 paper caveats list. The sections below replace §§3, 4 (only where noted), 6, 7, 9 and 10.

## 1. Already authorised (not re-asked)

The user has already authorised a public repository, network access to public sources (Census S3, Hugging Face, CellTypist, the 10x CDN, GitHub and the tectonic bundle) and no paid compute. The coordinator records the user's answer to §10 in `protocol/amendments/<date>-resume-operational.md`. The user does not edit any files.

## 2. Execution order

R0 → Mode R (R1–R7) → coordinator verification of Mode R → Mode F (F0–F5) → `compare` (§7) → harness build H (§6) → verify gates → paper → blog (§8). Mode F never overwrites Mode R.

## 3. Storage (replaces original §3 "fits in 5 GiB" and the §6 "≈ 2 GiB")

All caches are redirected into the study prefix so the cap measures real usage: `UV_CACHE_DIR`, `HF_HOME`, the CellTypist model folder, `XDG_CACHE_HOME`, `TMPDIR`/`JOBLIB_TEMP_FOLDER` (per-attempt scratch) and the tectonic cache. The cap is checked with `du -sk` over `companion/`, `runs/`, `.cache-study/` and `paper/build/`. Historical runs under `HISTORICAL_RUNS_ROOT` are outside the cap and read-only.

| Component | Mode R | Mode F (added on top of R's retained files) |
|---|---|---|
| venv (+ uv cache, if not hard-linked) | 0.5 (+ ≤ 1.0) | 0.5 (separate venv) |
| scTab checkpoint + CellTypist + CL obo | 0 (cached via D05) | 0.55 |
| data build | 0 | 0.35 |
| model fits + predictions | ≈ 0.3 (B M4–M6) | ≈ 0.5 (A + B) |
| CITE downloads (transient) + derived | ≈ 0.15 | ≈ 0.15 |
| joblib/torch scratch (transient, deleted after each step) | ≤ 2.0 | ≤ 2.0 |
| tectonic bundle + PDF build | — | ≈ 0.5 |
| **Peak (transient included)** | **≈ 3–4 GiB** | **≈ 4 GiB more, so ≈ 6–6.5 GiB study total** |
| Retained after the stage | ≈ 1–2 GiB | ≈ 3.5–4.5 GiB total |

Because these are estimates, R0 measures the venv and cache sizes and records them.

- **Study storage cap: 7 GiB** (`max_storage_mb: 7168`), up from 5 GiB. Exceeding it stops the stage (guard-stop).
- Disk guards are unchanged from OA-4. Each step needs ≥ 3 GiB free to start, and M4/M5/M6 fits need ≥ 4 GiB. A step is killed if free space falls below 1.5 GiB, checked every 30 s. The machine has about 11 GiB free, so a full study footprint leaves about 4 GiB. That is enough, but only just: the guards, not the estimates, are what prevent a repeat ENOSPC.

## 4. Operational amendments

OA-1 to OA-4 and OA-6 to OA-11 are as in the original plan. The changes are:

- **OA-5 (replaced). Memory ceiling enforcement.** macOS does not enforce `RLIMIT_AS`/`RLIMIT_RSS`, and `/usr/bin/time -l` only reports after the process exits. So:
  1. The driver starts each step in its own process group and runs a foreground watchdog that polls every 5 s.
  2. The watchdog's primary measure is per-process physical footprint (`phys_footprint`, from the macOS `footprint` tool or `proc_pid_rusage`), summed over the process group. RSS is a recorded fallback only. It double-counts shared joblib memmap pages, so a kill triggered by RSS is labelled `memory-watchdog-rss`.
  3. The process group is killed when the sum exceeds **12 GiB**, or when `sysctl vm.swapusage` used grows by more than 4 GiB during the step. Status: `memory-stop`.
  4. After the run, `/usr/bin/time -l` "peak memory footprint" above 12 GiB also marks the attempt as failed. That figure covers the parent process only. Under `n_jobs=4` it understates aggregate memory, and this is reported as a measurement limitation.
  5. A `memory-stop` counts as an infrastructure cause (one retry). Two memory-stops are a blocker. Threads, `n_jobs`, data or reps are never reduced to fit.
  6. R0 must show the watchdog works on a synthetic allocator with a 1 GiB test threshold. Otherwise execution is blocked.
- **OA-4 addition.** The storage cap is 7 GiB (§3).
- **OA-9 addition.** Symlinks are named exactly `M1`…`M6`, because `score_all.py` keys tables on directory names.

## 5. Decision required before scoring (finding B1)

**D-1 Natural-unknown stratum.** `protocol.md` §6 says "Unless stated, natural stratum only" and applies "all strata" only to the simulated unknowns of Arm B. `score_all.py` computes natural unknowns for Arm A and the practical track over **all strata**, which includes rare top-up cells. The same applies to `unknown_auroc`. First, R0 reads K from D05 `features_and_classes.json` (reference-only, so blinding holds) and reports which top-up classes fall outside K.

- If **none do**, the two definitions match and no action is needed.
- If **some do**, the user chooses one of these **before R6**:
  - **(a) recommended, follows the protocol text.** Primary natural-unknown metrics use the natural stratum only. This is implemented as an amendment-recorded scoring wrapper that reuses `evaluate.py` unchanged. `score_all.py`'s all-strata output is kept and labelled as a secondary, pre-specified sensitivity analysis.
  - **(b)** The `score_all.py` behaviour is kept as the primary result and recorded as a deviation in interpretation.

Either way, the choice is fixed and its code hashed before R6. It applies identically to Mode F.

## 6. Budgets and ceilings (replaces original §6 ceilings; steps and commands unchanged unless noted)

Per-step ceilings apply to each attempt. **Stage ceilings are the sum of wall time across all attempts, retries included.** Reaching a stage ceiling means stop and return blocked.

**Mode R.** Step ceilings: R0 30 min; R1 20 + 5 min; R2 50 + 10 min; R3 60 + 20 min; R4 20 min; R5 30 min; R6 120 min; R7 15 min. One attempt of every step adds up to 380 min. **Stage ceiling: 8 h** (the original 6 h was below the single-attempt sum). Expected time is 2–2.5 h.

The R7 command is completed as: `protein_check.py --workspace <repo> --cite <R4 attempt> --matched A=<R5 attempt> --thresholds <R6>/thresholds_validation.csv --out <R7 attempt>`. The R5 output must contain `M1`…`M6/predictions_<cite>.parquet`. `build_cite.py` writes `released_predictions_<name>.parquet`, so P1/P2 are included in the protein check (this answers checklist A3(c)).

**Mode F.** Step ceilings are as in the original plan: F0 30 min, F1 2 h, F2 2.5 h, F3 2.5 h, F4 1 h, F5 2.5 h, which add up to 11 h. **Stage ceiling: 14 h** across attempts, possibly spread over several days. Expected time is 3.5–4.5 h.

**H: harness reproduction (`make reproduce`).** Must, in order:
1. run Mode F (F0–F5) into new directories;
2. run `compare` (§7) and write `runs/C-repro-compare-<UTC>/report.json` and `results/full/results.json`;
3. regenerate **every** paper table and figure by script from the scoring outputs, with no hand-entered numbers;
4. compile `paper/build/main.pdf` from the **committed** `paper/main.tex`/`references.bib` with tectonic.

Budget: compare + tables + figures ≤ 20 min; PDF ≤ 15 min (including the first tectonic bundle fetch); **total `reproduction_seconds` = 54,000 (15 h)**; storage within the 7 GiB cap. Set `study.json` to `experiment` = stage drivers, `max_attempts: 2`, `max_storage_mb: 7168`, `reproduction_seconds: 54000`.

The single `abs_tolerance 1e-10 / rel 1e-8` cannot represent §7. It is replaced by a committed `protocol/tolerances.json` encoding §7, whose sha256 is recorded in the amendment before R6. *Open item for the coordinator (not a user decision):* confirm how the harness consumes the tolerance fields. If it supports only one abs/rel pair, the harness's numeric check is set to the M-tier (abs 0.01, rel 0) on `results.json`, and the tiered `compare` pass/fail becomes a separate required verify gate.

A separate light check, **H-paper**: from a clean checkout of the committed aggregate tables, tables, figures and the PDF are rebuilt with no network apart from the tectonic bundle. The regenerated table text must be byte-identical to the committed tables, and the PDF must compile with no undefined references. Budget 30 min and 1 GiB.

**Stopping rules:** as in the original plan, plus `memory-stop` twice, stage ceiling reached, or any watchdog or guard failure at R0.

## 7. Reproduction tolerances (replaces original §7; fixed before R6, never changed afterwards)

Definitions:
- `close(a,b; abs, rel)` means both values are finite and |a−b| ≤ abs + rel·max(|a|,|b|), **or** both are in the same non-finite state (NaN, `None`/"not attainable", `-inf`). A difference in state is a breach.
- Metric comparisons are on the absolute scale (no relative part), so they have no near-zero problem.
- The near-zero rule for signs is given in tier S.

| Tier | Quantity | Rule |
|---|---|---|
| T1 exact | sampled `soma_joinid` per study/role/stratum; `features_and_classes.json` (F_A, F_B, K, K_B, markers; also = D03); `cell_counts.csv`; `test_donors`; `f1_classes`, `test_scorable_natural`, `unknown_cells`; M4 chosen C per arm (if it differs, report `validation_macro_f1_by_C` from both modes; still a breach); P1 labels; bootstrap weights; ADT count tables | identical |
| T2 deterministic-up-to-BLAS | per query file (15 D-files + 4 CITE), M1–M5 and P2 labels; P1/P2/M1–M5 `conf` | disagreeing cells ≤ max(1, ⌊0.001·n⌋) per file; `conf` close(1e-5, 1e-5) on every agreeing cell |
| T2 thresholds | `tau_cov`, `tau_err` per arm × method | **state** identical (finite / `-inf` / not attainable). Finite values are not given a numeric tolerance, because `tau_err` jumps between tie blocks and margin-based τ can be close to 0. Their effect is checked through `validation_coverage_at_tau_cov` and `validation_error_at_tau_cov`, which use the M tier. Report |Δτ|. |
| T2 protein gating | per-cell protein class per CITE file (GMM `random_state=0`) | disagreement ≤ max(1, ⌊0.001·n⌋) |
| M metrics (**all** methods, M6 included, all arms and the practical track) | `summary_test.csv`: coverage, accepted_error, cross_lineage_share and cross_lineage_rate at both OPs; unassigned (= 1 − coverage, derived); macro_f1_closed; unknown_false_accept at both OPs; unknown_auroc; lineage_agreement_closed; coarser/outside_fraction; risk@0.50…1.00; max_coverage. Also every `*_ci95` endpoint; every `paired_differences_vs_M4.csv` mean_diff, ci95_lo and ci95_hi; the validation coverage/error at τ; protein `agreement_accepted` and `agreement_accepted_gateable_preds` per file × method | close(0.01, 0) |
| M metrics | AURC | close(0.005, 0); report relative size |
| M metrics | Brier, ECE (M4–M6, P1, P2) | close(0.01, 0) |
| S sign | **headline** paired differences, meaning Mode R CI excludes 0 **and** \|mean_diff\| > 0.01 | Mode F mean_diff has the same sign **and** its CI also excludes 0. A change in CI-exclusion status for a difference with \|mean_diff\| ≤ 0.01 in both modes is reported as "near-zero, not a sign breach". |
| Diagnostic, no pass/fail | M6 per-cell label agreement and `conf` differences per file | reported. The original "≥ 97%" line is shown only as a pre-registered heuristic **with no empirical basis**: no repeat scANVI CPU run exists. |
| Descriptive, not gated | per-study, per-class, platform, unknowns per class, risk-coverage points, reliability bins, NaN-replicate counts | max \|Δ\| reported; small n |
| Not toleranced | runtime, peak memory | flag > 2× |

Outcomes, one per arm × method, plus an overall result:
- **reproduced within pre-specified tolerance**: every gated tier passes;
- **partially reproduced**: breaches are listed, and both results are kept;
- **not reproduced at the data level**: any T1 breach.

An M6-only breach while M1–M5 pass may be described as "consistent with non-deterministic CPU training (not verified)". It is not waived. Mode R remains the result of record. No tolerance is widened, no tier is reassigned and no metric is dropped after any comparison is computed.

## 8. Uncertainty reporting and limitations (additions to original §8)

The bootstrap code produces CIs and paired differences for exactly seven metrics: coverage and accepted error at both OPs, macro-F1, unknown false-acceptance at OP-cov, and cross-lineage rate at OP-cov. All other metrics are reported as point estimates **with no interval**, labelled as such. The intervals are conditional on thresholds fixed on validation; validation uncertainty is not propagated. NaN replicates for unknown false-acceptance are counted and reported. Calibration uses un-renormalised top CellTypist probabilities for ECE and renormalised probabilities for Brier (deviation 3).

## 9. Paper and blog gating (replaces the original §9 blog bullet)

The paper and its caveats are as in the original §9. **No `blog-handoff/` is created** until all of the following hold:
1. Mode R is complete and independently verified by the coordinator.
2. Mode F has been **executed** and the §7 report exists. Its outcome, including any breaches, is stated in both the paper and the blog.
3. `make reproduce` (H) and H-paper pass within budget.
4. All harness verify gates pass.
5. The review is recorded in `evidence/reviews.json`.

A recorded reason that Mode F is infeasible does **not** satisfy the gate. In that case the study stays blocked and any change needs a new user amendment. A T1 breach also blocks the blog until the user decides.

## 10. Concrete items for user approval (the coordinator records the answer)

1. OA-1 to OA-11 with the revised OA-4 (7 GiB cap, redirected caches) and OA-5 (watchdog memory enforcement).
2. Budgets: Mode R 8 h; Mode F 14 h; `make reproduce` 15 h total; H-paper 30 min / 1 GiB; storage cap 7 GiB; max 2 attempts per step; the stopping rules.
3. The §7 tolerances as written. This includes M6 under the same metric tolerances, with no special relaxation.
4. D-1, if R0 shows top-up classes outside K: option (a) (recommended) or (b).
5. The notrun and infeasible items in original §3, which are unchanged.
6. The blog gate in §9.

Until this is recorded, the `Makefile` targets stay disabled, and no prediction is compared with any label.

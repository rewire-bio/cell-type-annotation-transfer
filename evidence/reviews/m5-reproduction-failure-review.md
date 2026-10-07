# Methods review: failed clean-reproduction comparison 78542e9d (M5 CellTypist retraining)

- **Role:** methods reviewer. This is a model review, not a human review, and it is not a scientific verification.
- **Date:** 2026-10-07. Worktree snapshot `67b294619a3107133dd02629cf7ff700b03d4d2e`.
- **Subject:**
  - reproduction `78542e9d412548edbfe42b38d452f7a8`, source `1e95aac46e212446d4ad08d10838084e9fc90df1`, status `failed`, exit code 2;
  - compared against original run `29879296d87343898100c190308744a1` (Mode R, the result of record);
  - protocol hash `0f8cc011…98e4`; science hash `b5097a7e…021a`;
  - tolerances `protocol/tolerances-v2.json` (sha256 `c335e6a9…0edb`, per the generation receipt).
- **Scope:**
  - I read the inputs only. I ran no fits, predictions, scoring or comparisons, and edited no inputs, implementation, paper or ledger.
  - I did not read the full 25 MiB comparison report (sha256 `2a663866746ee682b93cadcfaebba56715dbb6cf308bc78bdd86301f689d6dc8`, 26,158,936 bytes, held privately). I used its mechanical public derivative `comparison-failure-summary.json`. In that file, long confidence arrays are cut to a count, the maximum |Δ| and the first three rows. Nothing here relies on the omitted rows.

## Verdict: **FAIL** (current clean-reproduction gate)

The gate requires `scripts/compare_runs.py` to exit 0 (`study.json` → `reproduction.tiered_comparison.required_exit_code: 0`). It exited 1, with overall status **"partially reproduced"**:
- 1,523 checks;
- 54 gated breaches;
- 0 unsupported checks;
- 0 structural or T1 breaches.

Clean reproduction has **not** been achieved. Nothing below makes it pass, and the tolerances, tiers and recorded results stay as they are. The paper must not be compiled as if reproduced. Stopping the paper build after the failed comparison was correct.

## What the evidence establishes

### E1. Every breach is M5, and every gated M5 per-cell check breached

Source: `comparison-failure-summary.json` and the `engineering-diagnostic.json` field `breaches_by_method = {"M5": 54}`.

**Labels: 17 breaches.**
- Arm A, 8 files: ClonalHaem 7/4 allowed; Glaucoma 5/2; 10x Flex 4/1; BD Rhapsody 2/1; Parse v2 19/1; ScaleBio 12/1; PIP-seq 22/1; RA 28/8.
- Arm B, 9 files: Glaucoma 7/2; HIHA 22/10; JDM 6/3; 10x 3′ v3 4/1; HIVE 3/1; Parse v2 26/1; ScaleBio 24/1; PIP-seq 30/1; RA 30/8.

**Confidence: 32 breaches.** All 17 Arm A M5 query files (15 D files plus the 2 eligible CITE files) and all 15 Arm B M5 files.
- Per-file maximum |Δconf| on agreeing cells ranges from 0.030 (B JDM) to 0.217 (A HIHA).
- Per-file breach counts range from 229 (B 10x Flex) to 7,227 (A RA).
- The T2 rule is close(1e-5, 1e-5) on every agreeing cell.

So the M5 difference is systematic across all files, not local to a few. Label disagreement is largest on the out-of-distribution platform files (Parse, ScaleBio, PIP-seq: 1.2–3.0% of 1,000 cells).

**M-tier: 5 breaches, all Arm A M5, all natural-unknown metrics, abs tolerance 0.01.**

| Check | Original | Fresh | Abs diff |
|---|---|---|---|
| `summary_test:unknown_false_accept@OPcov` | 0.30 | 0.15 | 0.15 |
| `summary_test:unknown_auroc` | 0.8028 | 0.8256 | 0.0228 |
| `unknown_false_accept@OPcov_ci95.hi` | 0.3158 | 0.1579 | 0.158 |
| `paired:unknown_false_accept@OPcov:mean_diff` (vs A:M4) | −0.1321 | −0.2453 | 0.113 |
| `paired:unknown_false_accept@OPcov:ci95_hi` | 0.2105 | 0.0526 | 0.158 |

### E2. All other M5 summary and paired metrics stayed within the M tier

This comes from comparing `original/summary_test.csv` with `fresh/summary_test.csv`, and the two `paired_differences_vs_M4.csv` files.

Closed-set and selective-prediction metrics moved by less than 0.01:

| Metric | Original | Fresh |
|---|---|---|
| A:M5 macro_f1_closed | 0.68816 | 0.68907 |
| A:M5 coverage@OPcov | 0.79830 | 0.79793 |
| A:M5 accepted_error@OPcov | 0.08899 | 0.08883 |
| A:M5 AURC | 0.05255 | 0.05247 |
| B:M5 macro_f1_closed | 0.74713 | 0.74818 |
| B:M5 unknown_false_accept@OPcov (simulated, n=2,310) | 0.83377 | 0.83420 |

Paired M5−M4 macro-F1:
- original: −0.00607 [−0.01427, 0.00203];
- fresh: −0.00518 [−0.01355, 0.00294].

The signs of ledger claims M07 and M08 (lower bound < 0, upper bound > 0) hold in both draws. No threshold-state, T1, S-sign or protein breach appears in the failure list.

### E3. Inputs and preprocessing for the M5 fits are identical

Source: `engineering-diagnostic.json` → `input_checks.original_equals_fresh`.
- These are all true for the training reference: shape, CSR data/indices/indptr, obs/var names, target labels, `total_counts_all`, and `features_and_classes.json` (sha256 `0472df1f…`).
- The saved scaler `mean_`, `scale_` and `var_`, genes and classes are exactly equal in both arms.
- The `coef_` and `intercept_` hashes differ.
  - Arm A: max |Δcoef| 0.0667, |Δintercept| 0.0038.
  - Arm B: max |Δcoef| 0.0453, |Δintercept| 0.0053.
- The fresh predict receipts match their fresh fit-model hashes (A `8d2ba132…`, B `788647ee…`).

The divergence therefore enters at the solver fit, not in the data, features, labels or scaling.

### E4. The M5 estimator is stochastic and was not seeded

Sources:
- `engineering-diagnostic.json` → `model_parameters`: for both arms, original and fresh, `solver=sag`, `random_state=null`, `n_jobs=4`, `max_iter=500`, `tol=1e-4`, `C=1.0`, `multi_class=ovr`.
- `companion/src/celltransfer/methods.py` L153–154: `celltypist.train(..., check_expression=False, use_SGD=False, feature_selection=False, n_jobs=4)`, with no `random_state`.
- Diagnostic `solver_rule` for celltypist `train.py` L113–127 (sha256 `2c15d177…`, the same file in the current and fresh environments): with more than 50,000 cells, `solver=None` selects `sag`, and `LogisticRegression` receives no `random_state` unless it is passed through kwargs. Both arms exceed 50,000 reference cells (63,767 and 58,245).
- The engineering finding says `run_matched.py` does not call `numpy.random.seed`, and that `PYTHONHASHSEED=0` is not an estimator seed.

For comparison, the other methods are seeded:
- M4 passes `random_state=0` (methods.py L133);
- M2/M3 PCA passes `random_state=0` (L71);
- M6 sets `scvi.settings.seed = 0` (L190, L209).

### E5. Some per-class sub-problems hit the iteration cap

The `n_iter_` ranges are:
- A: original 371–500, fresh 391–500;
- B: original 369–500, fresh 331–500.

Up to 47 iterations differ between fits. So in every fit at least one one-vs-rest sub-problem reached `max_iter=500` before meeting `tol`. The fitted coefficients are therefore partly a stopping point along a random-order SAG path, not a converged optimum. That is consistent with the coefficient differences being larger than round-off.

## What is not established

- **N1. The causal share of the unseeded solver is not proven.**
  - E3–E5 make `random_state=None` with SAG the leading and sufficient candidate explanation. It is a concrete implementation gap, directly observed.
  - However, no fit was run with a fixed seed, so it is not shown that seeding alone gives agreement within T2.
  - Other contributors are not excluded:
    - unrecorded process runtime state;
    - BLAS or threading effects under `n_jobs=4`;
    - any difference between the historical Arm A environment and the fresh one.
  - Only a seed-controlled pair of fits can test this (see the proposal).
- **N2. Version and runtime provenance of the original fits is incomplete.**
  - The diagnostic records `historical: null` for `uv.lock`, `pyproject.toml`, `configs/full.json` and `data/manifest.json`.
  - The original Arm A M5 fit came from the historical run `T01-matched-armA-20261006T092352Z`, in a different workspace (`…/rewire.it/workbench/…`). Its process environment and NumPy RNG state were not recorded (diagnostic `limits[1]`).
  - Original library versions (celltypist 1.7.1, scikit-learn 1.5.2, numpy 1.26.4, scipy 1.13.1, joblib 1.6.0) are supported by the preserved lock files and serialized metadata. They are not supported by a per-process environment dump.
  - So a version or runtime difference for the original Arm A fit cannot be ruled out. It also cannot be fixed after the fact. A corrected design should make both the canonical and the reproduction fits in the same pinned and recorded environment, and must not depend on the historical environment.
- **N3. Fresh fit outputs were reused, not newly trained, in 78542e9d.** The M5 fits were computed in parent `727c2514a006421286527ce1d2f22148` and carried forward under hash-bound inventories. The `generation-receipt.json` steps `A_M5_fit` and `B_M5_fit` have `provenance: reused-completed-fresh-step` and `wall_seconds 0.0`. This does not weaken the finding. The models are hash-identified, and their predict receipts match. It does mean that "fresh" refers to the 727 lineage fits.
- **N4. The historical source of `run_matched.py` differs.** The historical hash is `0894eb1a…` and the current/fresh hash is `adeca9d6…`. Per the diagnostic, the difference is M6 checkpoint relocation and hash logging only, and the M5 path is unchanged. I did not diff the historical file, so I rely on the diagnostic for this.

## Findings

### Blocking

- **B1. Clean-reproduction gate FAIL.**
  - Evidence: reproduction `78542e9d…`, report `2a663866…`, compare returncode 1, 54 gated M5 breaches (E1).
  - Under protocol/resume-plan-reviewed §7, the outcome is "partially reproduced". This blocks the reproduction gate, the PDF and the blog gate (§9 items 2–3).
  - Not resolvable by tolerance changes, tier reassignment, dropping M5 or relabelling. All of these are prohibited ("No tolerance is widened, no tier is reassigned and no metric is dropped after any comparison is computed").
- **B2. The M5 implementation deviates from the protocol's training-seed rule, and the paper states the seed incorrectly.**
  - protocol.md §3 L60 says: "Seeds: 0 for model training". The M5 call supplies no seed, and the saved original estimators have `random_state=None` (E4).
  - paper/main.tex L129 says "The training seed is 0 for all methods". That is false for the recorded M5 fits.
  - These statements are also not true for M5 as historically fitted:
    - L89: method effects "under this … training seed";
    - L167 and L460: intervals "conditional on … a single training seed";
    - claim I01's limitation "one training seed".
  - Because M5 was unseeded, it had no fixed seed at all.
  - I find no entry for this in the inspected inputs. The protocol requires deviations to be logged in `evidence/protocol-deviations.md`. That file is not in my input set, so I cannot confirm whether it is logged.
  - The deviation must be logged and the paper corrected whatever repair is chosen.
- **B3. The T2 premise for M5 was wrong as implemented.**
  - The tiers place M5 labels and confidence in "T2 deterministic-up-to-BLAS".
  - With an unseeded SAG fit that stops at the iteration cap for some classes, M5 is not deterministic up to BLAS. The pre-specified gate could not reasonably have been met by this implementation.
  - The correct remedy is to make the implementation match the stated premise (seed 0, finding B2), not to move M5 to a looser tier. Moving the tier would be prohibited reclassification after seeing results.
- **B4. Historical M5 natural-unknown results are a single unseeded draw on 20 cells and are seed-fragile.**
  - Two draws on identical inputs gave A:M5 OP-cov natural-unknown acceptance of 6/20 and 3/20, and AUROC 0.803 and 0.826 (E1).
  - Paper L376 ("M5: 6 (most often predicted HSPC)") reports the first draw as the M5 count. The second draw equals M4's count (3).
  - The paper already restricts this section to counts with "no ranking or interval" (L369) and states that the 20 erythroid cells give no evidence about natural novel-type detection (L465). That disclosure is appropriate.
  - The specific M5 count, and any implicit M4–M5 contrast, is not a stable property of the method. If corrected results are adopted, this count must be versioned. In any case, the paper must say that it varied between unseeded fits.

### Non-blocking (must be disclosed, does not by itself block)

- **NB1. M5 closed-set and selective conclusions look stable across the two observed draws** (E2), including I01 / M07 / M08. Two draws are not a seed-variance estimate. The paper should say so and must not imply that seed variance was characterised.
- **NB2. Per-cell M5 labels on Parse, ScaleBio and PIP-seq changed for 1.2–3.0% of cells between draws.** The per-platform M5 values quoted in the paper (e.g. L399, Parse 0.434 and ScaleBio 0.548 closed-set accuracy) are single-draw descriptive values. The platform analysis is already descriptive and one-donor (protocol §7).
- **NB3. Hitting the iteration cap (E5) is a property of the specified method** ("defaults otherwise"). Raising `max_iter` or changing the solver would change the method and is **not** proposed. Seeding makes the fit repeatable, but the coefficients remain seed-dependent and not fully converged for some classes. This must be stated as a limitation.
- **NB4. Runtime is not toleranced.** The fresh and original M5 fit times are similar (A 749 s vs 776 s; B 537 s vs 562 s, from the `fit_info` `seconds_stage` fields). Nothing to flag.

## Implications for the historical results

- Run `29879296…` remains the preserved Mode R record. Its M5 outputs and models (A `a66a529f…`, B `832f53a3…`) must not be overwritten or deleted.
- Those outputs are, however, results from an **unseeded** fit. They cannot be regenerated bit-for-bit or within T2 by anyone, including us, because the RNG state was never recorded.
- Under the current implementation, M5 as reported therefore cannot meet the pre-specified reproducibility standard.
- Results for every other method are unaffected by this failure: no breach was recorded for M1–M4, M6, P1 or P2.
- A seeded correction would produce a new, versioned M5 result. Whether it becomes the primary M5 result in the paper is a protocol change that requires human approval (see the proposal). It cannot be decided here.

## Precise next action

1. The coordinator records this FAIL and keeps all failure artefacts: manifest `8d744a69…`, receipt `3e1160c1…`, comparison manifest `e2bac834…`, results `4c695aaf…`, report `2a663866…`.
2. The coordinator presents `evidence/reviews/m5-seed-repair-proposal.md` to the user for an explicit scientific and budget decision.
3. Until then:
   - no new fits, predictions, scoring or comparisons;
   - no paper build claiming reproduction;
   - no ledger or paper changes beyond logging the deviation (B2), which the owner of `evidence/protocol-deviations.md` must do.

## Inspected inputs

- `evidence/reviews/m5-failure-78542e9d…/`:
  - `comparison-failure-summary.json` (all 54 entries; confidence arrays only as summarised);
  - `engineering-diagnostic.json`;
  - `packet-index.json`;
  - `comparison-manifest.json`;
  - `reproduction-manifest.json`;
  - `generation-receipt.json` (step records via search; L1428–1497 and L2925–3055 read in full);
  - `original/` and `fresh/` `summary_test.csv`;
  - the A:M5 rows of both `paired_differences_vs_M4.csv` files.
- `protocol.md` §3–§8 (L50–100).
- `protocol/resume-plan-reviewed.md`.
- `protocol/tolerances-v2.json`.
- `protocol/reproduction-retry-plan.md`.
- `evidence/operational-approval.json`.
- `evidence/reviews/final-methods-r2.md`.
- `companion/src/celltransfer/methods.py` L120–179 (plus a search for seed and `random_state` usage).
- `companion/scripts/run_matched.py` (search).
- `scripts/continue_reproduction.py` L66–328.
- `scripts/reproduce.py` (search).
- `study.json`.
- `paper/main.tex` (search; L365–380 read in full).
- `evidence/claims.json` (search).

Not inspected:
- the inner `results.json`;
- the `thresholds_validation.csv` and `cell_counts.csv` files;
- the full private report.

No finding depends on them, apart from the absence of threshold or T1 breaches, which I take from the failure summary.

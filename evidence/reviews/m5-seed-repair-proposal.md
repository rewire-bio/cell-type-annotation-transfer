# Proposal: seed-controlled M5 repair after failed reproduction 78542e9d

**Status: PROPOSAL, NOT APPROVED.** This document does not authorise any fit, prediction, scoring, comparison, code edit, paper or ledger change, or budget extension. It contains no approval and must not be read as one. Only the user can approve it. The coordinator should record the user's decision in a new approval file bound to this file's sha256.

- **Basis:** `evidence/reviews/m5-reproduction-failure-review.md` (verdict FAIL; findings B1–B4).
- **Identifiers:**
  - reproduction `78542e9d412548edbfe42b38d452f7a8` (source `1e95aac`);
  - original run `29879296d87343898100c190308744a1`;
  - protocol hash `0f8cc011…98e4`;
  - tolerances `protocol/tolerances-v2.json` sha256 `c335e6a9…0edb`.
- **Date:** 2026-10-07.

## 1. Decision requested

**Option R (recommended): seed repair.** Make M5 training use seed 0, the seed the protocol already states for model training (`protocol.md` §3 L60). Then:
- produce **corrected, versioned** canonical M5 results;
- test them against an **independent seed-controlled reproduction** under the unchanged tolerances.

This is a **material change to the result of record for M5**. The resume plan says "Mode R remains the result of record", and the corrected M5 numbers would replace the historical M5 numbers as primary. So it needs explicit scientific approval, not only budget approval.

**Option H (no new compute):**
- keep the unseeded historical M5 as the result of record;
- log the deviation;
- correct the paper's seed statements;
- report the reproduction outcome as "partially reproduced (M5)".

Under resume-plan §9 the reproduction gate, PDF and blog then stay **blocked** until some later amendment. Option H is listed so that the choice is explicit.

**Not acceptable under any option** (each is prohibited after a comparison has been computed, or loses information):
- widening a tolerance;
- moving M5 to a diagnostic or looser tier, as for M6;
- dropping M5 or any metric;
- overwriting or deleting the original or failed outputs;
- describing the 78542e9d result as a successful reproduction.

The rest of this document specifies Option R.

## 2. The scientific change: exactly one

In `companion/src/celltransfer/methods.py` (current sha256 `914989c5…3cf14`), change only `CellTypistRetrained.fit` (L153–154) to pass `random_state=0` through to `celltypist.train`:

```python
self.model = celltypist.train(X, labels=adata.obs.target.to_numpy(), genes=np.array(self.genes),
                              check_expression=False, use_SGD=False, feature_selection=False, n_jobs=4,
                              random_state=0)
```

Why this route:
- The engineering diagnostic inspected celltypist `train.py` L113–127 (sha256 `2c15d177…`). It found that `LogisticRegression` receives `random_state` only through the kwargs passthrough. A pre-execution check (§5, V3) must confirm this by read-only inspection before any fit.

Everything else stays the same:
- solver selection: `sag`, chosen automatically for more than 50,000 cells;
- `max_iter=500`, `tol`, `C=1`, `n_jobs=4`;
- data, features, labels, classes and scaler;
- `annotate` without majority voting;
- the confidence definition, M4 comparator, operating points, metrics, bootstrap (1,000 replicates, seed 20261005), natural-unknown scope and tolerances-v2.

**Not changed, on purpose:**
- `max_iter` and the solver, even though some per-class SAG sub-problems stop at 500 iterations (review E5). Changing either would change the method. The cap is disclosed as a limitation instead.
- No global `numpy.random.seed`. The estimator-level seed is the smallest sufficient control, and it follows the M4 pattern (`random_state=0`, L133).

**What seeding does and does not do:** it is expected to make a fit repeatable. Whether it removes **all** run-to-run variation, for example from `n_jobs=4` one-vs-rest parallelism or BLAS, is **not established**. The design tests this directly, through the canonical-versus-reproduction comparison.

## 3. Versioning and preservation

- **Preserve unchanged:**
  - run `29879296…`, including the original M5 models (A `a66a529f…`, B `832f53a3…`);
  - the failed reproduction lineage `7860abd5…` → `108dfa6e…` → `727c2514…` → `78542e9d…`, with its manifests, receipts, fresh M5 models (A `8d2ba132…`, B `788647ee…`) and the private report `2a663866…`;
  - this review packet.
- Nothing is overwritten, moved or renamed.
- The corrected results get a **new run ID** and a version label, e.g. `m5-seed0-v2`, in every output path, manifest, receipt, `results.json` entry and paper macro source.
  - Corrected rows are labelled `M5 (seed 0, corrected v2)`.
  - The historical rows stay available as `M5 (unseeded, historical)`.
- Code: a new commit with the one-line change. Record the new `methods.py` sha256, plus a recorded diff showing that no other line changed.

## 4. Execution design: four M5 fits, two scoring stages

### Stage C: corrected canonical (new result of record for M5)

Run in the study workspace, under the pinned lock (`uv.lock` `05fa7e73…`, celltypist 1.7.1, scikit-learn 1.5.2, numpy 1.26.4, scipy 1.13.1, joblib 1.6.0). Record the environment and a per-process package list in the receipt.

1. `A_M5_fit`: seed 0, on the hash-verified D05 data (`reference_F.h5ad` `20c71221…`, `features_and_classes.json` `0472df1f…`).
2. `B_M5_fit`: seed 0, same data.
3. `A_M5_predict`, `B_M5_predict`.
4. `A_M5_cite`: Arm A M5 CITE predictions on the existing hash-verified eligible CITE build (eligibility sha256 `2135e734…`). The protein check uses Arm A M5.
5. `score`: the full `score_all.py --reps 1000 --natural-unknown-scope natural` over all methods.
   - M5 comes from steps 1–4.
   - M1–M4 and M6 come from **adopted** run-29879296 outputs (§6).
6. `protein`: on the corrected `armA_cite` set.
7. Write the corrected canonical `comparison_manifest.json`. This becomes the baseline manifest for Stage F′.

### Stage F′: independent seed-controlled reproduction

Run in a **separate clean checkout** at the corrected commit, in separate processes, with **no copy of any Stage C M5 artefact**.

1. Environment: `uv sync --frozen`, or a hash-validated venv copy as in the prior lineage. Record which.
2. `A_M5_fit` and `B_M5_fit` with seed 0, then their predict steps, then `A_M5_cite`.
3. M1–M4 and M6 fit and predict outputs **adopted** from the fresh lineage (`727c2514…` / `78542e9d…`). These already passed every gated check against run 29879296. CITE build and data come from the same lineage, hash-bound.
4. Full `score` and `protein`.
5. `compare_runs.py`: corrected canonical manifest vs F′ manifest, with `protocol/tolerances-v2.json` unchanged (sha256 `c335e6a9…`). It must exit 0.
6. Paper assets and PDF, only after step 5 passes.

**Totals:** four M5 fit invocations (two canonical, two reproduction) and two full score/bootstrap stages.

### Diagnostics only (read-only, non-gated, after F′ compare)

- Coefficient, intercept and `n_iter_` hash equality between the Stage C and F′ M5 models, as in the existing engineering diagnostic.
- A descriptive table of historical-unseeded vs corrected-seeded M5 summary metrics, computed from existing outputs and labelled descriptive. It is not a gate and not a seed-variance estimate.

## 5. Pre-execution validation (no compute; all must pass before any fit)

- **V1. Approval binding.** A user approval record names:
  - this file's sha256;
  - the protocol hash;
  - parent run and reproduction IDs;
  - Option R;
  - 4 fit invocations;
  - the ceilings in §7;
  - the worker-call cap of 24.

  The driver refuses to start if any of these differs. This mirrors the existing checks in `scripts/continue_reproduction.py` L78–91.
- **V2. Source diff.** The diff between source `1e95aac` and the corrected commit touches only `methods.py` `CellTypistRetrained.fit` (one argument), plus the driver and approval files. `run_matched.py` (`adeca9d6…`), `build_data.py` (`a3d267e8…`), `score_all.py`, `compare_runs.py`, `uv.lock`, `configs/full.json`, `data/manifest.json` and `tolerances-v2.json` are unchanged, by hash.
- **V3. Seed passthrough.** Read-only inspection of the installed celltypist `train.py` (sha256 `2c15d177…`) confirms that `random_state` in kwargs reaches `LogisticRegression`.
- **V4. Selective adoption** (§6). All checks pass. These include unit tests of the driver change against synthetic fixtures. The tests do not run the real fits.
- **V5. Resources.**
  - At least 4 GiB free for M5 fits; existing guards and watchdog unchanged.
  - Measured `du` of the study prefix leaves room for the new outputs within the 7 GiB cap.
  - If not, stop. Do not delete preserved evidence to make room.

## 6. Selective adoption: what must be validated

Adopting completed non-M5 outputs is scientifically justified because:
- their code path, inputs and environment are unchanged;
- in the fresh lineage they passed the full tiered comparison;
- re-fitting M6 would add stochastic CPU-training noise that is irrelevant to this repair.

It is justified **only** if the following hold:

1. **Hash-bound inventory.** Every adopted file has a recorded sha256, verified both before and after copying or symlinking. This covers:
   - each adopted fit and predict directory (both arms, M1–M4 and M6);
   - the M6 checkpoint sidecars;
   - the data build and CITE build;
   - the A M1–M4 and M6 CITE predictions;
   - pinned third-party inputs.

   No unlisted file and no link traversal is allowed (the same rules as `validate_inventory`). For Stage C the sources are run 29879296 and its historical Arm A T01 and adopted Arm B fits. For F′ the sources are the `727c2514…` / `78542e9d…` lineage.
2. **No M5 artefact is adopted** in either stage. The inventory must exclude every `*_M5_*` directory, the old score, protein and compare outputs, and any old `arms/` symlink to M5.
3. **Code identity for adopted steps.** The recorded command identity is unchanged. V2 shows that the only source change cannot affect M1–M4 or M6. The historical `run_matched.py` difference (`0894eb1a…` vs `adeca9d6…`, M6 checkpoint logging only) is already disclosed and stays disclosed.
4. **Scoring consumes the adopted outputs only as predictions.** Engineering must confirm by inspection that `score_all.py` and `protein_check.py` read the per-method prediction files from the `arms/` method directories, which are named `M1`…`M6` (OA-9). The adopted M1–M4 and M6 entries must resolve to the hash-verified directories, and M5 to the new outputs. *I did not inspect `score_all.py` for this proposal.*
5. **Non-M5 equality check after scoring.** In each stage, every non-M5 row of `summary_test.csv`, `thresholds_validation.csv` and the `cell_counts.csv` and bootstrap-weights T1 items must equal the corresponding source run's values, apart from paired-difference rows that involve M5. Any difference is a stop: it would mean the adoption or the scoring was not as specified.

**Harness support is not assumed.** I inspected `scripts/continue_reproduction.py` (L66–328). In its current form it:
- replays only a **completed prefix**, in strict step order (cursor L269–295, `Completed prefix mismatch`);
- allows only `B_M6_fit` or `cite_build` as the retry step (L103–115);
- refuses any other fit (`Unapproved extra fit retry`, L325–326);
- requires approval files specific to earlier continuations (`disk-continuation-approval.json`, `cite-preflight-retry-approval.json`).

`A_M5_fit` sits in the middle of the step order, followed by A M6 and all of Arm B. So the current driver **cannot** do this non-prefix, M5-only re-execution. A new or extended driver mode is required, for example an explicit `rerun_steps = {A_M5_fit, A_M5_predict, B_M5_fit, B_M5_predict, A_M5_cite, score, protein, compare}` list with every other step adopted. That mode must:
- carry its own approval binding (V1);
- pass tests;
- be reviewed before use.

That engineering work is outside my outputs. If it cannot be validated, the fallback is a full re-fit of every method. That exceeds the four-fit design and would need a separate approval.

## 7. Resources and ceilings

These are **ceilings from the existing step limits, not timing estimates**. They are unchanged: 4 threads, 12 GiB process-group memory watchdog, 7 GiB study storage cap, local compute only.

| Step | Per-step ceiling (s) | Stage C | Stage F′ |
|---|---|---|---|
| env (reproduction checkout) | 1,800 | – | 1,800 |
| M5 fit × 2 | 4,800 each | 9,600 | 9,600 |
| M5 predict × 2 | 1,200 each | 2,400 | 2,400 |
| A_M5_cite | 1,800 | 1,800 | 1,800 |
| score | 7,200 | 7,200 | 7,200 |
| protein | 900 | 900 | 900 |
| compare | 1,200 | – | 1,200 |
| paper (assets + build) | 1,800 (`paper_seconds`) | – | 1,800 |
| **Stage sum** | | **21,900** | **26,700** |

- **Worst-case total:** 48,600 s. Proposed **hard total ceiling: 54,000 s**, the existing `reproduction_seconds` for this repair cycle, covering both stages. That includes hash validation and copy overhead (the prior lineage's copy validation took 77 s).
- **For reference only, not a projection** (observed earlier durations):

  | Step | Observed (s) |
  |---|---|
  | M5 fit A | 776 / 749 |
  | M5 fit B | 562 / 537 |
  | score | 611 |
  | A_M5_cite | 11 |
  | protein | 6 |
  | compare | 11 |

- **Ledger choice for the approver.** The 78542e9d manifest records 7,085 s used of the original 54,000 s ledger, with 47,847 s remaining. The worst case of 48,600 s exceeds that remainder. The approver must therefore choose one of these, and the record must state which:
  - **(a)** a new 54,000 s ledger for this repair cycle; or
  - **(b)** the remaining 47,847 s, with Stage F′ paper steps moved to a separate H-paper budget (30 min / 1 GiB, per resume plan §6).
- **Attempts.** Each M5 fit runs **once**. The existing `max_attempts: 2` permits a retry only for an infrastructure status (memory-stop, disk-start, guard). If one is used, it must be reported as a fifth fit invocation and charged to the same ceiling. A non-infrastructure fit failure is a stop.

## 8. Stopping conditions (stop, preserve everything, return blocked)

1. Any V1–V5 or §6 validation fails.
2. A fitted M5 model does not record `random_state=0` and `solver=sag` (checked read-only after each fit), or its scaler, genes or classes differ from the historical ones (`mean_` A `1ee5179d…`, B `fbf36d22…`).
3. Any non-infrastructure step failure, or a second infrastructure failure of the same step.
4. Any stage or total ceiling reached, or the storage cap, memory watchdog or disk guard triggered twice.
5. The non-M5 equality check (§6 item 5) fails in either stage.
6. **The F′ comparison does not exit 0, for any reason**, including any T1, T2, M-tier or S breach.

   Then: no additional seeds, no extra fits, no `max_iter` or solver change, no tolerance or tier change. Report "seed control did not achieve T2 reproducibility". Name any residual sources (e.g. `n_jobs` one-vs-rest parallelism or BLAS) only as unverified candidates, and return to the user.
7. Any instruction to overwrite or delete preserved outputs.

## 9. Claims, paper and ledger updates (only after the F′ compare passes, except item 1)

1. **Needed under either option. These come from findings already established, not from new results.**
   - Log the M5 seed deviation in `evidence/protocol-deviations.md`: protocol §3 says seed 0, but the implementation passed no seed and the estimators had `random_state=None`.
   - Correct paper L129 ("training seed is 0 for all methods"), and the seed wording at L89, L167 and L460, plus the claim I01 limitation, for the historical M5.
2. **Claims ledger (`evidence/claims.json`):**
   - Do not delete or edit historical entries in place. Mark M5-dependent entries (M07, M08, and any interpretation using them, such as I01) as `superseded_by` new IDs.
   - The new IDs point to the corrected run ID and corrected `result_pointer`s, with the version label.
   - Add a measured finding for the 78542e9d failure: 54 M5 breaches; per-file label and confidence numbers by identifier; the report sha256.
   - Add an interpretation: "M5 historical fit was unseeded; two unseeded draws differed beyond T2; corrected results are seed 0". It should state the limitation that the cause was not isolated beyond the seed.
3. **Paper:**
   - Corrected M5 numbers from generated macros only.
   - A versioning note.
   - A reproducibility section that states, in order:
     - the historical-vs-fresh failure (78542e9d, "partially reproduced", 54 M5 breaches);
     - the cause addressed (unseeded SAG) and what remains unproven;
     - the corrected canonical-vs-reproduction outcome, worded exactly as `compare_runs.py` reports it.
4. **Limitations to add:**
   - M5 coefficients depend on the seed and some per-class fits stop at `max_iter=500`.
   - Seed variance is not characterised: two unseeded draws are not a variance estimate.
   - Natural-unknown M5 counts on 20 erythroid cells changed from 6 to 3 between unseeded draws, so any M4–M5 natural-unknown contrast is not interpretable.
   - Per-platform M5 values on Parse, ScaleBio and PIP-seq are single-draw descriptive values.
5. **Not permitted:** stating that the historical M5 result was reproduced, or presenting the corrected results without the version label and the historical failure.

## 10. Worker calls

The current cap is 22 (`evidence/operational-approval.json`). One call remains after this review. Requested: a **bounded extension to 24** (two more), each at most 900 s, giving three calls after this review:

| Call | Purpose |
|---|---|
| 22 | Corrected paper and claims-ledger authorship (§9), after the F′ compare passes. |
| 23 | Final methods and PDF review of the regenerated paper. |
| 24 | One repair reserve, used only to fix text found deficient in call 23. Not for new analyses. |

The code change, driver mode and tests (§2, §6) are assumed to be coordinator engineering work. If any of that must be done by a worker call, it uses the reserve. Any further deficiency is then a stop that needs a new approval.

## 11. Approval required (not given here)

The user must explicitly approve, in a record the coordinator writes:
- **(i)** Option R as a scientific correction of the M5 result of record, with versioning, or Option H;
- **(ii)** the single code change in §2;
- **(iii)** the selective-adoption design and the new driver mode, after engineering review;
- **(iv)** four M5 fit invocations and two score stages, under the §7 ceilings and ledger choice (a) or (b);
- **(v)** the worker-call extension to 24;
- **(vi)** the stopping conditions in §8.

No step in §4 may start before that record exists and V1–V5 pass.

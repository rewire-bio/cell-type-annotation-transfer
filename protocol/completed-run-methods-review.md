# Methods review of completed recorded run `29879296d87343898100c190308744a1` (before paper writing)

- **Reviewer role:** methods-reviewer worker. Snapshot `5befceda37568dd0f9be53770284a86835f1de2d`, 2026-10-06.
- **Nature of this document:** a reading of frozen evidence and code. It does **not** verify, approve or reproduce anything. No experiments, rescoring, input edits or approvals were made.
- **Verification status:** the run is a **recorded Mode R recovery** (`comparison_manifest.json`: `"fresh_execution": false`). Independent clean reproduction (Mode F) has **not** been done. Nothing here should be read as "verify passed".

## 0. What was inspected and what could not be checked

**Read in full:**
- `protocol.md`
- `protocol/amendments/protein-replacement-reviewed.md` and its approval record `2026-10-06-approved-protein-replacement.md`
- `2026-10-06-approved-resumption.md` (D-1a)
- in `evidence/results-29879296/`: `results.json`, `provenance.json`, `comparison_manifest.json`, `cite-eligibility.json`, `cite-receipt.json`, `protein/{protein_agreement.csv,gates.json}`
- in `evidence/results-29879296/score/`: `summary_test.csv`, `thresholds_validation.csv`, `per_study_test.csv`, `per_class_test.csv`, `unknowns_test.csv`, `unknowns_allstrata_secondary.csv`, `bootstrap_nan_counts.csv`, `calibration_test.csv`, `platform.csv`
- `companion/scripts/score_all.py`, `companion/src/celltransfer/evaluate.py`, `companion/scripts/protein_check.py`

**Not checked**, because this worker has no shell:
- whether the current scripts' sha256 match `provenance.json` (`score_all.py` `20f45720…`, `evaluate.py` `e5fae4e8…`, `protein_check.py` `94584094…`);
- per-donor cell counts. `bootstrap_ids.csv` is not in the evidence bundle;
- the label maps, `ontology.py` and the historical runs.

The coordinator should hash-check the three scripts before the paper cites them as "the code that produced these numbers".

Numerical cross-checks below were done by hand from the tables. For example:
- P2 `max_coverage` 0.84709 = 1 − `coarser_fraction` 0.15291;
- the M5 − M4 coverage difference, 0.7983 − 0.8165 = −0.018, matches `mean_diff` −0.0179;
- validation n = 13,163 = (6,914 + 2,177 + 3,997 + 185 mapped) − 110 not in K.

---

## 1. Bottom line

The run looks internally consistent:
- 32 test donors;
- 19,018 scorable natural test cells in Arm A and 18,628 in Arm B;
- 1,000 donor-bootstrap replicates;
- every matched method has `max_coverage` = 1.0, so no matched predictions are missing;
- eligibility was recorded before the protein outputs.

No arithmetic or pipeline error was found that invalidates the headline matched-track numbers.

There are, however, **five interpretation-level blocking findings (B1–B5)**. If the paper were written directly from the tables, each would produce a false statement. They need text-level handling, not new experiments. Two of them (B3, B4) also involve implementation behaviour that the paper must describe rather than hide.

---

## 2. Blocking findings (must be handled in the text before any claim is written)

### B1. Natural unknowns in Arm A are 20 erythroid cells. For P1/P2 these are mostly *correct* predictions, not false acceptances.

**Evidence:**
- `unknowns_test.csv`: every Arm A/practical natural unknown is class `erythroid`, n = 20.
- Practical-track top predictions on those cells:
  - P1: `{"erythroid": 0.8, …}`
  - P2: `{"erythroid": 0.9, "platelet/MK": 0.1}`
- `score_all.py` defines unknowns as mapped cells with `target ∉ K` (Arm A K) for **both** the matched and practical tracks. The released models have `erythroid` in their label space.

**Consequences:**
- The following do **not** measure open-set failure for P1/P2. Mostly they measure correct erythroid calls:
  - P2 `unknown_false_accept@OPcov` = 1.0 [CI 1.0, 1.0]
  - P1 = 0.70
  - paired P2 − M4 = +0.641 [0.0, 0.895]
  - P1 − M4 = +0.170 [−1.0, 0.632]
- Practical-track natural-unknown rows must be **excluded from any comparison** or reported only with this explanation. A rescoring that counts erythroid as correct for P1/P2 would be a new analysis needing approval. It is not authorised here.
- Even for matched methods, "natural unknown" means **one class (erythroid) from very few donors**:
  - 126/1,000 bootstrap replicates contain no unknown cell (`bootstrap_nan_counts.csv`). By inference, this fits roughly two donors in one 12-donor study, e.g. (10/12)^12 ≈ 0.11. The per-donor counts were not inspected.
  - The intervals are degenerate: M4 0.15 [0.105, 1.0], M3 0.55 [0.0, 0.579], paired M3 − M4 [−1.0, 0.474].
  - These intervals are computed only over the 874 replicates that contain unknowns (`np.nanpercentile`).
- **Allowed:** "On 20 natural-stratum erythroid cells (a single absent class, few donors), M4 accepted 3/20 and M1 17/20 at OP-cov; no reliable interval."
- **Not allowed:** any claim about natural novel-type detection in general, any method ranking on it, or any interval quoted as uncertainty.
- The all-strata sensitivity analysis (126 cells, `unknowns_allstrata_secondary.csv`) is still only erythroid. It is a point estimate only.

### B2. AURC and risk@ are not comparable across methods whose maximum coverage is below 1, and OP-cov for P2 is "accept every fine-level prediction"

**AURC truncation:**
- `evaluate.aurc` returns `mean(risk) × final coverage`, so the area stops at `max_coverage`.
- P2 `max_coverage` = 0.847 because 15.3% of its predictions are `coarser`. Its AURC of 0.0488 therefore covers only coverage ≤ 0.847, while M4 (0.0474) and M6 (0.0495) cover up to 1.0.
- "P2 AURC is comparable to M4/M6" would be a false statement.
- P1 (`max_coverage` 0.998) is nearly but not exactly comparable.

**Risk@ coverage:**
- For P2, risk@0.90, @0.95 and @1.00 are null because those coverages cannot be reached. This is "not reachable", not missing data.
- Use risk@0.80 for cross-track comparison:

| Method | risk@0.80 |
|---|---|
| M4 | 0.083 |
| M6 | 0.085 |
| M5 | 0.090 |
| M3 | 0.104 |
| P1 | 0.117 |
| P2 | 0.137 |
| M2 | 0.174 |
| M1 | 0.370 |

- These have no interval. For M3, see B3.

**P2 OP-cov is not a threshold:**
- P2's validation eligible cap is 0.798, below 0.90. By protocol §5, τ_cov = −∞ ("accept all fine-level predictions and report the shortfall").
- So P2 coverage@OPcov 0.847 and accepted error 0.159 describe P2 **with no abstention**. The paired P2 − M4 coverage difference (+0.031) compares an un-thresholded model with a thresholded one.

**Unassigned fraction:**
- Unassigned = 1 − coverage, and for P2 it includes the 15.3% `coarser` cells.
- Do not call this "abstention" for P2. Report it as "coarser-than-target labels (15.3%) plus nothing abstained".

### B3. M3 (kNN vote share) has heavily tied confidences. Its OP-cov is not a 90% operating point, and its risk-coverage numbers depend on row order.

**OP-cov:**
- M3 confidence takes only 16 values (k/15).
- `threshold_coverage` accepts `conf ≥ τ`, so whole tie blocks are accepted. Validation coverage at τ_cov is **0.943** (Arm A) and **0.924** (Arm B), not 0.900 (`thresholds_validation.csv`).
- Test coverage is 0.886 for M3 against 0.817 for M4. The paired M3 − M4 accepted-error difference (+0.036 [0.028, 0.044]) therefore compares different coverages and is not like-for-like.
- State this in the text.

**Risk-coverage curve:**
- `evaluate.risk_coverage` sorts with a stable argsort and does **not** average within tie blocks. Inside a tie block the order is the input row order, i.e. concatenated query-file/study order.
- So M3's AURC (0.0654) and risk@c values contain an arbitrary study-order component.
- This also applies to any method with exact float ties, e.g. saturated probabilities at 1.0. This was not checked.
- Do not rank M3 on AURC or risk@. Correcting it (tie-averaged risk) would mean rescoring a primary metric. That is a protocol-level change needing human approval, not something to do silently.

**OP-err:**
- OP-err is **not attainable** for M3 and M6 in both arms (`tau_err` null; 1,000/1,000 NaN bootstrap replicates).
- Report "not attainable", which is the protocol wording. Do not report "—", missing, 0 or 1.

### B4. Protein agreement compares fine RNA labels with six coarse protein classes by exact string match

**What the code does:**
- `protein_check.py` sets `agree = in_gate & (pt == cls)`.
- RNA predictions come from the 14-class K: ASC, B, CD14 mono, CD16 mono, CD4 T, CD8 T, HSPC, ILC, MAIT, NK, cDC, gamma-delta T, pDC, platelet/MK.
- Protein classes come from only six gates: CD4 T, CD8 T, B, NK, CD14 mono, CD16 mono.
- There is **no crosswalk**. For example:
  - a MAIT RNA call on a protein CD8 T cell counts as disagreement;
  - an ILC call on a protein NK cell counts as disagreement;
  - gamma-delta T cells (mostly CD4−CD8−) are usually unresolved.

**Consequences:**
- **`agreement_accepted`** mixes true disagreement with granularity mismatch. It penalises methods that emit more non-gateable fine labels.
  - Example: M1 on 5k gives 0.636 overall but 0.938 on gateable predictions.
- **`agreement_accepted_gateable_preds`** conditions on the *RNA prediction* being one of the six gate names. That is selection on the output: a method that sends hard cells to non-gateable labels is not penalised for it.
- Neither is an accuracy. Report both side by side, with this explanation.
- Denominators differ by method (`n_accepted_resolved`):
  - 10k: 5,027 (P2) to 6,331 (P1);
  - 5k: 3,306 (M1) to 3,726 (P1).
- So the methods are scored on different cell subsets. **No method ranking** may be drawn. The amendment also forbids matched-track comparison on these files (§1, §4.5).

**Inputs and denominators:**
- Thresholds are Arm A / practical validation τ_cov from Census data, applied to author-filtered totalVI data.
- P2 again uses −∞ (accept all). In `results.json` its `tau_cov` is serialised as `null`, while the CSV shows `-inf`; see §5.
- Resolved fraction:
  - 10k: 6,375/6,855 = 93.0%;
  - 5k: 3,762/3,994 = 94.2%.
- CD16 mono protein class: 46 cells (10k) and 43 (5k). Too small to interpret per class.
- The CLR row mean uses 14 antibodies (10k) against 29 (5k), and isotype controls were removed upstream. CLR scales, and therefore GMM gates, are not comparable between files.

**Status:**
- **Descriptive, exploratory, secondary.** Label it exactly `descriptive; replacement inputs (amendment 2026-10-06-approved-protein-replacement)`.
- Per file only: no pooling, no interval.
- Upstream author filtering (doublets, mitochondrial cap <0.10 in 10k against <0.20 in 5k, hand-chosen ADT library-size window, isotype removal, gene filter) may raise agreement.
- Donor identity and training overlap are **unknown**.
- Gene coverage:
  - G present: 12,933/19,331 = 66.9% (10k) and 12,822/19,331 = 66.3% (5k);
  - F_A present: 1,598/2,020 = 79.1% and 1,560/2,020 = 77.2%;
  - F_B present: 1,597/2,016 = 79.2% and 1,568/2,016 = 77.8%;
  - missing genes were zero-filled, which is not neutral after z-scoring;
  - P1 received all symbols unmapped.
- The 5k file is `5k_pbmc_protein_v3`, **not** the pre-specified `_nextgem`.
- Planned files 3–4 have no replacement. Files 2–4 were **never requested**.
- Both h5ad files were used from **cached bytes** (`cite-receipt.json`: `"source": "cached"`, `url: null`, sha256 matches the pins). This is permitted by the amendment's cached-bytes clause, but say so.
- All §11 amendment disclosures apply verbatim.

### B5. The intervals are donor-within-study intervals for four fixed studies. They are not study-level uncertainty, and pooled values are cell-weighted.

**How the intervals are built:**
- `donor_bootstrap_weights` resamples donors with replacement **within each of the 4 test studies**. Study membership is fixed.
- Pooled metrics weight studies by natural cell count: HIHA 7,042, RA 7,200, JDM 3,000 and Glaucoma 1,776 Arm A scorable cells. HIHA and RA make up 75%.
- Study heterogeneity is far larger than the intervals. For M4 at OP-cov:

| Study | Accepted error | Coverage | Macro-F1 |
|---|---|---|---|
| HIHA | 0.021 | 0.940 | 0.942 |
| JDM | 0.056 | 0.906 | 0.886 |
| Glaucoma | 0.144 | 0.847 | 0.707 |
| RA | 0.179 | 0.651 | 0.518 |

- Compare the pooled M4 accepted error of 0.087 [0.078, 0.096].
- Glaucoma has about 3 donors and JDM about 5, inferred from 600 natural cells per donor. Within-study resampling of 3 donors is very coarse.

**What the intervals do not include:**
- Thresholds are fixed, from two validation studies. The bootstrap does not re-estimate τ, so threshold uncertainty is absent.
- Single training seed (0). No training-seed variance is included, which matters most for M6 (see M2 below).

**Wording:**
- Every interval must be described as "95% donor-bootstrap percentile interval within the four test studies (1,000 replicates), conditional on fixed validation thresholds and a single training seed".
- Never call these intervals generalisation to new studies.
- Show per-study values beside every pooled number. The protocol already says "with four test studies there is no study-level interval".

---

## 3. Major issues (not blocking if disclosed as stated)

### M1. Author labels are the reference standard, with possible circularity for HIHA and platform labels

- Coordinator concern: HIHA and platform-collection labels may have been produced by reference-based annotation. In that case, agreement partly measures similarity to the labelling pipeline.
- **Not verified here.** No label-provenance file for these datasets was in the inputs. `literature/research.md` records only that the CH validation study was annotated with ScType plus manual curation.
- **Directional evidence consistent with the concern (not proof):**
  - HIHA is the easiest study for every method (M4 macro-F1 0.942, accepted error 0.021).
  - RA is the hardest (0.518, 0.179).
- **Disclosure:** "Accuracy is agreement with author labels mapped to the Cell Ontology; no adjudication. If author labels were themselves derived by reference mapping, agreement is inflated for methods resembling that pipeline. We did not verify label provenance for HIHA or the platform collection."
- Give no reason for RA's poor results beyond "lower agreement with RA author labels". Granularity or definitional mismatch is plausible but untested.

### M2. Arm B M6 changes sharply relative to Arm A M6. This must not be attributed to class removal.

**What changed:**

| Metric | Arm A M6 | Arm B M6 |
|---|---|---|
| Known-class accepted error @OPcov | 0.115 | 0.211 |
| Cross-lineage rate | 0.063 | 0.160 |
| RA accepted error | 0.220 | 0.516 |
| CD4 T closed-set recall | 0.922 | 0.614 |
| CD8 T closed-set recall | 0.731 | 0.572 |
| ECE | 0.134 | 0.249 |
| Brier | 0.299 | 0.530 |

- Arm B M6 predicts HSPC and ILC with natural-stratum precision of about 0.003.

**Why it cannot be attributed:**
- Arm A M6 is the cached historical T01 fit.
- Arm B M6 was fitted in recovery run `6ef42791…` and adopted.
- There is one seed, and both the reference training and the 50-epoch unlabelled query adaptation are stochastic.
- Seed or optimisation variance cannot be separated from the effect of removing pDC/ASC/MAIT.

**Wording:** "Arm B M6 performed markedly worse on known classes than Arm A M6; with a single training seed per arm we cannot attribute this to the class removal."

Paired B:M6 − B:M4 differences are valid within Arm B but inherit this caveat.

### M3. Arm B simulated unknowns cover three specific, near-neighbour classes and are mostly top-up cells

**Composition:**
- ASC 815, MAIT 748, pDC 747; 2,310 cells in total.
- Only 390 of these are natural-stratum cells: 19,018 − 18,628 scorable natural cells. About 83% come from the rare top-up stratum. Pooled false-acceptance therefore weights the three classes by sampling design (≈1/3 each), not by natural prevalence.

**Errors are mostly within-lineage near neighbours:**
- ASC → B (M4 0.899)
- MAIT → gamma-delta T / CD8 T (M4 0.639 / 0.277)
- pDC → cDC (M4 0.712)
- M6 is the exception for pDC: pDC → HSPC 0.959.

**Valid statement:**
- Confidence thresholds at OP-cov accepted most cells of these three removed types. False acceptance @OPcov:

| Method | False acceptance [95% CI] |
|---|---|
| M4 | 0.659 [0.632, 0.687] |
| M1 | 0.734 |
| M2 | 0.804 |
| M5 | 0.834 |
| M6 | 0.890 |
| M3 | 0.892 |

- Known-vs-unknown AUROC: M4 0.650, M1 0.643, M2 0.574, M6 0.496, M3 0.468, M5 0.443. Three methods are below 0.5, meaning their confidence is higher on the removed types than on known cells.

**Limits:**
- Do not generalise to "novel cell types". Distant or truly novel types were not tested.
- Arm B macro-F1 (8 classes) is **not comparable** to Arm A macro-F1 (11 classes). "Removing classes improved F1", e.g. M4 0.758 against 0.694, is false: the removed classes were among the hardest (ASC closed-set recall about 0.35).

### M4. Operating points are fixed on validation, and validation includes the rare top-up stratum

**How τ was set:**
- Protocol §5 sets τ on validation cells that are "mapped and in K". The code includes **both strata**: 13,163 Arm A validation cells, of which 2,362 are top-up minus non-K.
- So OP-cov is 90% of a rare-class-enriched validation mix from two studies.

**Transfer to test:**
- Test coverage at OP-cov ranges from 0.775 to 0.886, never 0.90.
- Validation error at τ exceeds test error, e.g. M4 0.145 against 0.087.
- Describe OP-cov as "the threshold that accepted 90% of validation cells", not "90% coverage".

**OP-err does not transfer reliably:**

| Method | Test accepted error at OP-err (target ≤ 0.05) | Test coverage |
|---|---|---|
| M1 | 0.164 [0.109, 0.227] | 0.191 |
| M2 | 0.032 | 0.416 |
| P1 | 0.034 | 0.372 |
| M5 | 0.010 | 0.065 |
| M4 | 0.000 (point and interval) | 0.044 |
| P2 | 0.043 [0.0, 0.104] | 0.0025 (≈ 47 cells) |

- M4's τ_err (0.99998) and P2's (0.99992) sit at the probability ceiling. Their OP-err results are near-degenerate.
- Per study: P2 accepts **no** RA cells at OP-err, so per-study accepted error there is undefined (NaN), not zero.
- The large M2 − M4 coverage@OPerr difference (+0.373 [0.339, 0.409]) is a real measured difference **at these fixed thresholds**. It reflects how each confidence score ranks validation errors. It is not evidence that a centroid classifier is "safer" in general.

**Validation reuse:**
- M4's C was also chosen on the same validation studies. This is a mild double use of validation. It does not affect test independence.

### M5. Practical track compared with matched track is not an architecture comparison

- P1/P2 differ from M-methods in training data, label set, gene space and label mapping.
- Some practical deficits are label-map artefacts, for example:
  - P1 gamma-delta T closed-set recall is 0.015 while P1 `coarser_fraction` is only 0.0016. So P1 assigns those cells to other mapped classes, most likely through how CellTypist labels map to `gamma-delta T`;
  - P2 has 15.3% `coarser` labels.
- **Allowed:** "As distributed and mapped by our frozen tables, P1 had lower closed-set macro-F1 than our matched M4 (paired difference −0.077 [−0.094, −0.060]); P2 was not distinguishable from M4 (−0.010 [−0.023, 0.003])."
- **Forbidden:** "CellTypist's architecture is worse than logistic regression".
- The matched track also does not support architecture causality beyond "under this reference, features, defaults and seed".
  - The four learned methods M3–M6 are indistinguishable on closed-set macro-F1. Paired differences against M4 all include 0: M3 −0.002, M5 −0.006, M6 −0.002.
  - "M4 is best" is not supported on macro-F1. At OP-cov, M4 and M5 have the lowest accepted error, but at lower coverage than M3 and M6.

### M6. Calibration semantics

- The protocol lists calibration for M4, M5, M6, P1 and P2, and labels M1–M3 uncalibrated. `calibration_test.csv` also reports M3 (Brier 0.272, ECE 0.065) from vote shares. Label it "vote-share reliability, not a calibrated probability", or omit it.
- **P1:** CellTypist one-vs-rest sigmoids are **renormalised to sum to 1** for Brier (`calibration()` divides by the row sum), but ECE uses the raw max sigmoid `conf`. P1 Brier (0.303) and ECE (0.121) are therefore computed on different probability objects and are not comparable to M4/M5/M6.
- **P2:** coarser predictions count as incorrect at their stated confidence in ECE.
- Comparable within matched probabilistic methods: M4 ECE 0.027, M5 0.081, M6 0.134 (Arm A).

### M7. Platform results are one donor per platform, with unknown label provenance

- 1,000 cells per platform, about 891–971 scorable. Descriptive only.
- The striking collapses should be reported as observations:
  - P2 coverage on Parse is 0.194 (closed-set accuracy 0.130), and on ScaleBio 0.179 (0.110);
  - M5 closed-set accuracy is 0.434 on Parse and 0.548 on ScaleBio, against ≥0.94 for M2, M3 and M6.
- Do not give causal explanations such as chemistry or gene detection.
- Platform labels may share one annotation pipeline across platforms (see M1).

---

## 4. Minor issues

1. **Bootstrap macro-F1 with absent classes.** If a resample drops all natural cells of an F1 class, `f1_score(..., labels=classes, zero_division=0)` scores that class 0. This biases replicate macro-F1 downward. The effect is probably small (classes need ≥20 natural cells), but the intervals are slightly conservative and asymmetric.
2. **Unknown AUROC ignores eligibility.** `auroc_known_unknown` uses `conf` for every known and unknown cell, including P2 `coarser` predictions that can never be accepted. Practical-track AUROC (P1 0.624, P2 0.530) is therefore not on the same footing as acceptance rates. It is also affected by B1.
3. **Paired-difference intervals at the bounds.** Unknown-acceptance intervals of exactly [−1, …] or [0, 0] (e.g. A:M3, M5, M6 against M4; P2 OP-err [0.0, 0.104]) signal too few cells. Do not quote them.
4. **Runtime and peak memory (protocol §6).**
   - This run's `/usr/bin/time` records cover only the CITE build, CITE predict, score and protein steps.
   - Their scope is "direct child only; understates aggregate memory under n_jobs>1".
   - Arm A fit/predict timings live in the historical runs; Arm B M4–M6 timings come from recovery run `6ef42791…`. The bundle reviewed here has no per-method runtime table.
   - Runtime claims must cite those records. Each is a single timed run, and timings came from different sessions.
5. **Provenance path mismatch to check.**
   - `score` ran with `B=…/29879296…/recovery/armB`, while `comparison_manifest.json` lists Arm B as `compare_arms/B`.
   - The protein step used `A=…/recovery/armA_cite`, while scoring used historical `T01`.
   - Probably intentional assembly directories. The coordinator should confirm by hash that `recovery/armB` contains exactly the adopted B M4–M6 outputs and cached B M1–M3.
6. **Attempt history.** B_M4_fit is recorded as `"attempt": 2`, and the CITE build is attempt 2 (R4′, the last permitted). Both are within budget. Keep the earlier attempts' records; they are not failures of the science.
7. **Approval wording.** The approval record quotes the user as "Ok clean out some old checkouts and continue", given in reply to an explicit approval request. The reviewed amendment noted the user had not been shown the floors, attempt accounting or tolerance changes before the earlier "sounds great, continue". This reviewer does not judge approvals. The paper's disclosure should state the amendment date and sha256 `e5ba0c34…`, as §11 requires.

---

## 5. Semantics of null / NaN / −inf in the exported tables (for writers)

| Value where | Meaning | Write as |
|---|---|---|
| `tau_err` null; `coverage@OPerr`, `accepted_error@OPerr` null (M3, M6, both arms); 1,000/1,000 NaN replicates | No validation threshold reached ≤5% accepted error | "not attainable" |
| `tau_cov` = `-inf` in CSV, `null` in `results.json` (P2 thresholds and protein rows) | Validation cap 0.798 < 0.90, so all fine-level predictions are accepted (protocol §5 shortfall rule) | "no threshold (accepts all fine-level labels; validation cap 79.8%)". **Not** "not attainable" and not missing. The JSON null loses this distinction. |
| `risk@c` null (P1 at 1.00; P2 at ≥0.90) | Coverage c cannot be reached because of coarser labels | "not reachable (max coverage 0.998 / 0.847)" |
| `cross_lineage_share@OPerr` null with accepted error 0 (A:M4) | No accepted errors, so the share is undefined | "no errors (share undefined)" |
| Per-study `accepted_error@OPerr` blank (P2 RA) | Zero cells accepted | "no cells accepted" |
| `unknown_false_accept@OPcov` intervals in Arm A/practical | 126/1,000 replicates had no unknown cell and were dropped | do not quote |
| `brier`/`ece` blank (M1, M2) | Uncalibrated score by design | "uncalibrated score" |
| `cells` null in `summary_test` | Unused column for pooled rows | omit |

Denominators:
- coverage = accepted / all scorable natural test cells (mapped, in K);
- accepted error = wrong / accepted;
- cross-lineage share = cross-lineage errors / errors;
- cross-lineage rate = cross-lineage errors / accepted;
- unknown false acceptance = accepted unknowns / unknowns (Arm A: natural stratum only, per D-1a; Arm B: all strata);
- per-class recall uses natural + top-up cells, precision uses natural cells only.

---

## 6. Reproducibility status (stated separately from scientific validity)

**Provenance as recorded:**
- **Cached and hash-verified (267 files):** data build D05, Arm A M1–M6 fit and predict (historical T01), Arm B M1–M3.
- **Adopted from prior recovery run `6ef42791…`** (clean git rev `5a0b9aaa…`): Arm B M4–M6 fit and predict.
- **Recomputed in this run:** CITE build (R4′, cached input bytes), Arm A CITE predict for M1–M6, scoring, protein check.

**Outstanding:** independent clean reproduction (Mode F, 15 h budget) has **not** been performed. This is an **outstanding verification step, not a scientific failure**. Nothing in the evidence suggests the recorded numbers are wrong. Equally, nothing yet shows they reproduce from scratch, especially:
- the stochastic M6 fits (single seed, query adaptation);
- the Arm B M4–M6 fits made in a different session.

**Required wording:** "results from a recorded run with cached and adopted steps; independent clean reproduction pending". Never write "verified" or "reproduced".

---

## 7. Concise author guidance (claims tied to exact table values)

**Frame every number as:** Census LTS 2025-11-08; four held-out test studies; 32 donors; natural stratum; author labels as the reference standard; 95% donor-within-study bootstrap; fixed validation thresholds; single seed; recorded run, reproduction pending.

**Supported statements:**

1. **Closed-set accuracy (Arm A, 11 classes, natural).**
   - M4 0.694 [0.669, 0.716], M3 0.692, M6 0.692, M5 0.688. Paired differences against M4 all include 0.
   - M2 0.629 (−0.066 [−0.077, −0.053]); M1 0.497 (−0.197 [−0.213, −0.179]).
   - P2 0.684 (−0.010 [−0.023, 0.003]); P1 0.617 (−0.077 [−0.094, −0.060]).
   - Always add per-study values: M4 ranges from 0.518 (RA) to 0.942 (HIHA).
2. **At the validation OP-cov threshold.**
   - M4 accepted 81.7% [77.6, 85.5] of test cells with 8.7% [7.8, 9.6] error.
   - M5: 79.8%, 8.9%. M6: 88.3%, 11.5%. M3: 88.6%, 12.3%, but its validation coverage was 94.3% (ties).
   - P1: 88.3%, 14.6%. P2: 84.7%, 15.9%, with no abstention and 15.3% coarser labels.
   - No method reached 90% test coverage.
3. **At the validation OP-err threshold.**
   - M2 kept 41.6% at 3.2% error; P1 37.2% at 3.4%.
   - M4 kept 4.4% at 0 errors; M5 6.5% at 1.0%.
   - M1 missed the target (16.4% error).
   - Not attainable for M3 and M6.
   - Frame as threshold transfer at fixed thresholds, not a method property.
4. **Removed types (Arm B; ASC, MAIT, pDC; 2,310 cells, 83% top-up).**
   - At OP-cov, 66% (M4) to 89% (M3, M6) were accepted with a known label, mostly the nearest known neighbour.
   - Known-vs-removed AUROC 0.44–0.65.
   - At M4's OP-err threshold, 0.2% were accepted, but at only 8.4% known-cell coverage.
5. **Natural unknowns.** Only 20 erythroid cells, one class, few donors. Report counts, no intervals, no ranking. Exclude P1/P2 or explain that they mostly assign the correct erythroid label (B1).
6. **Protein check.**
   - Per file, descriptive, replacement inputs, author-filtered, donor and overlap unknown, about 21–23% of F zero-filled.
   - Report `agreement_accepted` and `agreement_accepted_gateable_preds` together with `n_accepted_resolved`. Examples:
     - 10k M4: 0.904 / 0.978 (n = 6,009)
     - 5k M4: 0.912 / 0.950 (n = 3,321)
   - Explain the label-granularity mismatch. No ranking, no pooling, no interval, no ground-truth language.
7. **Platform.** One donor per platform. Descriptive observations only.

**Do not write:**
- "method X is best / causes / generalises to new studies";
- "architecture" conclusions from either track;
- "calibrated" for M1–M3;
- AURC comparisons involving P2;
- Arm A vs Arm B macro-F1 comparisons;
- "removing classes degraded scANVI";
- "protein validates";
- "verified" or "reproduced".

---

## 8. Checklist for the coordinator before drafting (no new experiments)

- [ ] Hash the current `score_all.py`, `evaluate.py` and `protein_check.py` against the `provenance.json` values. Not done here.
- [ ] Confirm the `recovery/armB` vs `compare_arms/B` and `recovery/armA_cite` vs `T01` directory equivalence by hash (§4.5).
- [ ] Locate the per-method runtime and peak-memory records (historical T01, recovery `6ef42791…`) if runtime is reported.
- [ ] Decide, with human approval, whether the M3 tie-handling issue (B3) and the practical-track erythroid scoring (B1) get a disclosed post hoc sensitivity analysis. Otherwise handle both by wording only.
- [ ] Carry the amendment §11 disclosures verbatim into the paper.

# Final methods review: recorded run `29879296d87343898100c190308744a1` and revised manuscript

- **Role:** methods-reviewer (model review). This is not a human review and not an independent reproduction. Nothing here verifies, approves or reproduces results.
- **Snapshot:** `94756e98123663fec60a3bf55e17423a4cdae7f9`, reviewed 2026-10-06.
- **Scope:** scientific support and wording only. No experiments, rescoring or input edits. The pending Mode F clean reproduction is a separate gate. It is **not** a reason for the verdict below.

## Verdict (METHODS only): **FAIL — two blocking findings, both fixable by text**

B1–B5 from the prior critique (`protocol/completed-run-methods-review.md`) are now handled correctly and faithfully. Two new problems block the gate:

- **F1:** the new absent-class bootstrap example rests on an arithmetic error in `claims.json` M16.
- **F2:** the new "absent classes" text misdescribes what the scoring code does.

Both need wording changes only. No new analysis is needed.

## What was checked

- **Read:** `paper/main.tex` (all), `evidence/claims.json`, the `results.json` sections listed below, `donor-count-check.json`, `assembly-check.json`, `score_all.py`, `evaluate.py` and `protein_check.py`.
- **`results.json` sections:** `summary_test`, `paired_differences_vs_M4`, `protein_agreement`, `thresholds_validation`, `cell_counts`, `score_info`.
- **Recorded CSVs:** `unknowns_test.csv`, `bootstrap_nan_counts.csv`, `per_study_test.csv`, and the γδ T/ASC rows of `per_class_test.csv`.
- **Also used:** a grep of `scripts/make_paper_assets.py` to find where the paired-difference macros come from.
- **Not re-checked:**
  - calibration values beyond the prior review;
  - literature claims L01–L04 (one web search for the HIHA annotation claim found nothing relevant, so this is unresolved rather than contradicted);
  - script hashes;
  - the generated `.tex` assets.

## Blocking findings

### F1. `claims.json` M16 is false, and the manuscript's "can even exclude the point estimate" has no support

- **M16 is wrong.** It says: "The lower bound of the bootstrap interval for M15 (0.105) lies above the point estimate", with status `supported`. But 0.105 < 0.15, so the statement is false. The recorded M4 natural-unknown interval [0.10526, 1.0] **contains** the point estimate 0.15.
- **The claims built on it inherit the error.**
  - I03's limitation ("the interval can exclude the point estimate") rests on M16.
  - The paper does the same in §"Absent classes in bootstrap replicates" ("they can even exclude the point estimate. The clearest case is … M4 … 0.15 with interval [0.105, 1.000]") and in the Limitations bullet "Bootstrap with absent classes" ("can exclude the point estimate").
- **No recorded interval of this kind excludes its point estimate.** I checked:
  - all eight Arm A/practical `unknown_false_accept@OPcov` intervals (M1 0.85 [0.842, 1]; M2 0.65 [0.632, 1]; M3 0.55 [0, 0.579]; M4 0.15 [0.105, 1]; M5 0.30 [0, 0.316]; M6 0.25 [0, 0.263]; P1 0.70 [0, 0.737]; P2 1.0 [1, 1]);
  - all seven paired natural-unknown difference intervals.

  So the example does not show what the sentence says it shows.
- **The example's own values are correct:** 0.15, [0.105, 1.000], 126/1,000 replicates with no unknown cell. Its correct reading is that the interval runs from 0.105 to 1.0 and rests on 874 replicates. That makes it uninformative, but it does not exclude the point estimate.
- **Required fix:**
  - correct or retract M16;
  - drop the exclusion clause from I03 and from both places in the paper, or state it only as a general property of percentile intervals with "this did not occur in the recorded intervals";
  - keep the M4 example as an illustration of a wide interval resting on 874 replicates.

### F2. The absent-class paragraph and the Limitations bullet misdescribe how the code handles a missing class

- **What the paper says:** "some replicates contain no cell of a rare class … Table counts the replicates in which each metric was undefined; such replicates cannot contribute a value", and "Replicates lacking a rare class … yield undefined values; intervals for those metrics are conditional on the class being present".
- **What the code does:**
  - `score_all.py` fixes `classes_f1` once, from the full sample.
  - `evaluate.macro_f1` calls `f1_score(..., labels=classes_f1, zero_division=0)`.
  - A replicate missing an F1 class therefore scores that class **0**. The replicate is **kept**, so the macro-F1 interval is pulled downward. It is not conditional on the class being present.
  - `bootstrap_nan_counts.csv` confirms this: `macro_f1_closed` has 0 undefined replicates for every method.
  - Undefined values arise only in two places in this run:
    - (a) `unknown_false_accept@OPcov` when a replicate has no unknown cell (126);
    - (b) OP-err when it is not attainable (1,000 for M3 and M6).
  - Accepted error could in principle also be undefined if a replicate accepts zero cells, but none of the OP-err metrics that were attainable had a NaN replicate.
  - No per-class metric is bootstrapped.
- **Required fix:**
  - Say that undefined replicates come only from (a) and (b).
  - Say that a replicate missing a macro-F1 class scores that class 0 and is kept. This biases replicate macro-F1 downward, and how often it happened was not recorded.
  - Remove "conditional on the class being present" except for the natural-unknown metric.

## B1–B5: status of the prior blocking findings

**B1 (erythroid natural unknowns): addressed and faithful.**
- **Matched-method counts** match `summary_test` ×20: M1 17, M2 13, M3 11, M4 3, M5 6, M6 5.
- **Released-model figures** match: P1 labels 16/20 erythroid and accepts 14/20; P2 labels 18/20 and accepts 20/20 (`unknowns_test.csv`).
- **"Mostly as …" wording** is consistent with the top-prediction shares:
  - M1 accepts 17 cells while 18/20 are predicted platelet/MK, so at least 15 of the accepted cells are platelet/MK.
  - M2 and M3 accept 13 and 11 cells while 16/20 and 19/20 are predicted CD4 T, so at least 9 and 10 of the accepted cells are CD4 T.
- Practical-track rows are excluded from comparison, and the all-strata analysis is not interpreted.
- Inference not stated in the paper: HIHA has 7,062 mapped cells against 7,042 scorable, so all 20 erythroid cells are from HIHA. That fits "few donors".

**B2 (AURC truncation, P2 with no threshold): addressed.**
- risk@0.80 macros are used.
- P2 OP-cov is described as accepting everything, with `coarser` cells (15.3%) as the unassigned part.
- The serialisation note (`-inf` in the CSV, `null` in JSON) is included.

**B3 (M3 ties, OP-err not attainable): addressed.**
- M3 validation coverage at τ_cov is 0.943 (Arm A) and 0.924 (Arm B), matching `thresholds_validation`.
- The order dependence is disclosed and M3 is not ranked.
- OP-err is reported as "not attainable".

**B4 (protein check): addressed and faithful to `protein_check.py`.**
- `agreement_accepted` = `agree / in_gate`, with denominator `n_accepted_resolved`.
- `agreement_accepted_gateable_preds` uses `in_gate & isin(pt, gates)`. That count is indeed not written to the outputs, and the paper says so correctly.
- Quoted values match `results.json`: 6,375/6,855 and 3,762/3,994 resolved; M4 0.904/0.978 (n = 6,009) and 0.912/0.950 (n = 3,321); M1 on 5k 0.636/0.938; denominators 5,027–6,331 (10k) and 3,306–3,726 (5k).
- No ranking, pooling or interval is drawn.

**B5 (within-study intervals): addressed.**
- The required interval wording is present.
- Per-study counts match the donor audit: 12/12/3/5 donors = 32, with 7,200/7,200/1,800/3,000 natural cells.
- Scorable counts 7,042 + 7,200 + 3,000 + 1,776 = 19,018 ✓; HIHA + RA ≈ 75% ✓.
- The per-study M4 table matches `per_study_test.csv`.
- The range is 0.1785 − 0.0215 = 0.157 and the interval width is 0.0178, so the ratio is 8.8 ("almost nine") ✓.

**Also checked and correct:**
- "HIHA highest and RA lowest for every method, arm and track" (all 14 rows checked).
- The Arm B M6 shifts (RA 0.220 → 0.516).
- P1 HIHA macro-F1 0.842.
- P2 accepting no RA cells at OP-err.
- OP-cov test coverage ranging from 0.798 to 0.886, with no method or arm reaching 0.900.

## Non-blocking corrections (recommended before release)

1. **Paired "differences" are bootstrap means.** The macros use `mean_diff` = `nanmean(boot_m − boot_M4)` (`make_paper_assets.py:698`), not the difference between point estimates.
   - For the quoted metrics the gap is ≤ 0.001: M5 − M4 coverage is −0.0179 as a bootstrap mean against −0.0182 between point estimates; M2 − M4 coverage@OPerr is 0.373 against 0.372.
   - State "mean of paired bootstrap differences" once in §Uncertainty.
   - For natural-unknown differences the gap is large (M1 − M4: 0.528 against 0.70). Those differences are not quoted, which is correct.
2. **The P1 γδ T inference goes too far.**
   - Recall 0.015 plus `coarser` 0.16% does not show that P1 gave γδ cells "other mapped classes". P1's `outside_fraction` (2.8% ≈ 530 natural cells) could absorb many of the 688 natural γδ cells.
   - Write "to other classes or to labels outside K".
3. **AUROC wording.** AUROC < 0.5 means a removed-type cell outranks a known cell more often than not. It does not mean mean confidence is higher. Also, M6 at 0.496 is effectively chance. Fix both places: Results ("on average higher") and Discussion item 4.
4. **"RA macro-F1 ranged from 0.353 (M1) to 0.518 (M4)"** holds only for the Arm A matched methods. Arm B M4 is 0.582 and P2 is 0.420. Add "(Arm A, matched)".
5. **"Pre-registered eligibility criterion"** should read "pre-specified (amendment) eligibility criterion". The protocol is stated as not externally registered.
6. **Arm B "accepted labels were mostly the nearest known relative".** The top-label table covers all cells of each class, not only accepted ones. M1's ASC cells go mostly to ILC (0.269). Write "most frequent predicted labels", and note that M1 is an exception.
7. **Original vs regenerated framing.** The "Which numbers are which" paragraph is adequate. Two refinements:
   - Captions also contain literals (94.3%/92.4%, 0.798, 0.847, 15.3%, 0.99998/0.99992). Say these are also original-run literals.
   - The "almost nine times" ratio mixes a literal (0.157) with a macro interval, so it may not hold after a rebuild. Flag it as original-run.

## Disclosed limitations accepted as adequate (no further request)

The following are disclosed and need no new experiments:
- a single training seed;
- fixed thresholds;
- four studies;
- possible label circularity for HIHA and the platform panel;
- a protein check on replacement inputs that is descriptive only;
- the platform panel coming from one donor;
- Mode R provenance with the reproduction still pending;
- no runtime table.

## Concrete blocking fixes (summary)

- **F1:**
  - Correct or retract `evidence/claims.json` M16. It says 0.105 > 0.15, which is false.
  - Remove "can exclude the point estimate" from I03.
  - In `paper/main.tex`, rewrite §"Absent classes in bootstrap replicates" and the Limitations bullet "Bootstrap with absent classes". Either delete the exclusion claim, or state it as a general possibility that did not occur here. Present M4 [0.105, 1.000] as a wide interval resting on 874 replicates.
- **F2:** In the same two places, state the actual implementation:
  - undefined replicates come only from "no unknown cell" (126) and "OP-err not attainable" (1,000);
  - a macro-F1 class missing from a replicate is scored 0 and the replicate is kept, giving a downward bias of unrecorded frequency;
  - macro-F1 intervals are not conditional on the class being present.

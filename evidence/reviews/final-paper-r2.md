# Final paper re-review (round 2): methods reviewer (model review, not human review)

- **Snapshot:** fa095bb935c0d423392375fee8ba1e3df887e1a3
- **Recorded run:** 29879296d87343898100c190308744a1 (Mode R)
- **Date:** 2026-10-06
- **Scope:** I checked the text corrections made after `final-paper-r1.md` (paper blockers 1–3) and `final-methods-r1.md` (F1, F2, non-blocking items 1–7). I did not redo the literature or citation review; the prior review found no issues there. I ran no new analyses and edited no inputs.
- **Reproduction:** the Mode F clean reproduction is a separate, later gate. The paper correctly reports it as pending (title page, abstract, §1, §6, Table 5). That status is not counted against the paper here, and this review does not claim reproduction or verification.

## Verdict: **PASS**

All three paper blockers and both methods blockers (F1, F2) are fixed in `paper/main.tex`, in `evidence/claims.json` and in the rendered preview PDF. The recommended text corrections are also present. I found no new blocking issue.

## What was inspected

- **`paper/main.tex`:** all 605 lines.
- **`protocol/paper-final-corrections.md`:** the corrections checklist.
- **`evidence/claims.json`:** all claims, with focus on M15, M16 and I03.
- **`results.json`:** spot checks against `evidence/results-29879296/results.json`:
  - `accepted_error@OPcov` and `coverage@OPcov` for all 14 rows;
  - the P2−M4 OP-cov coverage `mean_diff`.
- **`evidence/reviews/paper-preview.pdf`:**
  - read in chunks: pp. 1–12, pp. 13–24, then p. 25;
  - the PDF has **25 pages, not 24**: p. 26 is reported as out of range, and Table 9 (bootstrap NaN counts) is on p. 25;
  - every page renders, and no "??" or unresolved references appear;
  - Tables 1–9 fit the page.
- **Rebuild check:** the preview matches the corrected source. It contains the new §2.7 wording, the narrowed Discussion item 2 and the new AUROC wording, so it was rebuilt after the corrections.

## Blockers from round 1

| Item | Status | Evidence |
|---|---|---|
| **Paper B1 / Methods F1:** the false claim that an interval excludes its point estimate | **Resolved** | See below. |
| **Methods F2:** absent-class handling | **Resolved** | See below. |
| **Paper B2:** CLI rendering | **Resolved** | See below. |
| **Paper B3:** study vs method comparison | **Resolved** | See below. |

**Paper B1 / Methods F1: false "interval excludes point estimate"**
- **§2.7, PDF p. 6:** now reads "M4's recorded value is 0.15 with interval [0.105, 1.000]: the interval contains the point estimate but spans almost the whole range… could in principle exclude its point estimate, but none of the recorded natural-unknown intervals did."
- **Limitations, p. 15:** the exclusion claim is gone.
- **`claims.json` M16:** now says 0.105 is below 0.15, that the interval contains the point estimate and rests on 874 replicates, and it carries a dated correction note. Its value, 0.10526, is unchanged.
- **I03 limitation:** now says "No recorded interval of this kind excluded its point estimate."

**Methods F2: absent-class handling**
- **§2.7 (p. 5):**
  - macro-F1 fixes its class set once; a missing class scores 0 and the replicate is kept;
  - this biases macro-F1 downward, and how often it happened was not recorded;
  - macro-F1 intervals are "*not* conditional on the class being present";
  - undefined replicates arise only from the 126 replicates with no unknown cell and from M3/M6 OP-err, where the operating point was not attainable (1,000 replicates).
- **Limitations (p. 15) and I03:** say the same.
- **Table 9 (p. 25):** consistent with this. It lists only `unknown_false_accept@OPcov` (126) and M3/M6 OP-err rows (1,000), and has no macro-F1 row.

**Paper B2: CLI rendering (checked visually on the rendered pages)**
- **p. 17, item 5:** `score_all.py --reps 1000 --natural-unknown-scope natural` renders with spaces and double hyphens.
- **p. 17:** `--no-comparison` and `--comparison <report.json>` render with double hyphens.
- **p. 2:** the filter expressions `is_primary_data == True`, `disease == 'normal'`, `tissue_general == 'blood'` and `fresh_execution: false` keep their spaces.
- **pp. 16–17:** the `verbatim` blocks are intact.

**Paper B3: study vs method comparison**
- **Discussion item 2 (p. 15)** now reads "the test study mattered more than the choice among the learned matched methods".
- It states the M3/M5/M6 gaps as "0.036 or less" and labels them original-run point estimates.
- It excludes the marker and centroid baselines and states the limits: four studies, no interval.
- **Check against `results.json`:** Arm A accepted error at OP-cov is M3 0.1230, M5 0.0890 and M6 0.1151, against M4 0.0867. The largest gap is 0.0363, so "≤0.036" holds at three decimals. The M4 per-study range is 0.021–0.179 (0.157).

## Recommended corrections (methods r1 items 1–7; paper r1 optional items 1–2)

All are present in the source and in the PDF:

1. **Paired differences:** §2.7 (p. 5) says they are the mean of paired bootstrap differences, "differs … by at most 0.001". Spot check: for P2−M4 OP-cov coverage, `mean_diff` is 0.03055 and the point-estimate difference is 0.8471 − 0.8165 = 0.0306. ✓
2. **P1 γδ T (p. 7):** "to other classes or to labels outside *K*". ✓
3. **AUROC (p. 11 and Discussion item 4):** described as a rank probability ("more often than not") and explicitly not as mean confidence. M6 at 0.496 is called effectively chance, and the text says AUROC has no interval. ✓
4. **RA macro-F1 range:** scoped as "among the Arm A matched methods" (p. 8). ✓
5. **Protein check eligibility:** "pre-specified (amendment) eligibility criterion" (p. 13). ✓
6. **Arm B labels:** "most frequent predicted labels (over all cells…, not only accepted cells)", with the M1 ASC→ILC 0.269 exception (p. 11), and the Table 3 caption matches. ✓
7. **"Which numbers are which" (p. 2):** caption literals are listed as original-run values, and the "almost nine times" ratio is flagged as a literal-plus-macro ratio. The p. 8 text repeats the flag. ✓

**Abstract:** now says "much larger than the pooled accepted-error interval" (p. 1). ✓

## Non-blocking residual notes

None of these affects the verdict.

1. **Discussion item 2:** the M2 baseline's pooled gap from M4 (0.193 − 0.087 = 0.107) is still smaller than M4's study range (0.157). The text only says the claim "does not extend" to the baselines, which is conservative rather than wrong.
2. **§3.6 (p. 12):** says the natural-unknown intervals are "degenerate", while §2.7 says "uninformative". The two wordings are consistent in substance; "uninformative" is the more precise word.
3. **Unchanged from round 1 (declared out of scope in the corrections protocol):**
   - mid-token line breaks in `\nolinkurl` paths and identifiers: `Immune_All_L ow` (p. 2), `pe r_study_test.csv` (p. 7), `agreement_accepted_g ateable_preds` (p. 13), `unknowns _allstrata_secondary.csv` (p. 17), and the wrapped sha256 strings (p. 18);
   - the figure legends are still very small, about 5 pt.

   None of these affects a command. Copied hashes should be checked against the source.
4. **Page count:** the brief and round 1 describe the preview as 24 pages; this build has 25. Nothing is missing.

## Limits of this review

- This is a model review, not a human review.
- It does not verify or reproduce any result.
- Values were checked against the recorded `results.json` only where listed above.
- The paper was not rebuilt by this reviewer. The rendering findings come from the supplied `paper-preview.pdf`.

# Final paper review: methods reviewer (model review, not human review)

- **Snapshot:** 94756e98123663fec60a3bf55e17423a4cdae7f9
- **Run:** 29879296d87343898100c190308744a1 (Mode R)
- **Inputs read:** `paper/main.tex` (all 598 lines); `paper/references.bib`; `evidence/reviews/paper-preview.pdf` (all 24 pages); `evidence/claims.json`; `evidence/paper-claim-inventory.json` (searched for specific claims, not read line by line); `evidence/results-29879296/results.json` (all of it); `literature/research.md` (Cultrera, HIHA and scTab entries); `protocol/completed-run-methods-review.md` (B1–B5 and M1–M7 headings).
- **Reproduction:** Mode F clean reproduction is pending. The paper says so on the title page, in the abstract, in §1 and in §6/Table 5. That is correctly disclosed, and this review does not count it against the paper.

## Verdict: FAIL. Three text-only fixes are needed; no new experiments.

The paper is readable and well hedged. Every core number I checked against `results.json` matched. I found no equivalence claim, and no method ranking built on metrics that cannot be compared (AURC, P2 OP-cov, M3 ties, protein, natural unknowns, Arm A vs Arm B macro-F1). The protein denominators are stated correctly. Methods-review findings B1–B5 and M1–M7 are all handled in the text. Three specific defects remain.

### Blocker 1: a false uncertainty statement in the paper and the claim ledger
- **Paper, §2.7 "Absent classes in bootstrap replicates":** "...they can even exclude the point estimate. The clearest case is Arm A natural-unknown false acceptance ... M4's recorded value is 0.15 with interval [0.105, 1.000]."
  - That interval *contains* 0.15, so the example does not show what the sentence claims.
  - I checked every Arm A and practical-track natural-unknown interval in `results.json`, both `summary_test` and `paired_differences_vs_M4`. None excludes its point estimate. Examples: M1 0.85 [0.842, 1]; M3 0.55 [0, 0.579]; M5 0.30 [0, 0.316]; M6 0.25 [0, 0.263]; P1 0.70 [0, 0.737].
  - The same statement ("can exclude the point estimate") appears again in §5, in the "Bootstrap with absent classes" bullet.
- **`evidence/claims.json` M16** is marked `supported`, but its text says "The lower bound ... (0.105) lies above the point estimate." Its own value, 0.105, is *below* 0.15, so the claim is false. I03's `limitations` repeats the exclusion claim.
- **Required fix:**
  - Reword to what the data show: the interval is very wide and rests on 874 defined replicates. Either drop "can exclude the point estimate" or mark it explicitly as a theoretical possibility with no recorded instance.
  - Correct or withdraw ledger claim M16 and the wording in I03.

### Blocker 2: commands in the rendered PDF are corrupted
In PDF p.16, §6, the inline commands are broken:
- `\nolinkurl{score_all.py --reps 1000 --natural-unknown-scope natural}` renders as `score_all.py--reps1000--natural-unknown-scopenatural`, with the spaces lost.
- `\texttt{--no-comparison}` and `\texttt{--comparison <report.json>}` render as `-no-comparison` and `-comparison` with a single dash, because of the `--` ligature.

A reader copying these from the PDF gets invalid flags. The `verbatim` blocks are correct.

**Required fix:** typeset these with `\verb` or `verbatim`, or write `-{}-`, so the rendered text matches the real CLI.

### Blocker 3: one Discussion headline claim goes beyond the data
- **Claim:** Discussion item 2 says "The test study mattered more than the method."
- **What the data show:** M4's study-to-study range in accepted error is 0.157. But the recorded paired method differences are larger for some methods. At OP-cov, M1−M4 is 0.308 [0.286, 0.331]. Closed-set macro-F1 M1−M4 is −0.197.
- **Scope of the claim:** It holds only among the four learned matched methods: M3, M5 and M6 differ from M4 by 0.036 or less in accepted error. The study-level comparison also rests on four studies and has no interval.
- **Required fix:** limit the claim to the learned matched methods, for example "...mattered more than the choice among the learned matched methods", consistent with item 1.

## Checks passed
- **Abstract, title page and status macro:** the values match `results.json`, including:
  - 32 donors and 19,018 scorable cells;
  - M4 macro-F1 0.694 [0.669, 0.716];
  - OP-cov coverage 0.817 and error 0.087;
  - Arm B false acceptance 0.659–0.892.
  - "No method reached 0.90" also holds: the maximum is 0.886, and P1 is 0.883.
- **Closed set:** the M3, M5, M6 and P2 paired intervals all include zero, and the text says plainly that this is not equivalence. P1's −0.077 [−0.094, −0.060] is correctly reported as lower. "Within 0.006" is correct (0.0062).
- **OP-cov and OP-err details:**
  - M5−M4 coverage interval is [−0.028, −0.008], and the error interval includes zero.
  - M3's validation coverage is 0.943/0.924, which matches the threshold table.
  - P2's τ_cov is −∞ (cap 0.798) and its OP-err coverage of 0.0025 is about 47 cells. M4's OP-err result is 0 [0, 0].
  - The test error range of "0 to 16%" is correct (M1: 0.164).
- **Arm B:**
  - AUROC ranges from 0.443 to 0.650, and three of six methods are below 0.5.
  - The M6 Arm A→B changes are 0.115→0.211 and 0.063→0.160.
  - The 8- vs 11-class caveat is present.
- **Natural unknowns:** the counts 17/13/11/3/6/5 and P1 14, P2 20 match 20 × the recorded rates. P1 and P2 are correctly excluded.
- **Per-study:** the cell weights 7,042/7,200/3,000/1,776 match `cell_counts` (the 20 erythroid cells are subtracted from HIHA). The "almost nine times" ratio is correct (0.157 / 0.0178 = 8.8).
- **Protein:**
  - M4 10k: 0.904 (n=6,009) and 0.978. M4 5k: 0.912 (n=3,321). M1 5k: 0.636 and 0.938.
  - The denominator ranges 5,027–6,331 and 3,306–3,726 are correct.
  - Resolved fractions are 93.0% and 94.2%.
  - The paper states that the gateable denominator was not recorded. No ranking is drawn.
- **Literature:** the claims match the saved sources:
  - Cultrera: in-distribution macro-F1 80/82/84 fell to 55/57/52 on 21 studies.
  - scTab: donor split described as a "compromise"; 249 datasets; 22.2 M cells.
  - HIHA: annotation guided by CellTypist and Seurat.
  - Every bib entry carries a source ID from `sources.json`. I found no source support that had been invented.
- **Rendering:** all 24 pages render. Tables 1–9 fit the page. Captions and references [1]–[37] resolve, and I saw no "??".

## Optional improvements (non-blocking)
1. **Abstract:** "Between-study spread was much larger than any interval" is literally false for the natural-unknown intervals. Suggest "...than the pooled accepted-error interval".
2. **Arm B AUROC:** the text says confidence was "on average higher" on removed types. AUROC is a rank probability, so "more often higher" would be accurate. M6's 0.496 is essentially chance, and AUROC has no interval.
3. **Figures:** in Figs 1 and 2, the legend and axis text is very small (about 5 pt). The interval brackets in Tables 1 and 2 are tiny but readable. Enlarging both would help.
4. **Cosmetic line breaks:** `Immune_All_L ow` (p.2) and `pe r_study_test.csv` (p.6) break mid-token.

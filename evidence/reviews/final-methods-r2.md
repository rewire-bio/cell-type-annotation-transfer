# Final methods re-review (r2): corrected manuscript and claim ledger

- **Role:** methods-reviewer. This is a model review, not a human review and not a reproduction.
- **Snapshot:** `fa095bb935c0d423392375fee8ba1e3df887e1a3`. Run `29879296d87343898100c190308744a1` (Mode R). Reviewed 2026-10-06.
- **Scope:** METHODS only. I ran no new analyses and edited no inputs. The Mode F clean reproduction gate is still **pending**. This review does not claim it passed, and the verdict below does not depend on it.

## Verdict (METHODS): **PASS**

Both blocking findings from `final-methods-r1.md` (F1 and F2) are fully resolved. All seven recommended methods corrections are present and accurate. The scientific scope and limitations are adequately disclosed. I found no new blocking issue.

## Inspected

- `protocol/paper-final-corrections.md`
- `evidence/reviews/final-methods-r1.md` and `final-paper-r1.md`, as the basis for the prior findings
- `evidence/claims.json`: M15, M16, I03 and the footer
- `paper/main.tex`:
  - abstract (L65–67) and "Which numbers are which" (L80)
  - §Uncertainty (L167–183)
  - practical-track text (L216) and the per-study paragraph (L241)
  - Arm B (L327–350) and natural unknowns (L376–380)
  - Discussion (L447–451), Limitations (L460–461) and the Table `tab:nan` caption (L599)
- `companion/scripts/score_all.py`: L111–113, L164, L192–200, L211–212
- `companion/src/celltransfer/evaluate.py`: L72–99
- `evidence/results-29879296/results.json`: `accepted_error@OPcov`, Arm A and practical-track entries

## F1: false ".105 > .15" / "interval can exclude the point estimate"

**Resolved.**

- **M16** now reads: "lower bound … 0.105, below the 0.15 point estimate; the interval [0.105, 1.000] contains the point estimate, is very wide, and rests on the 874 of 1,000 replicates…". It includes a dated correction note.
  - `value` 0.10526 is unchanged.
  - The pointer `…M4.unknown_false_accept@OPcov_ci95_lo` is unchanged.
  - The text is now true.
- **I03 limitation:** the exclusion clause is gone. It now says "No recorded interval of this kind excluded its point estimate", which matches the r1 check of all 8 point intervals and all 7 paired intervals.
- **Paper L183:** "the interval contains the point estimate but spans almost the whole range". Exclusion appears only as an "in principle" property of percentile intervals, followed by "none of the recorded natural-unknown intervals did". The intervals are called uninformative.
- **Limitations L461:** no exclusion claim remains. The grep for `exclude` finds only unrelated uses (L460: "excluding HIHA"; L380: "We exclude both").

## F2: absent-class handling misdescribed

**Resolved, and checked against the code.**

**What the code does:**
- `score_all.py` L111 fixes `classes_f1` once, from the full sample (classes with ≥20 cells).
- L192 bootstraps with weights: `E.macro_f1(tn, classes_f1, w[m_sc])`.
- `evaluate.py` L91 calls `f1_score(..., labels=classes, sample_weight=w, zero_division=0)`.
- So a class with zero replicate weight gets F1 = 0, and the replicate is kept.

**What the paper and ledger now say:**
- Paper L180 says exactly this, adds the downward bias with unrecorded frequency, and says "*not* conditional on the class being present; no replicate was undefined for macro-F1".
- L181 limits undefined replicates to two sources:
  - natural-unknown false acceptance when a replicate has no unknown cell (126; code L193 returns NaN when `len(unk)==0`);
  - OP-err when it is not attainable (M3/M6, 1,000).
- It also says no per-class metric was bootstrapped.
- L461 and I03 repeat this consistently.
- "Conditional on … present" now applies only to the natural-unknown metric (L183, L461).

**Minor, non-blocking:** `evaluate.py` L82 can also return NaN accepted error when a replicate accepts zero weight. Per r1, this did not occur for any attainable OP-err metric, so the "only two ways" statement is accurate for this run.

## The seven r1 methods corrections

| # | Item | Status | Where it is now |
|---|---|---|---|
| 1 | Paired differences are bootstrap means | ✓ | L176: "mean of the paired bootstrap differences" plus percentile interval, gap ≤0.001 for quoted values. Matches `score_all.py` L211 (`np.nanmean(d)`). |
| 2 | P1 γδ T inference | ✓ | L216: "to other classes or to labels outside $K$", pointing to the `outside` fraction. |
| 3 | AUROC wording | ✓ | L350 and L451: rank probability, "more often than not", explicitly not mean confidence; M6 effectively chance; no interval. |
| 4 | RA macro-F1 range | ✓ | L241: "among the Arm A matched methods, … 0.353 for M1 to 0.518 for M4". |
| 5 | "Pre-registered" | ✓ | L408: "pre-specified (amendment) eligibility criterion". No `pre-registered` remains. |
| 6 | Arm B labels | ✓ | L344: "most frequent predicted labels (over all cells of each removed class, not only accepted cells)". L350 adds the M1 ASC→ILC (0.269) exception, consistent with the Table L334 row. |
| 7 | Original vs regenerated | ✓ | L80: caption literals (94.3%/92.4%, 0.798, 0.847, 15.3%, 0.99998/0.99992) listed as original-run, and the "almost nine times" ratio flagged. L241 repeats the flag. |

## Related text checks

- **Discussion item 2 (L449):** now limited to "the choice among the learned matched methods". The "0.036 or less" figure matches `results.json` Arm A OP-cov accepted error (M3 0.1230, M5 0.0890, M6 0.1151 vs M4 0.0867, a maximum gap of 0.0363). The baseline exception, the four-study limitation and the absence of an interval are all stated.
- **Abstract (L65):** now "than the pooled accepted-error interval".

## Unresolved / outside this gate

- **Mode F clean reproduction:** pending. This is a separate gate and is not assessed here.
- **Compilation of the new `\verb` uses:** not verified here. The corrections log says the paper was not rebuilt, so the coordinator should run `make paper`. This is a rendering check, not a methods finding.
- **Optional items:** figure font size and cosmetic line breaks were not addressed. They are non-blocking and outside the methods scope.

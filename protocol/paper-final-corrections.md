# Paper final corrections (text only) — response to final-methods-r1.md and final-paper-r1.md

Run 29879296d87343898100c190308744a1 (Mode R). No experiments, rescoring, generator or figure edits. No recorded numeric value changed. `evidence/paper-claim-inventory.json` preserved unchanged as historical draft. Dynamic reproduction-status macros and the original/regenerated-number disclosures are kept.

## Blocking
- [x] **F1 / Paper B1 (false ".105 > .15" / interval-excludes-point):** `claims.json` M16 text corrected (0.105 is below 0.15; interval contains the point estimate; rests on 874 replicates; correction noted); `value` unchanged. I03 limitation: exclusion clause removed, "no recorded interval of this kind excluded its point estimate" added. Paper §2.7 "Absent classes" and Limitations bullet rewritten; M4 [0.105, 1.000] kept as wide interval on 874 replicates; exclusion stated only as a theoretical property not observed.
- [x] **F2 (absent-class handling):** both places now state that undefined replicates come only from no-unknown-cell (126) and OP-err not attainable (1,000, M3/M6); a missing macro-F1 class scores 0 and the replicate is kept (downward bias, frequency unrecorded); macro-F1 intervals not conditional on class presence. Checked against `score_all.py` L111/L192 and `evaluate.py` L91 (`zero_division=0`).
- [x] **Paper B2 (CLI rendering):** `score_all.py --reps 1000 --natural-unknown-scope natural`, `--no-comparison`, `--comparison <report.json>` now `\verb`. Spaced filter expressions (`is_primary_data == True`, `disease == 'normal'`, `tissue_general == 'blood'`, `fresh_execution: false`) moved from `\nolinkurl` to `\verb`; `\nolinkurl` left only on paths/IDs/hashes.
- [x] **Paper B3 (study vs method):** Discussion item 2 scoped to "the choice among the learned matched methods" for accepted error; notes M3/M5/M6 within 0.036 of M4 (Arm A OP-cov point estimates: 0.123/0.089/0.115 vs 0.0867), baselines larger, four studies, no interval.

## Non-blocking (methods r1 items 1–7, paper optional 1–2)
- [x] 1 Paired differences = mean of paired bootstrap differences; stated once in §Uncertainty.
- [x] 2 P1 γδ T: "other classes or to labels outside K".
- [x] 3 AUROC: rank probability ("more often than not"), not mean confidence; M6 effectively chance; no interval (Results and Discussion item 4).
- [x] 4 RA macro-F1 range scoped "among the Arm A matched methods".
- [x] 5 "pre-registered" → "pre-specified (amendment)".
- [x] 6 Arm B: "most frequent predicted labels (over all cells of each class, not only accepted)"; M1 ASC→ILC (0.269) exception added.
- [x] 7 "Which numbers are which": caption literals listed as original-run; "almost nine times" flagged as original-run, literal-plus-macro ratio.
- [x] Abstract: "than any interval" → "than the pooled accepted-error interval".
- [ ] Not done (optional, out of scope): figure font size (generator not edited); cosmetic mid-token breaks.

## Validation
- Grep of `paper/main.tex` for `exclude the point`, `on average`, `pre-registered`, `any interval`, `\nolinkurl{… …}`, `\texttt{--…}`: no remaining matches (only "*not* conditional on the class" remains, intentionally).
- Paper not rebuilt in this task (no shell available); coordinator should run `make paper` to confirm compilation of the new `\verb` uses (all outside macro arguments).

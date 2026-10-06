# Paper author notes: recorded run `29879296d87343898100c190308744a1`

- **Role and date:** paper-author worker, 2026-10-06.
- **Snapshot:** `69207f08784ac1aaae0eeef2cba0d7a21753f38d`.
- **Owned outputs:**
  - `paper/main.tex`
  - `paper/references.bib`
  - `evidence/claims.json`
  - this file.

**What was not done:**
- No new analysis was run.
- No scientific code was changed.
- The paper was **not compiled**, as instructed.

**Status of the results:**
- The results are from a recorded Mode R recovery run.
- Independent clean reproduction is pending.
- The paper never states that the results are verified or reproduced.

## 1. Inputs read in full

- `protocol.md`
- `protocol/completed-run-methods-review.md`
- `protocol/amendments/protein-replacement-reviewed.md` and its approval record
- `protocol/amendments/2026-10-06-approved-resumption.md`
- `protocol/paper-assets-implementation.md`
- `paper/artifacts.json`
- the `evidence/paper-inputs/*.tex` samples
- in `evidence/results-29879296/`: `results.json`, `per_study_test.csv`, `unknowns_test.csv`, `protein_agreement.csv`, `platform.csv`, `calibration_test.csv`, `bootstrap_nan_counts.csv`, `unknowns_allstrata_secondary.csv`, the relevant rows of `per_class_test.csv`, `gates.json`, `cite-receipt.json`, `comparison_manifest.json`, `provenance.json` and `coordinator-code-check.json`
- `evidence/unintended-test-launch.json`
- `historical/evidence/protocol-deviations.md`
- `literature/sources.json` and `literature/research.md`
- `scripts/reproduce.py` (header), `scripts/build_paper.py`, `Makefile`, and the preamble and macro code of `scripts/make_paper_assets.py`

## 2. How the methods-review findings were handled (wording only)

| Finding | Handling in `main.tex` |
|---|---|
| **B1:** natural unknowns are 20 erythroid cells | §3.6 reports counts only (k/20), with no interval and no ranking. It explains that P1 and P2 mostly make correct erythroid calls (16/20 and 18/20 in the recorded top-prediction distribution) and excludes them from comparison. The generated `table_unknowns.tex`, `table_unknowns_allstrata.tex` and `fig_unknowns.pdf` are **not** included. The all-strata analysis (126 cells) is mentioned and not interpreted. |
| **B2:** AURC and risk@ truncation; P2 OP-cov is −∞ | §2.5 item 1 states the shortfall rule and the null/−inf serialisation. §3.2 says P2 at OP-cov abstains on nothing and that the paired coverage difference compares an unthresholded model with a thresholded one. §3.4 uses risk@0.80 across tracks, calls P2 at ≥0.90 and P1 at 1.00 "not reachable", and says P2 AURC is not comparable. P2's unassigned part is described as `coarser` labels. |
| **B3:** M3 ties | §2.5 item 2 gives validation coverage of 0.943 and 0.924. §3.2 notes that M3's paired error difference compares different coverages. §3.4 does not rank M3 on AURC or risk and notes that saturated ties in other methods were not checked. OP-err for M3 and M6 is "not attainable". The limitations section says that correcting this would require approval. |
| **B4:** protein fine/coarse mismatch | §3.9 carries the exact label and describes both metrics. Examples are given with their denominators. The denominator ranges are stated, with no ranking, pooling or interval. It covers upstream filtering, unknown donors and training overlap, zero-filled genes, CD16-mono counts of 46 and 43, and CLR antibody counts of 14 and 29. P2 uses −∞. The generated `fig_protein.pdf` is **not** included, to avoid a bar chart that invites ranking. |
| **B5:** donor-within-study intervals | §2.7 gives the required interval wording verbatim and lists what the intervals exclude. It states cell weighting (HIHA and RA make up 75%). A per-study table for M4 appears beside the pooled value, and the full per-study table is in the appendix. Per-study donor counts are **not** inferred from cell caps; the paper says they are not in the evidence bundle. |
| **M1:** author labels and circularity | §3.1 and the limitations cite the literature. HIHA annotation was guided by CellTypist and Seurat (source 27:136), and the platform labels came from a CellTypist and Seurat consensus (source 30:108–109). The review had marked this "not verified"; the literature now supports it as a reported fact about annotation, but Census label provenance is still unverified. For RA, only "lower agreement with RA author labels" is claimed. |
| **M2:** Arm B M6 change | §3.5 uses the review's required wording ("cannot attribute"). |
| **M3:** Arm B composition and near neighbours | §3.5 and Table `armb` give the composition (83% top-up). They make no claim about novel types and no Arm A against Arm B F1 claim. |
| **M4:** validation includes top-up; OP-err transfer | Covered in §2.5, §3.2 and §3.3. OP-cov is worded as "the threshold that accepted 90% of validation cells". M4's τ_err of 0.99998 and P2's of 0.99992 are written as literals, because the macros round them to 1.0000 and 0.9999. P2 accepting no RA cells is stated. |
| **M5:** practical track is not an architecture comparison | §2.1 and §3.1. The four learned methods are "indistinguishable", and no winner is named. |
| **M6:** calibration semantics | §3.7 and the appendix caption. |
| **M7:** platform, one donor | §3.8 gives observations only, with no causal explanation. |
| **Minor 1–7** | (1) Bootstrap with absent classes: **not** mentioned in the text. Reported here as a gap. (2) AUROC ignores eligibility: practical-track AUROC is not quoted. (3) Interval bounds: Arm A and practical unknown intervals are not quoted. (4) Runtime: the paper explains why there is no runtime table and reports only the recorded records. (5) Path equivalence: not checked (listed below). (6) Attempts: reported. (7) Approval: the amendment date and sha256 are given. |

## 3. Generated assets used

All paths are relative to `paper/` because Tectonic runs there.

**Inputs:**
- `generated/asset_preamble.tex`
- `generated/results_macros.tex`
- tables:
  - `closed_set`
  - `operating_points`
  - `protein`
  - `reproduction`
  - `thresholds`
  - `per_study`
  - `paired_differences` (appendix, with a warning caption)
  - `calibration`
  - `practical_labels`
  - `platform`
  - `cell_counts`
  - `bootstrap_nan`
- figures:
  - `fig_operating_points.pdf`
  - `fig_risk_coverage.pdf`

**Not used, deliberately:** `table_unknowns`, `table_unknowns_allstrata`, `fig_unknowns`, `fig_paired_differences` and `fig_protein`. They must still exist for `build_paper.py`'s artifact check, but they are not `\input` in the paper.

## 4. Unresolved issues and risks (honest list)

1. **The paper was not compiled.**
   - The real `paper/generated/` and `paper/figures/` files did not exist in this worktree; only the samples in `evidence/paper-inputs/` did.
   - Packages beyond the generated preamble: `adjustbox`, `xurl`, `natbib`/`unsrtnat`, `float`, `caption`, `lmodern`. Their presence in Tectonic bundle v33 is assumed, not checked.
   - The layout of the generated tables I have not seen (per-study, platform, cell counts, paired differences, reproduction) is unknown. `\gentable` caps each table at the text width and 0.82 of the text height.
   - **Action:** run `make paper` after the assets are generated, and check the log for overfull boxes and missing packages.
2. **Literal numbers do not update after reproduction.**
   - Pooled values use `\ctres`/`\ctci` macros and will refresh.
   - The following are literals in the text, each with a pointer in `evidence/claims.json`:
     - per-study, platform, calibration, per-class, protein-gate and erythroid count values;
     - τ_err at five decimals;
     - risk-table headings;
     - Arm B top-prediction fractions;
     - resource records.
   - After a Mode F run, these must be re-checked against the claims ledger; they will not change automatically.
   - Some macros render counts as `19018.000` or `11.000`. That is the generator's float formatting of count-like summary columns, so literals were used for those counts.
3. **One methods-review statement is slightly wrong.**
   - Review §3 M7 says M2, M3 and M6 have closed-set accuracy "≥0.94" on Parse and ScaleBio.
   - `platform.csv` gives M2 on Parse as 0.925.
   - The paper says "between 0.92 and 0.98".
4. **The promised HIHA sensitivity analysis is missing.**
   - `historical/evidence/protocol-deviations.md` caveat 1 promises a labelled post hoc sensitivity: practical track excluding HIHA.
   - This run's recorded outputs contain no such pooled estimate.
   - The paper shows per-study values instead, and does not compute an excluded-HIHA pooled value, which would be a new analysis.
   - **Coordinator decision:** produce it under approval, or record that it was dropped.
5. **Not checked by this worker:**
   - script hashes on disk against `provenance.json`; the paper states only that the recorded values match the coordinator's code-check record;
   - directory equivalence: `recovery/armB` against `compare_arms/B`, and `armA_cite` against T01;
   - the per-method runtime and peak-memory records (historical T01 and recovery `6ef42791…`).
   - The protocol §6 runtime metric is disclosed as not reported.
6. **Bootstrap downward bias.** Macro-F1 replicates are slightly biased downward when a class drops out of a replicate (review minor 1). This is not stated in the paper. **Suggestion:** add one sentence to §2.7 if desired.
7. **Bibliography provenance.**
   - Entries cover only sources in `literature/sources.json`.
   - Author lists use `others` where the recorded citation elides authors.
   - Given names were used only where `research.md` records them; otherwise initials are used.
   - The totalVI repository and 10x data are cited inline by URL and commit, not as bib entries, because they are not in `sources.json`.
8. **Approval wording.**
   - The amendment approval was recorded from the user's reply "Ok clean out some old checkouts and continue".
   - The paper gives the date and sha256 only.
   - The reviewed amendment notes that the user had not seen the floors and tolerances before an earlier reply. This author does not judge approvals.
9. **Affiliation and contact.**
   - Tim Richardson, Rewire Bio. The user's email appears as the contact.
   - No credentials, funding or competing interests were invented. The paper carries a placeholder: "Funding and competing-interest statements are to be completed by the author before any submission." **The user must supply these statements.**
10. **Length.**
    - Estimated at about 14–18 pages including the appendix tables. This is unmeasured because the paper was not compiled.

## 5. Validation performed by this worker

- Every macro key used in `main.tex` was checked by eye against `evidence/paper-inputs/results_macros.tex`. The groups are `A`, `B`, `practical`, `score/info`, and `comparison/report`; the metric suffixes include `-at-OPcov`, `-at-OPerr`, `risk-at-0.80`, `val-*` and `diff-vs-*`. No protein macros are used in the text; the protein table is used instead.
- Literal values were transcribed from the files listed in `evidence/claims.json`, which gives exact pointers and full-precision values.
- Derived figures were checked by hand:
  - 75% weight (14,242 / 19,018);
  - 390 natural removed-type cells and the 83% top-up share;
  - about 47 P2 OP-err cells;
  - an 8.8× ratio of the range to the interval width;
  - 93.0% and 94.2% of cells resolved by gates.
- `claims.json` is hand-written JSON. Run a JSON parser over it, for example `python -m json.tool evidence/claims.json`; this worker had no shell to do so.

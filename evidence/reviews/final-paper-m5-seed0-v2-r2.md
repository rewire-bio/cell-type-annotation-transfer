# Final paper review r2: rendered PDF, citations and claims (`m5-seed0-v2`, format rebuild 56fa2cab)

- **Role:** paper/PDF reviewer, final bounded review call 26.
- **Reviewer:** one local Claude Opus model session (`claude-opus-5-5`), independent of author25. This is a model review only. No human review, external review or second reviewer session is claimed, and it is not a scientific verification.
- **Date:** 2026-10-07. Worktree snapshot `8b60ddc547b9248edd1bb90fe4f91ae08c4889f7`.
- **Tools:** Read, Grep and Glob only. I ran no compile, test, command or hash computation, did no web retrieval, and edited no input.

## Subject

- `paper/main.tex`: 722 lines, read in full.
- `evidence/reviews/fresh-reproduction-56fa2cab…/paper.pdf`: 33 pages. I viewed all 33 pages as rendered images, including page 20.
  - Recorded sha `cf3cbf98…`. This equals the 56fa manifest artifact `paper/build/main.pdf` and the format note's `candidate_pdf_sha256`.
  - I did not compute this hash myself.
- **Generated provenance** (`asset_provenance.json`):
  - The inputs are the retained reproduction `continued/score` and `continued/protein` files. Their hashes equal c056's `out/score-1` and `out/protein-1` (for example `summary_test` `d5ce7291…`, `protein_agreement` `b09c2033…`).
  - The comparison input is the 56fa `compare/report.json` (`8b6c2ab6…`).
- **Generated outputs:** `results_macros.tex` (`9193acd6…`), `table_reproduction.tex` (`a5fc59e1…`) and all other generated tables and figures are hash-identical across the 2e1c, 553 and 56fa records.

## Verdict: **PASS** (with the non-blocking findings and limits below)

## 1. Prior FAIL items B1–B6

The prior FAIL concerned the 2e1c build (`final-paper-m5-seed0-v2.md`, preserved). Each item is now resolved in the source text and in the rendered PDF.

- **B1 (fit count).** Section 7, "Reproduction attempts" (PDF p. 24), states that all four permitted fits were used and where:
  - canonical A in 3f18;
  - canonical B in 448f;
  - reproduction A and B in c056.

  It also states that the ledger holds four fit reservations and two scoring reservations. This matches `invocation-ledger.json` and the receipts.
- **B2 (heading).** The limitation heading is now "Internal reproduction of the corrected M5 results." (p. 17). The heading no longer says "pending", and the duplicated sentence is gone.
- **B3 (tense).** The §6 Status (p. 18) and Section 7 "What remains unresolved" (pp. 25–26) are now in the past tense and describe completed execution.
- **B4 (failed attempt and continuation).** c056 is listed under "Failures and attempts" (p. 21) as a failed attempt with exit code 2. It is described as an operational harness failure: all scientific steps had completed and no comparison had run. 2e1c is listed as the exit-0 comparison-only continuation. Both outcomes are kept distinct, which matches the c056 and 2e1c manifests.
- **B5 (commands and runtime).**
  - The baseline-manifest binding and the continuation command (pp. 19–20) match the 2e1c manifest `command`.
  - The internal-only harness variables are disclosed, and public portability is stated as pending.
  - The continuation step times (41.4 / 41.5 / 16.2 / 6.1 s) match the 2e1c receipt.
  - The runtime arithmetic is 10,489.6 + 4,055.4 + 2,079.1 s, giving a cumulative 16,624.054019914955 s explicitly "through 2e1c". This matches the runtime ledger and the 2e1c manifest. Later rebuilds are stated to be recorded separately, and their time is not included.
- **B6 (source hash).** p. 25 explains the d978… → b5a5… hash change using `final-paper-B6-source-binding.json`:
  - paper, references, claims, `methods.py` and tolerances were byte-identical;
  - two continuation approvals were added under the review path;
  - two mechanical helper files were added.

  The paper also states that its own text was revised afterwards. This distinguishes the purely mechanical d978→b5a5 helper addition from the later author25 text revision (`1a6f46…`→`037881e6…`, recorded in 553 `paper_change` with `formatting_only: false`). It also distinguishes the six-wrapper format-only change (`037881e6…`→`3d06fc14…`, recorded in 56fa with `formatting_only: true`). No historical hash equality is claimed after these intentional changes.

## 2. Numbers and claims

All generated values I checked match the packet CSVs. These include:
- the abstract and §3 values;
- Tables 1, 2, 3, 4 and 7–10;
- the risk@0.80 table.

Ledger checks:
- All 27 measurement values in `claims.json` equal the recorded floats.
- The PDF renders them correctly at 3 dp. Examples: M4 0.694 [0.669, 0.716]; M5 0.689; M5−M4 −0.005 [−0.013, 0.003]; coverage 0.817/0.798; Arm B 0.659/0.892/0.833; AUROC 0.441; 4/20; τ_err 0.9999998; protein 0.904 / 6,009 / 0.978.

Literals I spot-checked against the packet, all of which match:
- **Erythroid:** counts 17/13/11/3/4/5; M5 HSPC 0.60; P1 16 and P2 18 erythroid labels.
- **Removed-type labels:** M5 B .853 / γδ T .595 / B .509 (cDC .455); M2 pDC B .451 / cDC .444.
- **Protein:** denominators 5,027–6,331 and 3,306–3,726; M1 5k 0.636/0.938.
- **"Within 0.005":** maximum gap 0.0049.
- **"0.036 or less":** M3 0.036, M6 0.028, M5 0.002.
- **"0 to 16%" OP-err:** M1 0.164.
- **P2 OP-err:** about 47 cells.

**Status text.** The title page, abstract, §1, §5, §6 and §7 render "reproduced within pre-specified tolerance" from the generated macro and call it an internal comparison, not independent verification. Table 5 (p. 19) shows 0 breaches and 0 unsupported for all 14 rows. This matches report `8b6c2ab6…`, and the table bytes are identical to the 2e1c build.

**Historical values.**
- These are 0.688/0.689, 6/20 and 3/20, the Parse/ScaleBio values 0.434/0.548, and Table 6.
- They appear only in Section 7 and are labelled with their source and the 2026-10-07 date.
- The 58-literal inventory is described as historical-only, and `claims.json` as the active ledger.

**Causal and generalisation language.**
- I found no unsupported claim.
- Equivalence is disclaimed.
- The Arm B M6 change "cannot be attributed".
- Platform and protein results are descriptive.
- HIHA and platform label circularity is disclosed.
- Intervals are scoped to four fixed studies, fixed thresholds and one seed.
- The natural unknowns support counts only.

**Labels, platform and licensing.**
- The P1/P2 erythroid artefact is excluded.
- The platform panel is one donor.
- The totalVI per-cell derivatives are not redistributed.
- Public full-baseline portability is pending, and the paper makes no fresh-clone claim.

## 3. Citations

- 37 rendered references carry "Source NN" tags. Web sources carry retrieval dates.
- The literature claims map to `literature/sources.json` (retrieved 2026-10-05):
  - L01 → 27 (Gong 2025, HIHA);
  - L02 → 26 (Cultrera di Montesano 2026);
  - L03 → 17 (Abdelaal 2019);
  - L04 → 01 (scTab).
- The in-text use of these sources is consistent with the claim texts.
- I did not re-retrieve any source. `sources.json` labels its entries as historical retrieval, so citation content is not freshly verified here.

## 4. Page and layout

- **p. 20:** The paragraph with the six `\nolinkurl` environment identifiers (it spans pp. 19–20) is within the margins. Identifiers wrap mid-token but remain legible. I saw no overflow on any of the 33 pages.
- **Cross-references:** I found no broken cross-reference ("??") and no missing citation.
- **p. 18 (cosmetic):** About 55% of the page is blank, because Table 5 `[H]` moves to p. 19.
- **Table 7 (p. 31; cosmetic):** τ_err shows 1.0000 for M4 and M5. This is 4-dp rounding of 0.99998 and 0.9999998, both given in the text and in the Table 2 caption.
- **Figures 1 and 2:** Readable, but the legend text is small.

## Non-blocking findings

- **N1. Same-number provenance.** Table 6's "corrected" column and the generated macros are built from the reproduction outputs. Their values equal the canonical 448f values, because the comparison shows 0 label disagreements and 0.0 confidence difference for M5. The limitation text calls the Table 6 column the "seeded canonical fit". This is numerically harmless, but a release note could say the values are identical by comparison.
- **N2. Paper-only rebuild budget.** The "30 min for a paper-only rebuild" budget is enforced on the asset and build steps (about 22 s). The 553 harness wall-clock duration was 2,992.4 s. The paper does not report post-2e1c rebuild times and says they are recorded separately. See the methods report N2.
- **N3. Unnamed rebuilds.** The paper does not name the 553 or 56fa rebuild IDs. It discloses generically that the text was revised after 2e1c and that rebuilds are recorded separately. This is acceptable, but naming them would aid traceability.

## Not inspected or not possible

- I could not compute sha256 values. I therefore cannot independently confirm that the worktree `paper/main.tex` equals the recorded `3d06fc14…`, or that the PDF bytes equal `cf3cbf98…`. I relied on matching recorded hash strings across the manifest, the format note and the bundle index.
- I did not read the compile logs or `references.bib`; I checked only the rendered references.
- I did not view `fig_paired_differences.pdf`, `fig_unknowns.pdf` or `fig_protein.pdf`. These figures are not included in the rendered paper.
- I did not check `per_class_test.csv`, `calibration_test.csv` or `per_study_test.csv` line by line. Their hashes are unchanged from the prior review, which checked those literals.
- I did not view the earlier 2e1c or 553 PDFs, and did not re-retrieve any citation.

## Blocking findings

None.

# Final paper review: rendered PDF, citations and claims (`m5-seed0-v2`, reproduction 2e1c5df1)

- **Role:** paper/PDF reviewer, review call 24 of the approved 24-call ceiling.
- **Reviewer:** one local Claude Opus model session, independent of the author sessions. This is a model review. No human scientific review and no second independently executed reviewer session are claimed. It is not a scientific verification.
- **Date:** 2026-10-07. Worktree snapshot `98584b1b5e7938722872908a6126d703f62635b2`.
- **Subject:**
  - `paper/main.tex`, 702 lines, read in full;
  - the rendered `evidence/reviews/fresh-reproduction-2e1c5df1…/paper.pdf`, sha `20b85f9c…`, 31 pages. I viewed all 31 pages as images;
  - its generated provenance (`asset_provenance.json`), the active ledger `evidence/claims.json`, the supersession map, and the reproduction score/protein outputs.
- **Tools used:** Read/Grep/Glob only.
  - No compile, test or command was run.
  - No web retrieval.
  - No input was edited.

## Verdict: **FAIL**

**What passes:**
- The numbers are right. Every generated macro and every literal I checked matches the recorded outputs.
- The generated status text correctly binds the actual, successful comparison report.

**Why it fails:** the frozen hand-written prose was authored before the reproduction ran. In the final rendered PDF, it now makes factually false or self-contradictory statements about the reproduction and the M5 fit count. It omits the failed reproduction attempt c056 from its list of failures. It gives reproduction instructions that do not describe the path actually executed. Unsupported claims may not pass.

None of the failures concerns a scientific number. All are bounded text corrections. Repairing them needs a renewed authoring/review allowance, because call 24 was the last approved call.

## Blocking findings

### B1. False current-tense fit count (PDF p. 23)

- **Source:** main.tex L604, Section 7, "Canonical attempts".
- **Text:** "Two of the four permitted M5 fits have now been used, one in attempt 2 and one in run 448f…".
- **Why it is false:** the same PDF (title page, abstract, §6, Table 5) reports that the seed-controlled reproduction was run. The records show all four permitted fits were used: 3f18 A, 448f B, c056 A, c056 B. Evidence: `invocation-ledger.json` (four fit reservations); c056 receipt `A_M5_fit`/`B_M5_fit` with `executed: true`.
- **Required:** state that all four permitted fits have been used, and name where each ran.

### B2. Self-contradictory limitation heading (PDF p. 17)

- **Source:** main.tex L487.
- **Problem:** the bold heading still reads "**Pending reproduction of the corrected M5 results.**". The body says the reproduction "was run and compared … 'reproduced within pre-specified tolerance'".
- **Redundancy:** the next sentence, "Even when a comparison report exists, it is an internal comparison…", repeats the preceding generated sentence.
- **Required:** a heading and wording that do not call the completed gate pending.

### B3. Stale planning prose presented as current (PDF p. 24 and p. 18)

- **Section 7, "What remains unresolved" (L637–638):**
  - It says the reproduction "**is planned** to refit M5 in both arms in a separate checkout…".
  - It says "If that comparison does not pass, the approved plan stops… and the outcome will be reported as it is".
  - Both are now false or moot: the refits happened (c056) and the comparison passed (2e1c). The generated status sentence then follows inside the same bullet. A reader gets a planned-and-completed mixture in one paragraph.
- **§6 Status (L501, PDF p. 18):** it says the reproduction, comparison and compile "are separate later gates; this manuscript does not anticipate their outcome". In the final build these gates have completed.
- **Required:** past-tense statements of what was executed, consistent with B4.

### B4. The failed reproduction attempt c056 and the comparison-only continuation are not disclosed (PDF pp. 18–21, 24)

- **Records:**
  - Reproduction `c056e758…` failed: manifest `status: failed`, exit 2.
  - Its receipt is `stopped` with blocker `'CELLTRANSFER_BASELINE_MANIFEST'`. This happened after it had executed `env`, both seed-0 M5 fits, the predictions, the CITE predictions, scoring and the protein check.
  - The comparison and the PDF were then produced by a separate continuation `2e1c5df1…`. That run re-executed no fit, prediction or scoring. It ran only `env_setup`, `compare`, `paper_assets` and `paper_build`, and retained c056's outputs by hash.
- **What the paper says:**
  - The heading "Failures and attempts (all records kept)" (L556–564) lists earlier failures, 78542e9d, c098 and 3f18, but not c056.
  - No passage says the passing comparison was run in a continuation of a failed attempt.
  - The generated sentence "A seed-controlled reproduction … was run and compared" is literally true, but it elides this two-record structure.
- **Policy:** research-integrity policy requires failed outcomes to be preserved and reported.
- **Required:** add c056 (operational stop before comparison; four fits and two score stages complete) and 2e1c (comparison-only continuation; zero extra fits or scores) to the failure/attempt list and to Section 7. Describe it as an operational harness failure, not a scientific one.

### B5. Reproducibility instructions do not match the executed path (PDF p. 19)

- **What the paper gives:** the M5 reproduction command (L534–535), `scripts/m5_seed_repair.py --stage reproduction …`, with no `CELLTRANSFER_BASELINE_MANIFEST` binding. That is exactly the omission that stopped c056.
- **What actually completed:** the reproduction record ran `scripts/continue_m5_comparison.py --stage reproduction --config configs/m5-seed-repair.json --output results/m5-seed0-v2/reproduction` (2e1c manifest `command`). That script requires `CELLTRANSFER_BASELINE_MANIFEST` and the harness adoption environment variables.
- **Budgets paragraph (L547):** it reports the cumulative total only through the canonical stage (10,489.6 s). It omits the reproduction-stage charges: c056 4,055.4 s and 2e1c 2,079.1 s, for a cumulative 16,624.1 s (`runtime-ledger.json`). That total is still within the 53,970 s ceiling. The paragraph is true as written but incomplete for the final build.
- **Required:**
  - the baseline-manifest binding in the M5 reproduction command;
  - the continuation command and its role;
  - the final cumulative runtime.

### B6. Verification item: manuscript binding (may be benign; must be explained before acceptance)

- The continuation approvals and the adoption inventory bind `frozen_manuscript_hash` `d9786526…`, which is c056's `manuscript_hash`.
- The completed 2e1c manifest records `manuscript_hash` `b5a5e34c…`.
- The records I inspected do not define what the hash covers. If it includes generated assets or build outputs, the change is expected, because only 2e1c generated them. If it covers only `main.tex`/`references.bib`, the manuscript changed after the independent scores existed, and that change is not documented.
- **Required:** the coordinator must show which files the hash covers, or show that the compiled `main.tex`/`references.bib` equal the version bound at `d9786526…`.

## Numerical and claim checks (pass)

### Provenance

- `asset_provenance.json` shows every macro, table and figure was generated from the reproduction's retained score and protein outputs, plus the 2e1c `compare/report.json` (`5b04fe7c…`).
- These score and protein files are byte-identical to the canonical 448f outputs. The hashes match `evidence/reviews/m5-canonical-448f…/bundle-index.json`: `summary_test` `d5ce7291…`, `paired` `01c65206…`, `thresholds` `f1ac14fd…`, `protein_agreement` `b09c2033…`.
- So "results of record from 448f" and "built from the reproduction outputs" give the same numbers in this build.

### Generated status text and Table 5

- The status sentences on the title page, the abstract, §1, §5, §6 and §7 correctly report the overall status "reproduced within pre-specified tolerance".
- They describe the comparison as internal and "not independent verification".
- Table 5 (p. 19) shows 0 gated breaches and 0 unsupported for all 14 arm:method rows, and "Result of record: Mode R (original)". This matches the report.

### Active ledger

- The ledger has 35 claims: 27 measurement, 4 literature, 4 interpretation.
- All 27 measurement values equal the recorded floats in the reproduction packet.
- The rendered text uses them correctly at 3 dp:
  - 32 donors; 1,000 reps; 19,018 cells;
  - M4 0.694 [0.669, 0.716]; coverage 0.817; error 0.087;
  - Arm B M4 0.659, M3 0.892, M5 0.833;
  - M5 macro-F1 0.689; coverage 0.798; error 0.089;
  - M5−M4 −0.005 [−0.013, 0.003];
  - natural-unknown 4/20; AUROC 0.441;
  - τ_err 0.9999998;
  - protein 0.904 / 6,009 / 0.978.

### Corrected-run literals spot-checked against the packet (all match)

- **Per-study M4:** HIHA 0.021/0.940/0.942, JDM 0.056/0.906/0.886, Glaucoma 0.144/0.847/0.707, RA 0.179/0.651/0.518. RA M1 0.353, RA M5 0.507, P1 HIHA 0.842.
- **Range-to-interval ratio:** 0.157 against an interval width of 0.0178, about 8.8×. "Almost nine times" holds.
- **Removed-type labels** (`unknowns_test.csv`): M5 B .853 / γδ T .595 / B .509 (cDC .455); M2 pDC B .451 / cDC .444.
- **Erythroid:** counts 17/13/11/3/4/5. M5 HSPC 0.60. P1 16 and P2 18 erythroid calls; P1 14/20 and P2 20/20 false acceptances.
- **Platform:** M5 Parse 0.434 / ScaleBio 0.552 accuracy, with acceptance 0.469 and 0.604. M1 0.211/0.223. P2 0.194 (0.130) and 0.179 (0.110).
- **Protein:** 6,375/6,855 and 3,762/3,994. Denominators 5,027–6,331 and 3,306–3,726. M1 5k 0.636/0.938. CD16 mono 46/43.
- **Natural-unknown intervals:** every Arm A and practical natural-unknown interval contains its point estimate. For example, M5 0.2 in [0, 0.211]. The "none excluded" sentence holds.
- **Paired-mean vs point-difference gap:** at most 0.001 for the quoted differences (for example M5 macro-F1: 0.0001).

### Historical values

- The historical values (Table 6; 6/20 and 3/20; 0.688/0.689; Parse/ScaleBio 0.434/0.548) are confined to Section 7.
- They are labelled with their source run and the 2026-10-07 failure-review date.
- They match the failure review E1/E2/NB2 and the supersession map.
- The original 58-literal inventory is correctly described as historical-only.

### Causal and generalisation language

- I found no unsupported causal or generalisation claim.
- Equivalence is explicitly disclaimed.
- The Arm B M6 change is "cannot be attributed".
- The platform and protein checks are labelled descriptive.
- The HIHA circularity is disclosed.
- The intervals are scoped to four fixed studies, fixed thresholds and one seed.

### Label, platform and licensing statements

- The P1/P2 erythroid scoring artefact is excluded from comparison.
- The platform panel is one donor.
- The totalVI per-cell derivatives are stated as not redistributed.

## Citations

- **Matching:** the 37 rendered references carry "Source NN" tags and retrieval dates for web sources. The 4 literature claims map to `literature/sources.json` entries with URLs and retrieval dates of 2026-10-05:
  - L01 → 27 (HIHA, Gong 2025);
  - L02 → 26 (Cultrera di Montesano 2026);
  - L03 → 17 (Abdelaal 2019);
  - L04 → 01 (scTab).
- **Interpretation:** the in-text interpretation is consistent with the claim texts.
- **Not re-verified:** I did not re-retrieve any source in this call. Citation content is therefore not freshly verified here. `sources.json` itself labels its entries as historical retrieval, not fresh verification.

## Non-blocking page and layout findings

- **p. 18:** about two thirds of the page is blank, because Table 5 (`[H]`) is pushed to p. 19. This is cosmetic.
- **Table 7 (p. 29):** shows τ_err as 1.0000 for M4/M5 in both arms, while the text gives 0.99998 and 0.9999998. This is 4-dp rounding. A caption note would stop readers inferring τ = 1.
- **Typesetting:** long hashes and file paths wrap mid-token (for example pp. 2, 7, 21–24). They remain legible.
- **Figures:** Figures 1–2 are readable at print size, but the legend text is small.
- **Overflow and references:** no table overflows the text block. I found no broken cross-reference ("??") or missing citation on any of the 31 pages.

## Not inspected or not possible

- I compiled nothing. I did not inspect `paper/build` logs, `references.bib` beyond its rendered output, `results_macros.tex` or the generated `.tex` tables directly, or `fig_paired_differences.pdf`, `fig_unknowns.pdf` and `fig_protein.pdf`. Those three figures are not included in the rendered paper.
- I did not inspect the per-cell data, `per_class_test.csv`, `calibration_test.csv` or `cell_counts.csv` (Arm B recall/precision literals, ECE/Brier prose, and the 390 natural removed-type cells). For these I checked only that the prose matches the rendered generated tables.
- I did no external re-retrieval of citations.

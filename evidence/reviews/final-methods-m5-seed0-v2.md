# Final methods review: corrected M5 result version `m5-seed0-v2` and its seed-controlled reproduction

- **Role:** methods reviewer, review call 24 of the approved 24-call ceiling.
- **Reviewer:** one local Claude Opus model session, independent of the author sessions. This is a model review. No human scientific review is claimed, and no second independently executed reviewer session is claimed. It is not a scientific verification.
- **Date:** 2026-10-07. Worktree snapshot `98584b1b5e7938722872908a6126d703f62635b2`.
- **Subject:**
  - corrected canonical run `448f32386dfe45588fefa84c5d486703` (results of record);
  - failed independent reproduction `c056e758da6842f59e611930ec06bb17`;
  - comparison-only continuation `2e1c5df1e88948cea0d9cfb29a9ad522`. Status `completed`, exit 0, code revision `f8070d06…`, overall "reproduced within pre-specified tolerance".
- **Tools used:** file Read/Grep/Glob only.
  - I ran no command, test, fit, prediction, scoring, comparison or build.
  - I did no web retrieval and no outreach.
  - I edited no input. This report is my only output for the methods review.

## Verdict: **PASS** (scientific methods, execution lineage and strict comparison)

- The design, the baselines and the uncertainty treatment are sound for the stated, deliberately narrow claims.
- The approved correction is the only scientific change. The records support four actual M5 fits and two score stages.
- The strict tiered comparison passed under unchanged tolerances. Its outcome is recorded faithfully.
- Failed attempts are preserved as failures. None is relabelled as a success.
- The non-blocking findings below should be recorded but do not invalidate the result.
- **This PASS does not cover the manuscript/PDF.** That is assessed in `evidence/reviews/final-paper-m5-seed0-v2.md`, which FAILS on text and claim accuracy about the completed reproduction.

## 1. Question, data, splits and leakage

- **Question.** The protocol asks two things, both answerable with this design: which annotation workflow to use for a new blood/PBMC cohort, and when to accept a label (`protocol.md` §1–2).
- **Data and splits.**
  - Reference, validation, test and platform data all come from Census LTS 2025-11-08.
  - The four test studies are each held out whole.
  - Validation studies are used only for thresholds and M4's C.
- **Leakage controls.**
  - Disclosed prior inspection was metadata only (protocol L5).
  - Absence from scTab training and the CellTypist build date are recorded (L28).
- **Residual training-overlap uncertainty.** This is disclosed for:
  - HIHA labels guided by CellTypist and Seurat;
  - the platform consensus labels;
  - the CITE donors.
- **Licensing.**
  - Census data are CC BY 4.0.
  - The totalVI repository has no licence file, so the h5ad files, derived query files, ADT tables, per-cell protein classes and per-cell CITE predictions are withheld.
  - The supplied public packet contains only aggregate protein outputs (`protein_agreement.csv`, `gates.json`). Per-cell parquet files appear in the bundle index only as paths and hashes.
  - I treat the packet as an aggregate review packet. It is not a claim that the withheld files are redistributed. Public release packaging is still pending.

## 2. Baselines, preprocessing and seeds

- **Matched baselines.** Matched M1–M6 share the reference cells, labels and feature set F. M4 was named as the paired comparator before any result (protocol L89). The practical track is kept separate and is not used for architecture claims.
- **Preprocessing and gene mapping.**
  - The gene mapping uses the Census table only. Zero-filling is disclosed.
  - The CITE feature coverage figures (79.1/77.2/79.2/77.8 %; scTab 66.9/66.3 %) are quoted from the amendment disclosures. I did not re-derive them.
- **Seeds.** I inspected `companion/src/celltransfer/methods.py`:
  - M5 now calls `celltypist.train(..., n_jobs=4, random_state=0)` at L153–154.
  - The preserved original `evidence/reviews/m5-original-methods-1e95aac.py` has the same call without `random_state` at L153–154.
  - M2/M3 PCA (L71), M4 (L133) and M6 (L190, L209) are already seeded with 0.
- **Science and protocol hashes.** The protocol hash `d3bbc2c0…` and the science hash `8abf7524…` are identical in the c056 and 2e1c manifests.
- **Limits of my check.**
  - I could not compute file sha256 values with my tools, so I rely on the recorded hashes.
  - The "only scientific change" claim rests on the line-level comparison above plus the unchanged science hash. I did not diff the full files.

## 3. Uncertainty, bootstrap and thresholds

- **Bootstrap.**
  - 1,000 donor-cluster replicates, resampled within each fixed test study, with seed 20261005 (`score_info.json`).
  - Paired against M4 within replicates.
  - Bootstrap weights and IDs are identical across stages: `bootstrap_weights.npy` `79375c46…`, `bootstrap_ids.csv` `f52fb5db…`.
- **Threshold handling.** Thresholds are fixed on validation and are not re-estimated inside the bootstrap. This is disclosed.
- **Undefined replicates.** 126 replicates are undefined for natural unknowns, and OP-err is not attainable for M3/M6 (`bootstrap_nan_counts`). Both are disclosed and handled conservatively.
- **Macro-F1 bias.** Absent classes score 0 and the replicate is kept. The resulting downward bias is disclosed.
- **What the intervals exclude.** Seed, threshold-estimation and study-level variance are explicitly excluded from the intervals. That is correct for four fixed studies.
- **Validation-selected thresholds** (`thresholds_validation.csv`, `f1ac14fd…`):
  - M3 tie inflation is visible (0.943 and 0.924 validation coverage against the nominal 0.900).
  - P2 τ_cov is −inf because its validation cap is 0.798.
  - The OP-err τ values for M4, P2 and M5 are at the probability ceiling (A:M5 0.9999997674; B:M5 0.9999997589).
  - All of this is correctly treated as close to degenerate.
- **Natural-unknown scope.** `--natural-unknown-scope natural` is in the score command, and `scoring_scope.json` (`b6bf9027…`) records it. That is the approved D-1a scope. There are 20 erythroid cells, and only counts are interpreted. This is appropriate.
- **Protein gate.**
  - Descriptive only, on replacement inputs.
  - Gates resolved 6,375/6,855 and 3,762/3,994 cells. CD16 mono had 46 and 43 cells (`gates.json`).
  - The two agreement measures have different denominators, and no ranking is drawn. This is appropriate.
- **Platform panel.** One donor per platform. Descriptive only. This is appropriate.

## 4. Execution lineage, invocation count and selective adoption

### Fit and score invocations

The invocation ledger (`invocation-ledger.json`, `fa9907e1…`) holds exactly four fit reservations and two score reservations, each stamped "reserved before invocation".

| Reservation | Stage | Run | Record |
|---|---|---|---|
| A fit 12:10:47Z | canonical | 3f18 | receipt step `A_M5_fit` executed, ok, model `111e03c3…` |
| B fit 12:51:29Z | canonical | 448f | receipt step `B_M5_fit` executed true, 501.2 s, model `15829b4c…` |
| score 13:00:04Z | canonical | 448f | receipt `score` executed, 613.4 s |
| A fit 14:17:32Z | reproduction | c056 | receipt `A_M5_fit` executed true, 759.5 s |
| B fit 14:30:21Z | reproduction | c056 | receipt `B_M5_fit` executed true, 526.0 s |
| score 14:39:23Z | reproduction | c056 | receipt `score` executed true, 615.7 s |

- **Canonical Arm A fit.** Run 448f retains the 3f18 fit with `executed: false`, `source_run` 3f18 and source step hash `7e52e4a6…`. There was no refit.
- **c056.**
  - Both M5 models record `random_state 0` and `solver sag`. A `5c3d0f67…`, B `fad495bd…`.
  - The c056 receipt adopts no M5 artefact from any canonical run (adopted file paths contain no `_M5_` entry).
- **Counts.** The bundle index states `successful_actual_M5_fit_steps: 4` and `newly_executed_successful_fit_steps_in_completed_receipts: 1`. Both are consistent with the records above.
- **Scope statement.** This is a fresh non-M5 lineage, adopted from failed reproduction 78542e9d with fits from 727c…/7860…/108d…, plus two newly executed seed-0 M5 fits. It is not a claim that all 12 fits ran again.

### Comparison-only continuation 2e1c

- **Retained steps.** The receipt has 8 retained steps, each with `executed: false`, `wall_seconds: 0`, `source_reproduction` c056, a source step hash, the source command and copied-file hashes. The retained step hashes match the bundle index and the r2 approval binding.
- **Executed steps.** Exactly four steps ran: `env_setup` (41.4 s), `compare` (41.5 s), `paper_assets` (16.2 s) and `paper_build` (6.1 s).
- **Fail-closed checks in `scripts/continue_m5_comparison.py`.** I read it in full. It:
  - refuses any step other than these four;
  - requires the c056 receipt to be `stopped` with blocker `'CELLTRANSFER_BASELINE_MANIFEST'`, every step `ok`/`executed true`, and `non_m5_equality` passed;
  - requires the four-fit/two-score ledger snapshot to equal the live ledger, with no reset;
  - binds the canonical baseline manifest hash to the approved `canonical_manifest_sha256` `60cfbe95…`.
- **Approval.** `m5-seed-repair-independent-comparison-continuation-approval-r2.json` records `remaining_fits 0`, `remaining_scores 0`, `fit_invocations 4` and `continuation_only true`.

### Failure preservation

- **c056.**
  - Manifest `status: failed`, `exit_code 2`, failure "Clean reproduction command failed".
  - Receipt `status: stopped`, blocker `'CELLTRANSFER_BASELINE_MANIFEST'`.
  - It is preserved byte-identical as a lineage file (`7d222651…`) and is not relabelled.
  - 2e1c is a separate record, `execution_kind: comparison_build_only_continuation`, `reproduction_continue_of` c056.
  - The failure is presented as an operational harness omission before comparison, not as a successful attempt.
- **c098.**
  - Manifest `failed`, exit 143, "storage budget exceeded".
  - The receipt still says `status: running` with `steps: []`. Per instruction, I do not require that preserved receipt to be rewritten.
  - The empty step list and the invocation ledger (no reservation before 12:10:47Z) are consistent with no fit or score having occurred.
- **3f18.** Manifest `failed` (exit 1). Receipt `stopped` after `env` and `A_M5_fit`.

### Historical results

- They are superseded, not lost.
- `evidence/claims-history/claims-original-29879296.json` and `evidence/paper-claim-inventory.json` (58 literals, historical-only) exist alongside `m5-seed0-v2-supersession.json`.
- The supersession map records M07→M21, M08→M22 and I01→I05 with their historical values.

## 5. Strict comparison (canonical 448f vs reproduction 2e1c)

- **Report.** `comparison-report.json`, original sha `5b04fe7c…`.
  - Tolerances `tolerances-v2.json`, sha `c335e6a9…`. This is the same file as in the 78542e failure review, so it is unchanged.
  - Overall "reproduced within pre-specified tolerance".
  - 1,521 checks, 0 gated breaches or structural failures, 0 unsupported gated checks, `failures: []`.
- **Ungated unavailable check.** The one ungated unavailable check is NaN-replicate counts, which are descriptive.
- **Per-cell agreement.**
  - My search found no T2 or diagnostic per-cell check with agreement below 1.0, and no non-zero `max_abs_conf_diff_agreeing`.
  - So every M5 file (and M6 diagnostically) agreed exactly per cell, although the M5 model pickles differ in bytes: canonical A `111e03c3…` vs reproduction `5c3d0f67…`.
- **Score and protein files.** The reproduction's `summary_test.csv`, `paired_differences_vs_M4.csv`, `thresholds_validation.csv` and `protein_agreement.csv` are byte-identical to the canonical run's outputs. The hashes match `evidence/reviews/m5-canonical-448f…/bundle-index.json`.
- **Non-M5 outputs.** All 12 arm×method entries plus P1/P2 report 0 breaches. That includes the independently fitted non-M5 lineage (for example, M6 checkpoint hashes differ from the canonical sources: A `0bb4cb3f…` vs `0b210fcc…`).

## 6. Claim ledger support (methods view)

- **Ledger shape.** The active `evidence/claims.json` has 35 claims: 27 measurement, 4 literature, 4 interpretation.
- **Measurement values.** I compared every measurement value against the reproduction packet:
  - `summary_test.csv`;
  - `paired_differences_vs_M4.csv`;
  - `thresholds_validation.csv`;
  - `protein_agreement.csv`;
  - `score_info.json` (test_donors 32, reps 1000);
  - eligibility (`n_eligible 2`, per the comparison report).
- **Result.** All 27 values match the recorded floats exactly, including:
  - M04 0.6943348958883646;
  - M21 −0.012919452282817398;
  - M22 0.002966559580046049;
  - M26 0.2;
  - M28 0.44078880463892267;
  - M29 0.9999997673623983.
- **Ordering qualifiers.** These also hold: M24 is the lowest Arm A coverage, and M28 is the lowest Arm B AUROC and below 0.5.
- **Interpretations.** I02–I05 stay within their bases and limitations. I05 correctly avoids an equivalence claim.

## Non-blocking findings (record; no change to verdict)

- **N1. Provenance label on executed continuation steps.** The 2e1c receipt labels `env_setup`, `compare`, `paper_assets` and `paper_build` with `provenance: "recomputed seed-controlled M5 repair"`. These are not M5 recomputations. The `kind` and `executed` fields are accurate. The label is inherited driver text and could mislead an automated reader.
- **N2. Inherited comparison-manifest flags.**
  - The reproduction comparison manifest keeps `mode: F` and `fresh_execution: true`, copied from c056.
  - Its `provenance` block correctly states "M5 only; unaffected outputs independently fitted in failed fresh parent".
  - Readers should rely on the `provenance` block.
- **N3. Runtime charges exceed the recorded start/finish interval.**
  - c056 is charged 4,055.4 s, but its `started_at`→`finished_at` interval is about 2,524 s.
  - 2e1c is charged 2,079.1 s, against an interval of about 581 s and a receipt `wall_seconds` of 110.9 s.
  - The ledger is internally consistent: 7,085.1 + 302.7 + 1,187.7 + 1,914.1 + 4,055.4 + 2,079.1 = 16,624.1 s, which equals the cumulative total.
  - Overcharging is conservative and well inside the 53,970 s effective ceiling.
  - The basis of the charge is not explained in the records I inspected.
- **N4. `runtime-ledger.json` uses `status: "finished"` for failed attempts** (c098, 3f18, c056). That means "stage ended", not success. Outcome status must be read from the manifests, which correctly say `failed`.
- **N5. Manuscript hash binding is not explained.**
  - The r2 approval and the adoption inventory bind `frozen_manuscript_hash` `d9786526…`, which equals c056's `manuscript_hash`.
  - The completed 2e1c manifest records `manuscript_hash` `b5a5e34c…`.
  - The records I inspected do not define what this hash covers. The difference may be benign: c056 never generated paper assets, and 2e1c did. But I cannot confirm that `paper/main.tex` and `references.bib` were unchanged between the two.
  - It does not affect scientific linkage, because the science and protocol hashes are equal. It is forwarded to the paper review as a verification item.
- **N6. Stale deviation record.** `evidence/protocol-deviations-m5-seed0-v2.md` §4 and §6 still say "Two of the four permitted M5 fits have been used" and that the reproduction is "pending".
  - This is accurate as a dated record.
  - The coordinator should add a dated addendum recording c056 (failed, missing baseline variable, all four fits and both scores done) and 2e1c (comparison passed). The current status is otherwise documented only in approvals and the bundle index.
- **N7. Stale worker-input list.** `worker-inputs.json` inside the bundle lists an older input set (for example `final-methods-r2.md` and `continue_reproduction.py`). It is not authoritative for this review.

## Inspected

**Reproduction bundle `evidence/reviews/fresh-reproduction-2e1c5df1…/`:**
- `bundle-index.json`, in full;
- `reproduction-manifest.json`;
- `generation-receipt.json`: L1–120, L200–742, and step records via search;
- `comparison-manifest.json`;
- `comparison-report.json`:
  - header/summary L1–200;
  - M5 and M6 check samples around L3486–3605 and L3990–4019;
  - searches for every non-pass status, breach, agreement below 1 and non-zero confidence difference;
- `canonical-generation-receipt.json`, via search;
- `runtime-ledger.json`, `invocation-ledger.json`;
- `lineage/failed-independent/c056…/manifest.json`;
- `lineage/failed-independent/c056…/generation_receipt.json`, via search;
- `lineage/failed-canonical/c098…` and `3f18…` manifests and receipts, via search;
- `results.json`, head and search;
- `paper/generated/asset_provenance.json`;
- `score/summary_test.csv`, `paired_differences_vs_M4.csv`, `thresholds_validation.csv`, `unknowns_test.csv`, `platform.csv` (searched), `per_study_test.csv` (searched);
- `inputs/score/score_info.json`;
- `protein/protein_agreement.csv`, `protein/gates.json`;
- `adoption-inventory.json`, via search;
- `sanitization-disclosure.md`, `worker-inputs.json`.

**Other files:**
- `protocol.md`, via search;
- `protocol/tolerances-v2.json`, in full;
- `evidence/protocol-deviations-m5-seed0-v2.md`;
- `evidence/reviews/m5-seed-repair-execution-note.md`;
- `evidence/reviews/m5-reproduction-failure-review.md`;
- `evidence/claims-history/m5-seed0-v2-supersession.json`;
- `evidence/claims.json`;
- `scripts/continue_m5_comparison.py`, in full;
- `scripts/m5_seed_repair.py` (`equal_non_m5`, `Repair.__init__` head);
- `companion/src/celltransfer/methods.py`, via search;
- `evidence/reviews/m5-original-methods-1e95aac.py`, via search;
- `evidence/reviews/m5-seed-repair-independent-comparison-continuation-approval-r2.json` (L1–30, L260–340, search);
- `evidence/reviews/m5-canonical-448f…/bundle-index.json`, via search;
- `literature/sources.json`, via search.

## Not inspected or not possible

- Any parquet, h5ad, pickle, npy or per-cell prediction file.
- The large per-cell confidence arrays in the comparison report beyond the searches described. I do not claim to have read them.
- Full-text diffs of `methods.py`, or computing any sha256. I have no hashing tool, so I rely on recorded hashes.
- `per_class_test.csv`, `calibration_test.csv`, `cell_counts.csv`, `risk_coverage_test.csv` and `bootstrap_ids.csv` contents.
- The adoption inventory beyond searches.
- The private-retention originals.
- Harness source code, so I could not determine the definition of `manuscript_hash`.
- The live `.research/` records outside the supplied bundle.
- No external literature was re-retrieved.

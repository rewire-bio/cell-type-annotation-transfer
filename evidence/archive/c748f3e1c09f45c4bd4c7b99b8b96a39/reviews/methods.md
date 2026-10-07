# Final methods review r2: corrected M5 seed repair (`m5-seed0-v2`), paper-format rebuild 56fa2cab

- **Role:** methods reviewer, final bounded review call 26 under the approved 26-call ceiling.
- **Reviewer:** one local Claude Opus model session (`claude-opus-5-5`), independent of the author session (call 25). This is a model review. It is not a human scientific review, not two independently executed reviewer sessions, and not a scientific verification.
- **Date:** 2026-10-07. Worktree snapshot `8b60ddc547b9248edd1bb90fe4f91ae08c4889f7`.
- **Tools:** Read, Grep and Glob only. I ran no command, compile, test, hash computation or web retrieval, and I edited no input. Where this report says two hashes are equal, I compared hash strings already recorded in the frozen records. I did not compute any hash myself.

## Verdict: **PASS** (with the non-blocking findings and inspection limits below)

The evidence supports these statements:
- The scientific design, the statistics and the claim ledger are sound for the stated, conditioned scope.
- The only scientific change is the M5 `random_state=0` argument.
- The repair used exactly four seed-0 M5 fits and two scoring stages.
- Failed attempts are kept as failures.
- The final paper-format rebuild invoked no scientific step.
- The strict comparison of record reports 0 gated breaches.

I found no blocking finding.

## 1. What I inspected

**Final rebuild packet** (`evidence/reviews/fresh-reproduction-56fa2cab…/`):
- `reproduction-manifest.json`;
- `generation-receipt.json` (step list, model identities, non-M5 equality block, retained-step bindings);
- `comparison-report.json` (header, per-arm:method outcomes, counts, failures, ungated items; I grep-searched all 1,521 check entries for non-pass statuses, label disagreements and nonzero confidence differences);
- `bundle-index.json`;
- `runtime-ledger.json` and `invocation-ledger.json`;
- `canonical-generation-receipt.json` (448f);
- `score/summary_test.csv`, `score/paired_differences_vs_M4.csv`, `score/thresholds_validation.csv` and `score/unknowns_test.csv`;
- `inputs/score/score_info.json`;
- `protein/protein_agreement.csv`;
- `paper/generated/asset_provenance.json`.

**Lineage records:**
- c056: manifest and receipt;
- 2e1c: manifest and receipt;
- 553: manifest and receipt;
- c098: manifest and receipt;
- 3f18: manifest and receipt.

**Other inputs:**
- `protocol.md`, read in relevant parts: seeds, sampling, splits, overlap exclusions, bootstrap, comparator;
- `evidence/claims.json`, all 35 entries;
- `evidence/claims-history/m5-seed0-v2-supersession.json`, read in part;
- `evidence/protocol-deviations-m5-seed0-v2.md`;
- `evidence/reviews/m5-seed-repair-execution-note.md`;
- `evidence/reviews/m5-paper-text-repair-approval.json` and `m5-paper-text-repair-plan.md`;
- `evidence/reviews/final-paper-B6-source-binding.json`;
- `evidence/reviews/m5-paper-layout-repair/format-note.json`;
- `evidence/reviews/m5-author25-provenance/resolved.json`;
- `evidence/reviews/final-paper-m5-seed0-v2.md` (the prior FAIL review);
- `scripts/continue_m5_comparison.py`, grep of guards;
- `scripts/rebuild_m5_paper.py`, grep of guards;
- `companion/src/celltransfer/methods.py`, grep of seed arguments;
- `literature/sources.json`, the entries for claims L01–L04;
- `paper/main.tex`, read in full.

**Not inspected or not possible:**
- I did not compute sha256 values, so I cannot independently confirm that the worktree `paper/main.tex` hashes to the recorded `3d06fc14…`.
- I did not open any per-cell parquet, model pickle, `bootstrap_weights.npy`, large confidence array or omitted per-cell file.
- I did not read the full `adoption-inventory.json` or the full `tolerances-v2.json` content. I compared only the tolerance file hash string `c335e6a9…`, as recorded in the report and in the B6 binding.
- I did not re-retrieve any external source.
- No human review took place, and I claim none.

## 2. Question, data, splits and leakage

- **Question and design.** The protocol asks which annotator to use for a new blood/PBMC cohort and when to accept a label. Whole-study holdout (four test studies) and separate validation studies (two) are appropriate to that question. Thresholds and M4's C were set on validation only; the paper discloses this double use of validation as mild.
- **Provenance and licensing.**
  - All RNA data come from Census LTS 2025-11-08 (CC BY 4.0).
  - The totalVI replacement CITE files have no licence file. Their per-cell derivatives are stated as not redistributed.
  - I reviewed the public packet as aggregate outputs only. It contains `protein_agreement.csv` and `gates.json`. I saw no per-cell protein classes or CITE predictions in the packet file list, and the paper makes no claim that withheld files are redistributed.
- **Training overlap with the released models.**
  - The protocol records that the evaluation studies are absent from scTab's 249 training datasets, share no donors with scTab's lookup, and post-date the CellTypist build.
  - For the protein files, donor identity and overlap are unknown, and the paper discloses this.
  - HIHA labels were partly CellTypist-guided. The paper discloses this circularity.
- **Preprocessing and gene mapping.** Features were selected on the reference only. CITE gene mapping used the Census symbol table, and the zero-fill fractions are disclosed (F_A 79.1%/77.2%; scTab 66.9%/66.3%).

## 3. Baselines, seeds and the single scientific change

- **Matched baselines.** M1–M6 were trained on identical reference cells and features. M4 was pre-specified as the comparator.
- **The seed change.** `methods.py` now passes `random_state=0` to `celltypist.train` (L153–154). M2/M3 PCA and M4 were already seeded (L71, L133).
- **What stayed unchanged.** The B6 binding records `methods.py` `d2cb0cde…` and `tolerances-v2.json` `c335e6a9…` as byte-identical across d905→f807. The comparison report's tolerance sha is also `c335e6a9…`. The deviation record lists solver, `max_iter`, data, thresholds, metrics, bootstrap and tolerances as unchanged. I found no contrary evidence.
- **Model identities.**
  - Both canonical receipts and the reproduction receipt record `random_state: 0` and `solver: sag`.
  - Reproduction model hashes are A `5c3d0f67…` and B `fad495bd…`.
  - Canonical model hashes are A `111e03c3…` and B `15829b4c…`.
  - The pickle bytes differ, but the predictions are identical (Section 6).

## 4. Four fits and two score stages, and lineage integrity

**Invocation ledger.** It holds exactly four fit reservations (canonical A, canonical B, reproduction A, reproduction B) and two score reservations (canonical and reproduction).

| Fit | Where it ran | Receipt evidence |
|---|---|---|
| Canonical A | failed attempt 3f18 | `executed: true`, 744.05 s |
| Canonical A, retained | run 448f | `executed: false`, `source_run` 3f18, step `7e52e4a6…`, model `111e03c3…` |
| Canonical B | run 448f | `executed: true`, 501.2 s; scoring 613.4 s and protein check 10.6 s also ran there |
| Reproduction A and B | failed attempt c056 | `executed: true`, 759.5 s and 525.95 s |

**c056 (failed).**
- Scoring (615.7 s) and the protein check (6.2 s) also ran in c056.
- Its manifest records `status: failed` and `exit_code: 2`.
- Its receipt records `status: stopped` with blocker `'CELLTRANSFER_BASELINE_MANIFEST'`.
- It is preserved as a failure and is not relabelled as successful.

**2e1c (comparison-only continuation).**
- Exit code 0, cumulative 16,624.054019914955 s.
- It lists the eight c056 steps as `executed: false`, each with source step hashes.
- It executed only `env_setup` (41.4 s), `compare` (41.5 s), `paper_assets` (16.2 s) and `paper_build` (6.1 s).

**553 (paper-text rebuild of 2e1c).**
- Records `paper_change` from `1a6f46…` to `037881e6…` with `formatting_only: false`.
- Executed only `env_setup`, `compare`, `paper_assets` and `paper_build`. Every scientific step has wall time 0.

**56fa (format-only rebuild).**
- Records `paper_change` from `037881e6…` to `3d06fc14…` with `formatting_only: true`, bound to `format-note.json` (sha `4a8ebbfd…`).
- Its receipt nests the bindings 56fa → 553 → 2e1c → c056. At each level the copied-file hashes are identical to c056's `out/*` hashes; for example, model `5c3d0f67…` and `summary_test` `d5ce7291…`.
- It executed only `env_setup` (30.5 s), `compare` (41.4 s), `paper_assets` (16.1 s) and `paper_build` (5.9 s).
- It made no new fit, prediction, scoring, bootstrap, data acquisition or protein invocation.

**Format note.** It covers exactly six `\verb`→`\nolinkurl` wrappers. `main.tex` L532 has six `\nolinkurl{RESEARCH_ADOPTION_*}` identifiers, which agrees with that scope.

**Selective adoption.**
- The c056 receipt adopts no M5 artefact from 78542e9d, 727c2514 or 448f (grep found 0 matches).
- The non-M5 equality check (summary, thresholds, cell counts, bootstrap ids and weights) records `passed` in c056, 2e1c and 56fa.

**c098.**
- Its manifest records `failed`, exit 143, "storage budget exceeded".
- Its receipt keeps the stale driver `status: running`, with no step and 3.1 s.
- The invocation ledger has no reservation that predates 3f18 for that stage, so no fit or score happened. As instructed, I do not require rewriting that receipt.

**3f18.** Its manifest records `failed`, exit 1. Its receipt is `stopped` with the identity-check blocker. Both failures are preserved and charged.

**Historical results.** The original unseeded M5 claims M07, M08 and I01 are mapped as `superseded` to M21, M22 and I05 in the supersession record. The 58-literal inventory is preserved as historical-only. Nothing is lost.

## 5. Statistics, uncertainty and thresholds

- **Bootstrap.** 1,000 donor-cluster replicates within each study (seed 20261005, `score_info`), with paired differences against M4. The scope of the intervals is clearly stated: conditional on fixed thresholds and one seed, with no study-level interval.
- **Validation-selected thresholds.** They are fixed and carried to the test set.
  - M3 ties give a validation coverage of 0.943/0.924, which is disclosed.
  - P2 has τ_cov = −inf, because its eligible validation cap is 0.798. This is disclosed.
  - The OP-err thresholds at the probability ceiling (M5 0.9999997674/0.9999997589) are flagged as near-degenerate.
- **Natural unknowns.**
  - These are 20 erythroid cells. 126 replicates contained none, and the paper reports counts only.
  - The M4 interval [0.105, 1.000] is called uninformative.
  - The P1/P2 erythroid scoring artefact is excluded from comparison.
  - D-1a natural scope is recorded.
- **Protein gates.** The check is descriptive and per file. The two agreement denominators are explained, and no ranking is drawn.
- **Platform panel.** One donor; descriptive only.

## 6. Strict comparison of record

**Report header and counts.**
- Report `8b6c2ab6…`; overall status "reproduced within pre-specified tolerance".
- 1,521 checks, 0 gated breaches or structural failures, 0 unsupported.
- `failures: []`.
- One ungated unavailable item: `nan_replicate_counts`, because `score_all.py` does not write it.

**Per arm and method.** All 14 arm:method rows have 0 breaches.

**M5 per-file checks.** Label disagreements are 0, and `max_abs_conf_diff_agreeing` is 0.0 in every M5 file I grep-searched. No check has a fail status.

**Why the outputs match canonical.** The seed-0 reproduction exactly repeated the canonical per-cell M5 outputs. This explains why the reproduction-built macros equal the canonical ledger values.

**Check count.** The failed historical comparison had 1,523 checks and this one has 1,521. I did not trace the difference of 2. It does not affect the gated outcome.

## 7. Claim ledger

- The ledger has 35 entries: 27 measurement, 4 literature and 4 interpretation.
- I matched every measurement value exactly to the packet:
  - `score_info`: 32 donors, 1,000 reps;
  - `summary_test`: M03, M04, M11–M16 and M23–M28;
  - `paired_differences_vs_M4`: M05, M06, M09, M10, M21 and M22;
  - `thresholds_validation`: M29;
  - `protein_agreement`: M17–M19;
  - the report's `n_eligible` 2: M20.
- The interpretations I02–I05 are worded within their stated limitations.

## Non-blocking findings

- **N1. Labels on the 56fa receipt steps.** The executed `env_setup`, `compare`, `paper_assets` and `paper_build` steps carry `provenance: "recomputed seed-controlled M5 repair"`. That is a generic driver label and not accurate for build-only steps. The receipt `scope` field ("all scientific steps retained without invocation") and the steps list are correct, so this is cosmetic. It should not be read as an M5 recomputation.
- **N2. Paper-only budget versus harness time.**
  - The approved `paper_seconds` budget is 1,800 s. The drivers enforce it as the step budget for asset generation plus build: the build timeout is 1,800 minus the asset time. Those steps took about 22 s.
  - The harness wall-clock duration of the 553 rebuild was 2,992.4 s, and that of 56fa was 381.7 s.
  - If the "30 min for a paper-only rebuild" in the paper were read as harness wall-clock time, 553 would exceed it.
  - The cumulative 19,998.17 s is well within the 53,970 s effective ceiling, and the plan states that the remaining total takes precedence.
  - I recommend that the coordinator state the budget definition explicitly in release notes.
- **N3. Stale pending section in the deviation record.** Section 6 of `protocol-deviations-m5-seed0-v2.md` still says the reproduction was "pending". The file is a dated, preserved record that the paper does not rely on, but a short pointer to the outcome would help readers.
- **N4. Seed scope.** One seed only, so no seed variance is estimated. The cause of the unseeded disagreement is not isolated beyond the seed. Both points are disclosed and do not block.

## Blocking findings

None.

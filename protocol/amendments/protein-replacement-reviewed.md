# PROPOSED amendment (reviewed): two totalVI author-hosted files for the protein check (NOT APPROVED)

Status: **proposal only, not approved, not executed.** It supersedes `protocol/amendments/proposed-protein-replacement.md` (the unedited draft). The reasons for every change are in `protocol/protein-replacement-review.md`.

This text was produced by the methods-reviewer worker on 2026-10-06 at snapshot `81e1f91d29990da243b16fdb32e6298f9449e527`. Neither the reviewer nor any other agent can approve it.

**What the user has and has not seen.** After being shown the two candidate files and their preprocessing limitations, the user said "sounds great, continue" (reported by the coordinator). The user has **not** seen:
- the numerical eligibility floors (§6);
- the per-file eligibility rule;
- the attempt accounting (§10);
- the tolerance changes (§7).

These are material. They take effect only through the **single** approval described in §12.

**Outcome blinding.** No CITE predictions, protein classes, GMM fits or agreement values exist, and none were looked at. The only things inspected were:
- file-level metadata (`evidence/protein-replacement/inspection.json`);
- the metadata-only overlap audit;
- the upstream scripts.

**Coordinator-reported facts.** The following are not recorded in the frozen evidence files:
- (C1) The commit-pinned `raw.githubusercontent.com` URLs in §2.2 served both files, and the bytes matched the pinned sha256 and size. No LFS fallback was needed.
- (C2) The 10x HTTP 403 used up R4 attempt 1 of the 2 approved.
- (C3) Free disk is currently below 1 GiB.
- (C4) The user's "sounds great, continue", as quoted above.

---

## 1. Question, contribution and claim boundary

**Question, unchanged from protocol §1/§7.** For RNA predictions accepted at each method's validation OP-cov threshold, how often does the accepted label agree with a coarse protein class from fixed ADT gates?

**What changes.** Only the inputs, and how much can be claimed from them.

**What the replacement can support.** A **descriptive, exploratory, secondary** comparison, reported per file, on up to two 10x PBMC samples that the totalVI authors filtered upstream.

**What it cannot support:**
- Ground truth, accuracy validation, or any holdout, transfer or generalisation claim. Training overlap is unknown (§4.3).
- Any claim about donors or replication. Donor identity, and therefore independence, is **unknown** (§4.2). No interval is computed.
- A like-for-like substitute for the four-file check in the frozen protocol. Two planned files have no replacement, including the only 5′/TotalSeq-C file, and one is replaced by a different 10x sample (§2).
- A matched-track method comparison. About 20% of F is zero-filled, and this affects methods unequally (§5, §4.5).

**Hypotheses.** None. No confirmatory test and no decision rests on this check.

**Original results are preserved.** The following are not recomputed, overwritten or reinterpreted:
- the core analysis (protocol §§2–6, D-1a, platform, uncertainty);
- every existing matched-track and practical-track run directory and result;
- tolerances v1.

CITE outputs are written only to new run directories. No fit is rerun.

## 2. Input change

### 2.1 Original inputs (preserved byte-for-byte)

Protocol §2 lists four 10x CDN `filtered_feature_bc_matrix.h5` files: `pbmc_10k_protein_v3` (3.0.0), `5k_pbmc_protein_v3_nextgem` (3.0.2), `10k_PBMCs_TotalSeq_B_3p` (6.0.0) and `vdj_v1_hs_pbmc3` (3.1.0).

**Observed:**
- Only the first file was requested.
- It was one plain `urllib` request on 2026-10-06T17:29:32Z, and it returned **HTTP 403** (`evidence/cite-access-blocker.json`).
- Files 2–4 were **not requested**. Their availability is **unknown**.
- The substitution is therefore not forced by demonstrated unavailability of files 2–4. This must be disclosed (§11).

The following stay unchanged:
- `protocol.md`
- `companion/scripts/build_cite.py`
- `companion/scripts/protein_check.py`
- `protocol/tolerances.json` (v1)
- `evidence/cite-access-blocker.json`

### 2.2 Replacement inputs (two files)

Source: `https://github.com/YosefLab/totalVI_reproducibility`, commit `27d65a9c49182f39df0c4325249bc7dc8e663dd0`, directory `data/`.

| `<name>` | File | sha256 (pinned, inspection 2026-10-06T18:02:29Z) | bytes | cells | genes (symbols) | non-control ADT |
|---|---|---|---|---|---|---|
| `totalvi_pbmc5k_protein_v3` | `pbmc_5k_protein_v3.h5ad` | `a1bf51e070d24b39627ea4de9b3e489a4637ff795e1061e0733e26c3baec8847` | 18,294,964 | 3,994 | 16,581 | 29 |
| `totalvi_pbmc10k_protein_v3` | `pbmc_10k_protein_v3.h5ad` | `5f08b8575febf9e04b209b94eb43f6335f1e33b0985cdcf44adf7320f6243c69` | 24,937,137 | 6,855 | 16,727 | 14 |

**Sole URL per file** (commit-pinned and immutable; C1):
`https://raw.githubusercontent.com/YosefLab/totalVI_reproducibility/27d65a9c49182f39df0c4325249bc7dc8e663dd0/data/<file>`

- There is no alternate host and no LFS fallback.
- **Binding identity:** the sha256 and the byte count. A response that matches neither, or that is HTML or an LFS pointer, is a failure and is never accepted.
- **Cached bytes:** the bytes inspected earlier may be used instead of a new GET, but only if they are still present unmodified, they match both pins, and the manifest labels them `cached` with their path (OA-3).

**How the files map to the plan (disclose exactly):**
- **`pbmc_10k_protein_v3.h5ad`.** Same 10x sample as planned file 1: `pbmc_10k.py` loads `Dataset10X("pbmc_10k_protein_v3")`. It was filtered and reprocessed by the authors.
- **`pbmc_5k_protein_v3.h5ad`.** This is `5k_pbmc_protein_v3`, **not** the planned `5k_pbmc_protein_v3_nextgem` (`pbmc_5k_v3.py` loads `Dataset10X("5k_pbmc_protein_v3")`). It is a different 10x library and chemistry run. Donor relation to either other sample: unknown.
- **Planned files 3 and 4 have no replacement.** As a result there is no 5′ chemistry and no CellRanger 6 data.

## 3. Preserved protein-check method

These are unchanged:
- Census pin, sampling, seeds, G, F_A/F_B, K/K_B, markers, M1–M6, P1/P2, arms, operating points, metrics, D-1a, uncertainty, and the JDM CITE-seq **test** study (Census RNA).
- The protein check, done by `companion/scripts/protein_check.py` (unchanged; hash recorded at E8):
  - per-cell CLR, `log1p(x) − row mean`;
  - a 2-component GMM per antibody with `random_state=0` and posterior > 0.5;
  - the six fixed gates and the exactly-one-gate rule;
  - agreement at the validation τ_cov;
  - `agreement_accepted` and `agreement_accepted_gateable_preds`;
  - P1/P2 via `released_predictions_<name>.parquet`.
- Frozen CITE QC is re-applied (≥200 detected genes, <20% mitochondrial counts).
- **Prediction uses existing models.** CITE prediction runs the existing Arm A `model.pkl` through `run_matched.py --stage predict --model-dir`. M6 per-query `load_query_data` with 50 unlabelled epochs is part of its approved predict stage. It runs once per eligible file and is not a reference refit.

## 4. Biases and limitations that cannot be removed (must be disclosed)

### 4.1 Upstream filtering cannot be undone

Taken from `pbmc_10k.py` and `pbmc_5k_v3.py`. The "direction" column is interpretation, not measurement.

| Step | 10k | 5k | Likely direction |
|---|---|---|---|
| DoubletDetection removal (`p_thresh=1e-7, voter_thresh=0.8`) | yes | yes | Removes cells likely to be multi-gate or discordant; may **inflate** agreement and the resolved fraction |
| min_genes 200 | yes | yes | Same as our QC |
| Mitochondrial fraction cut | **< 0.10** | < 0.20 | 10k is stricter than ours, so the two files differ in QC strictness |
| n_genes < 4500, n_counts < 20000 | yes | yes | Removes high-complexity cells |
| ADT library size 400–20000 ("manually selected based on histogram") | yes | yes | Hand-chosen; likely makes gating easier; cannot be reproduced from first principles |
| IgG isotype controls removed | yes | yes | The CLR row mean excludes isotype controls, unlike the planned raw files. The number removed is not recorded in the evidence. 10k has only 14 non-control antibodies. |
| Genes expressed in < 4 cells removed | yes | yes | Absent genes are zero-filled later. Library-size denominators shrink slightly. |
| `var_names_make_unique` on symbols; Ensembl IDs not kept | yes | yes | Mapping depends on symbols only (§5) |

Agreement on these files is agreement **on an author-curated subset of cells**. It is not comparable with what the frozen raw-file check would have produced.

### 4.2 Donor identity and independence unknown

- The files contain no donor IDs (`overlap-audit.json`).
- Whether the two samples share donors is **unknown**, either way.
- Results are reported per file only: no pooling, no cross-file averaging, no interval. Protocol §6 forbids cells as the unit of uncertainty.

### 4.3 Training overlap unknown

The audit was metadata-only:
- no title or DOI match among scTab's 249 training datasets, but 3 training IDs are unmapped;
- both samples predate CellTypist v2 (2022-07-16);
- the matched-track references were not audited.

No holdout or generalisation claim is made, especially for P1/P2.

### 4.4 Licence

- **Repository: no licence found.** Two checks on 2026-10-06 found none:
  - `api.github.com/repos/YosefLab/totalVI_reproducibility/license` returned 404 (no licence detected);
  - the top-level contents at the pinned commit contain no LICENSE or COPYING file.

  Both were read through a summarising tool, and the coordinator should confirm them.
- **10x source data:** the terms were not verified. Hence no republication (§9).

### 4.5 Zero-filled features are not neutral

- **M1–M3** z-score with the reference mean and SD. A zero-filled gene becomes a systematic −mean/SD value, not "missing".
- **P2 (scTab)** receives about a third of G as zeros.
- The frozen pipeline zero-fills missing genes too, so nothing is changed here. The effect is disclosed.

## 5. Deterministic symbol → Ensembl mapping (fixed before any outcome)

**Reference.** The pinned Census LTS `2025-11-08` var table `runs/data/census_2025-11-08_var.parquet`. It must pass its logical-digest check in `protocol/input-acquisition.md`. No alias resource and no manual edits are used.

**Procedure**, per file. Matching is exact and case-sensitive. `eid` is `feature_id` without the version suffix.

1. `S(sym)` is the set of `eid`s with Census `feature_name == sym`.
2. **Make-unique groups.** If `v` matches `^(.+)-(\d+)$` and its base `b` is also a var name in the file, every member of `{b, v, …}` gets `ambiguous_make_unique` and is excluded. The excluded names are listed.
3. Otherwise:
   - `|S(v)| == 1` → `mapped`
   - `> 1` → `ambiguous_census`
   - `0` → `unmapped`
4. **Collisions.** Var names that map to the same `eid` all get `ambiguous_collision`.
5. **Columns.** Mapped `eid`s go in G order. Missing G genes are zero-filled. `query_<name>_F.h5ad` is G restricted to F_A ∪ F_B, as in the frozen builder.
6. **P1** receives all h5ad genes under their symbols, with no mapping.

**Residual risk (disclose):**
- A lone symbol whose duplicate partner was removed upstream may correspond to a different gene. This cannot be detected.
- Symbol drift creates false zeros.

**Coverage report** (`mapping_<name>.json` and `.csv`):
- counts per status;
- present/total for G, F_A, F_B, markers_A and markers_B;
- per-class marker coverage for K and K_B;
- the difference from the feasibility counts below.

### Observed metadata feasibility (not realised coverage)

Source: `inspection.json` `mapping_feasibility`, using a looser rule ("exact unique feature_name in pinned G only"). These are observed counts. The frozen mapping is stricter, so realised coverage is **less than or equal to** these.

| File | G present | F_A present | F_B present |
|---|---|---|---|
| 5k | 12,957 / 19,331 (67.0%) | 1,565 / 2,020 (77.5%) | 1,576 / 2,016 (78.2%) |
| 10k | 13,064 / 19,331 (67.6%) | 1,603 / 2,020 (79.4%) | 1,605 / 2,016 (79.6%) |

**Not measured:** how the missing genes split between upstream gene filtering (removed for being expressed in < 4 cells) and symbol mismatch.
- For G, part of the loss is expected from the upstream filter, given about 16.6–16.7k surviving symbols. This is inference.
- For F, the split is unknown.

These numbers must not be quoted as realised coverage.

## 6. Eligibility (per file, fixed before any prediction)

**Timing.** Every criterion is evaluated in R4′ from metadata, names and counts only. This happens **before** any CITE prediction, GMM fit or agreement value.

**Disclosure about the floors.** The coverage and marker floors in items 4–5 were set **after** the feasibility counts were seen, but before any outcome. They are engineering floors and are reported as such.

**Per-file rule.** Each file is eligible or ineligible on its own:
- an ineligible file is dropped;
- an eligible file proceeds;
- if no file is eligible, the protein check is "not run".

| # | Criterion | Pass condition |
|---|---|---|
| 1 | Identity | sha256 and byte count match §2.2 |
| 2 | Structure | Shape `(3994, 16581)` / `(6855, 16727)`; protein matrix `(3994, 29)` / `(6855, 14)`; protein names identical in order to `inspection.json`; RNA and ADT are non-negative integers; barcodes unique; no ADT name starts with `IgG` |
| 3 | Mapping reference | Passes its digest check. A failure here stops **both** files. |
| 4 | Coverage (frozen mapping) | F_A ≥ 0.75, F_B ≥ 0.75, G ≥ 0.60, **and** no fraction more than 0.01 below its feasibility fraction in §5 |
| 5 | Marker coverage | Each K class corresponding to a gate (CD4 T, CD8 T, B, NK, CD14 mono, CD16 mono, under their K names) has ≥5 of its 10 `markers_A` mapped |
| 6 | Gate availability | `protein_check.find` applied to column **names** only shows all six gates available. This is stricter than frozen §7, which skips missing gates, and is a disclosed change. Reviewer reading of the names expects CD3, CD4, CD8a, CD14, CD16, CD19 and CD56 in both files, plus CD20 in 5k (unused because CD19 is present). E4 confirms this. |
| 7 | QC retention | Re-applying the frozen QC keeps ≥ 99% of h5ad cells (≤ 39 lost in 5k, ≤ 68 lost in 10k). Lost barcodes are listed. |

**Eligibility record.** `runs/<R4′>/eligibility.json` holds the verdict and the first failing criterion for each file. It is written and hashed **before** any query file or released prediction is built.

**On ineligibility:**
- Log "replacement ineligible: <file>, <criterion>" in `evidence/protocol-deviations.md`.
- Do not relax any criterion, try another mapping, or substitute another file.
- §11 wording applies to that file.
- If a mapping regression (criterion 4, drop > 0.01) stops a file, report it and return to the user; do not fix it within this amendment.

## 7. Expected counts and tolerances v2

**CITE query files: 4 → `n_eligible`.** This is the number of files with verdict `eligible` in `eligibility.json` (0, 1 or 2). It is fixed in R4′ before any prediction. For eligible files, the expected cells after QC are 3,994 / 6,855, minus any listed losses. The realised counts become T1-exact.

`protocol/tolerances.json` **v2** is a new file; v1 is retained unchanged. Its content is fixed by this table, and its sha256 is recorded at E8. No tier is widened.

| Field | v1 | v2 |
|---|---|---|
| `T2_labels.expected_query_files.CITE` | 4 | `n_eligible` read from the hashed `eligibility.json` |
| `T1_exact.adt_count_tables` | 4 files | the eligible files (29 / 14 non-control columns) |
| `T2_labels` per CITE file | `max(1, ⌊0.001·n⌋)` | unchanged formula (3 for 5k, 6 for 10k at full n) |
| `T2_protein_gating` | same formula | unchanged |
| `M_metrics.protein_fields` | close(0.01, 0) | unchanged, over the eligible files |
| **Added to T1** | — | input sha256 equal to pins; `eligibility.json` verdicts identical; `mapping_<name>.csv` identical; post-QC barcode list identical |

If Mode F reaches a different eligibility verdict from Mode R, that is a T1 breach and is reported as such. Final verification covers "the eligible replacement files" in place of "all four CITE files".

## 8. Execution order (single sequence)

No step that touches real data starts below the approved disk guard: **≥ 3 GiB free**, **≥ 4 GiB for R5** because M6 trains query adaptation, and a kill below 1.5 GiB. No study data, inputs, runs or evidence may be deleted to meet the guard.

| Order | Step | Content | Pass |
|---|---|---|---|
| 0 | Approval | Coordinator records the user's approval of **this file** with its sha256 (§12) | the record exists |
| 1 | Code | Write `companion/scripts/build_cite_totalvi.py`, its tests and `tolerances.json` v2. `build_cite.py` and `protein_check.py` stay unchanged. | — |
| 2 | E7 | Unit tests (no real data): mapping rules; hash mismatch fails closed; HTML or LFS-pointer response fails; output columns | all pass |
| 3 | E6-synthetic | 50-cell fixture built from the real var and ADT **names** with fabricated counts. It is labelled synthetic and excluded from results. `run_matched.py --stage predict` and the unchanged `protein_check.py` must read the builder outputs without modification. | passes |
| 4 | E8 | Coordinator records sha256 of this amendment, tolerances v2, the builder, the tests and `protein_check.py` | recorded |
| 5 | Disk guard | Free space ≥ 3 GiB | met |
| 6 | **R4′** (= R4 attempt 2, the last) | **E1:** a single GET per file of the §2.2 URL, or verified cached bytes, into `runs/<R4′>/inputs/` (git-ignored). Byte cap 64 MiB per file, atomic write. The manifest records the URL or cache path, UTC time and any error. **E2–E5:** §6 criteria 2–7. Then write `eligibility.json`. **E6-real:** for eligible files only, write `query_<name>_F.h5ad` (`assay="10x CITE-seq (totalVI-processed)"`), `adt_<name>.parquet`, `released_predictions_<name>.parquet` (P1/P2) and `receipt.json` with the mapping summary. | §6; outputs schema-valid |
| 7 | Disk guard | Free space ≥ 4 GiB | met |
| 8 | **R5** | CITE predict for M1–M6 with the existing Arm A models, eligible files only | — |
| 9 | **R7** | `protein_check.py` | — |

**Blinding.** Protein classes and agreement values are first produced in R7. Neither CITE predictions nor protein values are viewed before R4′ has written `eligibility.json`.

**Mode F.** The counterparts use the same pins, code and order.

## 9. Acquisition, storage and redistribution

**Publication.** Published material is limited to:
- URLs, commit, sha256 and byte counts;
- the builder and the mapping rules;
- the mapping summary, including the list of excluded symbols;
- the eligibility verdicts;
- aggregate results.

**Not committed or published:** the h5ad files, `query_*_F.h5ad`, `adt_*.parquet`, per-cell protein classes and per-cell CITE predictions. They stay local in git-ignored run directories.

**Licence statement:** "totalVI reproducibility repository: no licence file found (GitHub API, 2026-10-06); terms of the 10x source data not verified by us."

## 10. Budgets and attempts (no ceiling changes)

**Resources:**
- local compute only, four threads, 12 GiB memory watchdog;
- 7 GiB study storage cap; about 43 MB of downloads.

**Time ceilings:**
- Mode R stage: 8 h. Time already spent on R4 counts against it.
- Per step: R4′ 20 min, R5 30 min, R7 15 min.
- Mode F as approved. Clean reproduction 15 h. Paper only 30 min.
- Nothing is extended, and no time is reallocated.

**Attempts:**
- The 403 was R4 attempt 1 (C2). **R4′ is attempt 2, the last.** Each file gets one GET, with no in-helper retries and no alternate host.
- Any R4′ failure ends the replacement, including infrastructure failures (network, memory-stop, guard-stop). The R4′ attempt directory is kept, the §11 stop wording applies, and control returns to the user.
- R5 and R7 keep their 2 approved attempts each.
- No failure triggers a refit.

## 11. Required disclosures (paper, blog, results table)

1. "The study's protocol (v1.0, frozen locally on 2026-10-05; not externally registered) pre-specified four 10x CITE-seq files. Only the first was requested; it returned HTTP 403 on 2026-10-06. The other three were not requested, so their availability is unknown. Under an amendment approved on <date>, we instead used author-processed files from the totalVI reproducibility repository (commit 27d65a9c…), sha256 …"
2. "The 5k file is 10x `5k_pbmc_protein_v3`, not the pre-specified `5k_pbmc_protein_v3_nextgem`. No replacement was used for `10k_PBMCs_TotalSeq_B_3p` or the 5′ `vdj_v1_hs_pbmc3`."
3. "Both files were filtered by the totalVI authors (doublet removal, mitochondrial and complexity caps, manually chosen ADT library-size limits, isotype-control removal, gene filtering). These choices cannot be undone. They may raise the agreement compared with unfiltered data."
4. "Genes were mapped from symbols to Ensembl IDs using only the Census 2025-11-08 table. <realised %> of matched-track features and <realised %> of scTab genes were present; absent genes were set to zero, which is not neutral after z-scoring. Differences between methods on these files therefore mix method behaviour with robustness to missing genes."
5. "Donor identity is unknown for both files, so we cannot say whether they come from independent donors. Training overlap with the released models is unknown. Results are descriptive, per file, with no interval and no generalisation or holdout claim. Protein gates are a coarse orthogonal check, not ground truth."
6. Every CITE result is labelled **"descriptive; replacement inputs (amendment <id>)"**. If only one file was eligible, say so, and give the other file's failing criterion.

The realised percentages in item 4 come only from E3 output.

**If the replacement stops** (no eligible file, or R4′ fails): "No orthogonal protein check was performed. Of the four 10x files pre-specified in the locally frozen protocol, the only one requested returned HTTP 403; the replacement files <failed eligibility criterion X | could not be acquired or built in the final permitted attempt>. Accuracy is measured against author labels only."

## 12. Approval boundary

**One approval.** A single explicit user approval of this file, recorded by the coordinator with its sha256 in a new dated file under `protocol/amendments/`, authorises everything in §8. That includes the eligibility rule and floors (§6), the attempt accounting (§10), tolerances v2 (§7), the disclosures (§11) and the no-republication rule (§9). Implementation details need no separate decision.

**Replacement or deferral.** The user should approve this file or `proposed-cite-deferral.md`, not both. The deferral wording applies automatically if this replacement stops.

**Not authorised:**
- any other substitute file;
- requesting the remaining 10x files;
- alias or manual gene rescue;
- relaxing any §6 criterion or the floors once E3 has run;
- pooling across files;
- any refit;
- changing any existing result or tolerances v1;
- using CITE results in primary or headline claims;
- further R4 attempts;
- deleting data to free disk;
- merge, deployment or submission.

Any change after approval needs renewed approval and is logged in `evidence/protocol-deviations.md`.

**Current precondition (C3).** Free disk is below 1 GiB, which is under the guard in §8. Even after approval, steps 5 onward cannot start until enough space exists by means other than deleting study data.

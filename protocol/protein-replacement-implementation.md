# Protein-replacement implementation (amendment step 1 and E7)

Status: **code and synthetic tests only.** No real data was downloaded, opened or built. No prediction, refit, GMM fit or agreement value was produced, and none was inspected. No result values appear here. Author: research-engineer worker (claude-opus-5-5), 2026-10-06, snapshot `2bc2066af9086172d2dbdd39d5069e7300501807`.

**What this implements.** `protocol/amendments/protein-replacement-reviewed.md`, sha256 `e5ba0c34…eae1`. A test recomputes that hash and checks it against the approval record `protocol/amendments/2026-10-06-approved-protein-replacement.md`.

**What stays unchanged** (byte-identical, as `git status` shows):
- `companion/scripts/build_cite.py`
- `companion/scripts/protein_check.py`
- `protocol/tolerances.json` (v1)
- `scripts/recover.py`, `scripts/reproduce.py` and `scripts/compare_runs.py`

## 1. Artifacts

| Path | Purpose |
|---|---|
| `companion/scripts/build_cite_totalvi.py` | Replacement builder. Covers E1 acquisition, criteria 2–7 (E2–E5), the hashed eligibility record and E6-real outputs, plus the tolerances-v2 helpers. |
| `tests_protein_replacement/` | E7 unit tests: `test_pins_mapping.py`, `test_flow.py`, shared fixtures in `_support.py`, and the runner `run_tests.sh`. `_tmp/` is the only scratch location and is git-ignored. |
| `protocol/tolerances-v2.json` | Tolerances v2 (§7). v1 is retained, and v2 records v1's sha256 `98a41d81…5d7b`. |
| this file | Contract and integration notes. |

**Dependencies.** None were added. The builder uses the stack already pinned in `pyproject.toml`/`uv.lock`:
- numpy 1.26.4, pandas 2.2.3, scipy 1.13.1, anndata 0.12.19, pyarrow 17.0.0, scikit-learn 1.5.2;
- celltypist and torch, reached only through the unchanged `celltransfer.released` in E6-real.

The module imports only the standard library at the top level. Heavy imports are lazy, so `plan` and the comparison helpers run without the scientific stack.

## 2. Commands

```
# pins only; no network, no writes
python companion/scripts/build_cite_totalvi.py plan

# R4' (= R4 attempt 2): E1 -> E2-E5 -> eligibility.json(+.sha256) -> E6-real, one process
python companion/scripts/build_cite_totalvi.py r4prime --workspace <repo> --data <frozen data run> \
    --out runs/<R4'> [--cache-dir <dir holding the inspected h5ad bytes>] [--min-free-gib 3]

# the same phases separately (metadata-only phases never import prediction code)
python companion/scripts/build_cite_totalvi.py acquire     --data D --out runs/<R4'> [--cache-dir C]
python companion/scripts/build_cite_totalvi.py eligibility --data D --out runs/<R4'>
python companion/scripts/build_cite_totalvi.py build       --data D --out runs/<R4'>

# E7 (synthetic + mocks only). PYTHON must provide the pinned stack; it is used read-only.
sh tests_protein_replacement/run_tests.sh <PYTHON>
```

**Exit codes:**

| Code | Meaning | Effect |
|---|---|---|
| 0 | success, including `outcome: not_run` when `n_eligible == 0` | — |
| 2 | R4′ failure: network, HTTP status other than 200, timeout, byte cap, or E6 schema failure | The replacement stops (§10). The attempt directory is kept. |
| 3 | configuration error, detected **before any request**: wrong data run, disk below `--min-free-gib`, or a non-empty `--out` | No request is made. |
| 4 | `eligibility.json` missing, tampered or internally inconsistent | `build` refuses to run. |

## 3. Behaviour, mapped to the amendment

**E1, acquisition (§2.2, §10).**
- **Source.** One GET per file of `https://raw.githubusercontent.com/YosefLab/totalVI_reproducibility/27d65a9c…/data/<file>`. There are no retries, no alternate host and no LFS fallback, and the second file is not requested once the first has hit a transport failure.
- **Download handling.** The download streams to a `.part` file. A 64 MiB cap is enforced on `Content-Length` and again while streaming. The write is fsync'd and atomic, into `runs/<R4′>/inputs/`.
- **Manifest.** `acquisition.json` records the URL or cache path, `requests` (1 or 0), UTC times, HTTP status, content type and any error.
- **Cached bytes (`--cache-dir`).** The cached file must match the sha256 and byte pins **before** it is copied. It is labelled `source: cached` with its path. A cache mismatch fails closed **without** falling back to a GET.

**Criterion 1, identity.** The byte count and sha256 must equal the pins. A response is never accepted if it has an HTML content type or body, is an LFS pointer, or is not HDF5. The bytes are re-verified on disk when eligibility is evaluated.

**Criteria 2–7.** Evaluated per file, in order. The first failure stops that file, and the remaining criteria are recorded as `not_evaluated`.
- **2, structure.** RNA shape and ADT shape equal the pins. ADT names equal `inspection.json`, in the same order. RNA and ADT are non-negative integers. Barcodes are unique, and ADT rows align with them. No ADT name starts with `IgG`. Var names are unique.
- **3, mapping reference.** The logical digest of `runs/data/census_2025-11-08_var.parquet` must be `c6f8bc7c…` (the same function and constant as `scripts/acquire_inputs.py`; both are checked by tests). A failure here stops **both** files.
- **4, coverage.** The frozen §5 mapping is applied. The F_A, F_B and G fractions are compared as **exact rationals** with the floors 3/4, 3/4 and 3/5, and with the rule "no more than 1/100 below the feasibility fraction". Tests pin the boundaries: 5k F_A passes at 1545/2020 and fails at 1544; G passes at 12764/19331 and fails at 12763.
- **5, markers.** Each of the six gate classes needs ≥ 5 mapped `markers_A`.
- **6, gate availability.** Checked on ADT column **names** only, with the unchanged `protein_check.MARKERS`/`find`. All six gates must be available. The gate→antibody requirement table is checked against `protein_check.gate_cells` on synthetic data.
- **7, QC retention.** The frozen QC is ≥ 200 detected genes and an MT fraction < 0.20 (strictly less). The pass rule is `kept/n ≥ 99/100`, giving at most 39 lost cells in 5k and at most 68 in 10k. Lost barcodes are listed.

**Mapping (§5).**
- Matching is exact and case-sensitive. Census feature IDs lose their version suffix.
- Make-unique groups follow `^(.+)-(\d+)$` when the base name is also present. Statuses are `ambiguous_census` and `unmapped`, with collisions marked `ambiguous_collision`.
- **`mapping_<name>.csv`** is deterministic. Columns: `index,var_name,status,eid,census_eids,in_G,in_F_A,in_F_B`, in file order, with LF line endings.
- **`mapping_<name>.json`** holds:
  - the count per status;
  - present/total for G, F_A, F_B, markers_A and markers_B;
  - per-class marker coverage for K and K_B;
  - the difference from the feasibility counts;
  - the excluded var names.
- Mapping files are written for every file that reaches criterion 4, including files that are then ineligible.

**Eligibility record, written before any outcome.**
- **Files.** `eligibility.json` is written once, together with `eligibility.json.sha256`. It is written before any query file, released prediction, ADT table, gate or agreement exists, and a test checks this.
- **Contents:**
  - the verdict per file and its first failing criterion (number and name);
  - the details of every criterion that was evaluated;
  - `eligible_files`, `n_eligible` and `outcome` (`run` / `not_run`);
  - the sha256 of the amendment, the builder, `protein_check.py` and `acquisition.json`;
  - `deviation_log_lines`, the exact wording "replacement ineligible: <file>, criterion N (<name>)" for the coordinator to log.
- **Barcodes.** `barcodes_qc_<name>.txt` holds the post-QC barcode list, for eligible files only.
- **No prediction code.** A test checks that `eligibility` imports no prediction code (`celltransfer.released`, `celltypist`).

**E6-real, eligible files only.**
- **Preconditions.** Before writing anything, `build` checks that:
  - `eligibility.json` matches its `.sha256`;
  - each input's sha256 is unchanged;
  - the post-QC barcodes are identical to `barcodes_qc_<name>.txt`.

  It then uses exactly the hashed `mapping_<name>.csv`. If `n_eligible == 0` it writes `receipt.json` and `coverage.json` with `outcome: not_run` and calls no predictor.
- **Outputs:**
  - **`query_<name>_F.h5ad`.** Raw counts (verified integer, converted to float32 CSR) in G order with missing genes zero-filled, restricted to F_A ∪ F_B, written through `celltransfer.census_data.to_anndata` with gzip.
    - The obs columns are `soma_joinid, barcode, study, role, donor_id, stratum, label_status, target, assay, total_counts_all, total_counts_G`.
    - `assay` is `"10x CITE-seq (totalVI-processed)"`.
    - `total_counts_all` is the sum over all genes in the h5ad. This is the frozen definition applied to the author-filtered gene set (§4.1).
  - **`released_predictions_<name>.parquet`.** P1 through `celltypist_annotate` on **all h5ad genes under their symbols**. P2 through `ScTab.annotate` on the G-ordered matrix. Both come from the unchanged `celltransfer.released`, and `soma_joinid` comes first.
  - **`adt_<name>.parquet`.** `barcode` plus the pinned non-control antibodies, as int64. Rows are in the same order as the query and the released predictions.
  - **`receipt.json`.** Source (`get`/`cached`), pins, cells, the ADT obsm key, the mapping summary, the eligibility sha256 and seconds.
  - **`coverage.json`.** Machine-readable verdicts and mapping coverage across both files, aggregates only (§9).
  - **`features_and_classes.json`.** Copied from the data run, because `run_matched.py --stage predict` needs it.
- **Schema check.** `validate_outputs` checks the outputs; on failure the builder exits with code 2.

## 4. Implementation readings the coordinator should confirm (none relaxes a criterion)

1. **Two kinds of acquisition failure.**
   - **Transport or infrastructure failures** raise an R4′ failure that ends the replacement (§10): exception, HTTP status other than 200, timeout, or byte cap. No `eligibility.json` is written, and `acquisition.json` holds `status: failed`.
   - **Received bytes that fail the pins** (wrong hash or size, HTML, LFS pointer) are recorded as a **criterion 1 failure for that file only** (§6 row 1). The other file still gets its single GET.
2. **Cached mode.** A cached file that fails its pins is an R4′ failure. There is no GET fallback, because the cache path and a GET are alternatives chosen up front, not a retry chain.
3. **Pre-request checks.** The configuration and disk checks (exit 3) run before E1 and make no request. Whether such a stop consumes R4 attempt 2 is a matter for the coordinator's accounting; the builder records nothing as an attempt.
4. **Data-run totals.** The data run's G/F_A/F_B totals must equal the feasibility totals (19,331 / 2,020 / 2,016). Otherwise the §6.4 regression rule would compare against a different denominator, so a mismatch is treated as a configuration error.
5. **Criterion 5 edge cases.** A gate class missing from K or `markers_A` fails criterion 5 (fail closed). A class that lists fewer than 10 markers still needs ≥ 5 mapped.
6. **Locating the ADT matrix.** The evidence records the ADT names and shape but **not** which AnnData slot holds them. The builder identifies the slot by content: exactly one `obsm` entry (a DataFrame, or an array with `uns["<key>_names"]`/`uns["protein_names"]`) whose names equal the pinned list in order and whose shape is (n_obs, n_proteins). Zero or several candidates fail criterion 2. The key used is recorded.
7. **`target` column.** In `obs`, `target` is an all-missing categorical. In the synthetic test, an all-`None` object column, which is the frozen `build_cite.py` construction, raised `TypeError: Can't implicitly convert non-string objects to strings` when written under the pinned anndata 0.12.19. That was observed in this builder before the fix. **The frozen `build_cite.py` itself was not executed**, so its behaviour is inferred, not observed.

## 5. Tolerances v2 contract (dynamic `n_eligible`)

**What changes from v1.** `protocol/tolerances-v2.json` differs from v1 only in:
- `schema`, `source` and `note`;
- `T1_exact.items`, which gains `replacement_input_sha256_equals_pins`, `eligibility_verdicts`, `mapping_csv` and `post_qc_barcodes`;
- `T2_labels.expected_query_files.CITE`.

It also adds descriptive scope keys. Every numeric tolerance is identical to v1, and a test checks this.

**Rules a comparison must follow:**

1. **Expected CITE count.** `CITE = {"rule": "n_eligible", …}` is resolved **only** from the Mode R `<cite dir>/eligibility.json`, after verifying it against `eligibility.json.sha256`. The resolver is `build_cite_totalvi.expected_cite_files(cite_dir)`. It returns `n_eligible`, `eligible_files` and the record sha256. If the record is missing or tampered, the result is a structural failure; a count is never assumed.
2. **File sets.** In each mode, the CITE `released_predictions_*`, `adt_*` and `query_*_F` file sets must equal that mode's `eligible_files` **exactly**. The Mode F record must also give identical verdicts.
3. **Added T1 items.** `build_cite_totalvi.t1_replacement_checks(cite_dir_R, cite_dir_F)` returns one `{"tier":"T1","item",…,"status":"pass"|"breach"}` per check:
   - each `acquisition.json` identity sha256 equals its pin, for both files and both modes;
   - the verdict and first-failing-criterion number per file, and `n_eligible`, are identical;
   - `mapping_<name>.csv` is byte-identical (sha256) wherever either mode produced one;
   - `barcodes_qc_<name>.txt` is byte-identical.

   A missing record is a `breach`, never a skip. A different verdict in Mode F is a T1 breach (§7).
4. **Per-file T2 formulas.** `max(1, ⌊0.001·n⌋)` for labels and protein gating, and the protein M fields with close(0.01, 0), are unchanged and apply over the eligible files.
5. **No eligible files.** If `n_eligible == 0`, zero CITE files are expected. The protein check is "not run", so no protein comparison is attempted. Final-verification wording uses "the eligible replacement files".

## 6. Changes needed elsewhere (described only; NOT made here)

### `scripts/recover.py` (Mode R)

1. **Hashed code files.** Add `companion/scripts/build_cite_totalvi.py` and `protocol/tolerances-v2.json` to `CODE_FILES`, for the E8 hash record.
2. **`cite_build` step.** Replace the `build_cite.py` command with `build_cite_totalvi.py r4prime --workspace <repo> --data <D> --out <o> [--cache-dir …]`. Keep the step name `cite_build` and the 20-min ceiling.
   - **Attempt accounting.** Charge the earlier 403 as one prior attempt (`--prior-attempts '{"cite_build": 1}'`, which the existing `external_prior_attempts` supports). That way `MAX_ATTEMPTS = 2` leaves exactly one attempt, the R4′. There must be no retry, not even for infrastructure statuses.
   - **Exit 2.** Stop the run with the §11 stop wording and return control to the user. Do not continue to R5 or R7, and run no refit.
3. **Disk guard.** Require ≥ 3 GiB free before `cite_build` and ≥ 4 GiB before the first `A_M*_cite`, keeping the 1.5 GiB kill. No deletion of study data.
4. **After `cite_build` exits 0.** Call `expected_cite_files(ci)`.
   - If `n_eligible == 0`, record "protein check not run" in the assembly and skip `A_M*_cite` and `protein`. `score` is unaffected.
   - Otherwise run the existing `run_matched.py --stage predict --data <ci>` commands unchanged; they glob `query_*_F.h5ad`, so only eligible files exist to be predicted. Then run `protein_check.py` unchanged. Add `ci/eligibility.json` to each `A_M*_cite` step's `inputs`.
5. **Deviation log.** Copy `eligibility.json["deviation_log_lines"]` into `evidence/protocol-deviations.md`. This is a coordinator-owned file.

### `scripts/reproduce.py` (Mode F)

1. **Same command.** Use the same `build_cite_totalvi.py r4prime` command with the same pins and order. Mode F attempt rules are "as approved", and the amendment does not change them. Each attempt needs a fresh `--out`; `out/<name>-<attempt>` already provides one.
2. **Zero eligible files.** If Mode F's `n_eligible == 0`, skip `A_M*_cite` and `protein`, and pass `protein=None` to `write_compare_manifest`/`aggregate_results`. A verdict that differs from Mode R is left for `compare_runs` to report as a T1 breach; it is not a crash.
3. **Tolerances.** Pass `--tolerances protocol/tolerances-v2.json` (currently hard-coded to v1).

### `scripts/compare_runs.py`

1. **Resolving `CITE`.** In `run()`, replace the integer `t2["CITE"]` with this:
   - if it is a dict with `rule == "n_eligible"`, load the builder module by path with `importlib`, from `companion/scripts/build_cite_totalvi.py`. Its top level is standard library only.
   - call `expected_cite_files(o["cite"])` and `expected_cite_files(f["cite"])`. An `EligibilityRecordError` becomes `rep.structural("cite_eligibility", …)`.
   - require `n = n_eligible` from Mode R, and require each mode's file list to equal its `eligible_files`.
2. **T1 checks.** Add `for c in t1_replacement_checks(o["cite"], f["cite"]): rep.add("T1", c["item"], c["status"], file=c.get("file"), …)`.
3. **`n_eligible == 0`.** Skip `t1_adt`, CITE `t2_predictions` and `protein()`, and report a descriptive "protein check not run". `protein()` currently opens `protein_agreement.csv` unconditionally.
4. **v1 behaviour.** Keep v1 behaviour when `CITE` is an integer, so v1 comparisons are unchanged.

### `scripts/result_manifest.py` and `scripts/experiment.py`

When the protein check is not run, these files must accept `protein=None` and pass it through.

## 7. Validation performed (observed)

**Pinned stack.** `sh tests_protein_replacement/run_tests.sh <root .venv python>` ran **57 tests, OK, 0 skipped**. The interpreter was used read-only with `PYTHONDONTWRITEBYTECODE=1`, and caches went to `tests_protein_replacement/_tmp`. The run covered:
- **pins:** the amendment hash, the approval record, the pins against `inspection.json` and the amendment text, the commit-pinned URL and the census digest constant;
- **mapping:** every status, make-unique groups, collisions, CSV determinism and round-trip;
- **criterion boundaries:** coverage floor and regression as exact rationals, markers, gates (including the CD20 substitute), and QC (5k passes at 3955/3994 and fails at 3954; 10k passes at 6787/6855 and fails at 6786);
- **structure failures;**
- **acquisition:** a single GET, hash and size mismatch, HTML (type and body), an LFS pointer, 403/timeout/non-200 with no further request, the byte cap with and without `Content-Length`, cached bytes with no network, and a cache mismatch with no GET;
- **ordering:** `eligibility.json` is hashed before any output; an identity, reference, structure, coverage, marker, gate or QC failure stops a file; tampered inputs or records are rejected; and no predictor is called when nothing is eligible;
- **build:** output schema, row alignment and raw-count preservation;
- **unchanged `protein_check.py`:** `main()` reads the synthetic builder outputs (structure only; the values are meaningless);
- **tolerances v2:** its diff against v1, and the T1 helpers.

**Bare interpreter** (`python3` without numpy): 57 run, 25 pass, 32 skipped because a dependency is missing.

`build_cite_totalvi.py plan` ran with no network access and no writes.

**Not done (outside this worker's scope):**
- E6-synthetic with the **real** var names. That needs the h5ad var names, which only the acquired or cached bytes provide, plus a `run_matched.py --stage predict` read with the real Arm A models.
- E8 hash recording, the disk guard, R4′, R5 and R7.
- No result value exists.

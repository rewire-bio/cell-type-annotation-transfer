# Comparison implementation (§7 tiered compare) — integration report

Status: implemented and tested on **synthetic fixtures only**. No real experiment, scoring or historical prediction was read or run. This is not a verification of any result.

Files: `scripts/compare_runs.py`, `protocol/tolerances.json` (a numerical transcription of `resume-plan-reviewed.md` §7, approved in `protocol/amendments/2026-10-06-approved-resumption.md`), and `tests_comparison/`.

## Command

```
python scripts/compare_runs.py --original R.json --reproduction F.json \
    --tolerances protocol/tolerances.json --out runs/C-repro-compare-<UTC>/report.json
```

Exit codes:
- 0: every gated check passed.
- 1: a gated breach, a structural failure, or non-fresh reproduction inputs.
- 3: no breach, but a required artifact is unsupported, so the run is not assessable and does **not** count as reproduced.
- 2: argument error.

The core needs only the standard library. Reading parquet, `.npy` and `.h5ad` files needs pandas, pyarrow, numpy or anndata, which are imported lazily. The tests ran against the existing pinned environment, used read-only: Python 3.11.13, pandas 2.2.3, pyarrow 17.0.0 and numpy 1.26.4.

## Manifest schema `celltransfer-compare-manifest/1` (JSON, relative paths resolve against the manifest's directory)

| key | required | content |
|---|---|---|
| `schema` | yes | `"celltransfer-compare-manifest/1"` |
| `mode` | yes | `"R"` (original) / `"F"` (reproduction) |
| `fresh_execution` | F: yes | must be `true` |
| `data` | yes | D-run directory: `features_and_classes.json` and the 15 `released_predictions_<D>.parquet` files |
| `cite` | yes | CITE run directory: the 4 `released_predictions_<C>.parquet` files and `adt_<C>.parquet` |
| `arms` | yes | `{"A": [dir, ...], "B": [dir, ...]}`. Each directory holds `M1`…`M6/predictions_<file>.parquet`. Exactly one `M4/fit_info.json` per arm. A duplicate file across directories is fatal. |
| `score` | yes | a directory, or `{"primary": dir, "<name>": dir}`, holding `score_all.py`-schema outputs. The D-1a natural-stratum primary and the all-strata secondary can be given as named entries. The key sets must match across the two modes. |
| `protein` | yes | directory holding `protein_agreement.csv` and `gates.json` |
| `sampled_ids` | no | CSV or parquet with `study, role, stratum, soma_joinid`. If absent, it is read from `query_*_F.h5ad` obs via anndata. |
| `bootstrap_weights` | no* | `.npy` reps×test-cells matrix |
| `protein_classes` | no* | `{<cite file>: csv/parquet with barcode, protein_class}` |
| `d03_features` | no* | D03 `features_and_classes.json` |
| `resources` | no | `{step: {seconds, peak_memory_bytes, ...}}` |

\* If these are absent, the matching gated check is reported as `unsupported` and the run cannot reach "reproduced".

## What is encoded

- **Matching.** Every table is matched on stable keys:
  - `soma_joinid` per file
  - `(arm, method)`
  - `(arm, method, vs, metric)`
  - `(file, arm, method)`
  - `barcode`
  - `(role, study, stratum, label_status)`

  A missing or duplicate row, file, column or metric is a fatal `structural_failure`. Rows are never skipped or intersected. The expected file counts (15 D files and 4 CITE files) are enforced.
- **States.** `close` is implemented as defined in §7. NaN, None/empty, −inf and +inf are separate states, and any change of state is a breach. Limitation: pandas writes both NaN and None as an empty CSV cell, so the comparator cannot tell those two apart within score CSVs. Parquet keeps them distinct.
- **T1** (identical):
  - features and classes keys
  - sampled ids per study/role/stratum
  - `cell_counts.csv`
  - `test_donors`, `reps`, `seed`
  - `f1_classes`, `test_scorable_natural`, `unknown_cells`
  - M4 `chosen_C`. If it differs, `validation_macro_f1_by_C` is reported from both modes.
  - P1 target and status
  - bootstrap weights
  - ADT tables
- **T2:**
  - Labels for M1–M5 and P2: disagreements ≤ max(1, ⌊0.001n⌋) per file.
  - `conf` for P1, P2 and M1–M5: close(1e-5, 1e-5) on agreeing cells.
  - `tau_cov`/`tau_err`: state identical only, with |Δτ| reported.
  - Per-cell protein class: the same allowance as labels.
- **M tier:**
  - All `summary_test` metrics, plus derived unassigned = 1 − coverage, at abs 0.01.
  - Both endpoints of every `*_ci95`.
  - Every paired-difference field.
  - Validation coverage and error at τ.
  - Protein agreement fields.
  - AURC at abs 0.005, with relative size reported.
  - Brier and ECE for M4–M6, P1 and P2 at abs 0.01.
  - M6 is gated in this tier like every other method.
- **S tier.** A headline difference is one whose Mode R CI excludes 0 and whose |mean| > 0.01. For each headline, Mode F must have the same sign and a CI that excludes 0 on the same side. A near-zero change in exclusion status is noted but not gated.
- **Not gated:**
  - M6 per-cell labels and conf are diagnostic only, with the 97% heuristic flagged as having no empirical basis.
  - Descriptive tables report max |Δ| only: per-study, per-class, platform, unknowns, risk–coverage points, reliability bins, M1–M3 calibration and `gates.json`.
  - Runtime and memory are flagged at a ratio above 2× in either direction and are never compared for numeric equality.
- **Outcomes.** One outcome per arm × method plus an overall outcome:
  - "reproduced within pre-specified tolerance"
  - "partially reproduced"
  - "not reproduced at the data level", for any T1 breach
  - "not assessable", if anything is unsupported
  - "not compared", if the inputs are not fresh

  When only M6 breaches, the report offers the approved "consistent with non-deterministic CPU training (not verified)" wording. This is not a waiver.
- **No cached outputs counted.** Mode F must be `mode: F` with `fresh_execution: true`. No reproduction path or internal symlink may resolve into, or over, an original path.
- **Report contents.** The full report keeps every check with:
  - original and reproduction values
  - absolute differences and states
  - disagreeing cell ids
  - conf breaches
  - the tolerance file's sha256

## Blockers / unsupported exact artifacts (honestly exposed, not faked)

1. **Bootstrap weights (T1).** `score_all.py` never saves `Wb`. An exact comparison needs a `.npy` dump of `E.donor_bootstrap_weights(test_obs, reps, 20261005)` from each mode. That needs a scoring-wrapper change, which is outside this worker's ownership.
2. **Per-cell protein class (T2 gating).** `protein_check.py` writes only counts to `gates.json`. Per-file `barcode, protein_class` tables need a wrapper or amendment.
3. **"= D03" features.** This needs the D03 `features_and_classes.json` path recorded in the manifest.
4. **Sampled ids.** These need either a `sampled_ids` table or anndata, which is not present in the root environment.
5. **NaN-replicate counts.** `score_all.py` does not output them, so they are reported as unavailable. This item is descriptive and not gated.
6. **Integration with the coordinator's harness is still open.** The coordinator needs to:
   - wire this command into `study.json` and the Makefile as a separate required verify gate (per §6)
   - produce manifests for the real Mode R and Mode F runs
   - decide how the D-1a natural-stratum scoring output is named in `score`

Until items 1–3 are supplied, a real comparison will exit with code 3 ("not assessable") at best. No tolerance was relaxed to avoid this.

## Validation (synthetic)

`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests_comparison`: 11 core tests passed and 20 integration tests were skipped, because pandas is not installed in the stdlib Python.

`PYTHONDONTWRITEBYTECODE=1 <venv>/bin/python -m unittest discover -s tests_comparison`: all 31 tests passed. They cover:
- boundaries: 0.0078125 passes and 0.0125 fails; AURC 0.00488 passes and 0.0051 fails; the max(1, ⌊0.001n⌋) allowance; conf abs+rel limits
- every NaN/None/inf state
- label, CI, τ-state and chosen-C changes
- study-join and sampled-id changes
- missing and duplicate rows and files
- the sign rule and the near-zero note
- protein gating
- ADT and bootstrap exactness
- descriptive and resource flags
- rejection of cached or non-fresh inputs
- CLI exit codes

The tests write only to `tests_comparison/_tmp`, which they then remove.

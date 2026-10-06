# Amended recovery: integration with the finished replacement builder

Date: 2026-10-06. Snapshot: fab7a92. Scope: interface reconciliation only. No experiments, network
or model runs. This changes no design, protocol, config or study file.

## What was reconciled (scripts/)

| Mismatch in the partial integration (d531e80a) | Actual builder (`companion/scripts/build_cite_totalvi.py`) | Fix |
|---|---|---|
| R4' command `build_cite_totalvi.py --workspace --data --out` | `build_cite_totalvi.py r4prime --workspace W --data D --out O [--cache-dir C]` | `recover.py` and `reproduce.py` (amended Mode F) now pass `r4prime`. `recover.py --builder-cache-dir` forwards `--cache-dir`. It is optional and never set by default. |
| Unhashed ad-hoc `eligibility.json` with per-file `sha256`/`bytes` and a string criterion | `celltransfer-totalvi-eligibility/1`, which needs the `eligibility.json.sha256` sidecar. `first_failing_criterion` is `{"number", "name"}` or null. Input identity is in `acquisition.json`. | `result_manifest.parse_eligibility` delegates to the builder's `expected_cite_files` + `read_eligibility`, imported by path and used read-only. A missing or tampered record or sidecar raises `ManifestError`. |
| `postqc_barcodes_<name>.txt` | `barcodes_qc_<name>.txt` | `RM.postqc_barcodes_name` returns the builder name. |
| compare T1: own pin/mapping/barcode logic | `t1_replacement_checks(dir_o, dir_f)` is authoritative | `compare_runs.t1_eligibility` emits the builder's items unchanged (`eligibility_record`, `input_sha256_equals_pin`, `eligibility_verdicts`, `mapping_csv`, `post_qc_barcodes`). A missing record is reported as a breach and never skipped. |
| `cite_expectation` rejected `protocol/tolerances-v2.json` (`{"rule": "n_eligible", ...}`) | — | `{"rule": "n_eligible"}` is now accepted as dynamic. |
| recover's output check iterated `RM.REPLACEMENT_FILES` | builder `NAMES` | It now iterates the names in the verified record. |

These stay as they were: the 2-attempt accounting (`R4_ATTEMPTS_USED`, `--prior-r4-seconds`, pools), new-run
adoption validation, no refit of B M4–M6, strict unchanged-source resume, and fully fresh Mode F.

## Tests (synthetic only)

`tests_amended_recovery/test_builder_integration.py` (13 tests):
- **Real builder:** `acquire` (fake opener), `eligibility` (synthetic census and loader) and `build` (mocked
  predictors) are fed into `parse_eligibility`, `list_files` and `t1_eligibility`.
- **Dynamic outcomes:** 0, 1 and 2 eligible files; `tolerances-v2` is dynamic.
- **T1 breaches:** a verdict difference, a tampered barcodes_qc file, a changed mapping csv and a non-pinned acquisition sha256 are each T1 breaches.
- **Bad records:** a tampered record or a missing sidecar raises a structural error or `eligibility_record` breach.
- **Exact schema with real pins:** criterion shape, sidecar requirement and missing record.
- **recover.py:** the `r4prime` argv is used, `--cache-dir` is forwarded, and a tampered record or missing sidecar ends in a BLOCKED replacement with no Arm A CITE step.

The `_support.py` fake builder now asserts the `r4prime` argv and writes records with the builder's own
`canonical_json`/`write_atomic`. Two old assertions that encoded the wrong contract were updated: the argv
without `r4prime`, and the string criterion `"4"`.

## Fields to set in configs/full.json for the approved amendment (not done here)

`scripts/experiment.py::amended_recover_args` validates these and fails closed:

```json
"amendment": {"id": "2026-10-06-approved-protein-replacement",
              "cite_builder": "companion/scripts/build_cite_totalvi.py"},
"mode_r": {
  "adopt": {"prior_manifest": "evidence/completed-matched-recovery/recovery_manifest.json",
            "receipts_dir": "evidence/completed-matched-recovery"},
  "prior_r4_seconds": <measured seconds of R4 attempt 1 (HTTP 403) - see below>
}
```
- Remove `mode_r.prior_attempts` (currently `{"B_M4_fit": 1}`) and `mode_r.prior_seconds` (currently `60`).
  They are already inside the adopted manifest, and keeping them is refused as double counting.
- Before setting `receipts_dir`, confirm it is the directory holding the byte-identical receipt copies that
  `--adopt-receipts-dir` checks.
- `mode_f`: if the amendment block is present, reproduce.py requires `amendment.cite_builder` as above.
  It also refuses any `mode_f.adopt` key.
- `study.json`: no field is required by these scripts. Record the amendment id and approval record path there
  only if the coordinator's study schema calls for it.

## prior_r4_seconds: NOT determined

- `evidence/completed-matched-recovery/recovery_manifest.json` has no `cite_build` step. Its
  `stage_seconds_used` = 1826.824 covers only the matched recovery.
- A read-only search of `<root>/runs` (cite-input-preflight, preflight-*, …) and `<root>/historical/runs`
  found no R4 attempt-1 HTTP 403 receipt with a measured duration.
- The value is therefore not set and not invented. A human must supply it from the original attempt receipt. If that receipt
  is unavailable, the conservative choice (for example, charging the full 1200 s cite_build ceiling) is a protocol
  decision that needs approval.

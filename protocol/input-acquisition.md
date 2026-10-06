# Input acquisition helper (`scripts/acquire_inputs.py`)

Status: **code preparation only. Not executed against any network source.** Nothing here approves the protocol or changes any scientific choice. The helper has been checked only with mocked, standard-library unit tests (`tests_acquisition/`). Author: research-engineer worker (claude-opus-5-5), 2026-10-06.

## Purpose

The helper fetches the public, version-pinned metadata and model inputs that `historical/companion/scripts/build_data.py` and `build_cite.py` read, at the relative paths those scripts expect, under a study root:

| id | destination (relative to `--root`) | source | pin |
|---|---|---|---|
| sctab-checkpoint | `runs/data/downloads/sctab_val_f1_macro_epoch41.ckpt` | `https://huggingface.co/MohamedMabrouk/scTab/resolve/9d49621154863948c057db0741452b18dcb78559/val_f1_macro_epoch%3D41_val_f1_macro%3D0.847.ckpt` (**third-party mirror**) | sha256 `573b911f…70f56c`, 503,162,157 B |
| sctab-hparams | `evidence/probes/P00-metadata-20261005/hf-hparams.yaml` | `…/resolve/9d49621…/hparams.yaml` (**URL inferred**) | sha256 `e53f93c4…dfbf94`, 507 B |
| sctab-var | `evidence/probes/P01-census-blood-obs-20261005/sctab_var.parquet` | `…/resolve/9d49621…/var.parquet` (**URL inferred**) | sha256 `eca915f6…010317579`, 436,152 B |
| celltypist-immune-all-low | `runs/data/models/celltypist/Immune_All_Low.pkl` | `https://celltypist.cog.sanger.ac.uk/models/Pan_Immune_CellTypist/v2/Immune_All_Low.pkl` | sha256 `290874d3…36502` |
| celltypist-immune-all-high (optional) | `runs/data/models/celltypist/Immune_All_High.pkl` | `…/v2/Immune_All_High.pkl` | sha256 `a715fec3…60448` |
| cl-basic-obo | `runs/data/ontology/cl-basic-v2025-07-30.obo` | `https://github.com/obophenotype/cell-ontology/releases/download/v2025-07-30/cl-basic.obo` (**URL inferred**) | sha256 `ba24e243…78ba07d` |
| census-var | `runs/data/census_2025-11-08_var.parquet` | regenerated from Census LTS `2025-11-08` with `cellxgene-census==1.18.0` | logical digest (below) |
| label-map-* (3) | `evidence/label-maps/*.csv` | study-authored files committed at `historical/evidence/label-maps/` | sha256 of the committed files |

The full hashes, byte sizes, caps and provenance strings are in `ITEMS` in the script, and `python scripts/acquire_inputs.py list` prints them.

### Provenance of the pins (sources inspected, all read-only)

- The checkpoint URL and hash come from `historical/runs/data/downloads/fetch1.sh` and `fetch1.log`, the actual 2026-10-05 retrieval.
- The CellTypist URLs come from `historical/evidence/probes/P00-metadata-20261005/celltypist-models.json`, the saved `models.json`. Their hashes come from `historical/runs/data/models/celltypist/SHA256SUMS`.
- The CL hash comes from `historical/runs/data/ontology/cl-basic-v2025-07-30.obo.sha256`. The release tag comes from `historical/evidence/access-and-feasibility.md`.
- The `hparams.yaml`, `var.parquet` and census-var hashes were computed by this worker on 2026-10-06 from the preserved historical copies. They are **not upstream-published hashes**. Whether the probe copies are byte-identical to the upstream mirror files was not recorded.
- Mirror revision `9d49621` is in `access-and-feasibility.md`. The full SHA comes from `fetch1.sh`.

## Behaviour

- **Plain HTTP only.** The helper sends `https://` GET requests through `urllib` with a fixed, honest User-Agent. It uses no cookies, no browser emulation and no challenge solving. A `text/html` response, such as the Incapsula or Vercel challenge seen on `pklab.med.harvard.edu` and the 10x pages, is a failure and is not bypassed.
- **Bounds.** Each item has a byte cap, enforced both on `Content-Length` and while streaming. There are 3 attempts by default (at most 5) with exponential backoff. HTTP 4xx (except 429), hash mismatches and HTML responses are not retried. The total planned bytes must be ≤ 7 GiB, the study storage cap. In practice the total is about 0.52 GB plus the census var table. The outer resource guard still applies.
- **Atomic writes.** Each file streams to `<dest>.part` and is fsynced. It is renamed into place with `os.replace` only after both size and SHA-256 match. On failure the partial file is removed.
- **Writes are confined to `--root`.** Destinations are resolved and checked against the root, and the `.part` files and manifest also stay under the root. The cache root must lie outside `--root` and is never written to.
- **Idempotent.** A file that is already present with the pinned hash is recorded as `verified-existing` and is not fetched again.
- **Cached third-party fallback (explicit opt-in).** This requires both `--cache-root DIR` and `--allow-cache-fallback`. The cache is used only after the upstream retrieval has failed. The cached file must match the same pinned SHA-256. Its record gets the status `cached-third-party-fallback`, and its `source` is set to `cache:<relpath> (upstream <url> failed)`. This shows the input did not come from upstream in that run. The cache layout mirrors the preserved historical tree (for example `--cache-root /Users/timrichardson/Documents/projects/personal/blog/cell-type-annotation-transfer/historical`). The registry has no cache path for any expression data, prediction or run output, so **historical derived expression and predictions cannot be copied** by this tool.
- **Census var.** This table is regenerated, not downloaded and not copied, with `open_soma(census_version="2025-11-08")` and `census_data["homo_sapiens"].ms["RNA"].var.read()`. Parquet bytes are not assumed to be deterministic. The receipt records the row count, the columns and a **logical SHA-256**: the SHA-256 of CSV text of `soma_joinid, feature_id, feature_name` sorted by `soma_joinid`. With `--census-compare <historical parquet>`, the same digest is computed for the reference copy, and a mismatch marks the item `failed`. The cache fallback is never used for this item.
- **Manifest.** A run writes `runs/data/retrieval-manifest.json`. A dry run writes `runs/data/retrieval-plan.json`, and nothing else. Each item records its status, source URL, sha256, bytes, attempts, errors, retrieval UTC time, URL and hash provenance, licence text, a third-party flag and notes. Failures are kept in the manifest, and the process exits with code 1.

## Commands

```
python scripts/acquire_inputs.py list                                    # no network, no writes
python scripts/acquire_inputs.py acquire --root <study-prefix> --dry-run # writes only the plan
python scripts/acquire_inputs.py acquire --root <study-prefix> \
    [--cache-root <read-only historical root> --allow-cache-fallback] \
    [--census-compare <historical>/runs/data/census_2025-11-08_var.parquet] [--only ID ...] [--skip ID ...]
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests_acquisition -v
```

Python 3.11.13, as pinned in `pyproject.toml`. Downloads use the standard library only. Census regeneration needs the pinned `cellxgene-census==1.18.0`, `tiledbsoma` and `pandas`/`pyarrow` from `uv.lock`. Callers should point `TMPDIR`, `XDG_CACHE_HOME` and `HF_HOME` into the study prefix, as `resume-plan-reviewed.md` §3 requires. The helper does not rely on them for downloads.

## Licences (only what saved records support)

| Input | Recorded licence | Status |
|---|---|---|
| scTab checkpoint, hparams, var (HF mirror) | The mirror self-declares `mit`. The official scTab README states MIT **for the code repository** | Checkpoint licence from the scTab authors is **unknown**. The mirror tag is not authoritative (`historical/research/facts-verified.csv` #38) |
| CellTypist Immune_All v2 | — | **unknown** ("to verify" in access-and-feasibility.md) |
| Cell Ontology cl-basic | CC BY 4.0 | from access-and-feasibility.md; upstream LICENSE not re-inspected in this task |
| CELLxGENE Census data | CC BY 4.0 | "to be verified in dossier" (access-and-feasibility.md) |
| Label maps | study-authored | — |

## Not covered (out of scope or owned elsewhere)

- **10x CITE-seq `.h5` files**, used by `build_cite.py`. The four URLs are in the historical code, but no SHA-256 pins were found in the inputs inspected for this task, so the helper does not list them. Adding them needs pinned hashes from a recorded retrieval.
- **scTab vendored code** (`companion/vendor/sctab_cellnet`). This is code, not data, and is outside this task.
- Expression matrices and predictions. These are produced by `build_data.py` from Census at run time and are never copied.

## Open items / blockers

1. The URLs for `hparams.yaml`, `var.parquet` and `cl-basic.obo` are inferred, not recorded. Their pins are hashes of historical local copies. A first live run will either confirm them, if the hashes match, or fail closed. A failure would then need a decision, which the cache fallback could cover only with a label.
2. There is no recorded logical digest for the historical census var table, because pandas/pyarrow were not available to this worker. The reference comparison therefore needs `--census-compare` at run time. The historical generation command was not saved.
3. The licences for the CellTypist models and for the scTab checkpoint from its authors are unknown. The Census and CL licences are still marked "to verify".
4. 10x CITE-seq file hashes are absent, so these files are not covered.
5. The tool has not been executed against any live source. No download, regeneration or comparison has been performed.

# Cell-type annotation transfer

The study paper and private clean reproduction passed final verification. Public full reproduction with the compact package remains untested. Use the pinned source and release instructions below.

## Frozen study and delivery records

| Record | Actual value to insert |
| --- | --- |
| Verified scientific source commit | `fd4588c2b58eee214fea76b1874be1a37df1f0da` |
| Documentation/release tip commit | `Later documentation delivery; see this file in Git history.` |
| Verification record | `c748f3e1c09f45c4bd4c7b99b8b96a39` |
| Final independent reproduction | `56fa2cab73c045e8865aca59309c0770` |
| Final methods review | `b016a5de6503438e9b82360a5db64a35` |
| Final paper review | `6b73d31ed0a9418f8b653871ff21af26` |
| Public evidence archive | `public-evidence.tar.gz`, SHA256 `ba00209db3a8d422579d105c9359143d5b0a6b573c590373e8e734414b1935bf` |
| Compact baseline metadata | `compact-baseline.tar.gz`, SHA256 `37793da3eafe3a47fa7829aeb39c2c30fdacb436baa3ec765a3ad0243bc2c5fa` |
| Paper PDF | `cell-type-annotation-transfer.pdf`, SHA256 `cf3cbf988f2ef3a4af0dd86d115e815e2160597bf5430fc8ef2c0bac4063a13b` |
| GitHub release | `study-v1-seed0-20261007` / `https://github.com/rewire-bio/cell-type-annotation-transfer/releases/tag/study-v1-seed0-20261007` |

The verification record binds the scientific source commit above. The documentation/release tip may contain later delivery instructions; it is a distinct commit. Commands below check out the verified source. Read the release evidence for the actual comparison outcome and review records. Automated model reviews must be identified as model reviews; no human scientific review is implied.

## Run the recorded M4 CLI wiring example

The prepared `m4-example.tar.gz` is 944,277 bytes, SHA256 `7b798df27f35440f5c2c01ab1f39f284896a31fb5229dd342393d914cd1cdf78`. Its existing provenance and outputs accompany the original Arm A M4 export and 12-cell CELLxGENE Census query. The bundle contains the study’s own M4 coefficients, without upstream pretrained weights.

The recorded example passed input checks with every model gene present. All 12 cells received `unassigned`, reason `low_counts_or_genes`, using the default minimum of 500 total counts and 200 detected genes. This checks model loading, input wiring and output generation and supplies no accuracy estimate. Keep the default quality screen.

The locked environment uses Python 3.11.13. Recorded study execution used macOS on Apple Silicon; Linux resource guards require separate validation. Install the existing required tools before running these commands.

Replace the source and release placeholders, then run in a new directory:

```sh
CT_STUDY_SHA='fd4588c2b58eee214fea76b1874be1a37df1f0da'
CT_RELEASE_TAG='study-v1-seed0-20261007'
CT_DEMO_ROOT="$PWD/celltransfer-cli-example"
mkdir "$CT_DEMO_ROOT"
git clone https://github.com/rewire-bio/cell-type-annotation-transfer.git "$CT_DEMO_ROOT/study"
git -C "$CT_DEMO_ROOT/study" checkout --detach "$CT_STUDY_SHA"
test "$(git -C "$CT_DEMO_ROOT/study" rev-parse HEAD)" = "$CT_STUDY_SHA"

curl --fail --location \
  "https://github.com/rewire-bio/cell-type-annotation-transfer/releases/download/$CT_RELEASE_TAG/m4-example.tar.gz" \
  --output "$CT_DEMO_ROOT/m4-example.tar.gz"

python3 - "$CT_DEMO_ROOT/m4-example.tar.gz" <<'PY'
import hashlib
import sys
from pathlib import Path
p = Path(sys.argv[1])
h = hashlib.sha256()
with p.open('rb') as f:
    for block in iter(lambda: f.read(1024 * 1024), b''):
        h.update(block)
expected = '7b798df27f35440f5c2c01ab1f39f284896a31fb5229dd342393d914cd1cdf78'
if p.stat().st_size != 944277 or h.hexdigest() != expected:
    raise SystemExit('M4 example archive size or SHA256 differs')
print('M4 example archive verified')
PY

tar -xzf "$CT_DEMO_ROOT/m4-example.tar.gz" -C "$CT_DEMO_ROOT"
cd "$CT_DEMO_ROOT/study"
make env

(cd "$CT_DEMO_ROOT/m4-bundle" && shasum -a 256 -c SHA256SUMS)

PYTHONPATH="$CT_DEMO_ROOT/study/companion/src" .venv/bin/python \
  -m celltransfer.cli check \
  --bundle "$CT_DEMO_ROOT/m4-bundle" \
  --query "$CT_DEMO_ROOT/example/blood12.h5ad"

PYTHONPATH="$CT_DEMO_ROOT/study/companion/src" .venv/bin/python \
  -m celltransfer.cli annotate \
  --bundle "$CT_DEMO_ROOT/m4-bundle" \
  --query "$CT_DEMO_ROOT/example/blood12.h5ad" \
  --operating-point coverage90 \
  --out "$CT_DEMO_ROOT/predictions.csv"
```

Outputs are `predictions.csv` and `predictions.csv.summary.json`. Inspect `decision`, `reason`, `total_counts` and `genes_detected`. The recorded packaged outputs remain in `example/predictions.csv`.

For other queries, use full raw nonnegative integer counts in `.X`, or the supported `--layer counts` / `--use-raw` options. Use unique cell IDs and Ensembl gene IDs; keep all genes so library sizes come from the complete count matrix.

## Reproduce the study

Use the frozen source commit, locked environment, approved protocol and versioned tolerances. Full execution includes model fitting, predictions, scoring, comparison and paper generation. It requires acquisition of the pinned source data and sufficient resources; the small CLI example does not execute the study.

The public compact baseline contains aggregate/reference metadata and independently frozen original file hashes. It excludes withheld per-cell reference arrays, barcodes, source RNA/ADT matrices and fitted model objects. The original baseline and complete execution histories remain privately preserved. The public archive must disclose its omissions and every sanitized derivative.

The recovery tool can restore a separate local reference file only when the reader's independently generated candidate has the exact original recorded SHA256 and byte size. A missing or mismatching candidate leaves the reference unsupported. It cannot substitute a tolerance decision or claim successful reproduction. The unchanged study comparator still checks all gates after exact restoration.

Public fresh-clone execution with the compact baseline has **not been executed or validated**. Read the operational instructions at `evidence/reviews/public-reproduction-instructions.md`; do not infer public-clone validation from the existing private comparison. Preserve the reader's initial failed missing-reference receipt and report before any comparison-only recovery. Recovery must rerun only comparison, paper assets and PDF generation, with no repeated scientific generation or altered tolerances.

The original `original-baseline.tar.gz` is retained unchanged locally. It is excluded from these public compact-baseline instructions because it contains payloads omitted by the current redistribution policy.

## Evidence and paper

- Frozen LaTeX source: `paper/main.tex` at `fd4588c2b58eee214fea76b1874be1a37df1f0da`.
- Compiled PDF: `https://github.com/rewire-bio/cell-type-annotation-transfer/releases/download/study-v1-seed0-20261007/cell-type-annotation-transfer.pdf`.
- Final verified records and review reports: `https://github.com/rewire-bio/cell-type-annotation-transfer/releases/download/study-v1-seed0-20261007/public-evidence.tar.gz`.
- Portable baseline metadata and omission list: `https://github.com/rewire-bio/cell-type-annotation-transfer/releases/download/study-v1-seed0-20261007/compact-baseline.tar.gz`.

Earlier failures, stopped receipts and failed paper reviews must remain traceable in the disclosed lineage.

## Dataset attribution

The 12-cell demonstration is derived from Binvignat et al. (2024), “Single-cell RNA-seq analysis reveals cell subsets and gene signatures associated with Rheumatoid Arthritis Disease Activity”, [JCI Insight](https://doi.org/10.1172/jci.insight.178499), curated by [CZ CELLxGENE Discover](https://cellxgene.cziscience.com/collections/e1a9ca56-f2ee-435d-980a-4f49ab7a952b), dataset `d18736c3-6292-4379-919a-d6d973204c87`, Census `2025-11-08`. Data are supplied under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); the example selects twelve cells and removes source cell metadata. See `evidence/dataset-attribution.json` for study dataset citations.

[Completion and preserved failure history](evidence/reviews/final-release-completion-note.md). [Public omissions and transformations](evidence/archive/c748f3e1c09f45c4bd4c7b99b8b96a39/omissions.json). Scientific limitations and interpretation remain in the paper; no human review or external replication is claimed.

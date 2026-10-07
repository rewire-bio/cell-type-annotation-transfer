# Compact baseline operational instructions

The metadata package is prepared, but public fresh-clone execution has not been run or validated. These tools do not acquire data, fit models, predict, infer or score. They recover withheld references only after independently generated candidate bytes exactly match frozen original hashes, then use the unchanged comparator and paper scripts.

Use the recorded macOS/Apple Silicon platform and locked Python 3.11.13 environment. Existing guards bound the whole continuation and child processes to four threads, 12 GiB memory and the original 7 GiB storage cap, disk/swap limits and remaining runtime pools. The original failed receipt's finite `h_seconds_used` and `f_seconds_used` are required. Linux guards require separate validation. Budget exhaustion or a cryptographic mismatch leaves recovery unsupported.

## Pin the scientific source and auxiliary tools

Auxiliary code is a separate operational delivery commit. It does not change the verified scientific snapshot. Use two checkouts and run scientific code only at the verified commit:

```sh
CT_VERIFIED_SOURCE='fd4588c2b58eee214fea76b1874be1a37df1f0da'
CT_AUXILIARY_SOURCE='515cfe5e499d6cc9d54d5fd68d251972183fe65d'
CT_RELEASE_TAG='study-v1-seed0-20261007'
CT_BINDINGS_SHA='141671f37c00061858b7e0b2efd8781e27bbedb001328ae252df69e91e6ab43d'
CT_ROOT="$PWD/celltransfer-public-reproduction"
mkdir "$CT_ROOT"
git clone https://github.com/rewire-bio/cell-type-annotation-transfer.git "$CT_ROOT/study"
git -C "$CT_ROOT/study" checkout --detach "$CT_VERIFIED_SOURCE"
test "$(git -C "$CT_ROOT/study" rev-parse HEAD)" = "$CT_VERIFIED_SOURCE"
git clone https://github.com/rewire-bio/cell-type-annotation-transfer.git "$CT_ROOT/operational-tools-source"
git -C "$CT_ROOT/operational-tools-source" checkout --detach "$CT_AUXILIARY_SOURCE"
test "$(git -C "$CT_ROOT/operational-tools-source" rev-parse HEAD)" = "$CT_AUXILIARY_SOURCE"
CT_TOOLS="$CT_ROOT/operational-tools-source/evidence/reviews/reproduction-tools"

curl --fail --location \
 "https://github.com/rewire-bio/cell-type-annotation-transfer/releases/download/$CT_RELEASE_TAG/compact-baseline.tar.gz" \
 --output "$CT_ROOT/compact-baseline.tar.gz"
curl --fail --location \
 "https://github.com/rewire-bio/cell-type-annotation-transfer/releases/download/$CT_RELEASE_TAG/compact-release-bindings.json" \
 --output "$CT_ROOT/compact-release-bindings.json"
cd "$CT_ROOT/study"
make env
.venv/bin/python "$CT_TOOLS/compact_cli.py" unpack \
 --archive "$CT_ROOT/compact-baseline.tar.gz" --destination "$CT_ROOT/baseline-metadata" \
 --release-bindings "$CT_ROOT/compact-release-bindings.json" \
 --release-bindings-sha256 "$CT_BINDINGS_SHA"
```

The CLI pins the existing canonical run manifest SHA `60cfbe955c5b9516532750c3873653e16f558528551403a087bf0b545e2dd516`, canonical comparison manifest SHA `9f7aedd33310ee69e426002cd54acbcc5e3f2833bc0cc3fb8de041e6f1a85683`, compact record SHA `4e313ab65adcf474b76578e45dd9394745dfb5fa0f0ec6755746dc0849f65e57`, and prepared metadata archive SHA `37793da3eafe3a47fa7829aeb39c2c30fdacb436baa3ec765a3ad0243bc2c5fa`. The external bindings are separately hashed by the publisher; expected hashes are never taken from reader-generated candidates.

The archive has nine metadata files plus `compact-reference.json` and `checksums.json`. Both reserved controls are validated; they are excluded from the nine-file metadata staging rules. No withheld arrays or models are bundled.

## Complete the approved full scientific execution first

The baseline provides required original D03/eligibility metadata before execution. Read the frozen protocol, requirements and resource limits before beginning the approved full run. This command may require source-data downloads, considerable runtime and sufficient disk; the CLI wiring demo is separate.

```sh
cd "$CT_ROOT/study"
CELLTRANSFER_BASELINE_MANIFEST="$CT_ROOT/baseline-metadata/comparison_manifest.json" make reproduce
```

The current metadata-only package deliberately omits per-cell references. The normal scientific driver must still complete its own generation and record its actual failed missing-reference comparison. If execution stops earlier during acquisition, fitting, prediction, scoring or resource checks, this continuation cannot bypass that failure. Do not edit receipts to create a successful generation history.

Locate the actual Mode F `generation_receipt.json`, its existing `comparison.report` and the corresponding generated `comparison_manifest.json`. Keep the original files unchanged. Set the two following variables to the real files; no example run ID is invented here.

## Resume comparison and paper generation

```sh
CT_FAILED_RECEIPT='__ACTUAL_F_GENERATION_RECEIPT_PATH__'
CT_F_MANIFEST='__ACTUAL_F_COMPARISON_MANIFEST_PATH__'
cd "$CT_ROOT/study"
.venv/bin/python "$CT_TOOLS/compact_cli.py" resume \
 --workspace "$CT_ROOT/study" \
 --package-directory "$CT_ROOT/baseline-metadata" \
 --fresh-manifest "$CT_F_MANIFEST" --failed-receipt "$CT_FAILED_RECEIPT" \
 --reference-directory "$CT_ROOT/restored-original-reference" \
 --continuation-directory "$CT_ROOT/comparison-continuation" \
 --release-bindings "$CT_ROOT/compact-release-bindings.json" \
 --release-bindings-sha256 "$CT_BINDINGS_SHA"
```

The CLI preserves the initial failed receipt/report before preparing the sampled-ID CSV. It reads only the observations from sorted `query_*_F.h5ad` files using the established extraction recipe; it does not read `.X` or create scientific measurements. The original fresh manifest remains unchanged. Every candidate must have the independently frozen original byte size and SHA256 before any reference tree is created. The references are separate ordinary copies, with no symlink or hardlink to candidate files.

Missing or mismatching bytes produce unsupported status and no scientific tolerance verdict. After exact restoration, only the frozen `compare_runs.py`, `make_paper_assets.py` and `build_paper.py` run. Their hashes, the versioned tolerances, full configuration, verified source commit and auxiliary files are checked against the externally bound release record. The existing comparator must pass all gated checks with zero unsupported cases before a PDF is generated. Guard failures or comparator nonzero exits stop the continuation.

Inspect the continuation receipt, original failed records, restoration receipt, comparison report, resource guard receipts and compiled PDF. A successful local result concerns that reader's actual execution; it does not establish prior public-clone validation, additional harness approval, human scientific review or a new agent experiment.

One continuation reservation is retained per immutable failed receipt, including failed or resource-stopped attempts. Changing the output directory cannot reset the original runtime pool; preserve these records. Internal worker subcommands are not the public interface.

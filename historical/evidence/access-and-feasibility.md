# Access, feasibility and overlap inventory (article 349)

Date: 2026-10-05 (Europe/London; probes logged in UTC). Coordinator: Claude Opus (claude-opus-5-5).
Status: **FEASIBLE with recorded exclusions.** Decision taken before any expression matrix was downloaded.

## 1. Existing local work (read-only inspection)

| Location | Finding |
|---|---|
| `rewire-benchmarks` (commit ca73fa4) | No cell-annotation benchmark, data or code (only MFASS, ProteinGym examples, sequence campaigns). |
| `research-harness`, `research-harness-validation`, `researcher` | No scTab/CellTypist/scANVI material. |
| `rewire.it/workbench/outputs/blog-research-use-case-coverage-20260930/` | Prior extraction of scTab Supplementary Tables 1a/1b, Table 2, Table 6 for issue #349 ("donor-held-out annotation baselines... independent-study and coverage-aware unknown-type validation remain gaps"). Reused as background only; numbers will be re-verified from the primary source. |
| `rewire.it/workbench/outputs/benchmark-development-tracker-20261001/bodies/rewire.it-349.md` | Benchmark development text already in the issue plan. |
| Disk search for `*.h5ad` | None present locally. |
| Article for closed #232 | No published post or workspace about donor-held-out mapping found under `posts/` or `workbench/outputs`; nothing to reuse beyond the issue plan. |

## 2. Resources

- Free disk at start 3.49 GiB (`/System/Volumes/Data`), 16 GB RAM, Apple M4, CPU only, R not installed.
- Companion virtual environment (Python 3.11, `companion/env/requirements-full.lock.txt`) cost 0.47 GiB, mostly cloned from the uv cache. Free after: 3.01 GiB.
- Budget for data: Census subsets ≤0.6 GB, scTab checkpoint 0.50 GB, tutorial example h5ad 0.36 GB (temporary, deleted after the provenance check), 10x CITE-seq matrices ~0.1 GB, CellTypist models <0.1 GB. Floor: pause work below 1.0 GiB free.

## 3. Data access and provenance

| Resource | Access | Pinned identity | Licence | Decision |
|---|---|---|---|---|
| CELLxGENE Census | public S3 via `cellxgene-census` 1.18.0 / `tiledbsoma` 2.3.0 | LTS build `2025-11-08` (census schema 2.4.0, dataset schema 7.0.0) | CELLxGENE Discover data CC BY 4.0 (to be verified in dossier) | Use; bounded per-donor subsets only |
| Cell Ontology | GitHub release | `cl-basic.obo` v2025-07-30 (the CL release pinned by CELLxGENE schema 7.0.0), SHA-256 `ba24e243…ba07d` | CC BY 4.0 | Use |
| scTab code | GitHub `theislab/scTab` (default branch `devel`, head 5ede7f2, 2024-09-13) | MIT | | Use code path from official tutorial |
| scTab checkpoints (8.1 GB) and minimal subset (0.5 GB) | `pklab.med.harvard.edu` returns an Incapsula JavaScript challenge to non-browser clients | | | **Not circumvented.** Minimal-subset matrices not used |
| scTab checkpoint mirror | Hugging Face `MohamedMabrouk/scTab` rev 9d49621 (third party, MIT) | `val_f1_macro_epoch=41_val_f1_macro=0.847.ckpt` (503,162,157 bytes, LFS oid prefix 573b911f), `hparams.yaml`, `var.parquet` (19,331 genes), `categorical_lookup/*.parquet` | MIT | Use with provenance caveat. Official devel tutorial loads `scTab-checkpoints/scTab/run5/val_f1_macro_epoch=41_val_f1_macro=0.847.ckpt`, the same filename. Behavioural check planned: reproduce the tutorial's printed predictions on its example dataset `f8f41e86-…` (still hosted, 362,766,772 bytes) |
| CellTypist models | `celltypist.cog.sanger.ac.uk/models/models.json` | `Immune_All_Low.pkl` v2 (2022-07-16, 98 types), `Immune_All_High.pkl` v2 (32 types); source Domínguez Conde et al. 2022 Science | to verify | Use for practical track |
| 10x Genomics CITE-seq PBMC | dataset pages behind a Vercel bot checkpoint (not circumvented); direct CDN files `cf.10xgenomics.com/samples/...` return 200 | `pbmc_10k_protein_v3`, `5k_pbmc_protein_v3_nextgem`, `5k_pbmc_protein_v3` (3.1.0), `10k_PBMCs_TotalSeq_B_3p`, `vdj_v1_hs_pbmc3` (17–33 MB each) | CC BY 4.0 per 10x dataset licence (search snippet; to verify) | Use as unlabelled orthogonal-protein queries |
| Pan-Human Azimuth | `panhumanpy` 1.0.0 needs `tensorflow==2.17` and `scikit-learn==1.6.0`; Azimuth R path needs R/Seurat (absent) | | code MIT; model weights CC BY 4.0 (corrected 2026-10-05, see protocol-deviations.md) | **notrun**: environment would exceed disk budget and conflicts with pinned scikit-learn |
| scGPT | `scgpt` 0.2.4 pins `scvi-tools<1.0`, `torchtext`, `cell-gears<0.0.3`, `orbax<0.1.8` | | MIT | **notrun**: unresolvable alongside the pinned stack within disk budget; pretraining corpus is CELLxGENE-derived, so overlap with test studies would also need auditing |
| scANVI | `scvi-tools` 1.4.1 (Python 3.11, no JAX) | | BSD-3 | Use in matched track, CPU |

## 4. Census blood inventory (normal, primary, `tissue_general == 'blood'`)

13,822,662 cells, 64 datasets; 22 of these datasets are in scTab's training lookup (`categorical_lookup/dataset_id.parquet`, 249 datasets). Outputs: `probes/P01-census-blood-obs-20261005/blood_dataset_inventory.csv`, `donor_overlap_with_sctab.csv`, `cl_mapping_probe.csv`.

### Overlap findings that change the design

- **AIDA full release** (`c838aec3`, 625 donors, not itself in scTab's dataset list): 503 donor IDs (e.g. `JP_RIK_H001`) are in scTab's donor lookup. Not independent of scTab; excluded from validation and test.
- **Wells et al. 2025 multimodal** (`1b350d0a`): donors `621B, 637C, D496, D503` also appear in the 2022 cross-tissue immune atlas (`1b9d8702`, Domínguez Conde et al.), the CellTypist Immune_All training source. Excluded from validation and test.
- **COVID-19 mRNA vaccine** (`242c6e7f`): all nine donor IDs (`CV-…`) in scTab's donor lookup. Excluded.
- Generic donor IDs (`P1`, `1`, `CONTROL`, `H1`) produce uninformative matches; the chosen validation/test studies have zero matches of any kind.

### Label mapping

Fixed target level of 16 Cell Ontology classes (`companion/src/celltransfer/ontology.py`), deepest-target rule, three frozen overrides (classical monocyte → CD14 mono; non-classical monocyte → CD16 mono; CD141-positive myeloid DC → cDC, because cl-basic v2025-07-30 places it under pDC) and one precedence rule (ASC over B for plasmablasts). 97.3% of normal blood cells map to exactly one class; 264,340 cells carry coarser labels (e.g. "T cell"), 184,937 are outside the target set (e.g. intermediate monocyte, generic regulatory T cell, thymocyte-labelled cells), 715 are ambiguous (erythroid progenitor). Unmapped cells are excluded from training and fine-level scoring, never relabelled.

## 5. Chosen study roles (to be frozen in `protocol.md`)

| Role | Studies (CELLxGENE dataset, first CELLxGENE publication) | Independence |
|---|---|---|
| Reference (matched track training) | Hao 2021 `ed5d841d`; OneK1K `3faad104`; Perez 2022 `218acb0f`; van der Wijst 2021 `01ad3cd7`; COMBAT 2022 `ebc2e1ff`; CVID atlas `3c75a463` | All six were in scTab training and five predate CellTypist's model; acceptable for the matched track, which trains every method itself |
| Validation (threshold tuning only) | Kidney cancer blood `5af90777` (2023-07-18); Clonal haematopoiesis `19e46756` (2024-03-26) | Not in scTab datasets; zero donor-ID matches; published after CellTypist model build |
| Test (study held out) | Human Immune Health Atlas `e522d2cd` (2025-10-24); RA `d18736c3` (2024-08-19); Glaucoma `30c2a6fd` (2025-08-13); JDM CITE-seq `a199ca73` (2024-05-23) | Same criteria |
| Platform test (descriptive) | Comparative Analysis of Commercial scRNA-seq Technologies, collection `398e34a9` (2024-07-18): one donor profiled on 10x 3′ v3, 10x 5′ v2, 10x Flex, BD Rhapsody, HIVE, PIPseq, Parse, ScaleBio, Asteria | One donor, so platform-level, not donor-level, uncertainty |
| Orthogonal protein (unlabelled) | 10x CITE-seq PBMC files above | Each file is one sample; donor identity between files is not stated |

## 6. Feasibility decision

Feasible on this machine for: marker rules, nearest centroid, PCA+kNN, multinomial logistic regression, CellTypist (retrained on the matched reference and released Immune_All models), scANVI (matched, CPU), released scTab checkpoint (practical track, provenance caveat). Not run: Pan-Human Azimuth, scGPT (reasons above). A donor-held-out split is not used for the main claim; transfer claims rest on whole-study holdout. No human label adjudication was performed or will be implied; author labels mapped to the Cell Ontology are the reference standard, and the protein-gated check is a separate, coarse, orthogonal check.

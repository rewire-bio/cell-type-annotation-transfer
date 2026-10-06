# Frozen protocol: reference choice, annotation transfer and abstention (article 349)

Version 1.0, frozen 2026-10-05 before any validation, test, platform or CITE-seq expression data were downloaded or scored. Freeze receipt: `evidence/protocol-freeze-receipt.txt`.

**Disclosure of prior inspection.** Before freezing, the coordinator inspected Census *metadata* only: dataset/donor/assay counts and author-label composition per dataset (`evidence/probes/P01-…`). No expression values or predictions for any validation, test, platform or CITE-seq cell were seen. The only predictions seen were scTab outputs on the scTab tutorial dataset `f8f41e86-…` (run R01), which is not used below.

## 1. Question and claims allowed

How should an analyst choose a reference and annotation workflow for a new blood/PBMC single-cell cohort, and when should a label be accepted? Two tracks are kept apart:

- **Matched track.** Every method is trained by us on identical reference cells, labels and genes. Differences are method effects under this reference only.
- **Practical track.** Released artefacts are used as distributed: CellTypist `Immune_All_Low` v2 and the scTab run5 checkpoint. Their training data, label sets and gene spaces differ from each other and from the matched reference, so no architecture claim is made from practical-track differences.

Transfer claims rest on **whole-study holdout**. A platform comparison is descriptive (one donor). The CITE-seq protein check is a coarse orthogonal check, not ground truth. Author labels mapped to the Cell Ontology are the reference standard; no human adjudication was performed.

## 2. Data (CELLxGENE Census LTS `2025-11-08`, homo_sapiens)

Filter for every pull: `is_primary_data == True`, `disease == 'normal'`, `tissue_general == 'blood'`, and the dataset IDs below. Raw counts from `X/raw`.

| Role | Dataset IDs |
|---|---|
| Reference | `ed5d841d-6346-47d4-ab2f-7119ad7e3a35` (Hao 2021), `3faad104-2ab8-4434-816d-474d8d2641db` (OneK1K), `218acb0f-9f2f-4f76-b90b-15a4b7c7f629` (Perez 2022), `01ad3cd7-3929-4654-84c0-6db05bd5fd59` (van der Wijst 2021), `ebc2e1ff-c8f9-466a-acf4-9d291afaf8b3` (COMBAT 2022), `3c75a463-6a87-4132-83a8-c3002624394d` (CVID atlas) |
| Validation (thresholds, C only) | `5af90777-6760-4003-9dba-8f945fec6fdf` (kidney cancer cohort blood), `19e46756-9100-4e01-8b0e-23b557558a4c` (clonal haematopoiesis) |
| Test (study held out) | `e522d2cd-7927-4e59-a4ed-064009569279` (Human Immune Health Atlas), `d18736c3-6292-4379-919a-d6d973204c87` (RA), `30c2a6fd-d547-460f-a5e7-44c62a2af7ad` (Glaucoma atlas), `a199ca73-035d-44e2-9893-4c493151db21` (JDM CITE-seq) |
| Platform test (descriptive) | collection `398e34a9-8736-4b27-a9a7-31a47a67f446`: for each assay, the lexicographically smallest dataset ID |
| Orthogonal protein (no labels) | 10x Genomics CDN: `pbmc_10k_protein_v3` (3.0.0), `5k_pbmc_protein_v3_nextgem` (3.0.2), `10k_PBMCs_TotalSeq_B_3p` (6.0.0), `vdj_v1_hs_pbmc3` (3.1.0), `filtered_feature_bc_matrix.h5` |

Validation/test/platform studies were absent from scTab's 249 training datasets, share no donor IDs with scTab's 4,314-donor lookup, and were published after the CellTypist model build (2022-07-16). Exclusions for overlap (AIDA full release, Wells 2025, COVID-19 mRNA vaccine) are recorded in `access-and-feasibility.md`.

### Sampling (seed 20261005, numpy `default_rng`)

- Labels: author `cell_type_ontology_term_id` mapped with `companion/src/celltransfer/ontology.py` (frozen table `evidence/label-maps/census_blood_author_labels.csv`). Only `mapped` cells are used for training or fine-level scoring.
- Reference: per study, donors with ≥300 mapped cells; up to 12 donors at random; within each donor up to 150 cells per target class at random.
- Validation and test: per study, donors with ≥300 cells; up to 12 donors at random. *Natural stratum*: 600 cells per donor at random from all that donor's cells (all label statuses, so composition is preserved). *Rare top-up stratum*: for ASC, pDC, cDC, MAIT, gamma-delta T, CD16 mono, HSPC, ILC, platelet/MK, erythroid, up to 40 further mapped cells per donor and class not already sampled. Every cell records its stratum.
- Platform test: 1,000 cells at random per platform dataset (natural).
- CITE-seq: all cells with ≥200 detected genes and <20% mitochondrial counts.

### Genes and preprocessing

- Common gene universe G: the 19,331 scTab genes (`var.parquet`), matched by Ensembl ID without version. Missing genes are zero for scTab and reported.
- Matched-track features F (chosen on reference only): 2,000 highly variable genes (`scanpy.pp.highly_variable_genes`, `flavor='seurat_v3'`, `batch_key=study`, on counts) plus, for each reference class, the top 10 genes from `rank_genes_groups` (t-test, log1p CP10k, class versus rest). Stored files contain only F.
- Normalisation for all matched methods except scANVI: counts per 10,000, `log1p`. Linear, centroid and kNN methods additionally z-score with reference mean and SD (clipped at ±10). PCA (50 components) fit on reference only.
- Released models receive inputs in their documented form, computed on the fly from the Census pull: CellTypist log1p CP10k on all available genes; scTab raw counts on G with its own `sf_log1p` normalisation.

## 3. Methods

Matched track (all trained on the same reference cells, labels and F):

| ID | Method | Confidence score |
|---|---|---|
| M1 | Marker rule: markers = the 10 F genes per class from the reference ranking above; class score = mean z-scored expression of its markers; prediction = argmax | top minus second score (uncalibrated) |
| M2 | Nearest centroid on PCA, cosine similarity | top minus second similarity (uncalibrated) |
| M3 | PCA + kNN, k = 15, cosine, brute force | vote share of predicted class |
| M4 | Multinomial logistic regression (`lbfgs`, `max_iter=1000`), C ∈ {0.01, 0.1, 1} chosen by validation closed-set macro-F1 | maximum probability |
| M5 | CellTypist 1.7.1 `train` (`use_SGD=False`, `feature_selection=False`, defaults otherwise), `annotate` without majority voting | maximum CellTypist probability (one-vs-rest sigmoid) |
| M6 | scANVI (scvi-tools 1.4.1): SCVI `n_latent=30, n_layers=2`, batch = study×donor, 100 epochs; SCANVI from SCVI 20 epochs, `n_samples_per_label=100`; per held-out study, `load_query_data` then 50 epochs on **unlabelled** query cells (declared query adaptation) | maximum probability |

Practical track: P1 CellTypist `Immune_All_Low.pkl` v2 (sha256 `290874d3…6502`), no majority voting; P2 scTab run5 (`val_f1_macro_epoch=41_val_f1_macro=0.847.ckpt`, sha256 `573b911f…f56c`, behavioural provenance check R01 PASS). Released labels are mapped by `companion/src/celltransfer/label_maps.py` (frozen tables in `evidence/label-maps/`): `mapped` → target class; `coarser` → unresolved at the target level (never counted as accepted), lineage recorded; `outside` → if accepted, a fine-level error.

Tuning budget: only M4's C (3 values). Everything else uses the stated defaults. Seeds: 0 for model training, 20261005 for sampling and bootstrap. Not run: Pan-Human Azimuth and scGPT (reasons in `access-and-feasibility.md`).

## 4. Arms and class sets

- **Arm A (full reference).** Known classes K = target classes with ≥100 reference cells from ≥2 reference studies. Validation/test mapped cells whose class is not in K are **natural unknowns**.
- **Arm B (removed types).** Retrain M1–M6 with every pDC, ASC and MAIT cell removed from the reference (K_B = K minus these). Test cells of these classes are **simulated unknowns**, scored separately from natural unknowns. Thresholds re-tuned on validation known-class cells only.

## 5. Operating points (validation only)

For each method and arm, using validation cells that are mapped and in K:

- **OP-cov:** threshold τ accepting 90% of these validation cells (released labels mapped as `coarser` count as not accepted; if that cap is below 90%, accept all fine-level predictions and report the shortfall).
- **OP-err:** the lowest threshold whose validation accepted error is ≤5%; if none, report "not attainable".

## 6. Test metrics

Scorable test cells: mapped, in K. Unless stated, natural stratum only.

- Coverage (accepted fraction), accepted error, unassigned fraction at OP-cov and OP-err.
- Closed-set macro-F1 over K classes with ≥20 natural test cells (no abstention); per-class recall (natural + top-up) and precision (natural only).
- **Hierarchy error:** share of accepted errors that cross lineage group (fixed groups in `ontology.py`), and the cross-lineage error rate per accepted cell.
- Risk–coverage curve and area under it (AURC).
- **Unknown false acceptance:** fraction of unknown cells accepted at each operating point; natural (Arm A) and simulated (Arm B, all strata) separately; AUROC of confidence for known versus unknown.
- **Calibration** (probabilistic outputs M4, M5, M6, P1, P2): multiclass Brier score and 15-bin ECE of maximum probability; reliability plot. M1–M3 scores are labelled uncalibrated.
- Runtime and peak memory per method for fit and predict, measured in separate processes with `/usr/bin/time -l`, including data loading; a single timed run per step.
- Practical track additionally: fraction of scorable cells receiving `coarser` and `outside` labels, and lineage-level accuracy.

### Uncertainty

Cluster bootstrap over donors, resampled with replacement within each test study, 1,000 replicates, 95% percentile intervals. Method differences are paired within replicates (reference comparator: M4). Per-study estimates are shown; with four test studies there is no study-level interval. Cell counts are reported separately and never used as the unit of uncertainty.

## 7. Secondary analyses

- **Platform:** per-platform coverage and accepted error at OP-cov, descriptive, one donor.
- **Protein check:** per file, CLR-normalised ADT; per antibody, positive threshold from a 2-component Gaussian mixture on CLR values. Gates: CD4 T = CD3+CD4+CD8−; CD8 T = CD3+CD8+CD4−; B = CD19+CD3− (CD20 if CD19 absent); NK = CD56+CD3−CD19−CD14−; CD14 mono = CD14+CD3−CD19−CD56−; CD16 mono = CD16+CD14−CD3−CD19−CD56−. A cell matching exactly one gate gets that protein class; others are unresolved and counted. Metric: agreement of accepted RNA predictions (OP-cov) with protein class. Gates needing an absent antibody are skipped for that file.

## 8. Records, failures and reproducibility

- Each run has an immutable directory `runs/<ID>-<name>-<UTC timestamp>/` with command, inputs and hashes, stdout/stderr, `/usr/bin/time` output and results. Failed runs are kept; reruns get new directories. Cached outputs are labelled as cached.
- Disk guard: no pull or training step starts with less than 0.4 GiB free.
- Deviations from this protocol are logged in `evidence/protocol-deviations.md` with time and reason; primary results remain those defined here.

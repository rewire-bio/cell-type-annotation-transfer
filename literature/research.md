# Research Catalogue: Choosing a reference and annotation workflow for a new blood/PBMC cohort — and when to leave a cell unassigned

**Research Date**: 2026-10-05 (all retrievals 21:17–21:30 UTC; see `retrieval-log.md`)
**Total Sources**: 47 numbered sources (01–48; number 36 reserved for the 10x dataset licence, which could not be opened) held as 56 files (some sources have companion files, e.g. 01 + 01b SI + 02/02b/02c/02d repository files). By source: 42 with full text (article, preprint, author manuscript, or complete documentation), 5 abstract/metadata only (22 scGPT paper — paywalled, though its README 22b is complete; 31 OneK1K; 34 glaucoma collection record; 45 scGPT-calibration preprint record; 48 scDiagnostics abstract). By file: 49 full-text files, 7 metadata/abstract-only files (02d, 22, 25b, 31, 34, 45, 48). Originals total 19.8 MiB.
**Research Scope**: Primary sources for article 349 (Rewire benchmark of study-held-out annotation transfer, reference coverage and abstention in blood/PBMC), as required by `research/research-brief.md`: scTab (exact numbers), CellTypist, scANVI/scArches, Seurat v4/Azimuth and Pan-human Azimuth, CELLxGENE Census and Cell Ontology, rejection/unknown benchmarks, foundation-model evaluations, the primary papers of every reference/validation/test study in `evidence/protocol.md`, CITE-seq, and selective-classification/calibration background. No Rewire results are known or implied anywhere in this file.

**How to cite facts from this package.** Every location is `original-sources-text/<file>.txt:<line>` (abbreviated below as `<file stem>:<line>`). Line numbers are stable; the originals are in `original-sources/`. Text in "quotes" is verbatim from the cited line.

---

## Executive Summary

The published evidence on automated cell-type annotation is dominated by two evaluation designs that differ from the one the Rewire protocol freezes. The best-documented large-scale model, **scTab**, was trained and tested on a single CELLxGENE Census snapshot (LTS 2023-05-15) with **donor-level** splits: 22,189,056 cells, 5,052 donors, 164 cell types, 56 tissues, 10x assays only, and cell types with fewer than 5,000 cells or 30 donors removed (`01-paper-sctab-natcommun2024:70–80`). The authors explicitly chose donors over studies because a study split leaves cell types missing from train or test (`01-paper-sctab-natcommun2024:78`). Its "unknown cell type" analysis scores ROC-AUC of 1 − max-probability between correct predictions and the cell types that the rare-type filter itself removed (0.782), not between accepted and rejected cells at a fixed operating point (`01-paper-sctab-natcommun2024:240–248`). Comparators were trained on very different amounts of data (CellTypist 1.5 M cells, CIForm 750 k, fine-tuned scGPT 150 k, versus 15.2 M for scTab), which the paper states (`01-paper-sctab-natcommun2024:41,207,220,232`). When the same scTab corpus was later tested on **21 studies added in the next Census release**, macro-F1 fell from 80–84% to 52–57% for linear, MLP and TabNet models (`26-paper-hce-natcomputsci2025:30,34`). That drop is the single strongest published justification for whole-study holdout.

Rejection and uncertainty have been studied, but in separate pieces: Abdelaal et al. (2019) showed that a rejection option can fail badly when a whole lineage is missing (SVMrejection labelled "almost all T cells as B cells", `17-paper-abdelaal2019-genomebiol:149`); Theunissen et al. (2024) used accuracy–rejection curves within datasets (5-fold CV) (`19-paper-hierarchical-reject-bioinformatics2024:74,80`); conformal methods give finite-sample guarantees but rely on exchangeability that reference–query shift breaks (`20-paper-conformal-annotation-bioinformatics2025:112`); popV found that method-intrinsic certainties "are calibrated differently for the different methods" (`18-paper-popv-natgenet2024:41`); Engelmann et al. (2022) measured ECE and unseen-type detection on one lung atlas (`39-paper-engelmann-uq-atlas-cell-type-transfer-2022:55–56`). Foundation-model evaluations repeatedly find that simple baselines (HVG, PCA, logistic regression) match or beat zero-shot embeddings (`23-paper-kedzierska-zeroshot-genomebiol2025:38`; `24-preprint-boiarsky-deep-dive-scfm-biorxiv2023:73`; `25-paper-denadel-pretraining-size-natmethods2026-pmc:159`).

The novelty search (see `novelty-search.md`) found no published work that combines whole-study holdout, validation-tuned abstention compared at matched coverage, and removed-reference-type false acceptance across simple baselines and released models; the design is **partly anticipated** by the pieces above. The retrieval also surfaced several facts the coordinator should check before writing: the Human Immune Health Atlas test labels were *guided by* CellTypist Immune_All models and Seurat MapQuery (`27-paper-hiha-nature2025:136`), the platform study's labels were a CellTypist + Seurat consensus (`30-paper-scrnaseq-technologies-nar2025:109`), the CVID reference dataset consists of in-vitro-activated PBMCs (`42-paper-cvid-atlas-natcommun2022:87`), scGPT was pretrained on the same Census release as scTab (`22-paper-scgpt-natmethods2024-landing:89`), and the scTab census release carries an erratum of 243,569 duplicated primary cells (`12b-docs-census-data-release-info:246`). See "Findings that affect the protocol or article framing" below.

---

## A. scTab extraction (exact numbers with locations) — for contrast with the study-held-out design

| Item | scTab value | Location |
|---|---|---|
| Census release | CELLxGENE Census **2023-05-15**, chosen because it is an LTS release hosted ≥5 years | `01-paper-sctab-natcommun2024:70`; `02b-repo-sctab-docs-data-devel:6,15–16` |
| Gene space | 19,331 human protein-coding genes (GENCODE v38/Ensembl 104) | `01-paper-sctab-natcommun2024:70,138`; `02b-repo-sctab-docs-data-devel:17` |
| Primary-data filter | `is_primary_data == True` "to prevent label leakage" | `01-paper-sctab-natcommun2024:72`; `02b-repo-sctab-docs-data-devel:19` |
| Assays kept | 10x 5′ v2, 10x 3′ v3, 10x 3′ v2, 10x 5′ v1, 10x 3′ v1, 10x 3′ transcription profiling, 10x 5′ transcription profiling | `01-paper-sctab-natcommun2024:73`; `02b-repo-sctab-docs-data-devel:20–30` |
| Rare-type cut-off | ≥5,000 cells per type **and** ≥30 donors per type; otherwise the type is dropped | `01-paper-sctab-natcommun2024:75–76`; `02b-repo-sctab-docs-data-devel:33–35` |
| Coarse-label filter | type must have ≥7 parent nodes in the Cell Ontology (heuristic; coarse labels remain) | `01-paper-sctab-natcommun2024:35,77` |
| Ontology scoring rule | prediction counted correct if equal to, or a **subtype** of, the author label; a parent prediction is wrong | `01-paper-sctab-natcommun2024:125` |
| Resulting corpus | **22,189,056 cells; 164 cell types; 5,052 donors; 56 tissues**; 249 datasets | `01-paper-sctab-natcommun2024:80` (datasets: `:146` Fig. 1a caption); `02b-repo-sctab-docs-data-devel:80–87` |
| Split | by **donor**, 70/15/15 → train 15,240,192; val 3,500,032; test 3,448,832 cells | `01-paper-sctab-natcommun2024:78,80` |
| Why not study split | donor split "a sensible compromise between an entirely random split and a split based on holdout studies"; dataset splits give uneven sizes and miss cell types | `01-paper-sctab-natcommun2024:35,78` |
| Per-type train share | on average 68% of a type's cells in train; worst type 37% | `02b-repo-sctab-docs-data-devel:44–46` |
| Training donors | 3,536 donors at 100% donor subsample | `01-paper-sctab-natcommun2024:87` |
| scTab macro-F1 | 0.8295 ± 0.0007 (5 runs); 0.8300 ± 0.0069 with donor bootstrap (4 runs) | `01b-supplement-sctab-natcommun2024-si:96,112` |
| Optimised linear | trained on full 15.2 M; 0.7848 ± 0.0001 (4 runs) | `01-paper-sctab-natcommun2024:41`; `01b-…-si:99` |
| XGBoost | 256-d PCA input; 0.8127 ± 0.0005 (5 runs in Table 1a; Table 6 lists 4 runs — conflict) | `01-paper-sctab-natcommun2024:167`; `01b-…-si:97,168` |
| MLP | 0.7971 ± 0.0012 | `01b-…-si:98` |
| CellTypist | **subsampled to 1.5 M cells** (350 GB RAM), SGD mini-batch, `with_mean=False`, v1.5.3; 0.7304 ± 0.0015; default params 0.6258 ± 0.0036 | `01-paper-sctab-natcommun2024:41,59,207–217`; `01b-…-si:100,169` |
| scGPT zero-shot | logistic regression on whole-human scGPT embeddings, **1.5 M** training cells; 0.7301 ± 0.0035 | `01-paper-sctab-natcommun2024:41,220–227`; `01b-…-si:102` |
| scGPT fine-tuned | **150,000** cells (memory); 0.749 (1 run) | `01-paper-sctab-natcommun2024:41,232`; `01b-…-si:103` |
| CIForm | **750,000** cells; 0.766 (1 run) | `01-paper-sctab-natcommun2024:41`; `01b-…-si:104` |
| UCE zero-shot | linear probe on 1.5 M cells; Census 2023-12-15 embeddings, so evaluated on **736 of 758** test donors; 0.7611 ± 0.0018 | `01-paper-sctab-natcommun2024:235–236`; `01b-…-si:107` |
| Training cost | CellTypist ~16 h on 20 CPU cores; scTab ~33 h on one A100 | `01b-…-si:121,123` |
| Unknown/uncertainty setup | deep ensemble of **5** models; uncertainty = 1 − max(softmax); Group 1 correct, Group 2 incorrect (known types), Group 3 = types "excluded from the CELLxGENE training data because there were too few observations" | `01-paper-sctab-natcommun2024:239–246` |
| Unknown/uncertainty result | ROC-AUC 0.782 (correct vs absent types); 0.891 (correct vs incorrect) | `01-paper-sctab-natcommun2024:248` |
| Platform transfer | trained on 10x only; macro-F1 "~0.4" on about half of non-10x protocols vs "~0.8" on held-out 10x; poor on STRT-seq, Smart-seq2, BD Rhapsody Targeted | `01-paper-sctab-natcommun2024:49` |
| Coarse labels | 164 → 31 coarse labels: macro-F1 0.897 vs 0.830 fine | `01-paper-sctab-natcommun2024:42` |
| Authors' own caveat | strength "does not lie in correctly classifying novel cell types, but rather in context-specific suggestions" | `01-paper-sctab-natcommun2024:63` |
| Released artefacts | data 164 GB, checkpoints 8.1 GB, minimal subset 0.5 GB on pklab.med.harvard.edu; code MIT; devel head 5ede7f2 (2024-09-13) | `01-paper-sctab-natcommun2024:282,285`; `02-repo-sctab-readme-devel:8–10,65–67` |
| Tutorial checkpoint | `scTab-checkpoints/scTab/run5/val_f1_macro_epoch=41_val_f1_macro=0.847.ckpt`; genes from minimal store `var.parquet` | `02c-repo-sctab-model-inference-tutorial-devel:38–39,81,118–124` |
| Third-party mirror | Hugging Face `MohamedMabrouk/scTab`, created 2024-08-12, revision 9d49621…, tag `license:mit` | `02d-meta-huggingface-sctab-mirror` (JSON; fields `createdAt`, `sha`, `tags`) |
| Census erratum (scTab's release) | LTS 2023-05-15: 243,569 observations "represented at least twice with is_primary_data = True" | `12b-docs-census-data-release-info:242–248` |

**Contrast with the Rewire protocol (for the article, not a result):** scTab = one Census snapshot, donor holdout inside the same 249 studies, rare types removed before training, unknown types = those removed types, ROC-AUC rather than matched-coverage acceptance, comparators trained on 0.15–1.5 M versus 15.2 M cells. Rewire = Census LTS 2025-11-08, whole-study holdout with studies absent from scTab's 249 datasets, validation-only threshold tuning, accepted-error/coverage at fixed operating points, simulated unknowns by removing pDC/ASC/MAIT from the reference, matched-track comparators trained on identical cells (protocol §§2–6). The HCE paper (26) is the only published test of scTab-family models on new studies.

---

## B. Findings that affect the protocol or article framing (flag to coordinator)

1. **Test-label circularity risk (HIHA).** The Human Immune Health Atlas labels were produced by expert curation *guided by* CellTypist `Immune_All_High`, `Immune_All_Low` (98 types) and `Healthy_COVID19_PBMC`, plus Seurat `FindTransferAnchors`/`MapQuery` (`27-paper-hiha-nature2025:136`; expert step `:145`). P1 in the practical track is `Immune_All_Low`. Agreement between P1 and HIHA author labels is therefore not fully independent. (The reference used for MapQuery is not named on that line — unverified which.)
2. **Platform-study labels are model-derived.** The NAR technology comparison labelled cells by consensus of CellTypist and Seurat label transfer trained on the `pbmcsca` reference (ten labels); discordant cells were "Unassigned" (`30-paper-scrnaseq-technologies-nar2025:108–109,163`). Platform "accuracy" is agreement with a CellTypist/Seurat consensus at ~10-label resolution.
3. **CVID reference = activated cells.** The CVID study's ~100 k-cell single-cell cohort was PBMCs stimulated with CD40L + IL-21 or anti-CD3/CD28 (`42-paper-cvid-atlas-natcommun2022:87,104`); the CELLxGENE dataset title is "Activated PBMCs – Expanded cohort CITE-seq" (from the coordinator's inventory, not a source here). Healthy-control cells in this reference are likely in-vitro activated — verify in Census metadata before describing the reference as resting blood.
4. **scGPT corpus = scTab's census.** scGPT pretraining data "can be retrieved from the CELLxGENE census, release version 15 May 2023" (`22-paper-scgpt-natmethods2024-landing:89`); README: whole-human model "Pretrained on 33 million normal human cells" (`22b-repo-scgpt-readme:62`). Any test study present in that release would leak into scGPT.
5. **Census 2023-05-15 duplicates.** 243,569 cells marked primary more than once (`12b-docs-census-data-release-info:246`) — relevant to scTab's leakage control, which relied on `is_primary_data` (`01-paper-sctab-natcommun2024:72`). Do not claim this affected scTab's test set; it is unverified.
6. **CellTypist label counts differ by version.** Paper (author manuscript): low-hierarchy classifier with **91** types from **19 studies**, 20 tissues (`03-paper-celltypist-science2022:33,79,97`); registry v2 (2022-07-16): `Immune_All_Low` **98** types, "20 tissues of **18** studies"; `Immune_All_High` 32 types (`04-docs-celltypist-models:6–22`). Cite the registry for the model actually run.
7. **Pan-human Azimuth numbers.** Portal: "23 human tissues and **380** high-resolution cell types" (`08-web-azimuth-portal:5`); documentation site: "**381** different cell types" (`09b-web-pan-human-azimuth-site:35`); preprint: corpus ~27.04 M cells collected, final training set ~9.8 M split 7:1:2 (`09-preprint-pan-human-azimuth-2026:29,155`). Licence: panhumanpy code MIT (GitHub API), **model weights CC BY 4.0** (`10-repo-panhumanpy-readme:47–55`); preprint CC BY-NC 4.0. `access-and-feasibility.md` lists only "MIT".
8. **Tissue-specific Azimuth apps retired.** "we are no longer creating or updating tissue-specific Azimuth references, and we are no longer supporting the web applications" (`08-web-azimuth-portal:12`); R mapping to existing references still possible (`:13`).
9. **pklab host reachable today.** A plain ranged request to the scTab minimal archive returned HTTP 206 (gzip) at 21:27Z (retrieval-log §5), unlike the earlier challenge. Not used; recorded for provenance options.
10. **Validation study used elsewhere.** DenAdel et al. used the clonal-haematopoiesis dataset (Heimlich et al.) as their first cell-type classification benchmark (`25-paper-denadel-pretraining-size-natmethods2026-pmc:145`; ref. 32 at `:367`). Not a leakage issue for Rewire (no model trained on it), but worth knowing.
11. **Glaucoma test study has no publication.** CELLxGENE collection record has `doi: null`; links only to GitHub `mcrewcow/PBMC_Glaucoma_human` and GEO GSE268936; dataset 30c2a6fd has 207,952 cells, 10x 5′ v2, disease `normal` and `open-angle glaucoma`, 8 donors in total (`34-meta-cellxgene-glaucoma-collection`, JSON keys `doi`, `links`, `datasets`). The protocol's normal-only filter leaves 3 donors (coordinator inventory). Related ARVO abstract page is challenge-protected.
12. **OneK1K and Perez cell numbers.** OneK1K: 1,267,758 PBMCs from 982 donors (`31-meta-onek1k-yazar-science2022-europepmc:421`). Perez: >1.2 million PBMCs, 162 SLE cases, 99 controls (`32-paper-perez-lupus-science2022-pmc:257`).

---

## Source Inventory

Licence/access and "Supports" are recorded for each source. Retrieval date for all: 2026-10-05. Protocol element references are to `evidence/protocol.md` section numbers; article sections are the likely ones (Intro/why it matters; Published evidence; Method/benchmark design; Results context; Choosing a workflow; Limitations).

### 1. scTab: Scaling cross-tissue single-cell annotation models (01, 01b, 02, 02b, 02c, 02d)
- **Type**: Academic paper + supplement + repository docs + tutorial + third-party mirror metadata
- **Author(s)**: Felix Fischer, David S. Fischer, Roman Mukhin, Andrey Isaev, Evan Biederstedt, Alexandra-Chloé Villani, Fabian J. Theis
- **Publication/Platform**: Nature Communications 15, 6611; GitHub theislab/scTab (devel); Hugging Face mirror
- **Date**: 2024-08-04 (paper); repo head 5ede7f2, 2024-09-13; docs/data.md dated 29.08.2023
- **URL**: https://www.nature.com/articles/s41467-024-51059-5 ; https://github.com/theislab/scTab/tree/devel ; https://huggingface.co/MohamedMabrouk/scTab
- **Original File**: `original-sources/01-paper-sctab-natcommun2024.xml`, `01b-supplement-sctab-natcommun2024-si.pdf`, `02-repo-sctab-readme-devel.md`, `02b-repo-sctab-docs-data-devel.md`, `02c-repo-sctab-model-inference-tutorial-devel.ipynb`, `02d-meta-huggingface-sctab-mirror.json`
- **Licence/access**: Article CC BY 4.0 (`01-…:12`); code MIT (`02-…:65–67`); mirror tagged MIT (third party). Full text.
- **Supports**: Protocol §2 (overlap exclusion vs 249 datasets/4,314-donor lookup), §2 genes (19,331 scTab genes), §3 P2 (run5 checkpoint, `sf_log1p`), §4–6 contrast (unknown handling, metrics); article "Published evidence" and "Why study holdout".
- **Summary**: Trains a TabNet-derived classifier on 15.2 M cells from 249 CELLxGENE datasets and shows nonlinear models beat a tuned linear model under donor holdout; includes an uncertainty/novel-type ROC analysis and a non-10x transfer check. Exact numbers in Section A.
- **Key Insights**:
  - Donor split deliberately chosen over study split (`01-…:35,78`).
  - Comparators trained on far less data than scTab (`01-…:41,207,220,232`).
  - Novel types for the uncertainty test are the rare types the filter removed (`01-…:243`); AUC 0.782 (`:248`).
  - Default vs tuned hyperparameters matter: CellTypist 0.6258 → 0.7304, XGBoost 0.5855 → 0.8127 (`01-…:59`).
- **Quotable Content**: "We defined test holdouts based on donor annotation, which we see as a sensible compromise between an entirely random split and a split based on holdout studies." (`01-…:35`) / "the strength of these current models for automated cell type annotation does not lie in correctly classifying novel cell types" (`01-…:63`).

### 2. CellTypist — Domínguez Conde et al., Science 2022 (03) and model registry/README (04, 04b)
- **Type**: Academic paper (author manuscript) + documentation
- **Author(s)**: C. Domínguez Conde, C. Xu, L. B. Jarvis, … S. A. Teichmann
- **Publication/Platform**: Science 376, eabl5197; celltypist.cog.sanger.ac.uk; GitHub Teichlab/celltypist (main, fe357564a662)
- **Date**: 2022-05-13; Immune_All_* v2 built 2022-07-16
- **URL**: https://doi.org/10.1126/science.abl5197 ; https://celltypist.cog.sanger.ac.uk/models/models.json ; https://github.com/Teichlab/celltypist
- **Original File**: `03-paper-celltypist-science2022.xml`, `04-docs-celltypist-models.json`, `04b-repo-celltypist-readme.md`
- **Licence/access**: Author manuscript CC BY 4.0 (`03-…:14`); code MIT. Full text.
- **Supports**: Protocol §3 M5 and P1 (model identity, probability definition, no majority voting), §5 (`coarser` handling), article "Choosing a workflow".
- **Summary**: Introduces CellTypist, an L2-regularised logistic-regression annotator trained by mini-batch SGD with a top-300-genes-per-type feature selection (`03-…:97`). README defines the probability matrix as the sigmoid transform of the decision matrix (`04b-…:129`), default `best match` mode, optional `prob match` with `p_thres = 0.5` that yields "Unassigned" (`04b-…:132–138`), and majority voting over over-clustering (`04b-…:209–215`).
- **Key Insights**:
  - Registry: `Immune_All_Low.pkl` v2, 98 types, "immune sub-populations combined from 20 tissues of 18 studies"; `Immune_All_High.pkl` v2, 32 types (`04-…:6–22`).
  - Paper's low-hierarchy model had 91 types from 19 studies (`03-…:33,79,97`) — version mismatch (Section B.6).
  - Probabilities are one-vs-rest sigmoids, so they need not sum to 1 (`04b-…:129,134`).
  - Logistic regression training "usually leads to an unbiased probability range" for ≤100 k cells (`04b-…:421`).
- **Quotable Content**: "Query cell will get the label of 'Unassigned' if it fails to pass the probability cutoff in each cell type." (`04b-…:136`)

### 3. scANVI — Xu et al., Mol Syst Biol 2021 (05)
- **Type**: Academic paper
- **Author(s)**: Chenling Xu, Romain Lopez, Edouard Mehlman, Jeffrey Regier, Michael I. Jordan, Nir Yosef
- **Publication/Platform**: Molecular Systems Biology 17, e9620
- **Date**: 2021-01-25
- **URL**: https://doi.org/10.15252/msb.20209620
- **Original File**: `05-paper-scanvi-msb2021.xml`
- **Licence/access**: CC BY 4.0 (`05-…:13`). Full text.
- **Supports**: Protocol §3 M6 (scANVI, confidence = max posterior), article "Methods compared".
- **Summary**: Semi-supervised extension of scVI that propagates labels through a shared latent space with fully probabilistic outputs (`05-…:16,116,120`).
- **Key Insights**:
  - Confidence evaluated as the maximum posterior probability over observed classes; with an unlabelled dataset scANVI uses N + 1 classes (`05-…:247`).
  - scANVI is "robust to mislabeling", motivating explicit label-uncertainty modelling (`05-…:112`).
  - Label-transfer experiments are dataset pairs with full/partial overlap, not multi-study holdouts (`05-…:38,84–85`).
- **Quotable Content**: "The maximum posterior probability for the observed classes is the highest probability of a cell being assigned to one of the N observed classes." (`05-…:247`)

### 4. scArches — Lotfollahi et al., Nat Biotechnol 2022 (06)
- **Type**: Academic paper
- **Author(s)**: Mohammad Lotfollahi, Mohsen Naghipourfar, Malte D. Luecken, … Fabian J. Theis
- **Publication/Platform**: Nature Biotechnology 40, 121–130
- **Date**: epub 2021-08-30
- **URL**: https://doi.org/10.1038/s41587-021-01001-7
- **Original File**: `06-paper-scarches-natbiotechnol2022.xml`
- **Licence/access**: CC BY 4.0. Full text.
- **Supports**: Protocol §3 M6 (`load_query_data` query adaptation is scArches-style surgery), §4 Arm B background (left-out tissue), article "Methods compared".
- **Summary**: Transfer-learning "architecture surgery" maps query data onto a frozen reference without sharing raw data; label transfer via weighted kNN with an uncertainty score.
- **Key Insights**:
  - Cells with >50% uncertainty reported as unknown; ~84% accuracy across tissues; misclassified and unseen-tissue cells got high uncertainty (`06-…:67,217`).
  - Comparator rejection rules were ad hoc: Seurat lowest 20% projection scores → unknown; SVM uncertainty > 0.7 → unknown (`06-…:206–207`).
- **Quotable Content**: "We reported cells with more than 50% uncertainty as unknown to detect out-of-distribution cells with new labels" (`06-…:217`).

### 5. Seurat v4 / multimodal PBMC reference — Hao et al., Cell 2021 (07)
- **Type**: Academic paper
- **Author(s)**: Yuhan Hao, Stephanie Hao, Erica Andersen-Nissen, … Rahul Satija
- **Publication/Platform**: Cell 184, 3573
- **Date**: 2021-05-31 online (issue 2021-06-24)
- **URL**: https://doi.org/10.1016/j.cell.2021.04.048
- **Original File**: `07-paper-hao2021-seurat-v4-cell.xml`
- **Licence/access**: CC BY 4.0 (`07-…:13`). Full text.
- **Supports**: Protocol §2 reference study `ed5d841d` (Hao 2021); article "Reference choice" and CITE-seq context.
- **Summary**: Weighted-nearest-neighbour analysis of CITE-seq builds a PBMC reference of 210,911 cells (8 HIV-vaccine-trial volunteers × 3 time points; 228-antibody 10x 3′ panel) with 57 WNN clusters; introduces supervised PCA mapping and the Azimuth web app.
- **Key Insights**:
  - 8 volunteers, days 0/3/7; 10x 3′ (228 antibodies) and 10x 5′ (54 antibodies) → 210,911 cells; 161,764 10x 3′ cells in UMAP (`07-…:74–75`). The CELLxGENE dataset used by Rewire matches the 161,764 3′ cells/8 donors (coordinator inventory).
  - 57 clusters across all 24 samples (`07-…:78`).
  - Azimuth released as an automated web app (`07-…:468`).
- **Quotable Content**: "a CITE-seq dataset of 211,000 human peripheral blood mononuclear cells (PBMCs) with panels extending to 228 antibodies" (`07-…:16`).

### 6. Azimuth portal (08), Pan-human Azimuth preprint (09), site (09b) and panhumanpy README (10)
- **Type**: Web page, preprint, documentation, repository README
- **Author(s)**: HuBMAP/NYGC; Sourav Sarkar, Zhuoyan Li, … Rahul Satija (preprint)
- **Publication/Platform**: azimuth.hubmapconsortium.org; bioRxiv 2026.07.16.738997 (PMC13419436); satijalab.org; GitHub satijalab/panhumanpy (1.0.0 "Orion", head 06b9aba32c11)
- **Date**: preprint posted 2026-07-21; README commit 2026-07-27; portal undated (accessed 2026-10-05)
- **URL**: https://azimuth.hubmapconsortium.org/ ; https://doi.org/10.64898/2026.07.16.738997 ; https://satijalab.org/pan_human_azimuth/ ; https://github.com/satijalab/panhumanpy
- **Original File**: `08-web-azimuth-portal.html`, `09-preprint-pan-human-azimuth-2026.xml`, `09b-web-pan-human-azimuth-site.html`, `10-repo-panhumanpy-readme.md`
- **Licence/access**: preprint CC BY-NC 4.0 (`09-…:11`); code MIT; model weights CC BY 4.0 (`10-…:47–55`). Full text.
- **Supports**: Protocol §3 "Not run: Pan-Human Azimuth" (reason context), article "What a user can download today".
- **Summary**: Pan-human Azimuth replaces tissue-specific Azimuth apps with one hierarchical neural classifier across 23 tissues; returns hierarchical labels, calibrated confidence and an "Unassigned" class trained on empty droplets/multiplets.
- **Key Insights**:
  - Portal: replaces separate tissue apps; tissue-specific references no longer created or supported as web apps (`08-…:5,12–13`).
  - Corpus ~27.04 M cells, 23 tissues; quality-filtered, final ~9.8 M cells split 7:1:2 with stratified sampling — not a study holdout (`09-…:29,128,155`).
  - Confidence calibrated by entropy-informed temperature scaling per hierarchy level (`09-…:43`).
  - "Unassigned" is learned from ~145,000 negative profiles (empty droplets, multiplets), i.e. a QC reject class, not a novel-type detector (`09-…:131–134`).
  - New-donor check on Tabula Sapiens v2: median calibrated confidence 0.95; no systematic confidence decrease for new donors (`09-…:48`).
- **Quotable Content**: "Pan-Human Azimuth replaces the previous model of choosing separate Azimuth web applications for individual tissue or organ references." (`08-…:5`)

### 7. CZ CELLxGENE Discover (11), Census releases (12, 12b), schema 7.0.0 (13), AWS registry licence (14)
- **Type**: Academic paper + official documentation
- **Author(s)**: CZI Cell Science Program, Shibla Abdulla, Brian Aevermann, et al.
- **Publication/Platform**: Nucleic Acids Research 53, D886–D900; cellxgene-census docs; single-cell-curation repo; AWS Open Data Registry
- **Date**: NAR epub 2024-11-28; Census docs "Last edited: Nov 8th, 2025"; schema repo head 2026-09-02
- **URL**: https://doi.org/10.1093/nar/gkae1142 ; https://chanzuckerberg.github.io/cellxgene-census/cellxgene_census_docsite_data_release_info.html ; https://census.cellxgene.cziscience.com/cellxgene-census/v1/release.json ; https://github.com/chanzuckerberg/single-cell-curation/blob/main/schema/7.0.0/schema.md ; https://registry.opendata.aws/biohub-cellxgene-census/
- **Original File**: `11-…xml`, `12-docs-census-release-json.json`, `12b-docs-census-data-release-info.html`, `13-docs-cellxgene-schema-7.0.0.md`, `14-web-aws-registry-cellxgene-census.html`
- **Licence/access**: NAR article CC BY 4.0; hosted data "CC-BY 4.0" per AWS registry (`14-…:10–11`). Full text.
- **Supports**: Protocol §2 (LTS 2025-11-08, `is_primary_data`, schema 7.0.0, CL release), licence statement for redistribution; article "Data and provenance".
- **Summary**: CELLxGENE Discover hosts >93 M unique cells under a standard schema; Census exposes them as versioned TileDB-SOMA builds with LTS releases kept ≥5 years.
- **Key Insights**:
  - LTS 2025-11-08: Census schema 2.4.0, dataset schema 7.0.0, 1,845 datasets; 162,025,130 human cells of which 99,633,637 unique (`12b-…:83–100`); `release.json` marks `stable = 2025-11-08`, `lts: true` (`12-…:2,124–140`).
  - Schema 2.4.0 change: `disease` may now hold multiple values delimited by " || " so exact-match filters can be incomplete (`12b-…:94`). Relevant to the protocol filter `disease == 'normal'`.
  - `is_primary_data` "MUST be True if this is the canonical instance of this cellular observation" (`13-…:725`).
  - Schema 7.0.0 pins Cell Ontology release 2025-07-30 (`13-…:225`).
  - LTS kept "for at least 5 years upon publication" (`12b-…:69`); erratum for 2023-05-15 (`12b-…:242–248`).
  - Corpus ">93 million" unique cells, ~62% of human data from healthy donors (`11-…:35,61`).
- **Quotable Content**: "each observation (cell) should be marked is_primary data = True exactly once in the Census" (`12b-…:246`).

### 8. Cell Ontology — 2016 paper (15), v2025-07-30 release (16), 2025 preprint (40)
- **Type**: Academic paper, release record, preprint
- **Author(s)**: Alexander D. Diehl, Terrence F. Meehan, et al. (2016); Shawn Zheng Kai Tan, Aleix Puig-Barbe, et al. (2025, 35 authors)
- **Publication/Platform**: J Biomed Semantics 7, 44; GitHub obophenotype/cell-ontology; arXiv:2506.10037v3
- **Date**: 2016-07-04; release 2025-07-30T13:04:27Z; preprint v1 2025-06-10, v3 2026-02-13
- **URL**: https://doi.org/10.1186/s13326-016-0088-7 ; https://github.com/obophenotype/cell-ontology/releases/tag/v2025-07-30 ; https://arxiv.org/abs/2506.10037
- **Original File**: `15-…xml`, `16-release-cell-ontology-v2025-07-30.json`, `40-preprint-cell-ontology-2025-arxiv-v3.pdf`
- **Licence/access**: 2016 paper CC BY 4.0; preprint CC BY 4.0; CL licence not restated in release JSON. Full text.
- **Supports**: Protocol §2 label mapping (`cl-basic.obo` v2025-07-30), hierarchy error definition (§6); article "Labels and granularity".
- **Summary**: CL is the species-agnostic reference for canonical cell types used by CELLxGENE; the 2025 preprint describes its role in atlases and ongoing work on transcriptomic types.
- **Key Insights**:
  - Release tag `v2025-07-30`, "2025-07-30 Release", published 2025-07-30 (`16-…:29–37`).
  - 2025 preprint: CL as "a pivotal resource" for FAIR annotation across platforms (`40-…:4`).
  - scTab and HCE both note that CL is "continuously evolving" / "work in progress", which affects scoring (`01-…:63`; `26-…:52`).
- **Quotable Content**: "The Cell Ontology (CL) has emerged as a pivotal resource for achieving FAIR … data principles by providing standardized, species-agnostic terms for canonical cell types" (`40-…:4`).

### 9. Abdelaal et al., Genome Biology 2019 (17)
- **Type**: Benchmark paper
- **Author(s)**: Tamim Abdelaal, Lieke Michielsen, Davy Cats, Dylan Hoogduin, Hailiang Mei, Marcel J. T. Reinders, Ahmed Mahfouz
- **Publication/Platform**: Genome Biology 20, 194
- **Date**: 2019-09-09
- **URL**: https://doi.org/10.1186/s13059-019-1795-z
- **Original File**: `17-paper-abdelaal2019-genomebiol.xml`
- **Licence/access**: CC BY 4.0. Full text.
- **Supports**: Protocol §4 Arm B (removed-type design), §6 unknown false acceptance; article "Published evidence on rejection".
- **Summary**: 22 classifiers on 27 datasets, intra- and inter-dataset (incl. PbmcBench across 7 platforms), with negative-control and removed-population rejection experiments.
- **Key Insights**:
  - Scope: 22 methods, 27 datasets, accuracy + % unclassified + time (`17-…:20`).
  - Removed-population experiment: all T cells, then CD4+ T, then CD4+/CD45RO+ memory T removed from training (`17-…:148`).
  - SVMrejection "labels almost all T cells as B cells" when T cells are removed; posterior-based rejection "ignores the actual similarity between each cell and the assigned population" (`17-…:149`).
  - Overall recommendation: linear SVM with rejection (`17-…:171,181`).
- **Quotable Content**: "despite the importance of incorporating a rejection option in cell identity classifiers, the implementation of this rejection option remains challenging." (`17-…:149`)

### 10. popV — Ergen et al., Nat Genet 2024 (18)
- **Type**: Method + evaluation paper
- **Author(s)**: Can Ergen, Galen Xing, Chenling Xu, Martin Kim, Michael Jayasuriya, Erin McGeever, Angela Oliveira Pisco, Aaron Streets, Nir Yosef
- **Publication/Platform**: Nature Genetics 56, 2731
- **Date**: 2024-11-20
- **URL**: https://doi.org/10.1038/s41588-024-01993-3
- **Original File**: `18-paper-popv-natgenet2024.xml`
- **Licence/access**: CC BY-NC-ND 4.0. Full text.
- **Supports**: Protocol §6 calibration (method-specific confidence scales), article "When to accept a label".
- **Summary**: Ensemble of eight annotation methods with ontology-based voting; the consensus score acts as an uncertainty measure; evaluated on Lung Cell Atlas with Tabula Sapiens reference.
- **Key Insights**:
  - Method-intrinsic certainties "are calibrated differently for the different methods" (`18-…:41`).
  - Score ≥6 → >90% exact matches; score 8 → 98%; ≤3 → <50% (`18-…:52`).
  - Low scores arise from continua, reference-absent populations and reference annotation errors (`18-…:53–55`).
- **Quotable Content**: "we found that the certainties are calibrated differently for the different methods, which makes this approach futile" (`18-…:41`).

### 11. Theunissen et al., Bioinformatics 2024 — hierarchical reject option (19)
- **Type**: Evaluation paper
- **Author(s)**: Lauren Theunissen, Thomas Mortier, Yvan Saeys, Willem Waegeman
- **Publication/Platform**: Bioinformatics 40, btae128
- **Date**: 2024-03-05
- **URL**: https://doi.org/10.1093/bioinformatics/btae128
- **Original File**: `19-paper-hierarchical-reject-bioinformatics2024.xml`
- **Licence/access**: CC BY 4.0. Full text.
- **Supports**: Protocol §5 (thresholding), §6 (risk–coverage, `coarser` as partial rejection); article "Abstention".
- **Summary**: Compares full rejection, partial (internal-node) rejection and no rejection with flat and hierarchical LR/RF/SVM on five datasets including Azimuth PBMC, using accuracy–rejection curves.
- **Key Insights**:
  - Hierarchical + partial rejection preferred; threshold should be chosen by examining rejection behaviour (`19-…:21`).
  - Evaluated with 5-fold CV within dataset (80/20), validation split for hyperparameters (`19-…:74`) — not cross-study.
- **Quotable Content**: "For optimal rejection implementation, the rejection threshold should be determined through careful examination of a method’s rejection behavior." (`19-…:21`)

### 12. Conformal inference for scRNA-seq annotation, Bioinformatics 2025 (20)
- **Type**: Method paper
- **Author(s)**: Marcos López-De-Castro, Alberto García-Galindo, José González-Gomariz, Rubén Armañanzas
- **Publication/Platform**: Bioinformatics 41, btaf521
- **Date**: epub 2025-09-18
- **URL**: https://doi.org/10.1093/bioinformatics/btaf521
- **Original File**: `20-paper-conformal-annotation-bioinformatics2025.xml`
- **Licence/access**: CC BY 4.0. Full text.
- **Supports**: Article "Alternatives to thresholds" and "Limitations" (exchangeability); novelty search.
- **Summary**: OOD detector plus conformal classifier; leave-one-cell-type-out tests; immune experiments use the CellTypist cross-tissue immune atlas as reference with two independent lung queries.
- **Key Insights**:
  - Only one prior single-cell conformal work (Khatri & Bonn 2022) (`20-…:36`).
  - Reference = Domínguez Conde 2022 immune atlas; independent queries (`20-…:85`); calibration set 40% of training (`20-…:91`).
  - Covariate shift between reference and query can compromise exchangeability (`20-…:112`); low detector recall undermines guarantees (`20-…:129`).
- **Quotable Content**: "the derived conformal p-values directly control the marginal False Positive Rate" (`20-…:60`).

### 13. mtANN — Xiong et al., PLoS Comput Biol 2023 (21)
- **Type**: Method + benchmark paper
- **Author(s)**: Yi-Xuan Xiong, Meng-Guo Wang, Luonan Chen, Xiao-Fei Zhang
- **Publication/Platform**: PLoS Computational Biology 19, e1011261
- **Date**: 2023-06-28
- **URL**: https://doi.org/10.1371/journal.pcbi.1011261
- **Original File**: `21-paper-mtann-ploscompbiol2023.xml`
- **Licence/access**: CC BY 4.0. Full text.
- **Supports**: Novelty search (closest prior on PBMC dataset-held-out + unseen types); protocol §4 Arm B.
- **Summary**: Multi-reference ensemble for annotation with unseen-type identification; each PBMC-collection dataset (seven technologies) is held out as query in turn, with leave-one-cell-type-out to simulate unseen types; AUPRC for detection.
- **Key Insights**:
  - PBMC collection of seven datasets from different technologies; Pancreas collection (`21-…:38–39`).
  - Alternating query + one cell type left out; AUPRC (`21-…:44–45`).
  - Fixed thresholds (scmap) and fixed ratios (Seurat v3) generalise poorly; mtANN selects threshold from data (`21-…:48`); some experiments set the threshold from the true unseen proportion (`21-…:52`).
- **Quotable Content**: "Most methods for identifying unseen cell types use a fixed threshold … or a fixed ratio … as the threshold, which may not generalize well on new datasets." (`21-…:48`)

### 14. scGPT — Cui et al., Nat Methods 2024 (22, 22b)
- **Type**: Paper landing page (paywalled) + README
- **Author(s)**: Haotian Cui, Chloe Wang, Hassaan Maan, Kuan Pang, Fengning Luo, Nan Duan, Bo Wang
- **Publication/Platform**: Nature Methods 21, 1470–1480; GitHub bowang-lab/scGPT (main, cebd6fae655b)
- **Date**: 2024-02-26
- **URL**: https://doi.org/10.1038/s41592-024-02201-0 ; https://github.com/bowang-lab/scGPT
- **Original File**: `22-paper-scgpt-natmethods2024-landing.html`, `22b-repo-scgpt-readme.md`
- **Licence/access**: Paywalled; abstract/data availability only. Code MIT.
- **Supports**: Protocol §3 "Not run: scGPT" and pretraining-overlap concern; article "Foundation models".
- **Summary**: Generative pretrained transformer over "a repository of over 33 million cells" (`22-…:44`); pretraining data from Census 2023-05-15 (`22-…:89`); whole-human checkpoint "Pretrained on 33 million normal human cells" (`22b-…:62`).
- **Key Insights**: see Section B.4.
- **Quotable Content**: "Pretraining datasets can be retrieved from the CELLxGENE census, release version 15 May 2023" (`22-…:89`).

### 15. Kedzierska et al., Genome Biology 2025 — zero-shot evaluation (23)
- **Type**: Evaluation paper
- **Author(s)**: Kasia Z. Kedzierska, Lorin Crawford, Ava P. Amini, Alex X. Lu
- **Publication/Platform**: Genome Biology 26, 101
- **Date**: 2025-04-18
- **URL**: https://doi.org/10.1186/s13059-025-03574-x
- **Original File**: `23-paper-kedzierska-zeroshot-genomebiol2025.xml`
- **Licence/access**: CC BY 4.0. Full text.
- **Supports**: Article "Foundation models", justification for simple baselines in protocol §3.
- **Key Insights**:
  - scGPT and Geneformer zero-shot "perform inconsistently" vs HVG, scVI, Harmony (`23-…:38`).
  - Partial overlap between evaluation datasets and pretraining corpora found (`23-…:36`).
  - scGPT variants pretrained on 814 k kidney, 10.3 M blood, 33 M human cells compared (`23-…:37`).
- **Quotable Content**: "these models may face reliability challenges and could be outperformed by simpler methods" (`23-…:18`).

### 16. Boiarsky et al., bioRxiv 2023 — A Deep Dive into scRNA-seq foundation models (24)
- **Type**: Preprint
- **Author(s)**: Rebecca Boiarsky, Nalini Singh, Alejandro Buendia, Gad Getz, David Sontag
- **Publication/Platform**: bioRxiv 10.1101/2023.10.19.563100
- **Date**: posted 2023-10-23 (`24-…:269`)
- **URL**: https://www.biorxiv.org/content/10.1101/2023.10.19.563100v1.full
- **Original File**: `24-preprint-boiarsky-deep-dive-scfm-biorxiv2023.html`
- **Licence/access**: bioRxiv; licence not captured. Full text.
- **Supports**: Article "Simple baselines"; protocol M4.
- **Key Insights**:
  - L1-regularised logistic regression competitive with scBERT/scGPT for annotation "even in the few-shot setting" (`24-…:73`).
  - On Zheng68K, LR beat scBERT on accuracy and macro-F1 (`24-…:77–78`).
- **Quotable Content**: "We find that a simple logistic regression baseline is competitive with the pre-trained models for annotating cell types even in the few-shot setting." (`24-…:73`)

### 17. DenAdel et al., Nat Methods 2026 — pretraining size and diversity (25, 25b)
- **Type**: Evaluation paper (PMC author manuscript + publisher landing page)
- **Author(s)**: Alan DenAdel, Madeline Hughes, Akshaya Thoutam, Anay Gupta, Andrew W. Navia, Nicolo Fusi, Srivatsan Raghavan, Peter S. Winter, Ava P. Amini, Lorin Crawford
- **Publication/Platform**: Nature Methods 23, 1447–1457
- **Date**: 2026-06-09 (`25b-…:21,35`)
- **URL**: https://doi.org/10.1038/s41592-026-03120-y ; https://pmc.ncbi.nlm.nih.gov/articles/PMC13412022/
- **Original File**: `25-paper-denadel-pretraining-size-natmethods2026-pmc.html`, `25b-landing-denadel-natmethods2026.html`
- **Licence/access**: author manuscript (no CC licence); publisher page paywalled.
- **Supports**: Article "Foundation models / scale"; corpus link to scTab.
- **Key Insights**:
  - 400 models pretrained on subsets of the 22.2 M-cell scTab corpus; 6,400 experiments (`25-…:127,140`).
  - Fine-tuned classification "typically saturated at 1% of the training data and never required more than 10%" (`25-…:159`).
  - Baselines: HVG/PCA nearest neighbour; regularised logistic classifier on HVGs (`25-…:146`); first benchmark dataset = clonal haematopoiesis (`25-…:145`).
- **Quotable Content**: "current methods tend to plateau in performance with pre-training datasets that are only a fraction of the size of current training corpora" (`25-…:127`).

### 18. Hierarchical cross-entropy — Cultrera di Montesano et al., Nat Comput Sci 2026 (26)
- **Type**: Method + evaluation paper
- **Author(s)**: Sebastiano Cultrera di Montesano, Davide D’Ascenzo, Srivatsan Raghavan, Ava P. Amini, Peter S. Winter, Lorin Crawford
- **Publication/Platform**: Nature Computational Science 6, 243
- **Date**: 2026-01-30 (DOI 10.1038/s43588-025-00945-z)
- **URL**: https://www.nature.com/articles/s43588-025-00945-z
- **Original File**: `26-paper-hce-natcomputsci2025.xml`
- **Licence/access**: CC BY 4.0. Full text.
- **Supports**: Protocol §1 (why whole-study holdout), §6 hierarchy error; article "Published evidence" (headline contrast).
- **Summary**: Trains linear, MLP and TabNet on the scTab training split and tests both on scTab's donor-held-out test set (ID) and on 2.6 M cells from 21 studies newly added in Census 2023-12-15 (OOD).
- **Key Insights**:
  - ID macro-F1 80/82/84% → OOD 55/57/52% (linear/MLP/TabNet), drops of 24–32% (`26-…:30,34`).
  - OOD set: ~2.6 M cells, 21 studies, 470 donors, 16 tissues, 80 of 164 types, all 10x (`26-…:30,49`).
  - HCE loss improves OOD macro-F1 by 12–15% and recovers "roughly half" of the drop (`26-…:39`).
  - Prior benchmarks used "donor-partitioned training and test splits, a design we refer to as the in-distribution (ID) setting" (`26-…:29`).
- **Quotable Content**: "such splits do not reflect how cell atlases evolve in practice, where new studies are continually added and must be annotated upon release." (`26-…:29`)

### 19. Human Immune Health Atlas — Gong et al., Nature 2025 (27)
- **Type**: Primary study (test set e522d2cd)
- **Author(s)**: Qiuyu Gong, Mehul Sharma, Marla C. Glass, … Claire E. Gustafson
- **Publication/Platform**: Nature 648, 696
- **Date**: first published 2025-10-29
- **URL**: https://doi.org/10.1038/s41586-025-09686-5
- **Original File**: `27-paper-hiha-nature2025.xml`
- **Licence/access**: CC BY-NC-ND 4.0. Full text.
- **Supports**: Protocol §2 test study; article "Test cohorts" and limitations (label provenance).
- **Key Insights**:
  - Atlas labels: 9 (AIFI_L1), 29 (AIFI_L2), 71 (AIFI_L3) classes by expert annotation after iterative clustering (`27-…:145`); labelling guided by CellTypist Immune_All models and Seurat MapQuery (`27-…:136`).
  - >13.7 M PBMCs labelled with the atlas across the longitudinal cohort (`27-…:37`); 1,952,128 cells passed QC in the atlas build (`27-…:139`).
- **Quotable Content**: "To guide cell-type identification, we labelled cells from each sample using CellTypist (v.1.6.1)" (`27-…:136`).

### 20. RA PBMC scRNA-seq — Binvignat et al., JCI Insight 2024 (28)
- **Type**: Primary study (test set d18736c3)
- **Author(s)**: Marie Binvignat, Brenda Y. Miao, Camilla Wibrand, … Marina Sirota
- **Publication/Platform**: JCI Insight 9, e178499
- **Date**: 2024-07-02
- **URL**: https://doi.org/10.1172/jci.insight.178499
- **Original File**: `28-paper-ra-jciinsight2024.xml`
- **Licence/access**: CC BY 4.0. Full text.
- **Supports**: Protocol §2 test study.
- **Key Insights**: 36 individuals (18 RA, 18 matched controls), 10x Chromium, 18 PBMC subsets (`28-…:16,41,46`); Scanpy preprocessing (`28-…:100`).

### 21. JDM CITE-seq — Rabadam et al., JCI Insight 2024 (29)
- **Type**: Primary study (test set a199ca73)
- **Author(s)**: Gabrielle Rabadam, Camilla Wibrand, Emily Flynn, … Jessica Neely
- **Publication/Platform**: JCI Insight 9, e176963
- **Date**: 2024-05-14
- **URL**: https://doi.org/10.1172/jci.insight.176963
- **Original File**: `29-paper-jdm-jciinsight2024.xml`
- **Licence/access**: CC BY 4.0. Full text.
- **Supports**: Protocol §2 test study (CITE-seq; labels from WNN clustering of RNA + surface protein).
- **Key Insights**: scRNA-seq paired with surface protein (`29-…:16`); 15 JDM patients, 22 samples (`29-…:40`); WNN clustering (`29-…:43`).

### 22. Commercial scRNA-seq technologies — De Simone et al., NAR 2025 (30)
- **Type**: Primary study (platform test collection 398e34a9)
- **Author(s)**: Marco De Simone, Jonathan Hoover, Julia Lau, … Spyros Darmanis
- **Publication/Platform**: Nucleic Acids Research 53, gkae1186
- **Date**: epub 2024-12-16
- **URL**: https://doi.org/10.1093/nar/gkae1186
- **Original File**: `30-paper-scrnaseq-technologies-nar2025.xml`
- **Licence/access**: CC BY 4.0. Full text.
- **Supports**: Protocol §7 platform analysis (one donor); limitations.
- **Key Insights**: nine kits, four technology groups, PBMCs from a single donor, 169,262 cells (`30-…:19`); labels from CellTypist + Seurat consensus, discordant → "Unassigned" (`30-…:109,163`).

### 23. OneK1K — Yazar et al., Science 2022 (31)
- **Type**: Primary study (reference 3faad104), abstract only
- **Author(s)**: Seyhan Yazar, José Alquicira-Hernandez, Kristof Wing, … Joseph E. Powell
- **Publication/Platform**: Science 376, eabf3041
- **Date**: 2022-04-08
- **URL**: https://doi.org/10.1126/science.abf3041
- **Original File**: `31-meta-onek1k-yazar-science2022-europepmc.json`
- **Licence/access**: Paywalled; abstract via Europe PMC.
- **Supports**: Protocol §2 reference study.
- **Key Insights**: 1,267,758 PBMCs from 982 healthy subjects; 14 cell types for eQTL mapping (`31-…:421`).

### 24. Perez et al., Science 2022 — lupus (32)
- **Type**: Primary study (reference 218acb0f), PMC author manuscript
- **Author(s)**: Richard K. Perez, M. Grace Gordon, Meena Subramaniam, … Chun Jimmie Ye
- **Publication/Platform**: Science 376, eabf1970
- **Date**: 2022-04-08 (`32-…:55`)
- **URL**: https://pmc.ncbi.nlm.nih.gov/articles/PMC9297655/
- **Original File**: `32-paper-perez-lupus-science2022-pmc.html`
- **Licence/access**: author manuscript; no CC licence. Full text.
- **Supports**: Protocol §2 reference study.
- **Key Insights**: >1.2 M PBMCs, 162 SLE cases, 99 controls, multiplexed scRNA-seq (`32-…:257,263`).

### 25. COMBAT, Cell 2022 (33)
- **Type**: Primary study (reference ebc2e1ff)
- **Author(s)**: COVID-19 Multi-omics Blood ATlas (COMBAT) Consortium
- **Publication/Platform**: Cell 185, 916
- **Date**: first published 2022-01-21; issue 2022-03-03
- **URL**: https://doi.org/10.1016/j.cell.2022.01.012
- **Original File**: `33-paper-combat-cell2022.xml`
- **Licence/access**: CC BY 4.0. Full text.
- **Supports**: Protocol §2 reference study.
- **Key Insights**: multi-omic blood atlas comparing COVID-19 severities with influenza, sepsis and healthy volunteers (`33-…:16`).

### 26. Glaucoma PBMC atlas — CELLxGENE collection record (34)
- **Type**: Dataset metadata (no publication)
- **Author(s)**: contact Emil Kriukov (collection record)
- **Publication/Platform**: CZ CELLxGENE Discover collection de2cde16-c8d3-4a6d-80be-1be9e879aaca
- **Date**: published 2025-08-13; revised 2026-06-11
- **URL**: https://cellxgene.cziscience.com/collections/de2cde16-c8d3-4a6d-80be-1be9e879aaca
- **Original File**: `34-meta-cellxgene-glaucoma-collection.json`
- **Licence/access**: CELLxGENE data CC BY 4.0 (AWS registry); record itself states no licence.
- **Supports**: Protocol §2 test study (provenance caveat).
- **Key Insights**: see Section B.11. Description concerns HSP60 tolerance in glaucoma mice and PBMC scRNA-seq of POAG vs controls (record field `description`).

### 27. CITE-seq — Stoeckius et al., Nat Methods 2017 (35)
- **Type**: Method paper (PMC author manuscript)
- **Author(s)**: Marlon Stoeckius, Christoph Hafemeister, William Stephenson, Brian Houck-Loomis, Pratip K. Chattopadhyay, Harold Swerdlow, Rahul Satija, Peter Smibert
- **Publication/Platform**: Nature Methods 14(9), 865–868 (`35-…:55`)
- **Date**: 2017-07-31
- **URL**: https://pmc.ncbi.nlm.nih.gov/articles/PMC5669064/
- **Original File**: `35-paper-citeseq-stoeckius-natmethods2017-pmc.html`
- **Licence/access**: author manuscript; no CC licence.
- **Supports**: Protocol §7 protein check (background); article "Orthogonal evidence".
- **Key Insights**: CITE-seq combines oligo-barcoded antibody detection with transcriptome profiling in the same cells (`35-…:120`).

### 28. Selective classification — Geifman & El-Yaniv 2017 (37)
- **Type**: Conference paper (NeurIPS 2017; arXiv)
- **Author(s)**: Yonatan Geifman, Ran El-Yaniv
- **Date**: arXiv 2017 (PDF dated 2 June 2017)
- **URL**: https://arxiv.org/abs/1705.08500
- **Original File**: `37-paper-geifman-selective-classification-neurips2017.pdf`
- **Licence/access**: arXiv non-exclusive licence. Full text.
- **Supports**: Protocol §5–6 (OP-cov, OP-err, risk–coverage, AURC); article "Accept or abstain".
- **Key Insights**: selective classifier = classifier + selection function gθ(x) = 1 if confidence κ ≥ θ; selective risk and coverage defined empirically (`37-…:21`); goal to guarantee a desired risk while maximising coverage (`37-…:15`); softmax response (SR) as confidence-rate function (`37-…:42,45`).
- **Quotable Content**: "Selective classification techniques (also known as reject option) … can potentially significantly improve DNNs prediction performance by trading-off coverage." (`37-…:3`)

### 29. Calibration — Guo et al. 2017 (38)
- **Type**: Conference paper (ICML 2017; arXiv)
- **Author(s)**: Chuan Guo, Geoff Pleiss, Yu Sun, Kilian Q. Weinberger
- **URL**: https://arxiv.org/abs/1706.04599
- **Original File**: `38-paper-guo-calibration-icml2017.pdf`
- **Licence/access**: arXiv non-exclusive licence. Full text.
- **Supports**: Protocol §6 (ECE with 15 bins, reliability plot); article "Is the confidence honest?".
- **Key Insights**: perfect calibration defined as P(Ŷ = Y | P̂ = p) = p (`38-…:29`); ECE bins predictions into M equal-width bins (`38-…:31–32`); modern networks are poorly calibrated (`38-…:12,27`).

### 30. Engelmann et al. 2022 — UQ for atlas-level cell-type transfer (39)
- **Type**: Workshop paper (ICML 2022 CompBio; arXiv)
- **Author(s)**: Jan Engelmann, Leon Hetzel, Giovanni Palla, Lisa Sikkema, Malte Luecken, Fabian Theis
- **Date**: arXiv 2022-11-07
- **URL**: https://arxiv.org/abs/2211.03793
- **Original File**: `39-paper-engelmann-uq-atlas-cell-type-transfer-2022.pdf`
- **Licence/access**: arXiv non-exclusive licence. Full text.
- **Supports**: Novelty search; protocol §6 calibration + unknown detection.
- **Key Insights**: HLCA (14 datasets, 107 individuals, 58 types) (`39-…:11`); baselines WKNN/RF worse on a leave-out dataset; ECE reported; B, mast and ionocytes left out for unseen-type AUPR (`39-…:55–56`); "baseline methods are not well calibrated" (`39-…:81`).
- **Quotable Content**: "it is not possible to state the model doesn’t know when it doesn’t know" (`39-…:80`).

### 31–34. Reference/validation study papers: van der Wijst 2021 (41), CVID atlas 2022 (42), kidney cancer 2022 (43), clonal haematopoiesis 2024 (44)
- **Type**: Primary studies (reference 01ad3cd7, reference 3c75a463, validation 5af90777, validation 19e46756)
- **Author(s)**: van der Wijst MGP et al. (UCSF COMET); Rodríguez-Ubreva J … Ballestar E; Li R … Mitchell TJ; Heimlich JB … Ferrell PB
- **Publication/Platform**: Sci Transl Med 13, eabh2624; Nat Commun 13, 1779; Cancer Cell 40, 1583; Blood Adv 8, 3665
- **Date**: 2021-08-24; 2022-04-01; 2022-11-23; 2024-03-22
- **Original File**: `41-…xml`, `42-…xml`, `43-…xml`, `44-…xml`
- **Licence/access**: CC BY 4.0 (41, 42, 43); CC BY-NC-ND 4.0 (44). Full text.
- **Supports**: Protocol §2 data roles; label provenance.
- **Key Insights**: CVID single-cell cohort = PBMCs stimulated in vitro (`42-…:87`); kidney study profiled peripheral blood alongside tumour regions (`43-…:16,197`); CH study annotated with ScType plus manual curation of low-confidence types (`44-…:47`).

### 35. "When Simpler Models Win" — Khosravi et al., Research Square 2026 (45)
- **Type**: Preprint record (abstract only)
- **Author(s)**: Khosravi A, Khosravi A, Langowski K, Sieczczynski M, Pastuszak K, Supernat A, Zaczek A
- **Date**: 2026-07-20
- **URL**: https://doi.org/10.21203/rs.3.rs-10152510/v1
- **Original File**: `45-meta-khosravi-scgpt-calibration-researchsquare2026-europepmc.json`
- **Licence/access**: not stated; not peer reviewed.
- **Supports**: Novelty search; article "calibration of foundation-model pipelines".
- **Key Insights**: within-atlas evaluation of six atlases (1.3 M cells); matched-gene logistic regression macro-F1 0.94–0.99 with ECE ≤ 0.013 on every atlas; scGPT-embedding + LogReg "substantially miscalibrated" (`45-…:68`).

### 36. Hu et al. 2025 — matching benchmark (46)
- **Type**: Preprint (in PMC)
- **Author(s)**: Joyce Hu, Beverly Peng, … Yun Zhang
- **Date**: 2025-04-16
- **URL**: https://doi.org/10.1101/2025.04.10.648034
- **Original File**: `46-paper-hu-matching-benchmark-2025.xml`
- **Supports**: Article "What happens to cells the reference lacks".
- **Key Insights**: CellRef cells mapped to HLCA could be "unassigned" (`46-…:65`); megakaryocyte/platelet cells absent from HLCA were matched to mast cells by CellTypist and poorly matched by Azimuth/scArches; only FR-Match left them unassigned (`46-…:85`).

### 37. Huang et al., GPB 2021 — R annotation packages (47)
- **Type**: Benchmark paper
- **Author(s)**: Qianhui Huang, Yu Liu, Yuheng Du, Lana X. Garmire
- **Date**: epub 2020-12-24 (vol. 19, 267–281, 2021)
- **URL**: https://doi.org/10.1016/j.gpb.2020.07.004
- **Original File**: `47-paper-huang-annotation-r-packages-gpb2021.xml`
- **Supports**: Background on "unknown allowed" methods.
- **Key Insights**: ten R methods; table of which allow unknown types (`47-…:27–38`).

### 38. scDiagnostics, bioRxiv 2026 (48)
- **Type**: Preprint abstract
- **Author(s)**: Anthony Christidis, Andrew Ghazi, Smriti Chawla, Nitesh Turaga, Robert Gentleman, Ludwig Geistlinger
- **Date**: posted 2026-02-02 (`48-…:72`)
- **URL**: https://doi.org/10.64898/2026.01.29.701618
- **Original File**: `48-preprint-scdiagnostics-biorxiv2026-abstract.html`
- **Supports**: Novelty search; article "diagnostics after annotation".
- **Key Insights**: diagnostic package for ambiguous/conflicting annotations when transferring from a reference (`48-…:56`); not an abstention benchmark.

### Not obtained: 10x Genomics dataset licence (36)
- Dataset pages blocked (Vercel checkpoint). Search snippets for other 10x PBMC datasets show CC BY 4.0; the four protocol files' licence is **unverified** (retrieval-log §4 items 18–19, §5).

---

## Thematic Organization

### Theme 1: Evaluation design — donor, study, platform holdout
- Sources: 01, 02b, 26, 17, 21, 30, 39, 09
- Key Points: scTab and most large-model benchmarks use donor splits inside one snapshot (01:35,78; 26:28). Holding out new studies cut macro-F1 by 24–32% (26:34). Platform transfer from 10x-only training dropped to ~0.4 on half of non-10x protocols (01:49). Earlier benchmarks did cross-dataset (Abdelaal PbmcBench, mtANN) but at small scale and without abstention at matched coverage (17; 21). Pan-human Azimuth uses a stratified 7:1:2 split plus new-donor checks (09:48,155).

### Theme 2: Abstention, rejection and unknown types
- Sources: 01, 04b, 06, 17, 18, 19, 20, 21, 39, 46, 37
- Key Points: Rejection is usually a fixed or ad-hoc threshold (CellTypist p_thres 0.5, scArches 50%, Seurat lowest 20%, SVM 0.7) (04b:134; 06:206–207,217). Posterior-based rejection can fail when a whole lineage is missing (17:149) and closed-set methods force absent types into the nearest label (46:85). scTab measures novel-type separability by ROC-AUC, not acceptance at an operating point (01:248). Selective-classification theory supplies coverage/risk definitions (37:21).

### Theme 3: Calibration and confidence semantics
- Sources: 04b, 05, 09, 18, 20, 38, 39, 45
- Key Points: Confidence scores mean different things: CellTypist one-vs-rest sigmoid (04b:129), scANVI max posterior (05:247), scTab 1 − max softmax of a 5-model ensemble (01:239,245), Pan-human Azimuth temperature-scaled per level (09:43). popV found method certainties calibrated differently (18:41). ECE definition (38:31–32); baselines miscalibrated on atlas transfer (39:81); scGPT embedding pipelines miscalibrated vs matched LR within atlases (45:68).

### Theme 4: Reference coverage, label granularity and the ontology
- Sources: 01, 03, 04, 13, 15, 16, 26, 40, 19
- Key Points: Granularity varies by study; scTab counts a finer prediction as correct and a coarser one as wrong (01:125); HCE aligns training with that rule (26:72). CellTypist High/Low (32/98 types) give two resolutions (04:6–22). Partial rejection to an internal node preserves information (19:21). CELLxGENE schema 7.0.0 pins CL 2025-07-30 (13:225).

### Theme 5: Simple baselines versus foundation models
- Sources: 01, 22, 23, 24, 25, 45
- Key Points: Tuned linear models remain strong (01:41; 24:73); zero-shot FMs inconsistent (23:38); FM pretraining saturates early (25:159); scGPT corpus from Census 2023-05-15 (22:89).

### Theme 6: Data provenance, overlap and licence
- Sources: 11, 12, 12b, 13, 14, 22, 27, 30, 34, 42, 02d
- Key Points: `is_primary_data` semantics and the 2023-05-15 duplicate erratum (13:725; 12b:246); LTS 2025-11-08 details and multi-valued `disease` (12b:83–100,94); CC-BY 4.0 for Census data (14:11); test-label provenance (27:136; 30:109); activated CVID reference (42:87); glaucoma study without paper (34); scTab checkpoint via third-party mirror (02d).

---

## Content Gaps & Further Research

- **10x CITE-seq licence** for the four protocol files is unverified (dataset pages bot-protected).
- **scGPT full text** inaccessible; pretraining-corpus composition by dataset ID not verified here.
- **Glaucoma atlas** has no peer-reviewed description; donor/disease handling rests on the CELLxGENE record.
- **CVID dataset composition** in Census (activated vs resting cells; condition fields) should be checked in metadata before calling the reference "blood/PBMC" without qualification.
- **HIHA MapQuery reference** (which Seurat reference guided labels) not stated on the retrieved line; check Methods/Extended Data.
- **Khatri & Bonn 2022 (PMLR v179)** conformal label-transfer paper not retrieved.
- **scTab Supp. Fig. 4** ROC curves are images; only the AUC values in the main text are machine-readable.
- **No source** reports matched-coverage accepted error or unknown false-acceptance for CellTypist Immune_All_Low or scTab on independent PBMC studies — this is the gap the Rewire benchmark addresses (see `novelty-search.md`).
- Discrepancy notes to carry into the article: CellTypist 91 vs 98 types; Pan-human Azimuth 380 vs 381 types; scTab XGBoost run count 5 vs 4 (01b:97 vs :168); scTab docs typo "3.500.,032" (02b:84).

---

## Citation Quick Reference

- Fischer F, et al. scTab: Scaling cross-tissue single-cell annotation models. *Nat Commun* 15, 6611 (2024). https://doi.org/10.1038/s41467-024-51059-5
- Domínguez Conde C, et al. Cross-tissue immune cell analysis reveals tissue-specific features in humans. *Science* 376, eabl5197 (2022). https://doi.org/10.1126/science.abl5197
- Xu C, et al. Probabilistic harmonization and annotation of single-cell transcriptomics data with deep generative models. *Mol Syst Biol* 17, e9620 (2021). https://doi.org/10.15252/msb.20209620
- Lotfollahi M, et al. Mapping single-cell data to reference atlases by transfer learning. *Nat Biotechnol* 40, 121–130 (2022). https://doi.org/10.1038/s41587-021-01001-7
- Hao Y, et al. Integrated analysis of multimodal single-cell data. *Cell* 184, 3573 (2021). https://doi.org/10.1016/j.cell.2021.04.048
- Sarkar S, et al. Organism-scale annotation with Pan-human Azimuth. *bioRxiv* (2026). https://doi.org/10.64898/2026.07.16.738997
- CZI Cell Science Program, et al. CZ CELLxGENE Discover. *Nucleic Acids Res* 53, D886–D900 (2025). https://doi.org/10.1093/nar/gkae1142
- Diehl AD, et al. The Cell Ontology 2016. *J Biomed Semantics* 7, 44 (2016). https://doi.org/10.1186/s13326-016-0088-7
- Tan SZK, et al. The Cell Ontology in the age of single-cell omics. arXiv:2506.10037 (2025).
- Abdelaal T, et al. A comparison of automatic cell identification methods for single-cell RNA sequencing data. *Genome Biol* 20, 194 (2019). https://doi.org/10.1186/s13059-019-1795-z
- Ergen C, et al. Consensus prediction of cell type labels in single-cell data with popV. *Nat Genet* 56, 2731 (2024). https://doi.org/10.1038/s41588-024-01993-3
- Theunissen L, et al. Uncertainty-aware single-cell annotation with a hierarchical reject option. *Bioinformatics* 40, btae128 (2024). https://doi.org/10.1093/bioinformatics/btae128
- López-De-Castro M, et al. Conformal inference for reliable single cell RNA-seq annotation. *Bioinformatics* 41, btaf521 (2025). https://doi.org/10.1093/bioinformatics/btaf521
- Xiong Y-X, et al. Cell-type annotation with accurate unseen cell-type identification using multiple references. *PLoS Comput Biol* 19, e1011261 (2023). https://doi.org/10.1371/journal.pcbi.1011261
- Cui H, et al. scGPT. *Nat Methods* 21, 1470–1480 (2024). https://doi.org/10.1038/s41592-024-02201-0
- Kedzierska KZ, et al. Zero-shot evaluation reveals limitations of single-cell foundation models. *Genome Biol* 26, 101 (2025). https://doi.org/10.1186/s13059-025-03574-x
- Boiarsky R, et al. A Deep Dive into Single-Cell RNA Sequencing Foundation Models. *bioRxiv* (2023). https://doi.org/10.1101/2023.10.19.563100
- DenAdel A, et al. Evaluating the role of pretraining dataset size and diversity on single-cell foundation model performance. *Nat Methods* 23, 1447–1457 (2026). https://doi.org/10.1038/s41592-026-03120-y
- Cultrera di Montesano S, et al. Improving atlas-scale single-cell annotation models with hierarchical cross-entropy loss. *Nat Comput Sci* 6, 243 (2026). https://doi.org/10.1038/s43588-025-00945-z
- Gong Q, et al. Multi-omic profiling reveals age-related immune dynamics in healthy adults. *Nature* 648, 696 (2025). https://doi.org/10.1038/s41586-025-09686-5
- Binvignat M, et al. *JCI Insight* 9, e178499 (2024). https://doi.org/10.1172/jci.insight.178499
- Rabadam G, et al. *JCI Insight* 9, e176963 (2024). https://doi.org/10.1172/jci.insight.176963
- De Simone M, et al. *Nucleic Acids Res* 53, gkae1186 (2025). https://doi.org/10.1093/nar/gkae1186
- Yazar S, et al. *Science* 376, eabf3041 (2022). https://doi.org/10.1126/science.abf3041
- Perez RK, et al. *Science* 376, eabf1970 (2022). https://doi.org/10.1126/science.abf1970
- COMBAT Consortium. *Cell* 185, 916 (2022). https://doi.org/10.1016/j.cell.2022.01.012
- Stoeckius M, et al. Simultaneous epitope and transcriptome measurement in single cells. *Nat Methods* 14, 865–868 (2017). https://doi.org/10.1038/nmeth.4380
- Geifman Y, El-Yaniv R. Selective Classification for Deep Neural Networks. NeurIPS 2017. arXiv:1705.08500
- Guo C, et al. On Calibration of Modern Neural Networks. ICML 2017. arXiv:1706.04599
- Engelmann J, et al. Uncertainty Quantification for Atlas-Level Cell Type Transfer. ICML 2022 CompBio Workshop. arXiv:2211.03793

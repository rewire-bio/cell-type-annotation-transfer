# Novelty search — article 349 (study-held-out annotation transfer with abstention and unknown false acceptance)

**Date**: 2026-10-05 (searches 21:17–21:29 UTC). **Searcher**: blog-research-curator worker. **Tools**: WebSearch (US index), Europe PMC REST search, direct reading of retrieved full texts. Exact queries and hits are listed in `retrieval-log.md` §4 (queries 6–16 and 20–24 were novelty-directed).

## Question searched

Has prior work already evaluated cell-type annotation with **all** of the following together?

- (A) **Study- or platform-held-out** query data (whole studies not seen in training, not donor or random splits);
- (B) **Abstention compared at matched coverage** (thresholds tuned on separate validation data, then accepted error compared at a fixed accepted fraction, or coverage at a fixed error);
- (C) **Removed-reference-type (unknown) false acceptance** (entire cell types removed from the reference and the fraction of those cells *accepted* with a label reported at the operating point);
- (D) Across **simple baselines** (marker rule, centroid, kNN, logistic regression) **and released models** (e.g. CellTypist Immune_All_Low, scTab), with a matched-training track separating method effects from training-data effects.

## Queries run (novelty-directed)

1. `conformal prediction cell type annotation single-cell abstention unknown cell types 2024 2025`
2. `benchmark cell type annotation cross-study reference mapping rejection unknown cell types 2024 2025 Genome Biology`
3. `single-cell cell type annotation "selective classification" OR "risk-coverage" OR "accuracy-rejection" curve benchmark`
4. `open-set cell type annotation benchmark unseen cell types rejection held-out dataset logistic regression baseline foundation model 2025`
5. `benchmarking single-cell foundation models cell type annotation out-of-distribution new studies held-out datasets scGPT Geneformer logistic regression 2025`
6. `"Uncertainty-aware single-cell annotation with a hierarchical reject option" Bioinformatics`
7. `leave-one-study-out cell type annotation PBMC unknown cell type false positive rejection threshold CellTypist scANVI comparison`
8. `cell type annotation benchmark "missing cell types" in reference query "false" assignment Azimuth CellTypist scANVI SingleR independent dataset 2024`
9. `"cell type annotation" calibration "expected calibration error" single-cell reference mapping uncertainty benchmark`
10. `scTab follow-up evaluation independent dataset "scTab" CellTypist comparison held-out study annotation 2025`
11. `"cell type" annotation "unseen" OR "novel" cell types removed from reference "false positive" rate benchmark CellTypist scANVI Seurat SingleR "held-out" study 2025 bioRxiv`
12. `cell annotation "reject option" OR "abstain" "coverage" PBMC cross-dataset benchmark "logistic regression" "kNN" 2024 2025 2026 preprint`
13. `"cell type annotation" "accepted" "coverage" "unassigned" benchmark "new study" OR "held-out studies" reference atlas confidence threshold calibrated validation 2026`
14. `single-cell annotation benchmark "out-of-reference" OR "reference-absent" cell types false acceptance confidence threshold PBMC independent cohorts CellTypist Azimuth scTab comparison`
15. Europe PMC: `TITLE:"scGPT" AND SRC:PPR` (to find calibration benchmarks of foundation models).

Limitations of the search: one web index (US), English only, no paywalled full texts (scGPT, OneK1K), no conference proceedings beyond what search surfaced (e.g. Khatri & Bonn 2022 PMLR not read), no citation chasing beyond the retrieved papers. A missed preprint is possible, especially in the July–October 2026 window.

## What was found (closest prior work, by criterion)

| Work | (A) study/platform holdout | (B) matched-coverage abstention, validation-tuned | (C) removed-type false acceptance | (D) simple baselines + released models, matched track | Evidence |
|---|---|---|---|---|---|
| scTab (Fischer 2024) | No — donor split inside one Census snapshot; non-10x transfer reported descriptively | No — uncertainty only as ROC-AUC | Partly — "absent" types are those removed by the rare-type filter; ROC-AUC 0.782, no acceptance rate | Partly — CellTypist, linear, XGBoost, MLP, scGPT, CIForm, UCE, but on very different training sizes | `01-paper-sctab-natcommun2024:35,49,78,239–248`; `01b-…-si:94–117` |
| HCE (Cultrera di Montesano 2026) | **Yes** — 21 new studies from Census 2023-12-15 | No | No | Partly — linear/MLP/TabNet trained identically; no released models | `26-paper-hce-natcomputsci2025:30,34,49` |
| Abdelaal 2019 | Partly — inter-dataset PbmcBench (platforms) | No — % unlabelled reported, not matched coverage | **Yes** — T cells / CD4 T / CD4 memory T removed; % unlabelled | Partly — 22 methods incl. kNN, NMC, LDA, SVM; no released pretrained atlas models | `17-paper-abdelaal2019-genomebiol:20,148–149` |
| mtANN (Xiong 2023) | **Yes** — each of 7 PBMC platform datasets held out in turn | No — threshold selection compared; AUPRC; some settings use the true unseen proportion | **Yes** — leave-one-cell-type-out, AUPRC | Partly — scmap, Seurat v3, ItClust, scGCN etc.; no released atlas models | `21-paper-mtann-ploscompbiol2023:38–39,44–48,52` |
| Engelmann 2022 | Partly — one leave-out dataset in HLCA | No — ECE and calibration curves, no operating point | **Yes** — B, mast, ionocytes left out; AUPR | No — WKNN, RF, DKL, MIMO on a fixed latent space | `39-paper-engelmann-uq-atlas-cell-type-transfer-2022:11,55–56` |
| Theunissen 2024 | No — 5-fold CV within datasets | Partly — accuracy–rejection curves | No | Partly — LR, RF, linear SVM (flat vs hierarchical) | `19-paper-hierarchical-reject-bioinformatics2024:21,74,80` |
| Conformal (López-De-Castro 2025) | Partly — CellTypist immune atlas → independent lung queries; one-subject-out pancreas | Partly — conformal sets with coverage guarantees (assume exchangeability) | **Yes** — leave-one-cell-type-out; power/FPR/FDR | Partly — scmap, CellTypist, TorchNet | `20-paper-conformal-annotation-bioinformatics2025:85–91,112,129` |
| popV (Ergen 2024) | Partly — TS reference → Lung Cell Atlas query | Partly — accuracy by consensus score, no validation-tuned threshold | Anecdotal — query-specific populations get low scores | Partly — eight methods incl. CellTypist, scANVI, kNN | `18-paper-popv-natgenet2024:41,52–55` |
| Hu 2025 (matching benchmark) | **Yes** — CellRef ↔ HLCA lung atlases | No | Anecdotal — cells absent from reference (platelets/MK) mis-assigned by CellTypist | Partly — Azimuth, CellTypist, scArches, FR-Match | `46-paper-hu-matching-benchmark-2025:65,85` |
| Khosravi 2026 (scGPT calibration) | No — "within-atlas" | No — ECE only | No | Partly — matched-gene LR/XGBoost/RF vs scGPT probes | `45-…:68` |
| Pan-human Azimuth 2026 | No — stratified 7:1:2 split; new donors in Tabula Sapiens v2 | Partly — calibrated confidence, Unassigned for QC failures | No | No | `09-preprint-pan-human-azimuth-2026:43,48,131–134,155` |
| scDiagnostics 2026 | n/a (diagnostic tool) | No | Partly — detects anomalous/out-of-reference annotations | n/a | `48-preprint-scdiagnostics-biorxiv2026-abstract:56` |

No retrieved work reports **accepted error at a validation-fixed coverage (or coverage at a fixed error)** for **CellTypist Immune_All_Low or scTab on PBMC studies that are absent from their training data**, nor **unknown false acceptance at that same operating point**, nor separates **matched-training method effects from released-artefact effects**.

## Conclusion

**Partly anticipated, not already done.** Each ingredient exists in prior work — study holdout (HCE; mtANN for platforms), removed-type unknowns (Abdelaal; mtANN; Engelmann; conformal), rejection curves (Theunissen) and calibration (Engelmann; Khosravi) — but no source found combines whole-study holdout with validation-tuned, matched-coverage abstention and removed-type false acceptance across simple baselines and released models on blood/PBMC. The Rewire contribution should therefore be framed as the *combination and the operating-point reporting*, not as the first test of unknown detection (scTab, Abdelaal and mtANN already did that) or the first cross-study test (HCE already showed the study-shift drop).

Wording the article can safely use: "We did not find a published benchmark that …" (with the search date and scope above), rather than "This is the first …".

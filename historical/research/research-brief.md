# Research brief (frozen 2026-10-05 for worker use; do not edit)

Workspace root `W` = `/Users/timrichardson/Documents/projects/personal/blog/rewire.it/workbench/outputs/blog-post-cell-type-annotation-transfer-20261005-182352`

## Article

Working question: *How should a single-cell analyst choose a reference and annotation workflow for a new blood/PBMC cohort, and when should a predicted label be accepted or left unassigned?* Audience: computational biologists and ML practitioners. 2,500–3,500 words, British English. The article is built around a new Rewire benchmark (study-held-out transfer, reference-coverage and abstention) whose design is fixed in `W/evidence/protocol.md` and `W/evidence/access-and-feasibility.md`; read both. Results are not yet available to workers; do not invent any.

## Hard rules

- Primary sources first (papers, official docs, repositories, dataset pages). Record URL, authors, publication date, retrieval date (2026-10-05 or later) and licence where relevant.
- Never send any personal details (names, email addresses, account identifiers) in any web request, API parameter or header. Do not use APIs that ask for an email (e.g. NCBI E-utilities `email=`, PMC ID converter, Unpaywall); use publisher/arXiv/bioRxiv/PMC pages directly.
- Do not bypass bot checks, paywalls or JavaScript challenges (10x Genomics dataset pages and pklab.med.harvard.edu are known to be challenge-protected). Record such sources as inaccessible.
- Disk is severely limited (<1 GiB free on the machine). Keep `research/automated-research/original-sources/` under **120 MB in total**. Prefer HTML or PMC/arXiv full text; save a PDF only when no full-text HTML exists, and skip supplementary archives. Never delete or modify anything outside your owned paths.
- Write only to the paths your task assigns.
- Old claims in the issue plan must be re-verified from the primary source; rhetorical framing in an introduction may be contradicted by a paper's results or discussion, so read conclusions and limitations too.

## Source targets (at least 20; aim for 25–35)

Must cover, verifying current versions:
1. scTab (Fischer et al., Nat Commun 2024) full text, incl. training data size (cells, donors, cell types, census version), donor-held-out split, rare-type filtering, unknown-type/rejection analysis, comparator training amounts, platform/assay restrictions; scTab GitHub README (devel branch).
2. CellTypist (Domínguez Conde et al., Science 2022) and CellTypist docs/model registry (Immune_All_Low/High: training studies, tissues, label counts, probability definition, majority voting).
3. scANVI (Xu et al., Mol Syst Biol 2021) and scArches (Lotfollahi et al., Nat Biotechnol 2022): reference mapping, query adaptation, uncertainty.
4. Hao et al. 2021 (Cell) Seurat v4/Azimuth PBMC CITE-seq reference; current Azimuth portal (Pan-Human Azimuth; retirement of tissue-specific apps) and the Pan-Human Azimuth preprint/package.
5. CELLxGENE Census (paper/docs: LTS releases, schema 7.0.0, `is_primary_data`, licence of hosted data) and the Cell Ontology (paper + v2025-07-30 release).
6. Annotation benchmarks with rejection/unknown handling: Abdelaal et al. 2019 Genome Biology; popV (Ergen et al. 2024); any 2023–2026 benchmark of reference-mapping across studies/platforms or of abstention/conformal prediction for cell types.
7. Foundation-model evaluations relevant to annotation: scGPT (Cui et al. 2024) incl. pretraining corpus; Kedzierska et al. (zero-shot evaluation); Boiarsky et al. (logistic-regression baselines); "Evaluating the role of pretraining dataset size and diversity on single-cell foundation model performance" (Nat Methods 2026); "Improving atlas-scale single-cell annotation models with hierarchical cross-entropy loss" (Nat Comput Sci 2025).
8. Study datasets used in the benchmark (primary papers): Human Immune Health Atlas (Nature 2025, doi 10.1038/s41586-025-09686-5), RA scRNA-seq (JCI Insight, doi 10.1172/jci.insight.178499), JDM CITE-seq (JCI Insight, doi 10.1172/jci.insight.176963), Comparative Analysis of Commercial scRNA-seq Technologies (NAR, doi 10.1093/nar/gkae1186), Hao 2021, OneK1K (Yazar 2022 Science), Perez 2022 Science, COMBAT 2022 Cell; Glaucoma PBMC atlas if a publication exists.
9. CITE-seq method (Stoeckius et al. 2017) and 10x Genomics dataset licence (CC BY 4.0) if verifiable without bypassing the bot check (e.g. via search snippets or mirrored documentation, labelled as such).
10. Calibration/selective classification background: risk–coverage curves (e.g. Geifman & El-Yaniv 2017), expected calibration error (Guo et al. 2017).

## Novelty search (required)

Search specifically for prior work that already evaluates *study- or platform-held-out* cell-type annotation together with *abstention at matched coverage* and *removed-reference-type (unknown) false acceptance* across simple baselines and released models. Record queries, dates and what was found in `research/automated-research/novelty-search.md`; state plainly whether the Rewire design is new, partly anticipated, or already done.

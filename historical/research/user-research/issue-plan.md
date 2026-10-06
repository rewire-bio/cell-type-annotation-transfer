# [Article plan] Choosing models for cell-type annotation transfer

<!-- rewire-use-case-article-plan:cell-type-annotation-transfer -->

## Decision and scope

Help a single-cell analyst choose a **reference and annotation workflow for a new cohort**, including which labels to accept and which cells to leave unassigned. Initial example: immune-cell annotation at a fixed Cell Ontology level, with donor holdout for the small demonstration and an independent study/platform cohort for transfer evidence. Keep rare populations and absent-reference types visible. The article should explain how reference coverage, label granularity and abstention change the choice of model.

**Scientific priority:** existing R4 focus priority. **Editorial readiness:** strongest near-term executable starting point among these five research questions, but study independence and unknown-type evaluation remain gates. No current use-case-specific comparison is mapped in release `2026-09-28-c7b5ac6d34f2`; see [pinned R4 brief](https://github.com/rewire-bio/rewire-database/blob/5acd6c59f23b6cbc944336d0377c4523bd30b0a9/data/omics/use-cases/sources/research-priorities-2026-09-28.md).

## Starting evidence and required extraction

Primary sources checked 29 September 2026:

- [scTab paper](https://www.nature.com/articles/s41467-024-51059-5), published 4 August 2024, evaluates donor holdouts, hierarchy-aware labels and platform transfer. Its main corpus filters rare types and restricts technologies; its reported main result cannot establish performance on all rare/unknown populations or every new study. Extract the exact training amounts for each comparator, not just the model names.
- [scTab code and data](https://github.com/theislab/scTab) link a 0.5 GB minimal train/validation/test subset, tutorial notebooks and checkpoints. Treat the supplied subset as a reproducibility demonstration with known provenance, not fresh independent validation of its pretrained model.
- [Azimuth's current portal](https://azimuth.hubmapconsortium.org/) introduces Pan-Human Azimuth and says tissue-specific web apps are no longer supported. Freeze the actual supported reference/workflow; avoid a tutorial depending on retired web apps.
- [CELLxGENE](https://cellxgene.cziscience.com/) is a reference-data discovery lead. Select exact dataset UUIDs/releases with donor, assay and provenance metadata; audit redistribution conditions before packaging any cells.

Build an extraction matrix with reference release, training cells/donors/studies, pretraining overlap, label ontology, gene space, technology, disease state, measured confidence and unknown-class policy. Find an independent immune-cell cohort with orthogonal protein/marker evidence and public metadata. Author labels are an imperfect reference: predefine adjudication for ambiguous cells and report unresolved labels rather than force agreement. Check duplicated cells appearing in primary studies and atlases.

## Candidate methods and fair controls

Required CPU controls: marker-based rules fixed by training/reference evidence; nearest centroid or PCA plus nearest-neighbour transfer; multinomial logistic regression/CellTypist. Compare an eligible scANVI reference-transfer workflow and scTab; a scGPT frozen embedding plus the same simple classifier is a useful model-complexity test if training provenance can be recovered. Optional Azimuth comparison uses a pinned reference and executable mapping path, not an unrecorded website session.

Run two separate tracks: matched training/reference information to study method effects; and practical released workflows to compare what a user can download. Do not attribute gains from a larger reference or finer training labels solely to architecture. Freeze label mapping, common gene identifiers, feature preprocessing and allowed unlabelled query adaptation. Tune every confidence/abstention threshold on validation only. Label predictions without calibrated probabilities as such.

Hold out donors for the demonstration; whole studies and platforms for the main transfer claim. Group all cells from the same donor and preserve datasets reused by reference releases. Simulate absent-reference classes by removing complete types from training, while keeping them in a separately scored query; assess natural unknown populations too where trusted labels exist. Restrict closed-set accuracy claims to known classes.

Report macro-F1, per-type precision/recall, a fixed hierarchy-aware error definition, rare-class errors, unknown-type detection and risk-versus-coverage curves. Compare accuracy at matched accepted coverage; always include the unassigned fraction. Assess calibration with a named scoring rule/reliability plot, and runtime/peak memory including loading/reference mapping. Paired intervals should resample donors/studies, with cell-level counts shown separately. UMAP appearance and batch mixing are not annotation accuracy.

## Original benchmark contribution and tutorial

Contribute a **reference-coverage and abstention comparison**: hold out studies, intentionally remove selected reference types, calibrate on validation, and show the best supported annotation depth at a fixed review budget. The value is a reproducible answer to “when should I accept this label?” including failures, not another embedding plot.

Build a real-data CPU quick start using a documented subset of the scTab minimal archive or a provenance-complete CELLxGENE immune cohort. Run nearest-reference and logistic/CellTypist methods from counts, emit cell IDs, labels, confidence, unassigned status and marker checks. Supply a separate scANVI/scTab inference adapter and full-scale transfer recipe with any GPU dependencies. Preserve donor groups during subsetting, pin the ontology/reference and keep the large supplied pretrained subset outside independent validation claims. Include download/hash manifest, environment, command-line workflow, expected output schema, mismatch checks and a clean-environment execution log.

## Dependencies and sequence

Inspect any article artifact arising from [closed article #232](https://github.com/rewire-bio/rewire.it/issues/232), whose body covers donor-held-out mapping and related evaluation protocols. Reuse verified background; this article adds reference choice, rejection thresholds and a working example. [Database #31](https://github.com/rewire-bio/rewire-database/issues/31) tracks provenance and named scientific review, including scGPT corpus uncertainty. First audit candidate reference/query overlap; then implement common controls, freeze the transfer/unknown protocol, evaluate, obtain atlas-curator review and write the conditional selection guide.

## Delivery and acceptance

- [ ] Freeze the research dossier, source/extraction matrix and protocol before inspecting final test results; preserve publication date, retrieval date, exact locations, licences and artifact hashes.
- [ ] Deliver real-data baseline predictions, paired comparisons with uncertainty, eligible/scored/failed counts and measured runtime/memory. Distinguish published evidence, independent evaluations and new Rewire runs.
- [ ] Provide a clean-environment quick start with pinned dependencies, download checksums, runnable commands, expected output schema, smoke test and full reproduction path. Cached predictions must be identified as cached; no fabricated execution outputs.
- [ ] Have an independent scientific reviewer check endpoint relevance, leakage, exclusions and conclusion; name the reviewer or retain the unresolved gate.
- [ ] Write the article around the reader's decision, one worked example, a conditional model-selection table, runnable code, failure cases and conditions requiring more data. Complete `$blog-write-post` and editorial review after evidence is ready; publication is a separate workflow.

This issue plans evidence collection, benchmark development and an article. No benchmark was executed and no result or model winner is claimed by this plan. Generated research/article work belongs under ignored `workbench/outputs/`; reusable evaluation code should live in the benchmark repository with a commit-pinned article companion.

## Catalogue traceability

Use-case ID: `use-case-cell-type-annotation-transfer`. [Frozen definition](https://github.com/rewire-bio/rewire-database/blob/5acd6c59f23b6cbc944336d0377c4523bd30b0a9/data/omics/use-cases/inputs.json); release `2026-09-28-c7b5ac6d34f2`; planning date 29 September 2026.

No protocol/evaluation mapping currently supports this use case. Discover and review existing catalogue records before creating new identities; add direct/proxy applicability links only after the evidence satisfies the defined question.


<!-- rewire-benchmark-development:2026-10-01 -->

## Benchmark development and missing baselines — 1 October 2026

Programme: [25 — missing/potential benchmarks and baseline gaps](https://github.com/rewire-bio/rewire-benchmarks/issues/25), items **B349 / BL349**. This adds development tasks alongside the existing article plan. Novelty across the literature remains to be established.

**Existing evidence and scope:** scTab provides donor-held-out known-type comparisons and unknown-rejection analysis; author annotations and assay scope limit stronger deployment claims.

- [ ] **Register the proposed endpoint:** Measure annotation transfer to a new study or platform, including useful refusal of unsupported labels, under a common evaluation protocol.
- [ ] **Resolve the baseline gap:** The audited comparison does not establish matched cross-study/platform transfer and abstention across all models; scTab already tests unknown-type rejection, so unknown detection itself is not a missing benchmark.
  - Required comparator panel: CellTypist or logistic regression; Nearest-centroid/kNN reference mapping; Marker-rule annotation; Fixed abstention rule
- [ ] **Prespecify outcomes:** Error at fixed coverage; Coverage at a fixed error threshold; Rare-type macro F1; Unknown-type false acceptance; Calibration and analyst correction time
- [ ] **Complete the first milestone:** Freeze ontology and reference data; hold out whole studies and platforms, include rare and reference-absent types, and tune rejection thresholds only on development studies. Score identical cells across methods.
- [ ] **Resolve dependencies and review:** Audited study/platform splits and pretrained-data overlap; Independent blinded label adjudication with uncertainty retained; Pinned checkpoints and label ontology

Link the frozen protocol, reviewed baseline implementations/artifacts, matched measurements and coverage/uncertainty here and in the programme tracker. Keep existing results immutable. Source extraction, historical replay, new execution and independent validation are separate evidence states. Previously inspected outcomes remain exploratory; stronger claims require an independent evaluation appropriate to the endpoint.

<!-- /rewire-benchmark-development:2026-10-01 -->

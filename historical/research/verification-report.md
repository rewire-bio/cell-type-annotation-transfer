# Fact verification report: article 349 (cell-type annotation transfer)

**Verification date**: 2026-10-05  
**Input**: `research/facts.csv` (242 rows) against `research/automated-research/original-sources-text/`  
**Output**: `research/facts-verified.csv` (original columns + `verified`, `verification_status`, `verification_notes`, `live_check`)  
**Verifier**: independent fact-verifier (did not extract these facts)

## Summary

- Facts checked: 242/242. All 56 source paths resolve.
- **PASS: 163** (67%)
- **WARNING: 79** (33%). Of these:
  - 27 are format-only: the quote matches once line breaks or whitespace are collapsed. They are usable as they stand.
  - 12 are extraction artefacts: the quote matches the local text, but that text differs from the published rendering (glued reference numbers, missing hyphens or spaces, HTML tags, a quote cut off mid-sentence).
  - 40 are context, provenance or units caveats.
- **FAIL: 0**

**Mechanical check.**

- 212 quotes are byte-exact at the cited lines.
- 30 match once whitespace is collapsed. Most are multi-line JSON, markdown or PDF-table quotes; 3 of them (25, 26, 31) also carry context warnings.
- 0 fail.
- No line-number errors were found. The extractor's self-check result (242/242) is reproduced.

**Context check.** I read ±3 lines around every quote. For results and limitations claims I also read the surrounding section and the Discussion where relevant. I found no quote whose meaning is reversed by its context, so nothing is marked FAIL. Several *extractor notes* (not quotes) are inaccurate or overstated: 77, 151, 218 and the units in 159/161. These are downgraded to WARNING so that writers do not reuse the notes as claims.

## Status by category

| Category | PASS | WARNING | FAIL | Total |
|---|---|---|---|---|
| benchmark | 4 | 5 | 0 | 9 |
| expert-opinion | 3 | 4 | 0 | 7 |
| finding | 26 | 18 | 0 | 44 |
| historical | 10 | 2 | 0 | 12 |
| limitation | 7 | 0 | 0 | 7 |
| methodology | 57 | 15 | 0 | 72 |
| statistics | 27 | 3 | 0 | 30 |
| technical-spec | 29 | 32 | 0 | 61 |

## FAIL

None.

## WARNING: context, provenance, units and extraction artefacts (must read)

| # | Category | Source file | Reason |
|---|---|---|---|
| 1 | methodology | 01-paper-sctab-natcommun2024.txt:70-70 | Exact match to local text. Extraction artefact: "CELLxGENE15" glues superscript reference 15; quote as "CELLxGENE census version 2023-05-15". |
| 17 | methodology | 01-paper-sctab-natcommun2024.txt:239-239 | Exact match to local text. Extraction artefact: "deep ensembles34" (ref 34) and "1−maximumpredictedprobability" (formula without spaces). Published: "1 − maximum predicted probability". Note also this is the 5-model ensemble, not the single run5 checkpoint used in Rewire P2. |
| 20 | finding | 01-paper-sctab-natcommun2024.txt:248-248 | Exact match at cited lines. Context caveat: Context: ROC-AUC values come from the 5-model deep ensemble (not the single run5 checkpoint Rewire runs), measured on Census cells. "Group 3" (0.782) = cell types removed by scTab's own rare-type filter; 0.891 is correct-vs-incorrect, not unknown detection. ROC-AUC is threshold-free; it says nothing about false acceptance at an operating point. Do not swap the two numbers. |
| 21 | finding | 01-paper-sctab-natcommun2024.txt:49-49 | Exact match at cited lines. Context caveat: Context: ~0.4 applies to "about half" of non-10x protocols, which the authors call "decent"; the remaining protocols (STRT-seq, Smart-seq2, BD Rhapsody Targeted) generalise "quite poorly". These are also unseen datasets, so platform and study shift are confounded. Do not write "fell to 0.4 on non-10x data" without the "about half" qualifier. |
| 25 | benchmark | 01b-supplement-sctab-natcommun2024-si.txt:97-97 | [Also whitespace-normalised multi-line quote.] Internal inconsistency in scTab SI: XGBoost 0.8127 ± 0.0005 listed with 5 runs (Supp. Table 1a) and 4 runs (Supp. Table 6). Cite the score, not the run count. Fact 26 first value (0.5855) is default hyperparameters. |
| 26 | benchmark | 01b-supplement-sctab-natcommun2024-si.txt:168-168 | [Also whitespace-normalised multi-line quote.] Internal inconsistency in scTab SI: XGBoost 0.8127 ± 0.0005 listed with 5 runs (Supp. Table 1a) and 4 runs (Supp. Table 6). Cite the score, not the run count. Fact 26 first value (0.5855) is default hyperparameters. |
| 31 | methodology | 02b-repo-sctab-docs-data-devel.txt:40-42 | [Also whitespace-normalised multi-line quote.] Rhetorical/authors' claim in repository docs: "better represents how the classifier generalises to unseen donors / data sets" is contradicted for data sets (studies) by HCE (fact 159: 24-32 point macro-F1 drop on new studies) and is more strongly worded than the paper, which calls the donor split "a sensible compromise" (fact 11). Quote only as the authors' rationale. |
| 36 | technical-spec | 02d-meta-huggingface-sctab-mirror.txt:3-3 | Exact match at cited lines. Context caveat: Third-party Hugging Face mirror (not the scTab authors); metadata only. Use only to describe provenance of the mirror. |
| 37 | technical-spec | 02d-meta-huggingface-sctab-mirror.txt:76-76 | Exact match at cited lines. Context caveat: Third-party Hugging Face mirror (not the scTab authors); metadata only. Use only to describe provenance of the mirror. |
| 38 | technical-spec | 02d-meta-huggingface-sctab-mirror.txt:23-23 | Exact match at cited lines. Context caveat: Third-party self-declared licence tag on an unofficial mirror; not authoritative for the checkpoint licence. Official README states MIT for the repository only (fact 28). |
| 39 | methodology | 03-paper-celltypist-science2022.txt:97-97 | Exact match at cited lines. Context caveat: Version mismatch: paper-era Methods say "20 tissues of 19 studies"; the released Immune_All_Low v2 used by Rewire is registered as "20 tissues of 18 studies", 98 types (fact 44, verified live). Cite the registry for the model that is run. |
| 41 | technical-spec | 03-paper-celltypist-science2022.txt:33-33 | Exact match at cited lines. Context caveat: Version mismatch: 91 types is the paper-era low-hierarchy model; registry v2 Immune_All_Low has 98 types (fact 44; HIHA also cites 98). Do not describe the run model as 91-type. |
| 52 | technical-spec | 04b-repo-celltypist-readme.txt:421-421 | Exact match at cited lines. Context caveat: Vendor documentation claim ("unbiased probability range") with no evidence given; the "<=100k cells" is described as an empirical estimate. Attribute to CellTypist docs; do not present as an established property. |
| 55 | methodology | 05-paper-scanvi-msb2021.txt:65-65 | Exact match to local text. Extraction artefact: "c 0" is subscript c₀ in the original. |
| 60 | finding | 06-paper-scarches-natbiotechnol2022.txt:67-67 | Exact match at cited lines. Context caveat: Dataset context: this is mouse Tabula Muris (Senis) query mapping with an unseen tissue, not human blood/PBMC; ~84% is accuracy across tissues. |
| 61 | methodology | 06-paper-scarches-natbiotechnol2022.txt:206-206 | Exact match to local text. Extraction artefact: "publication48" glues reference 48. |
| 67 | technical-spec | 08-web-azimuth-portal.txt:5-5 | Exact match at cited lines. Context caveat: Inconsistent count: portal says 380 high-resolution types, the documentation site says 381 (fact 80). Write "about 380" or cite both. |
| 75 | methodology | 09-preprint-pan-human-azimuth-2026.txt:155-155 | Exact match at cited lines. Context caveat: Preprint. Size inconsistency within the preprint: "~9.8 million" final training set vs 9,665,434 high-confidence cells (fact 74); the gap may be the ~145k Unassigned negatives (extractor inference, unconfirmed). Split is stratified 7:1:2 by cell, not by study. |
| 76 | methodology | 09-preprint-pan-human-azimuth-2026.txt:43-43 | Exact match to local text. Extraction artefact: "scaling56" glues reference 56. Preprint (bioRxiv 2026, not peer reviewed). |
| 77 | finding | 09-preprint-pan-human-azimuth-2026.txt:48-48 | Exact match at cited lines. Context caveat: Preprint finding; extractor note is misleading. The median calibrated confidence of 0.95 is over the whole Tabula Sapiens atlas (v1 donors may overlap training data), not the 9 new v2 donors only; the v2 claim is only "no systematic decrease in confidence". Confidence is not accuracy. |
| 80 | technical-spec | 09b-web-pan-human-azimuth-site.txt:35-35 | Exact match at cited lines. Context caveat: Inconsistent count: site says 381 types; portal says 380 (fact 67). |
| 86 | statistics | 11-paper-cellxgene-discover-nar2025.txt:35-35 | Exact match at cited lines. Context caveat: Time-bound figure ("now surpasses 93 million") as of the NAR 2025 paper; Census LTS 2025-11-08 lists 99.6 M unique human cells alone (fact 96). Date it if used. |
| 101 | technical-spec | 13-docs-cellxgene-schema-7.0.0.txt:725-725 | Exact match to local text. Quote contains literal HTML <code> tags from schema markdown; strip when quoting. Field definition also starts with a spatial-data clause (omitted, does not change meaning). |
| 104 | technical-spec | 14-web-aws-registry-cellxgene-census.txt:9-9 | Exact match at cited lines. Context caveat: Stated cadence ("LTS every 6 months") is not borne out by the LTS list (2023-05-15, 2023-07-25, 2023-12-15, 2024-07-01, 2025-01-30, 2025-11-08; ~9.5-month gap before the current one). Also weekly "latest" has not advanced past 2025-11-17 as of 2026-10-05 (live release.json). Avoid quoting the cadence as fact. |
| 112 | expert-opinion | 40-preprint-cell-ontology-2025-arxiv-v3.txt:4-4 | Exact match at cited lines. Context caveat: Promotional framing from a CL consortium preprint (arXiv v3, not peer reviewed). Use as authors' view only. |
| 147 | finding | 24-preprint-boiarsky-deep-dive-scfm-biorxiv2023.txt:73-73 | Exact match at cited lines. Context caveat: bioRxiv 2023 preprint (Boiarsky et al.); a peer-reviewed successor exists (Nat Mach Intell 2024) but was not retrieved. Results are within-dataset (Zheng68K 80/20 split) and section title says LR wins "in a dataset-dependent manner". |
| 148 | finding | 24-preprint-boiarsky-deep-dive-scfm-biorxiv2023.txt:78-78 | Exact match at cited lines. Context caveat: bioRxiv 2023 preprint (Boiarsky et al.); a peer-reviewed successor exists (Nat Mach Intell 2024) but was not retrieved. Results are within-dataset (Zheng68K 80/20 split) and section title says LR wins "in a dataset-dependent manner". |
| 149 | methodology | 24-preprint-boiarsky-deep-dive-scfm-biorxiv2023.txt:78-78 | Exact match at cited lines. Context caveat: bioRxiv 2023 preprint (Boiarsky et al.); a peer-reviewed successor exists (Nat Mach Intell 2024) but was not retrieved. Results are within-dataset (Zheng68K 80/20 split) and section title says LR wins "in a dataset-dependent manner". |
| 151 | finding | 25-paper-denadel-pretraining-size-natmethods2026-pmc.txt:159-159 | Exact match at cited lines. Context caveat: Ambiguity: "training data" here means the unlabelled PRE-training corpus (scTab corpus), not labelled fine-tuning data. Do not conflate with scTab comparator training sizes (1.5 M / 750 k / 150 k labelled cells). |
| 159 | finding | 26-paper-hce-natcomputsci2025.txt:34-34 | Exact match at cited lines. Context caveat: Units: "24-32%" matches the absolute drop in macro-F1 percentage points (80→55, 82→57, 84→52 = 25, 25, 32 points); relative drops are ~30-38%. Write "24-32 percentage points". Live source uses hyphen. |
| 161 | finding | 26-paper-hce-natcomputsci2025.txt:39-39 | Exact match at cited lines. Context caveat: Units: "12-15%" is most consistent with percentage points (≈ half of a 25-32 point drop, fact 162). Write "12-15 percentage points". |
| 164 | methodology | 27-paper-hiha-nature2025.txt:136-136 | Exact match to local text. Extraction artefact: "(v.1.6.1)53" glues reference 53. Content verified live. Circularity caveat: HIHA labels were guided by Immune_All_Low/High — same family as Rewire P1. |
| 165 | methodology | 27-paper-hiha-nature2025.txt:136-136 | Exact match to local text. Extraction artefact: "(v.5.0.1)54" glues reference 54. Content verified live. |
| 181 | benchmark | 30-paper-scrnaseq-technologies-nar2025.txt:163-163 | Exact match at cited lines. Context caveat: Context: 94/81/86/81% is the CellTypist+Seurat agreement procedure scored on a held-out split of the pbmcsca reference (7,750 cells), before cluster smoothing; it is not an accuracy of the published kit labels. |
| 202 | technical-spec | 37-paper-geifman-selective-classification-neurips2017.txt:8-8 | Exact match to local text. PDF spacing artefacts ("f ,", "r∗ ,"). Context: the guarantee holds for test data drawn from the same distribution as the calibration sample; do not imply it survives study/platform shift. |
| 205 | finding | 38-paper-guo-calibration-icml2017.txt:12-12 | Exact match to local text. PDF artefact: "singleparameter" should read "single-parameter". |
| 207 | technical-spec | 38-paper-guo-calibration-icml2017.txt:32-32 | Exact match to local text. Quote ends mid-sentence ("... bins (similar to the reliability diagrams) and"); sentence continues on next page. Paraphrase or complete the sentence from the PDF before quoting. |
| 209 | finding | 39-paper-engelmann-uq-atlas-cell-type-transfer-2022.txt:55-55 | Exact match at cited lines. Context caveat: ICML 2022 workshop paper (arXiv), lung atlas (HLCA), not blood. Internal tension: Conclusion says baselines "not well calibrated" (213) while Results say WKNN calibration improves on the leave-out dataset to be comparable to UQ models (210). Quote both or neither. |
| 210 | finding | 39-paper-engelmann-uq-atlas-cell-type-transfer-2022.txt:55-55 | Exact match at cited lines. Context caveat: ICML 2022 workshop paper (arXiv), lung atlas (HLCA), not blood. Internal tension: Conclusion says baselines "not well calibrated" (213) while Results say WKNN calibration improves on the leave-out dataset to be comparable to UQ models (210). Quote both or neither. |
| 213 | finding | 39-paper-engelmann-uq-atlas-cell-type-transfer-2022.txt:81-81 | Exact match at cited lines. Context caveat: ICML 2022 workshop paper (arXiv), lung atlas (HLCA), not blood. Internal tension: Conclusion says baselines "not well calibrated" (213) while Results say WKNN calibration improves on the leave-out dataset to be comparable to UQ models (210). Quote both or neither. |
| 218 | methodology | 42-paper-cvid-atlas-natcommun2022.txt:87-87 | Exact match at cited lines. Context caveat: Extractor note overstates: the CVID single-cell data include stimulated PBMCs AND unstimulated (but 48 h cultured) controls, all B-cell enriched 2:1 (facts 220, 221). Do not write "the CVID reference is stimulated PBMCs". |
| 228 | methodology | 45-meta-khosravi-scgpt-calibration-researchsquare2026-europepmc.txt:68-68 | Exact match at cited lines. Context caveat: Preprint (Research Square 2026, not peer reviewed); Europe PMC abstract record only; within-atlas evaluation, not cross-study. |
| 229 | finding | 45-meta-khosravi-scgpt-calibration-researchsquare2026-europepmc.txt:68-68 | Exact match at cited lines. Context caveat: Preprint (Research Square 2026, not peer reviewed); Europe PMC abstract record only; within-atlas evaluation, not cross-study. |
| 230 | finding | 45-meta-khosravi-scgpt-calibration-researchsquare2026-europepmc.txt:68-68 | Exact match to local text. PDF/record artefacts: "matchedgene" and "scGPTembedding" lack hyphen/space. Also preprint (Research Square, not peer reviewed), abstract-only record; within-atlas evaluation. |
| 231 | expert-opinion | 45-meta-khosravi-scgpt-calibration-researchsquare2026-europepmc.txt:68-68 | Exact match at cited lines. Context caveat: Preprint (Research Square 2026, not peer reviewed); Europe PMC abstract record only; within-atlas evaluation, not cross-study. |
| 232 | finding | 46-paper-hu-matching-benchmark-2025.txt:85-85 | Exact match at cited lines. Context caveat: bioRxiv 2025 preprint (via PMC12190912), lung atlases (CellRef vs HLCA), not blood. 234: agreement across methods is not accuracy (authors say so). |
| 233 | finding | 46-paper-hu-matching-benchmark-2025.txt:85-85 | Exact match at cited lines. Context caveat: bioRxiv 2025 preprint (via PMC12190912), lung atlases (CellRef vs HLCA), not blood. 234: agreement across methods is not accuracy (authors say so). |
| 234 | statistics | 46-paper-hu-matching-benchmark-2025.txt:69-69 | Exact match at cited lines. Context caveat: bioRxiv 2025 preprint (via PMC12190912), lung atlases (CellRef vs HLCA), not blood. 234: agreement across methods is not accuracy (authors say so). |
| 235 | expert-opinion | 46-paper-hu-matching-benchmark-2025.txt:79-79 | Exact match at cited lines. Context caveat: bioRxiv 2025 preprint (via PMC12190912), lung atlases (CellRef vs HLCA), not blood. 234: agreement across methods is not accuracy (authors say so). |
| 237 | technical-spec | 47-paper-huang-annotation-r-packages-gpb2021.txt:35-35 | Exact match at cited lines. Context caveat: Context/conflict: Huang 2021 Table 1 lists Seurat 3.0.1 as not allowing unknown cell types, whereas scArches (fact 61) and mtANN (fact 137) apply a lowest-20% prediction/projection-score rule to Seurat to create "unknown". Say "Seurat's label transfer has no built-in reject option; others add a fixed 20% cut-off". |
| 240 | expert-opinion | 48-preprint-scdiagnostics-biorxiv2026-abstract.txt:56-56 | Exact match at cited lines. Context caveat: bioRxiv 2026 preprint abstract (scDiagnostics), not peer reviewed; general framing only. |
| 241 | finding | 48-preprint-scdiagnostics-biorxiv2026-abstract.txt:56-56 | Exact match at cited lines. Context caveat: bioRxiv 2026 preprint abstract (scDiagnostics), not peer reviewed; general framing only. |

## WARNING: format only (usable as is)

Each quote below matches its cited span once line breaks or whitespace runs are collapsed. Most span several lines of JSON, markdown, a notebook or a PDF table. Several also contain markdown or table tokens (`*`, `#`, `[ROW]`, `|`), which writers should drop when quoting.

| # | Source file:lines | Extra note |
|---|---|---|
| 5 | 01-paper-sctab-natcommun2024.txt:75-76 | - |
| 23 | 01b-supplement-sctab-natcommun2024-si.txt:99-99 | - |
| 24 | 01b-supplement-sctab-natcommun2024-si.txt:112-112 | This is SI Table 1b (seeds + donor bootstrap, 4 runs); main text and Table 1a give 0.8295 ± 0.0007 (5 runs). State which. |
| 27 | 02-repo-sctab-readme-devel.txt:9-10 | - |
| 28 | 02-repo-sctab-readme-devel.txt:65-67 | Licence applies to the repository; README says nothing explicit about checkpoints or data. |
| 29 | 02-repo-sctab-readme-devel.txt:61-63 | - |
| 30 | 02b-repo-sctab-docs-data-devel.txt:44-46 | - |
| 33 | 02c-repo-sctab-model-inference-tutorial-devel.txt:118-120 | - |
| 34 | 02c-repo-sctab-model-inference-tutorial-devel.txt:80-81 | - |
| 35 | 02c-repo-sctab-model-inference-tutorial-devel.txt:32-33 | - |
| 44 | 04-docs-celltypist-models.txt:6-13 | Cite this registry entry (98 types, 18 studies) for the model Rewire runs. |
| 45 | 04-docs-celltypist-models.txt:16-21 | - |
| 46 | 04-docs-celltypist-models.txt:331-336 | - |
| 47 | 04b-repo-celltypist-readme.txt:129-130 | - |
| 50 | 04b-repo-celltypist-readme.txt:136-137 | - |
| 84 | 10-repo-panhumanpy-readme.txt:53-55 | - |
| 90 | 12-docs-census-release-json.txt:2-3 | - |
| 91 | 12-docs-census-release-json.txt:124-140 | The quoted text is identical for every LTS block; the release (2025-11-08) is identified only by the line range — say so when citing. |
| 92 | 12-docs-census-release-json.txt:4-20 | The quoted text is identical for every LTS block; the release (2023-05-15) is identified only by the line range. |
| 94 | 12b-docs-census-data-release-info.txt:86-90 | - |
| 100 | 13-docs-cellxgene-schema-7.0.0.txt:225-225 | - |
| 103 | 14-web-aws-registry-cellxgene-census.txt:10-11 | - |
| 109 | 16-release-cell-ontology-v2025-07-30.txt:29-31 | - |
| 142 | 22b-repo-scgpt-readme.txt:62-62 | - |
| 143 | 22b-repo-scgpt-readme.txt:65-65 | - |
| 154 | 25b-landing-denadel-natmethods2026.txt:21-22 | - |
| 195 | 34-meta-cellxgene-glaucoma-collection.txt:176-181 | - |

## Live spot-check against primary online sources (84 facts, retrieved 2026-10-05)

Method:

- Each page was fetched with a plain HTTP GET and a generic user agent. No personal details were sent and no bot checks were bypassed. Nothing was stored on disk.
- HTML tags were stripped, and Unicode, quote marks and whitespace were normalised.
- Each quote was then searched for in the live text. Any non-exact hit was inspected by eye.

**Result:** every one of the 84 facts is present on the live source. None has a substantive mismatch. The only differences are rendering: superscript reference numbers, subscripted F1, a LaTeX formula, the italic method name SVM_rejection, a hyphen in place of a minus sign, numbered versus dashed lists, and HTML `<code>` tags.

| Source (URL) | Facts checked | Result |
|---|---|---|
| https://www.nature.com/articles/s41467-024-51059-5 | 1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22 | exact match; match; live renders formula \(1-maximum predicted probability\) and superscript ref 34; match; live renders superscript ref (CELLxGENE^15), local text glues it; match; live uses numbered list (4., 5.) where local text has "-" |
| https://github.com/theislab/scTab/blob/devel/README.md | 27, 28, 29 | exact match (raw devel README) |
| https://github.com/theislab/scTab/blob/devel/docs/data.md | 30, 31, 32 | exact match (raw devel docs/data.md) |
| https://celltypist.cog.sanger.ac.uk/models/models.json | 44, 45, 46 | exact match; registry last_update 2026-03-16; Immune_All_Low v2 still 98 types/18 studies |
| https://github.com/Teichlab/celltypist/blob/main/README.md | 47, 48, 49, 50, 51 | exact match (raw main README) |
| https://azimuth.hubmapconsortium.org/ | 67, 68, 69, 70 | exact match |
| https://pmc.ncbi.nlm.nih.gov/articles/PMC13419436/ | 71, 72, 73, 74, 75, 76, 77 | exact match (PMC13419436, bioRxiv preprint); match (punctuation rendering only); match; live renders superscript ref 56 |
| https://github.com/satijalab/panhumanpy/blob/main/README.md | 83, 84, 85 | exact match (raw main README) |
| https://census.cellxgene.cziscience.com/cellxgene-census/v1/release.json | 90, 91, 92 | confirmed: 2025-11-08 and 2023-05-15 both lts=true, do_not_delete=true; exact match; stable 2025-11-08, latest still 2025-11-17 |
| https://chanzuckerberg.github.io/cellxgene-census/cellxgene_census_docsite_data_release_info.html | 93, 95, 98 | exact match; match (whitespace/punctuation rendering only); erratum still present |
| https://github.com/chanzuckerberg/single-cell-curation/blob/main/schema/7.0.0/schema.md | 100, 101, 102 | exact match (raw schema.md); match once HTML <code> tags are removed; live text also begins with spatial is_single clause |
| https://registry.opendata.aws/biohub-cellxgene-census/ | 103, 104 | exact match; match (markdown heading rendering only) |
| https://genomebiology.biomedcentral.com/articles/10.1186/s13059-019-1795-z | 115, 117, 118, 119, 121, 122 | exact match; match; live renders method name as SVM_rejection (italic/subscript) where local text has SVMrejection |
| https://www.nature.com/articles/s43588-025-00945-z | 156, 157, 158, 159, 160, 161, 162, 163 | exact match; match; live renders F1 with subscript ("F 1"); match; live uses hyphen "24-32%" (local has minus sign) |
| https://www.nature.com/articles/s41586-025-09686-5 | 164, 165, 166, 167, 168 | exact match; match; live renders reference numbers 53/54 as superscripts |
| https://pmc.ncbi.nlm.nih.gov/articles/PMC11754665/ | 177, 178, 179, 180, 181, 182 | exact match (PMC11754665); match (quote-mark/whitespace rendering only) |

Notes on live state as of 2026-10-05:

- **CellTypist registry.** `models.json` has `last_update` 2026-03-16. `Immune_All_Low` is unchanged: v2, dated 2022-07-16, 98 types, "20 tissues of 18 studies".
- **Census `release.json`.** `stable` = 2025-11-08 and `latest` = 2025-11-17. The weekly "latest" build has not advanced in about 11 months.
- **Census 2023-05-15 erratum.** Still published (243,569 duplicate primary cells).
- **AWS registry.** Still lists the licence as CC-BY 4.0. The registry slug is `biohub-cellxgene-census`, and the dataset is "Managed by Biohub".
- **Azimuth portal.** Text is unchanged: tissue-specific web apps are retired, existing references can still be used in R, and the portal gives 380 types.
- **Not live-checked.**
  - 10x Genomics dataset licence: bot-protected, and there are no facts for it.
  - bioRxiv and Research Square landing pages: not needed, because the Pan-human Azimuth preprint was checked through PMC instead.
  - Paywalled scGPT full text.

## Facts writers must phrase carefully

1. **HCE study-transfer drop (159, 161, 162).** "24-32%" and "12-15%" are absolute macro-F1 *percentage points*, matching 80→55, 82→57 and 84→52. In relative terms the drop is about 30-38%. The OOD set is 21 studies added in Census 2023-12-15, restricted to 80 of the 164 types and 10x assays only. These are the HCE authors' re-implementations (linear, MLP, TabNet), not the released scTab checkpoint. Cite as Nat Comput Sci 2026 (online 30 Jan 2026).
2. **scTab unknown-type ROC (17-20).**
   - 0.782 is correct versus *absent* types. 0.891 is correct versus *incorrect* predictions. Do not swap them.
   - "Absent" means cell types that scTab's own rare-type filter removed from the same Census corpus.
   - The scores come from a 5-model deep ensemble, not the single run5 checkpoint Rewire runs.
   - ROC-AUC is threshold-free and does not measure false acceptance at an operating point.
   - The authors' Discussion says the models' strength "does not lie in correctly classifying novel cell types" (22).
3. **scTab splits, comparators and platform transfer (7-16, 21, 24-26, 31).**
   - The split is by donor, which the paper calls "a sensible compromise". The docs' claim that it represents generalisation to unseen "data sets" is contradicted by HCE.
   - Comparators were trained on less labelled data: CellTypist 1.5 M cells (with tuned hyperparameters), CIForm 750 k, scGPT fine-tuned on 150 k, and the scGPT zero-shot LR on 1.5 M.
   - The non-10x "~0.4" applies to "about half" of the protocols. The rest were worse.
   - The XGBoost run count is inconsistent between SI tables. scTab is 0.8295 (Table 1a) or 0.8300 (Table 1b, donor bootstrap).
   - Do not write "CELLxGENE15" (extraction artefact).
4. **CellTypist version and labels (39, 41, 44-50, 164).**
   - The model Rewire runs is registry `Immune_All_Low` v2: 98 types, 18 studies, dated 2022-07-16 (verified live). The paper's "19 studies / 91 types" describes the earlier model.
   - Probabilities are one-vs-rest sigmoids, and "Unassigned" exists only in `prob match` mode (p_thres 0.5).
   - The HIHA atlas labels were *guided by* Immune_All_Low/High and Seurat before expert curation, so P1 agreement on HIHA is partly circular.
   - The CellTypist-*predicted* labels (168) belong to the longitudinal Sound Life datasets, not to test dataset e522d2cd.
5. **"Unassigned", platform labels and Azimuth (67-80, 178-182).**
   - The platform-study labels are a CellTypist + Seurat consensus. Discordant cells were later relabelled by subcluster majority, reaching 96.2% annotation.
   - The 94/81/86/81% validation figures describe the agreement step on a held-out reference split, not the final kit labels.
   - Pan-human Azimuth's "Unassigned" is a QC class (empty droplets, multiplets), not a novel-type detector. Its confidence scores are calibrated per level by temperature scaling.
   - Type counts conflict: 380 on the portal, 381 on the docs site.
   - The 0.95 median confidence covers the whole Tabula Sapiens atlas, not new donors only.
   - The work is a preprint (CC BY-NC); the weights are CC BY 4.0.

Further cautions:

- **Census.**
  - The erratum (243,569 duplicate primary cells) applies to LTS 2023-05-15, which scTab and scGPT used.
  - Schema 2.4.0 makes `disease` multi-valued, so an exact match on `disease == 'normal'` can miss healthy cells.
  - The AWS registry's "LTS every 6 months" does not match the actual release dates, so do not quote it.
  - CC-BY 4.0 is the AWS registry's summary licence.
- **Fixed thresholds differ by tool and are not comparable** (CellTypist 0.5, scArches 50% uncertainty, SVMrejection 0.7, Seurat lowest 20%). Seurat's label transfer has no built-in reject option (237); the 20% rule is added by other authors.
- **Abdelaal rejection results** (116-122) come from removing populations *within one dataset*. The SVMrejection recommendation (122) was made despite the T→B failure (118).
- **Preprints and non-peer-reviewed sources.** Attribute these as preprints and do not state them as settled:
  - Pan-human Azimuth (09)
  - Boiarsky (24; a Nat Mach Intell 2024 version exists but was not retrieved)
  - CL 2025 (40)
  - Khosravi (45; Research Square abstract)
  - Hu et al. (46)
  - scDiagnostics (48)
  - Engelmann (39; ICML workshop, with an internal tension between Results and Conclusion)
- **DenAdel "saturation at 1%" (151, 152)** refers to *pre-training* corpus size, about 200 k cells, not labelled training data.
- **Reference realism.**
  - The CVID data include stimulated PBMCs *and* cultured unstimulated controls, all B-cell enriched 2:1 (218-221). Do not write "stimulated only".
  - The Hao 2021 reference includes post-vaccination days 3 and 7 (62, 64).
  - RA labels exclude platelets/MK and cells with more than 1,000 genes (172).
- **Quote clean-up when quoting verbatim:** 1, 17, 55, 61, 76, 164 and 165 contain glued reference numbers or subscripts. 101 contains HTML `<code>` tags. 205 ("single-parameter") and 230 lack hyphens. 207 is cut off mid-sentence.

## Source file issues

- All source files are accessible, and all line numbers are within range.
- Source 36 (10x Genomics dataset licence) has no text file and no facts. The CC BY 4.0 licence of the 10x CITE-seq files remains unverified.
- Several files are metadata or abstract only: 22, 25b, 31, 34, 45, 48 and 02d. Facts from them are limited to what the abstract or record says.

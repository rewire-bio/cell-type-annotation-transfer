# Retrieval log (article 349, cell-type annotation transfer)

All times UTC. Client: `curl` (default user agent, no cookies, no personal details) unless stated; WebSearch/WebFetch tools for discovery. No API requiring an email parameter was used. Europe PMC REST (`www.ebi.ac.uk/europepmc/webservices/rest/...`) requires no identifying parameter and was used for open-access full-text XML and DOI→PMCID lookups.

## 1. Retrieval sessions

Session: 2026-10-05, 21:17–21:30 UTC, single worker. Disk free at start ≈964 MiB; originals kept under 20 MiB (well below the 120 MB cap). A scratch helper script (curl wrapper + JATS/HTML/PDF-to-text converter) and scratch copies were first kept in `/tmp/a349/`; at the coordinator's request (≈21:32Z) the helper, the raw fetch log and the hash manifest were moved to `research/automated-research/.scratch/` and `/tmp/a349/` was deleted. Text conversion: JATS XML → one paragraph/caption/table row per line; HTML → one block element per line (scripts/styles dropped); PDF → `pdftotext` (poppler) with one paragraph per line, or `-layout` lines for the scTab SI (tables), with Unicode bidi control characters removed. Note: the `AUTHORS:` header line produced from JATS can include non-author contributors (e.g. handling editor Anthony Mathelier in sources 19 and 20); the bibliography in `sources.md` lists authors only.

## 2. File-level request log (every HTTP download attempted with curl)

| # | UTC time | HTTP status / content type | bytes | SHA-256 (first 16) | URL | Outcome / saved as |
|---|---|---|---|---|---|---|
| 1 | 2026-10-05T21:19:43Z | 200 application/xml | 156173 | `e61b11cd873f3d13` | https://www.ebi.ac.uk/europepmc/webservices/rest/PMC11298532/fullTextXML | 01-paper-sctab-natcommun2024.xml |
| 2 | 2026-10-05T21:19:43Z | 200 application/xml | 158729 | `16afb473c351c8b0` | https://www.ebi.ac.uk/europepmc/webservices/rest/PMC7612735/fullTextXML | 03-paper-celltypist-science2022.xml |
| 3 | 2026-10-05T21:19:44Z | 200 application/xml | 223764 | `11d48d3b8149f462` | https://www.ebi.ac.uk/europepmc/webservices/rest/PMC7829634/fullTextXML | 05-paper-scanvi-msb2021.xml |
| 4 | 2026-10-05T21:19:44Z | 200 application/xml | 290900 | `6b746e28e26ea717` | https://www.ebi.ac.uk/europepmc/webservices/rest/PMC8763644/fullTextXML | 06-paper-scarches-natbiotechnol2022.xml |
| 5 | 2026-10-05T21:19:45Z | 200 application/xml | 378756 | `435eb55ba8318004` | https://www.ebi.ac.uk/europepmc/webservices/rest/PMC8238499/fullTextXML | 07-paper-hao2021-seurat-v4-cell.xml |
| 6 | 2026-10-05T21:19:45Z | 200 application/xml | 189105 | `ea707517678eaca1` | https://www.ebi.ac.uk/europepmc/webservices/rest/PMC11701654/fullTextXML | 11-paper-cellxgene-discover-nar2025.xml |
| 7 | 2026-10-05T21:19:46Z | 200 application/xml | 175449 | `6df0937c5a2d8ba0` | https://www.ebi.ac.uk/europepmc/webservices/rest/PMC6734286/fullTextXML | 17-paper-abdelaal2019-genomebiol.xml |
| 8 | 2026-10-05T21:19:46Z | 200 application/xml | 129473 | `0a78b34e5fe4c639` | https://www.ebi.ac.uk/europepmc/webservices/rest/PMC11631762/fullTextXML | 18-paper-popv-natgenet2024.xml |
| 9 | 2026-10-05T21:19:47Z | 200 application/xml | 118176 | `af7f1d7b4a5cd508` | https://www.ebi.ac.uk/europepmc/webservices/rest/PMC10957513/fullTextXML | 19-paper-hierarchical-reject-bioinformatics2024.xml |
| 10 | 2026-10-05T21:19:47Z | 200 application/xml | 153353 | `9c560d3a8ad759c9` | https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12506889/fullTextXML | 20-paper-conformal-annotation-bioinformatics2025.xml |
| 11 | 2026-10-05T21:19:48Z | 200 application/xml | 199030 | `07ad2713213e45cd` | https://www.ebi.ac.uk/europepmc/webservices/rest/PMC10335708/fullTextXML | 21-paper-mtann-ploscompbiol2023.xml |
| 12 | 2026-10-05T21:19:48Z | 200 application/xml | 83155 | `2a0f1d329f2cad6e` | https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12007350/fullTextXML | 23-paper-kedzierska-zeroshot-genomebiol2025.xml |
| 13 | 2026-10-05T21:19:49Z | 200 application/xml | 81160 | `632c0980d5a81009` | https://www.ebi.ac.uk/europepmc/webservices/rest/PMC13021517/fullTextXML | 26-paper-hce-natcomputsci2025.xml |
| 14 | 2026-10-05T21:19:49Z | 200 application/xml | 231662 | `6a8b078e19756541` | https://www.ebi.ac.uk/europepmc/webservices/rest/PMC13419436/fullTextXML | 09-preprint-pan-human-azimuth-2026.xml |
| 15 | 2026-10-05T21:19:49Z | 200 application/xml | 226040 | `4297d9934e1f95af` | https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12711581/fullTextXML | 27-paper-hiha-nature2025.xml |
| 16 | 2026-10-05T21:19:50Z | 200 application/xml | 153728 | `5948d2ccf2a8bbde` | https://www.ebi.ac.uk/europepmc/webservices/rest/PMC11343607/fullTextXML | 28-paper-ra-jciinsight2024.xml |
| 17 | 2026-10-05T21:19:50Z | 200 application/xml | 181263 | `c8ee9ea4aec2901a` | https://www.ebi.ac.uk/europepmc/webservices/rest/PMC11383589/fullTextXML | 29-paper-jdm-jciinsight2024.xml |
| 18 | 2026-10-05T21:19:51Z | 200 application/xml | 176219 | `34b26b6d9922a951` | https://www.ebi.ac.uk/europepmc/webservices/rest/PMC11754665/fullTextXML | 30-paper-scrnaseq-technologies-nar2025.xml |
| 19 | 2026-10-05T21:19:52Z | 200 application/xml | 639438 | `d053737c1f00bb6e` | https://www.ebi.ac.uk/europepmc/webservices/rest/PMC8776501/fullTextXML | 33-paper-combat-cell2022.xml |
| 20 | 2026-10-05T21:19:52Z | 500 application/json | 150 | `13515bc15512f872` | https://www.ebi.ac.uk/europepmc/webservices/rest/PMC5669064/fullTextXML | (failed; not saved) |
| 21 | 2026-10-05T21:20:13Z | 200 application/pdf | 3135287 | `392c5da175e1a225` | https://static-content.springer.com/esm/art%3A10.1038%2Fs41467-024-51059-5/MediaObjects/41467_2024_51059_MOESM1_ESM.pdf | 01b-supplement-sctab-natcommun2024-si.pdf |
| 22 | 2026-10-05T21:20:33Z | 200 text/plain; charset=utf-8 | 3719 | `b9208a3232ffbcf8` | https://raw.githubusercontent.com/theislab/scTab/devel/README.md | 02-repo-sctab-readme-devel.md |
| 23 | 2026-10-05T21:20:34Z | 200 text/plain; charset=utf-8 | 4506 | `267b09f2baf984b8` | https://raw.githubusercontent.com/theislab/scTab/devel/docs/data.md | 02b-repo-sctab-docs-data-devel.md |
| 24 | 2026-10-05T21:20:34Z | 200 text/plain | 25568 | `f617fcd7863b08e6` | https://celltypist.cog.sanger.ac.uk/models/models.json | 04-docs-celltypist-models.json |
| 25 | 2026-10-05T21:20:34Z | 200 text/plain; charset=utf-8 | 44270 | `d1a086776c56a93c` | https://raw.githubusercontent.com/Teichlab/celltypist/main/README.md | 04b-repo-celltypist-readme.md |
| 26 | 2026-10-05T21:21:20Z | 200 application/xml | 133904 | `e3a2c884cf234967` | https://www.ebi.ac.uk/europepmc/webservices/rest/PMC4932724/fullTextXML | 15-paper-cell-ontology-2016-jbiomedsem.xml |
| 27 | 2026-10-05T21:21:20Z | 500 application/json | 149 | `90f48753b09557da` | https://www.ebi.ac.uk/europepmc/webservices/rest/PPR746234/fullTextXML | (failed; not saved) |
| 28 | 2026-10-05T21:21:20Z | 200 application/xml | 442913 | `5b54148cc7976200` | https://www.ebi.ac.uk/europepmc/webservices/rest/PMC8601717/fullTextXML | 41-paper-vanderwijst-ifn-autoantibodies-scitranslmed2021.xml |
| 29 | 2026-10-05T21:21:21Z | 200 application/xml | 227625 | `65a98862efa7d5a1` | https://www.ebi.ac.uk/europepmc/webservices/rest/PMC8975885/fullTextXML | 42-paper-cvid-atlas-natcommun2022.xml |
| 30 | 2026-10-05T21:21:21Z | 200 application/xml | 241552 | `bd76c17dadf3874c` | https://www.ebi.ac.uk/europepmc/webservices/rest/PMC9767677/fullTextXML | 43-paper-kidney-cancer-ccell2022.xml |
| 31 | 2026-10-05T21:21:22Z | 200 application/xml | 119668 | `db2e7227ba5dbcf7` | https://www.ebi.ac.uk/europepmc/webservices/rest/PMC11284682/fullTextXML | 44-paper-clonal-haematopoiesis-bloodadv2024.xml |
| 32 | 2026-10-05T21:21:31Z | 200 text/html; charset=UTF-8 | 5415 | `edcdbdbb8ff488aa` | https://azimuth.hubmapconsortium.org/ | 08-web-azimuth-portal.html |
| 33 | 2026-10-05T21:21:32Z | 200 text/html; charset=UTF-8 | 19013 | `610a3efe0f60e421` | https://satijalab.org/pan_human_azimuth/ | 09b-web-pan-human-azimuth-site.html |
| 34 | 2026-10-05T21:21:33Z | 200 text/plain; charset=utf-8 | 2785 | `fd53668728fb3130` | https://raw.githubusercontent.com/satijalab/panhumanpy/main/README.md | 10-repo-panhumanpy-readme.md |
| 35 | 2026-10-05T21:21:33Z | 200 application/json | 5248 | `409739c0a0d385b1` | https://census.cellxgene.cziscience.com/cellxgene-census/v1/release.json | 12-docs-census-release-json.json |
| 36 | 2026-10-05T21:21:34Z | 200 text/html; charset=utf-8 | 60314 | `255a55f0df631d08` | https://chanzuckerberg.github.io/cellxgene-census/cellxgene_census_docsite_data_release_info.html | 12b-docs-census-data-release-info.html |
| 37 | 2026-10-05T21:21:34Z | 200 text/plain; charset=utf-8 | 148571 | `75a7570c47519d96` | https://raw.githubusercontent.com/chanzuckerberg/single-cell-curation/main/schema/7.0.0/schema.md | 13-docs-cellxgene-schema-7.0.0.md |
| 38 | 2026-10-05T21:21:35Z | 200 application/json; charset=utf-8 | 182017 | `ebb029436fc59e4c` | https://api.github.com/repos/obophenotype/cell-ontology/releases/tags/v2025-07-30 | 16-release-cell-ontology-v2025-07-30.json |
| 39 | 2026-10-05T21:21:35Z | 403 text/html; charset=iso-8859-1 | 990 | `142b767cd56c6545` | https://www.biorxiv.org/content/10.1101/2023.04.30.533439v2.full | (403 Forbidden; not saved) |
| 40 | 2026-10-05T21:21:36Z | 200 text/html; charset=utf-8 | 223030 | `3a353668457fe46e` | https://www.biorxiv.org/content/10.1101/2023.10.19.563100v1.full | 24-preprint-boiarsky-deep-dive-scfm-biorxiv2023.html |
| 41 | 2026-10-05T21:21:36Z | 200 text/html; charset=utf-8 | 406579 | `bf9e87662e22c8bf` | https://www.nature.com/articles/s41592-026-03120-y | 25b-landing-denadel-natmethods2026.html (paywalled landing page; abstract/metadata only) |
| 42 | 2026-10-05T21:21:37Z | 200 text/html; charset=utf-8 | 273952 | `cf383d9448a53074` | https://pmc.ncbi.nlm.nih.gov/articles/PMC9297655/ | 32-paper-perez-lupus-science2022-pmc.html |
| 43 | 2026-10-05T21:21:37Z | 200 text/html; charset=utf-8 | 174762 | `13ceafec2485471c` | https://pmc.ncbi.nlm.nih.gov/articles/PMC5669064/ | 35-paper-citeseq-stoeckius-natmethods2017-pmc.html |
| 44 | 2026-10-05T21:21:51Z | 200 text/html; charset=utf-8 | 305616 | `685eea805343d19d` | https://pmc.ncbi.nlm.nih.gov/articles/PMC13412022/ | 25-paper-denadel-pretraining-size-natmethods2026-pmc.html |
| 45 | 2026-10-05T21:21:52Z | 429 text/plain; charset=UTF-8 | 17 | `e395ad55dd18b1bf` | https://www.biorxiv.org/content/10.1101/2024.12.13.628448v1.full | (429 Too Many Requests; not retried) |
| 46 | 2026-10-05T21:22:16Z | 200 application/pdf | 614365 | `91899dfcbc41553f` | https://arxiv.org/pdf/1705.08500 | 37-paper-geifman-selective-classification-neurips2017.pdf |
| 47 | 2026-10-05T21:22:17Z | 200 application/pdf | 1349691 | `cb654a65acb785ed` | https://arxiv.org/pdf/1706.04599 | 38-paper-guo-calibration-icml2017.pdf |
| 48 | 2026-10-05T21:22:17Z | 200 application/pdf | 4550188 | `cea1fba47755a71b` | https://arxiv.org/pdf/2211.03793 | 39-paper-engelmann-uq-atlas-cell-type-transfer-2022.pdf (first saved under a mistaken "khatri" name, renamed 21:24Z after reading the author list) |
| 49 | 2026-10-05T21:22:18Z | 200 text/html; charset=utf-8 | 46744 | `1a3a3d3afedc8db3` | https://arxiv.org/abs/2506.10037 | (abs page used for metadata/licence only; not kept) |
| 50 | 2026-10-05T21:22:29Z | 200 application/pdf | 3235297 | `5ef93203898e7005` | https://arxiv.org/pdf/2506.10037v3 | 40-preprint-cell-ontology-2025-arxiv-v3.pdf |
| 51 | 2026-10-05T21:22:30Z | 200 text/html; charset=utf-8 | 419791 | `ae35e2efbbe17fe0` | https://www.nature.com/articles/s41592-024-02201-0 | 22-paper-scgpt-natmethods2024-landing.html (paywalled landing; abstract, data availability, metadata) |
| 52 | 2026-10-05T21:22:31Z | 200 text/plain; charset=utf-8 | 8908 | `b0503e8ca789f19f` | https://raw.githubusercontent.com/bowang-lab/scGPT/main/README.md | 22b-repo-scgpt-readme.md |
| 53 | 2026-10-05T21:22:31Z | 200 application/json;charset=UTF-8 | 11726 | `3c3f3d402e52e7d0` | https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI:%2210.1126/science.abf3041%22&format=json&resultType=core | 31-meta-onek1k-yazar-science2022-europepmc.json |
| 54 | 2026-10-05T21:22:32Z | 403 text/html; charset=UTF-8 | 5559 | `400bd1344db95ba4` | https://iovs.arvojournals.org/article.aspx?articleid=2800289 | (403 Cloudflare "Just a moment..." challenge; not circumvented) |
| 55 | 2026-10-05T21:22:45Z | 200 application/json | 6648 | `efd47dd28d6fe038` | https://api.cellxgene.cziscience.com/curation/v1/collections/de2cde16-c8d3-4a6d-80be-1be9e879aaca | 34-meta-cellxgene-glaucoma-collection.json |
| 56 | 2026-10-05T21:22:52Z | 500 application/json | 149 | `6df98d79732742b7` | https://www.ebi.ac.uk/europepmc/webservices/rest/PPR653043/fullTextXML | (failed; no full text in Europe PMC) |
| 57 | 2026-10-05T21:22:52Z | 500 application/json | 150 | `a93fb0889683be25` | https://www.ebi.ac.uk/europepmc/webservices/rest/PPR1281376/fullTextXML | (failed; no full text in Europe PMC) |
| 58 | 2026-10-05T21:23:09Z | 200 text/html | 21510 | `9cf03ec9c845c5c4` | https://registry.opendata.aws/biohub-cellxgene-census/ | 14-web-aws-registry-cellxgene-census.html |
| 59 | 2026-10-05T21:23:10Z | 429 text/html; charset=utf-8 | 33953 | `d3b4dfce60d12151` | https://www.10xgenomics.com/datasets/10-k-pbm-cs-with-totalseq-b-3-standard-3-0-0 | (429 Vercel Security Checkpoint; not circumvented) |
| 60 | 2026-10-05T21:23:50Z | 200 application/xml | 155111 | `bfe42835ea76279a` | https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12190912/fullTextXML | 46-paper-hu-matching-benchmark-2025.xml |
| 61 | 2026-10-05T21:23:51Z | 200 application/json;charset=UTF-8 | 4144 | `f6ed68ff5083c509` | https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=EXT_ID:PPR1281376%20AND%20SRC:PPR&format=json&resultType=core | 45-meta-khosravi-scgpt-calibration-researchsquare2026-europepmc.json |
| 62 | 2026-10-05T21:23:56Z | 200 application/xml | 132992 | `8b84f2215ba66921` | https://www.ebi.ac.uk/europepmc/webservices/rest/PMC8602772/fullTextXML | 47-paper-huang-annotation-r-packages-gpb2021.xml |
| 63 | 2026-10-05T21:27:21Z | 200 text/plain; charset=utf-8 | 19906 | `d4293f61ca4c4966` | https://raw.githubusercontent.com/theislab/scTab/devel/notebooks-tutorials/model_inference.ipynb | 02c-repo-sctab-model-inference-tutorial-devel.ipynb |
| 64 | 2026-10-05T21:27:21Z | 200 application/json; charset=utf-8 | 1815 | `d72cc21bf7c53767` | https://huggingface.co/api/models/MohamedMabrouk/scTab | 02d-meta-huggingface-sctab-mirror.json |
| 65 | 2026-10-05T21:28:43Z | 200 text/html; charset=utf-8 | 104215 | `2d16b314e2bddb30` | https://www.biorxiv.org/content/10.64898/2026.01.29.701618v1 | 48-preprint-scdiagnostics-biorxiv2026-abstract.html |

The AWS Registry page was requested twice (second copy is the one kept; identical URL). arXiv/Europe PMC HEAD requests used only to check sizes are not listed individually.

## 3. Metadata look-ups (not saved as sources)

| UTC time (approx.) | Endpoint | Purpose / result |
|---|---|---|
| 21:17:25 | Europe PMC REST `search?query=DOI:"…"&resultType=lite` for 18 DOIs | DOI → PMCID and open-access flags. scGPT (10.1038/s41592-024-02201-0) and OneK1K (10.1126/science.abf3041) have no PMC copy; Perez 2022 (PMC9297655) is in PMC but not OA in Europe PMC. |
| 21:21 | Europe PMC search for 11 further DOIs | PMCIDs for van der Wijst 2021, CVID 2022, kidney 2022, CH 2024, Cell Ontology 2016, DenAdel 2026 (PMC13412022, not OA in Europe PMC), conformal 2025; no record for Boiarsky Nat Mach Intell 10.1038/s42256-024-00949-w; HCE preprint PPR1009630. |
| 21:22 | Europe PMC search `TITLE:"scGPT" AND SRC:PPR` | Found scGPT preprint PPR653043 (10.1101/2023.04.30.538439) and the 2026 Research Square calibration preprint PPR1281376. |
| 21:20:33 | `api.github.com/repos/theislab/scTab` and `/commits/devel` | default branch `devel`, MIT, head `5ede7f2ba1f9618b86924f2ff587931de18f4ada` (2024-09-13T10:55:09Z) — matches the README hash recorded on 2026-09-30. |
| 21:24:57 | `api.github.com/repos/{satijalab/panhumanpy, Teichlab/celltypist, bowang-lab/scGPT, chanzuckerberg/single-cell-curation}` | default branch `main` for all; licence MIT for all; heads 06b9aba32c11 (2026-07-27), fe357564a662 (2025-06-25), cebd6fae655b (2026-04-27), 21898c7df376 (2026-09-02). |
| 21:22:18 | `arxiv.org/abs/2506.10037`, `/abs/2211.03793`, `/abs/1705.08500`, `/abs/1706.04599` | Licences: 2506.10037 = CC BY 4.0; the other three = arXiv non-exclusive distribution licence 1.0. |
| 21:27:26 | HEAD requests to candidate figure URLs (media.springernature.com, journals.plos.org, ars.els-cdn.com, europepmc.org/…/bin, ncbi …/bin) | Springer Nature and PLOS figure URLs return image/png 200; Europe PMC `bin/` returned 403 and old NCBI `bin/` 404 (not pursued). No image bodies downloaded. |

## 4. Web searches (WebSearch tool; US index; no personal data in queries)

Times are approximate (all between 21:17 and 21:29 UTC, in this order).

1. `"Evaluating the role of pretraining dataset size and diversity on single-cell foundation model performance" Nature Methods` → Nature s41592-026-03120-y, bioRxiv 2024.12.13.628448, PMC13412022.
2. `"Improving atlas-scale single-cell annotation models with hierarchical cross-entropy loss" Nature Computational Science` → s43588-025-00945-z, PMC13021517.
3. `Pan-Human Azimuth preprint bioRxiv 2025 panhumanpy` → bioRxiv 10.64898/2026.07.16.738997 (posted 2026-07-21), PMC13419436, satijalab.org/pan_human_azimuth.
4. `glaucoma PBMC single-cell atlas CELLxGENE 2025 peripheral blood` → Signal Transduct Target Ther 2025 POAG paper (110+110 Chinese-ancestry donors; *not* the CELLxGENE glaucoma dataset), CELLxGENE sitemap entry "Human PBMC Glaucoma Atlas – Immune Tolerance to HSP60 …".
5. `"Immune Tolerance to HSP60" glaucoma neurodegeneration` → ARVO IOVS meeting abstracts (articleid 2766661, 2800289). No peer-reviewed full paper found for the CELLxGENE glaucoma collection.
6. `conformal prediction cell type annotation single-cell abstention unknown cell types 2024 2025` → Bioinformatics btaf521 (PMC12506889), GitHub cellconformal, popV.
7. `benchmark cell type annotation cross-study reference mapping rejection unknown cell types 2024 2025 Genome Biology` → CAMUS preprint, spatial benchmarks, STAMapper (not retained: spatial/cross-species focus).
8. `single-cell cell type annotation "selective classification" OR "risk-coverage" OR "accuracy-rejection" curve benchmark` → Huang 2021 GPB, Theunissen 2024 (hierarchical reject), NeurIPS 2024 AUGRC paper (not retained, general ML).
9. `open-set cell type annotation benchmark unseen cell types rejection held-out dataset logistic regression baseline foundation model 2025` → arXiv 2607.17227, Boiarsky.
10. `benchmarking single-cell foundation models cell type annotation out-of-distribution new studies held-out datasets scGPT Geneformer logistic regression 2025` → several FM benchmarks (zero-shot, CellBench-LS); none with abstention.
11. `"Uncertainty-aware single-cell annotation with a hierarchical reject option" Bioinformatics` → btae128 / PMC10957513.
12. `leave-one-study-out cell type annotation PBMC unknown cell type false positive rejection threshold CellTypist scANVI comparison` → mtANN (PMC10335708), scParadise, PBMCpedia.
13. `"Harmonised benchmarking of foundation models for single-cell and spatial transcriptomics" arXiv 2607.17227` → arXiv abs (submitted 2026-07-19); no HTML full text (404); not retained.
14. `cell type annotation benchmark "missing cell types" in reference query "false" assignment Azimuth CellTypist scANVI SingleR independent dataset 2024` → Hu et al. 2025 (FR-Match benchmark), Cell Ontology 2025 preprint.
15. `"cell type annotation" calibration "expected calibration error" single-cell reference mapping uncertainty benchmark` → Engelmann et al. arXiv 2211.03793, Khatri & Bonn PMLR v179 (not retrieved; cited by the conformal paper), AnnQ.
16. `scTab follow-up evaluation independent dataset "scTab" CellTypist comparison held-out study annotation 2025` → HCE paper (21 new studies), CellMaster.
17. `CZ CELLxGENE Discover data license CC BY 4.0 datasets "Creative Commons" policy` → AWS Open Data Registry page (licence "CC-BY 4.0"), NAR 2025 paper.
18. `10x Genomics datasets license "Creative Commons Attribution" pbmc_10k_protein_v3` → search snippets for several 10x PBMC dataset pages stating CC BY 4.0. The specific CITE-seq file pages could not be opened (bot checkpoint) — **licence of the four protocol files is unverified**.
19. `10x Genomics public datasets licensed "Creative Commons Attribution 4.0" support article datasets terms` → Visium HD example data page and multiome dataset page snippets (CC BY 4.0); still not the specific files.
20. `"cell type" annotation "unseen" OR "novel" cell types removed from reference "false positive" rate benchmark CellTypist scANVI Seurat SingleR "held-out" study 2025 bioRxiv` → LLM-annotation papers, spatial benchmarks; nothing matching the Rewire design.
21. `"Benchmarking single cell transcriptome matching methods for incremental growth of reference atlases"` → bioRxiv 2025.04.10.648034, PMC12190912.
22. `cell annotation "reject option" OR "abstain" "coverage" PBMC cross-dataset benchmark "logistic regression" "kNN" 2024 2025 2026 preprint` → Theunissen 2024, binned multinomial LR (arXiv 2111.12149), CAMUS.
23. `"cell type annotation" "accepted" "coverage" "unassigned" benchmark "new study" OR "held-out studies" reference atlas confidence threshold calibrated validation 2026` → 2026 spatial annotation benchmark, cytometry benchmark, harmonisation benchmark; none with matched-coverage abstention.
24. `single-cell annotation benchmark "out-of-reference" OR "reference-absent" cell types false acceptance confidence threshold PBMC independent cohorts CellTypist Azimuth scTab comparison` → scDiagnostics (bioRxiv 2026.01.29.701618), CellMaster, VICTOR.

## 5. Failures, blocks and challenge pages (none circumvented)

- **bioRxiv scGPT full text** (`10.1101/2023.04.30.533439v2.full`): 403 Forbidden at 21:21:35Z. Not retried. Nature Methods version is paywalled; landing page saved instead (abstract, data-availability statement, metadata). Europe PMC has no preprint full text (PPR653043 → 500).
- **bioRxiv DenAdel preprint** (`2024.12.13.628448v1.full`): 429 Too Many Requests at 21:21:52Z; not retried. The PMC author-manuscript HTML (PMC13412022) was used for full text.
- **Boiarsky preprint via Europe PMC** (PPR746234): 500 (no full text); bioRxiv HTML full text retrieved instead (200).
- **ARVO IOVS glaucoma abstract** (`iovs.arvojournals.org/article.aspx?articleid=2800289`): 403 with Cloudflare "Just a moment..." JavaScript challenge at 21:22:32Z. Not circumvented. Glaucoma study documented from the CELLxGENE curation API record instead.
- **10x Genomics dataset page** (`www.10xgenomics.com/datasets/10-k-pbm-cs-with-totalseq-b-3-standard-3-0-0`): 429 "Vercel Security Checkpoint" at 21:23:10Z. Not circumvented. 10x licence remains unverified for the specific files.
- **Stoeckius 2017 via Europe PMC XML** (PMC5669064): 500; PMC HTML (author manuscript) retrieved instead.
- **pklab.med.harvard.edu** (scTab data/checkpoints host): a single ranged request (`Range: bytes=0-1023`) for the 0.5 GB minimal archive at 21:27:26Z returned **HTTP 206 application/x-gzip** (no challenge page this time; the coordinator recorded an Incapsula challenge earlier on 2026-10-05). Only 1 KiB was transferred to `/tmp` and deleted; nothing kept. Recorded so the coordinator can re-check provenance options; no circumvention was involved.
- **Europe PMC / NCBI figure `bin/` URLs**: 403 / 404 on HEAD; not pursued.
- **Nature Methods DenAdel article page**: 200 but paywalled (abstract only); kept as `25b-…` for publication metadata (vol. 23, pp. 1447–1457; published 9 June 2026).

## 6. Corrections made during retrieval

- `39-…` was first saved as "khatri-uncertainty-label-transfer"; on reading the PDF the authors are Engelmann, Hetzel, Palla, Sikkema, Luecken, Theis (ICML 2022 CompBio workshop). Renamed at ≈21:24Z. Khatri & Bonn (PMLR v179, 2022) is a different paper and was **not** retrieved.
- The issue plan calls the Boiarsky work a "logistic-regression baseline" paper; the retrieved item is the bioRxiv preprint "A Deep Dive into Single-Cell RNA Sequencing Foundation Models" (posted 23 Oct 2023). The Nature Machine Intelligence Matters Arising ("Deeper evaluation of a single-cell foundation model", 2024) was not found in Europe PMC and was not retrieved (paywalled); not cited as verified.

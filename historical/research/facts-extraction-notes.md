# Facts extraction notes: article 349 (cell-type annotation transfer)

Extraction date: 2026-10-05. Output: `research/facts.csv` (242 rows). Substrate: line-stable text files in `research/automated-research/original-sources-text/` only; these files were not modified. Every `fact_text` is a contiguous quote from the cited line range. The only normalisation is collapsing whitespace runs to a single space, which matters for PDF-extracted and JSON files where one quote spans several lines.

## Self-check

A separate script read `facts.csv` back from disk and, for each row, joined lines `line_start..line_end` of `source_file` and checked that the whitespace-normalised `fact_text` occurs in that span.

- **Result: 242/242 pass (100%), 0 failures.** `fact_id` runs from 1 to 242 with no gaps, and all 56 `source_file` paths resolve.
- All 350 candidate facts also passed the same check before pruning.

## Size and pruning

- 350 verified candidates were extracted. 108 lower-value ones were removed: publication-date lines, duplicates of figures stated elsewhere, and peripheral results.
- The result, 242, is above the 130–160 target. Two requirements set a higher floor:
  - At least 3 facts per substantive source across 47 numbered sources held as 56 files gives a floor of about 141–168 rows.
  - The must-include list needs about 15 scTab facts and multiple facts each for CellTypist, Census, Azimuth, Abdelaal and calibration.
- If a smaller set is needed, the order is already a reasonable priority order within each source. Categories `historical` (12) and `expert-opinion` (7) are the most expendable.

## Category counts

| Category | n |
|---|---|
| methodology | 72 |
| technical-spec | 61 |
| finding | 44 |
| statistics | 30 |
| historical | 12 |
| benchmark | 9 |
| limitation | 7 |
| expert-opinion | 7 |

Confidence: high 224, medium 17, low 1. Medium is used for preprints and records that are not peer reviewed (45, 48), third-party mirror metadata (02d), vendor documentation claims, and the conflicting XGBoost run counts. Low is used for the mirror's self-declared MIT tag.

## Per-source fact counts (file → n)

| File | n | File | n |
|---|---|---|---|
| 01 scTab paper | 22 | 25 DenAdel (PMC) | 4 |
| 01b scTab SI | 4 | 25b DenAdel landing | 2 |
| 02 scTab README | 3 | 26 HCE | 8 |
| 02b scTab data.md | 3 | 27 HIHA | 6 |
| 02c scTab tutorial | 3 | 28 RA | 4 |
| 02d HF mirror metadata | 3 | 29 JDM | 3 |
| 03 CellTypist paper | 5 | 30 platform (NAR) | 6 |
| 04 CellTypist registry | 3 | 31 OneK1K (abstract) | 3 |
| 04b CellTypist README | 6 | 32 Perez | 3 |
| 05 scANVI | 4 | 33 COMBAT | 3 |
| 06 scArches | 5 | 34 Glaucoma record | 4 |
| 07 Hao 2021 | 5 | 35 CITE-seq | 3 |
| 08 Azimuth portal | 4 | 37 Geifman & El-Yaniv | 5 |
| 09 Pan-human Azimuth preprint | 9 | 38 Guo et al. | 5 |
| 09b Pan-human Azimuth site | 3 | 39 Engelmann et al. | 5 |
| 10 panhumanpy README | 3 | 40 CL 2025 preprint | 3 |
| 11 CELLxGENE Discover (NAR) | 4 | 41 van der Wijst | 4 |
| 12 Census release.json | 3 | 42 CVID atlas | 4 |
| 12b Census release info | 6 | 43 kidney cancer | 3 |
| 13 Schema 7.0.0 | 4 | 44 clonal haematopoiesis | 3 |
| 14 AWS registry | 3 | 45 Khosravi (record) | 4 |
| 15 CL 2016 | 3 | 46 Hu et al. | 4 |
| 16 CL v2025-07-30 release | 3 | 47 Huang et al. | 4 |
| 17 Abdelaal | 8 | 48 scDiagnostics (abstract) | 3 |
| 18 popV | 4 | 19 hierarchical reject | 4 |
| 20 conformal | 4 | 21 mtANN | 4 |
| 22 scGPT landing | 3 | 22b scGPT README | 2 |
| 23 Kedzierska | 3 | 24 Boiarsky | 3 |

Coverage:
- All 56 text files and all 47 numbered sources are covered.
- Two companion files have 2 facts each: 22b and 25b. Their numbered sources have 5 (scGPT, 22 + 22b) and 6 (DenAdel, 25 + 25b) facts in total.
- By numbered source, every source has at least 3 facts.

## Sources skipped or limited

- **No file was skipped.**
- **Source 36 (10x Genomics dataset licence)** has no text file because it could not be retrieved (bot-protected). No facts were extracted for it, so the CC BY 4.0 licence of the four 10x CITE-seq files remains unverified.
- **Metadata or abstract only:** facts from these come from abstracts or record fields, not full text.
  - 22: scGPT landing page plus data-availability statement
  - 25b: publisher landing page
  - 31: OneK1K Europe PMC record
  - 34: CELLxGENE collection JSON
  - 45: Research Square record, not peer reviewed
  - 48: bioRxiv abstract
  - 02d: third-party Hugging Face metadata
- **Personal data:** the contact email in the glaucoma collection record (34) and author emails in PDF headers were deliberately not quoted.

## Must-include items (fact locations by file:line)

- **scTab:**
  - corpus: 01:70, 01:80, 01:146
  - filters: 01:72–77
  - donor split and the reason against study holdout: 01:35, 01:78; 02b:40–46
  - comparator training amounts: CellTypist 1.5 M at 01:41; CIForm 750 k at 01:41; scGPT 1.5 M zero-shot at 01:220 and 150 k fine-tuned at 01:232
  - unknown-type analysis: 01:239, 01:243, 01:248
  - platform transfer: 01:49
  - authors' caveat: 01:63
  - checkpoint and genes: 02c
- **HCE study-transfer drop:** 26:29, 26:30 (ID and OOD), 26:34, 26:39, 26:43
- **Abdelaal rejection:** 17:20, 17:148 (×2), 17:149 (×3), 17:181, 17:186
- **CellTypist:**
  - registry: 04:6–13, 04:16–21, 04:331–336
  - probability (sigmoid): 04b:129–130
  - best match: 04b:132
  - prob match / Unassigned: 04b:134, 04b:136–137
  - majority voting: 04b:209
  - paper: 03:97, 03:33
- **HIHA CellTypist-guided labelling:** 27:136 (×2), 27:145, 27:160
- **Platform-study consensus labels:** 30:108, 30:109 (×2), 30:163 (×2)
- **CVID stimulation:** 42:87 (×2), 42:104 (×2)
- **Census:**
  - LTS: 12:2–3, 12:124–140; 12b:69, 12b:86–90; 14:9
  - `is_primary_data`: 11:35; 13:725; 01:72
  - erratum: 12b:246
  - multi-valued `disease`: 12b:94
  - licence: 14:10–11
  - schema pins CL 2025-07-30: 13:225
- **Azimuth:**
  - portal: 08:5 (×2), 08:12, 08:13
  - Pan-human Unassigned class: 09:29, 09:131
  - calibration: 09:43
  - split: 09:155
  - weights licence: 10:53–55
- **scANVI/scArches query mapping:**
  - 05:247 (×2), 05:65, 05:86
  - 06:79, 06:112, 06:217, 06:67, 06:206
- **Calibration and selective classification:**
  - 37:6, 37:8, 37:13 (×2), 37:42
  - 38:12 (×2), 38:29, 38:32, 38:142

## Contradictions, tensions and caveats between or within sources

1. **CellTypist label counts by version.**
   - The paper (author manuscript) describes a low-hierarchy model with 91 types from "20 tissues of 19 studies" (03:33, 03:97).
   - Registry v2 (2022-07-16), the model actually distributed, lists `Immune_All_Low` with 98 types from "20 tissues of 18 studies" (04:10–11).
   - HIHA cites 98 types (27:136). Cite the registry for the model that is run.
2. **Pan-human Azimuth type count.** The portal says 380 high-resolution types (08:5); the documentation site says 381 (09b:35).
3. **Pan-human Azimuth corpus size.**
   - 9,665,434 high-confidence cells (09:128) versus a "~9.8 million" final training set (09:155).
   - The gap fits the ~145,000 "Unassigned" negatives added afterwards (09:29), but that link is my inference.
   - Separately, "Unassigned" is a QC class for empty droplets and multiplets (09:131), not a novel-cell-type detector. The portal's "confidence scores" wording (08:5) should not be read as unknown-type rejection.
4. **scTab XGBoost run count.** Supp. Table 1a gives 5 runs (01b:97); Supp. Table 6 gives 4 runs for the same 0.8127 ± 0.0005 (01b:168).
   - Not quoted: scTab `docs/data.md` prints the validation count as "3.500.,032" (02b:84), a typo for 3,500,032 (01:80).
5. **Donor split versus study holdout.**
   - scTab's docs say a donor split "better represents how the classifier generalises to unseen donors / data sets" (02b:42).
   - HCE reports that the same corpus loses 24–32% macro-F1 on 21 newly released studies (26:34). It says donor splits "do not reflect how cell atlases evolve in practice" (26:29).
   - scTab's own non-10x check also fell to ~0.4 macro-F1 (01:49). The scTab paper is more cautious than its docs here: it calls the donor split "a sensible compromise" (01:35).
6. **scTab's general-annotation framing versus its Discussion.** The framing in the introduction and abstract contrasts with the Discussion caveat that the models' strength "does not lie in correctly classifying novel cell types" (01:63). The "unknown" group in its ROC analysis consists of the types its own rare-type filter removed (01:243).
7. **Platform-study labels (refines protocol-deviation caveat 2).**
   - Discordant CellTypist/Seurat cells were first marked "Unassigned" (30:109).
   - They were then relabelled by subcluster majority vote and neighbourhood smoothing, "yielding 96.2% cell annotation across all kits" (30:109, 30:163).
   - So the final labels are model consensus plus cluster smoothing, and the "Unassigned" share in the published labels is small.
   - Whether the Census dataset holds pre- or post-smoothing labels is **unverified**. The deviation note's claim that Unassigned cells are excluded and so over-represent agreement cells should be checked against Census metadata.
8. **HIHA label provenance has two layers.**
   - The atlas (about 1.95 M cells, 27:139) got expert labels, guided by CellTypist `Immune_All_*` and Seurat MapQuery (27:136, 27:145).
   - The 13.8 M-cell longitudinal dataset was labelled by CellTypist models trained on the atlas (27:160, 27:169).
   - If Census dataset `e522d2cd` is the longitudinal set rather than the atlas, its test labels are themselves logistic-regression predictions, not expert labels. This is **unverified** and should be checked in Census metadata.
9. **CVID reference composition.**
   - The source describes "steady-state and activated B cells" and ~100 k PBMCs stimulated for 48 h. Unstimulated *cultured* controls are also present (42:87, 42:104).
   - All samples were enriched with sorted CD19+ B cells at a 2:1 ratio (42:104).
   - So even the "unstimulated" cells are cultured, and lineage proportions are deliberately distorted. This goes beyond the deviation note's "includes stimulated PBMCs".
10. **Hao 2021 reference includes activated cells.** The reference spans "resting (unvaccinated) and activated (post-vaccination)" states, days 0, 3 and 7 after a VSV-vectored HIV vaccine (07:74). "Healthy blood" is therefore only approximate.
11. **`is_primary_data` specification versus practice.**
    - The schema and the NAR paper say each cell is marked primary exactly once (11:35; 13:725).
    - The Census 2023-05-15 LTS release, which scTab and scGPT used, has 243,569 cells marked primary at least twice (12b:246).
    - scTab relied on this flag "to prevent label leakage" (01:72). Its effect on scTab's test set is unverified.
12. **Engelmann et al., within-paper tension.**
    - The Conclusion says "the baseline methods are not well calibrated" (39:81).
    - The Results report that on the leave-out dataset WKNN's calibration *improves*, becoming "comparable to models that quantify uncertainty" (39:55).
    - Their unseen-type test removes types inside one atlas; the authors say a real OOD study is still needed (39:79).
13. **Abdelaal: expectation reversed by results.**
    - The authors expected removing all T cells to be easy and removing CD4+ memory T cells to be hard. "almost all classifiers ... show the opposite" (17:148).
    - SVMrejection labelled removed T cells as B cells (17:149).
    - Even so, the paper recommends SVMrejection overall (17:181).
14. **Fixed rejection thresholds differ by tool and are mostly ad hoc:**
    - CellTypist `p_thres` 0.5 (04b:134)
    - scArches 50% uncertainty (06:217)
    - Seurat lowest 20% of projection scores (06:206; 21:48)
    - SVMrejection 0.7 (17:186)
    - Theunissen et al. show optimal thresholds "differ quite severely" between classifiers (19:80).
    - popV found method-intrinsic certainties "calibrated differently" (18:41).
15. **Pan-human Azimuth licences.** Preprint CC BY-NC 4.0 (09:11); model weights CC BY 4.0 (10:53–55); code MIT (per the catalogue, not quoted here). The Hugging Face scTab mirror self-tags MIT (02d:23) as a third party. The official scTab README states MIT for the repository (02:65–67) and says nothing explicit about the checkpoints.
16. **HCE publication date.** The DOI suffix (s43588-025-…) and the brief say 2025, but the journal record gives 2026-01-30 (26:4). Cite as Nat Comput Sci 2026 (online 30 Jan 2026).
17. **Census multi-valued `disease`.** Exact-match filters "may yield incomplete results" (12b:94). This bears on the protocol filter `disease == 'normal'` and the glaucoma dataset, which mixes `normal` and `open-angle glaucoma` donors (34:176–181).
18. **RA labels exclude platelets and high-gene cells.** RA preprocessing removed cells with >1,000 genes and all platelet/megakaryocyte-marker cells (28:100). The test-set label space therefore lacks platelet/MK, and the gene cap may also drop some large or activated cells.
19. **Foundation models versus simple baselines.** The evidence is consistent across sources, not contradictory:
    - Boiarsky, LR competitive (24:73)
    - Kedzierska, zero-shot FMs inconsistent (23:38)
    - DenAdel, saturation at 1% of the scTab corpus (25:159)
    - Khosravi, preprint: matched-gene LR well calibrated, scGPT-embedding LR miscalibrated (45:68)
    - Opposing view: scGPT's abstract claims "superior performance" after transfer learning (22:44), from a paywalled source where only the abstract was available.

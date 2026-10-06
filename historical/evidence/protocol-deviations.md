# Protocol deviations and post-freeze caveats (article 349)

Primary analyses remain exactly as frozen in `protocol-frozen-original.md` (receipt `protocol-freeze-receipt.txt`). Items below are either implementation clarifications that do not change any frozen choice, or post-hoc additions that are labelled as such wherever they are reported.

## Implementation clarifications (no change to frozen choices)

1. 2026-10-05 21:33 UTC. Disk guard changed from "stop" to "wait up to 2 h" because free space fluctuates with other jobs' temporary files. Data run D02 aborted after its first study and replaced by D03 with identical code and seed; no data from D02 were used.
2. Library size for log1p CP10k in matched methods is the total over all genes in the Census pull (`obs.total_counts_all`), not over the stored feature subset.
3. CellTypist (P1, M5) produces one-vs-rest sigmoid probabilities. Thresholding uses the top-label probability as frozen; for the multiclass Brier score only, target-level probabilities are renormalised to sum to one. Reported as such.
4. Released-model predictions that are `outside` the target set count as accepted errors if above threshold (as frozen); the lineage used for the hierarchy-error split comes from fixed CL lineage anchors in `ontology.py` (`LINEAGE_ANCHORS`). A prediction with no anchored lineage counts as cross-lineage.

## Post-freeze caveats from the research dossier (found 2026-10-05 ~21:40 UTC, before any held-out result was scored)

1. **Test labels partly derived from a compared model.** The Human Immune Health Atlas labelled cells with CellTypist `Immune_All_High`/`Immune_All_Low` and Seurat to guide annotation before expert curation (`research/automated-research/original-sources-text/27-paper-hiha-nature2025.txt:136`). Agreement between P1 (released Immune_All_Low) and HIHA labels is therefore partly circular. **Post-hoc sensitivity (labelled):** practical-track results are also reported excluding HIHA.
2. **Platform-panel labels are a CellTypist + Seurat consensus**, with discordant cells marked "Unassigned" (`30-…:107-109`). Unassigned cells are outside our scored set, so the platform panel over-represents cells on which label-transfer methods already agree. Platform results are descriptive only, as frozen; P1 on this panel is flagged as circular.
3. **CVID reference study includes stimulated PBMCs** (CD40L/IL-21 or anti-CD3/CD28; `42-…:87`). It remains in the reference as frozen (same for every matched method); recorded as a limitation of reference realism.
4. **Census `disease` may be multi-valued under schema 2.4.0** (`12b-…:94`); the exact `disease == 'normal'` filter may omit some healthy cells. Affects inclusion only.
5. **Access-and-feasibility correction:** Pan-Human Azimuth model weights are CC BY 4.0 (Zenodo 10.5281/zenodo.20401417), not MIT; the `panhumanpy` code is MIT. The notrun decision is unchanged.
6. **scTab host access changed:** on 2026-10-05 21:39 UTC `pklab.med.harvard.edu` answered a plain ranged request with HTTP 206 (no challenge). A byte-level comparison of the mirror checkpoint with the official archive is planned by streaming (no storage); it is an added provenance check, not a protocol change.

### Additions after fact extraction (2026-10-05 ~21:55 UTC, before scoring)

7. HIHA identity checked: test dataset `e522d2cd` is the 1,821,725-cell "Human Immune Health Atlas" (expert-curated labels guided by CellTypist/Seurat), not the CellTypist-labelled "Sound Life" longitudinal datasets (`46104f0b`, `47e00f43`, `420d0f5d`, `3cb646ab`), which are not used.
8. Platform study: after the CellTypist/Seurat consensus step, unassigned cells were relabelled by cluster majority ("96.2% cell annotation across all kits", `30-…:109,163`). Whether Census holds pre- or post-relabelling labels is unverified; caveat 2 stands in weakened form.
9. CVID reference: unstimulated controls were also cultured for 48 h and samples were B-cell enriched 2:1 (`42-…:87,104`). Hao 2021 reference includes days 0, 3 and 7 after vaccination (`07-…:74`). RA test labels exclude platelets/megakaryocytes by preprocessing.

### Implementation clarification added 2026-10-06 08:40 UTC (before any held-out result was scored)

10. D03 (identical code and seed to the frozen plan) stopped at 2026-10-06 00:17 UTC on the 2 h disk-guard timeout after pulling all six reference studies in memory; only `features_and_classes.json` and `gene_universe_G.csv` were written, and no query data were pulled or scored. `build_data.py` now writes per-study checkpoints (reference parts at the full gene universe G, the saved state of the sampling RNG, atomic file writes) and accepts `--resume`. Sampling functions, seed, study order and feature selection are unchanged. Equivalence test D04: a smoke build interrupted after its first study and resumed gave reference and query matrices, cell IDs, released-model predictions and receipt entries identical to the uninterrupted smoke run D01. The full build is D05; D03's `features_and_classes.json` is kept as a determinism reference for D05.

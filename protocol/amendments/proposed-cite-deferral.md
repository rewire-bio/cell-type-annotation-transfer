# PROPOSED amendment: defer the protein check (NOT APPROVED)

This file is optional and needs the user's approval. Writing it does not approve it.

**Trigger.** `evidence/cite-access-blocker.json`: the first frozen 10x file (`pbmc_10k_protein_v3`) returned HTTP 403 to an ordinary urllib request at 2026-10-06T17:29Z. Files 2–4 were not attempted, because no further retries were authorised. No protein data were acquired.

**Change (only if approved)**
1. The protocol §7 protein check is recorded as **not run (10x CDN 403)**. It must never be recorded as passed, skipped-as-pass or partial. Steps R4, the CITE part of R5, R7, F4 and the protein part of F5 are not executed.
2. Only these protein/CITE-derived gates are removed (`protocol/tolerances.json` gets a new version, and the old file and its hash are kept):
   - T1 `adt_count_tables`
   - T2 protein gating
   - `expected_query_files.CITE` (4 → 0)
   - M-tier `protein_fields`
   - the descriptive `protein gates.json counts`
   - the final-verify requirement for all four CITE files
3. Everything else stays exactly as approved: data, Census pin, sampling, seeds, features, M1–M6, P1/P2, Arms A/B, operating points, every core metric and tolerance, D-1a natural-unknown scope, platform analysis, the uncertainty method and the blog gates. The **JDM CITE-seq test study `a199ca73…` stays in the test set.** It is a Census RNA dataset, and the 403 does not affect it.
4. Budgets: all ceilings stay as approved (8 h / 15 h / 30 min / 7 GiB / 12 GiB / 2 attempts). Time freed by the dropped steps is not given to anything else.
5. Disclosure: the paper and the blog must both say: "No orthogonal protein validation was performed: the first frozen 10x download returned HTTP 403, and the other three were not attempted; accuracy is measured against author labels only." The reproduction outcome is reported for the core scope with "protein check not run" next to it.
6. If the user later authorises access, the frozen §7 check may be run unchanged and reported as a separate addendum.

**Timing.** This amendment must be recorded and hashed before R6 scoring. No predictions have been compared with labels and no threshold has been changed.

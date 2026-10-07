# Protocol deviation and approved correction: M5 training seed (m5-seed0-v2)

- Written: 2026-10-07, during authorship of the corrected manuscript (paper-author worker). Revised the same day as a bounded authoring correction of draft22 (`evidence/reviews/m5-author23-inputs/draft22/protocol-deviations-m5-seed0-v2.md`, sha256 `568a995193eeaba26e78a249d6703f75ce7def731d37c80061d8b9bcfbceb0cf`). This record describes evidence already on file. It is not an approval, a review verdict or a scientific verification.
- Protocol rule: `protocol.md` §3 (line 60): "Seeds: 0 for model training".
- Affected method: M5, CellTypist 1.7.1 trained on the study reference, both arms.
- Results of record after correction: run `448f32386dfe45588fefa84c5d486703`, result version `m5-seed0-v2`.

## 1. Deviation

- `companion/src/celltransfer/methods.py` (original sha256 `914989c507d02ffe04886907b0812fd3c80ac597c8c87a657890923f35cf3c14`, preserved as `evidence/reviews/m5-original-methods-1e95aac.py`) called `celltypist.train(...)` with no seed.
- With more than 50,000 reference cells (63,767 in Arm A and 58,245 in Arm B), CellTypist selects the SAG solver. It passes `random_state` to scikit-learn's `LogisticRegression` only through keyword arguments.
- The saved original M5 estimators therefore record `random_state=None`, with `solver=sag`, `max_iter=500`, `tol=1e-4`, `C=1.0`, `multi_class=ovr` and `n_jobs=4`.
- In every unseeded fit, at least one one-vs-rest sub-problem stopped at `max_iter=500`.
- Source: `evidence/reviews/m5-reproduction-failure-review.md`, findings E4 and E5.
- M2/M3 (PCA), M4 and M6 were seeded with 0. M1 has no random component.
- The earlier manuscript stated "The training seed is 0 for all methods". That statement was incorrect for the historical M5 fits. It is corrected in `paper/main.tex`.

## 2. How it was detected

Reproduction `78542e9d412548edbfe42b38d452f7a8` was compared with original run `29879296d87343898100c190308744a1` under `protocol/tolerances-v2.json`. The comparison did not exit 0.

Retained summary: `evidence/reviews/m5-failure-78542e9d412548edbfe42b38d452f7a8/comparison-failure-summary.json` (derived from report sha256 `2a663866746ee682b93cadcfaebba56715dbb6cf308bc78bdd86301f689d6dc8`; packet index `evidence/reviews/m5-failure-78542e9d412548edbfe42b38d452f7a8/packet-index.json`). It records:

- overall status "partially reproduced";
- 1,523 checks;
- 54 gated breaches;
- 0 unsupported checks.

All 54 breaches are M5:

- **17 per-file label checks:** 8 Arm A files and 9 Arm B files. The other M5 label files stayed within the allowed number of disagreeing cells.
- **32 per-file confidence checks:** all 17 Arm A and all 15 Arm B M5 files.
- **5 metric checks:** all Arm A natural-unknown quantities.

M1–M4, M6, P1 and P2 passed their declared gated checks.

The inputs to the two M5 fits were identical: training matrix, labels, features and scaler. The coefficients differed.

## 3. Approved correction

- Decision: Option R of `evidence/reviews/m5-seed-repair-proposal.md`, with the clarifications in `evidence/reviews/m5-seed-repair-execution-note.md`.
- Approved by the user ("approved") on 2026-10-07. Record: `evidence/reviews/m5-seed-repair-user-consent.json`.
- The only scientific change is to pass `random_state=0` to M5 training. The seeded `methods.py` sha256 is `d2cb0cdef8a25cdc98df43ffdff3c9fcf6040972cab51b8ad5416be7da2f167e`.

Unchanged:

- the solver, `max_iter=500`, `tol`, `C` and `n_jobs`;
- data, features, labels and classes;
- thresholds, metrics, the bootstrap, the natural-unknown scope and the tolerances;
- threads (4), process-group memory (12 GiB) and study storage (7 GiB) limits;
- the runtime ledger (54,000 s raw, 53,970 s effective).

Scope:

- Four seed-0 M5 fits are permitted: canonical A and B, and reproduction A and B.
- Two scoring stages are permitted.
- No fit retry is permitted.

This is a material change to the M5 result of record. The corrected M5 results are labelled `m5-seed0-v2`. The historical unseeded M5 outputs are retained and are not overwritten.

## 4. Execution history of the corrected canonical stage

All three attempts are retained and charged to the cumulative ledger. Failure records: `evidence/reviews/m5-author23-inputs/failed-c098-manifest.json` (original sha256 `6a3405b9ed52f563eda5274a750578650af8a307610c1d1b4600c13ccd9a9c82`), `failed-c098-receipt.json` (`4734949241614fab394ebe2f8d89298016eaa45c3de6ece6cf5a0d96f4764fd7`) and `failed-3f18-receipt.json` (original `048f0851453afe612e32ecc7640f7adcdc8a77ced689d2be41c65b77bbaaad8d`); path-substitution details in `evidence/reviews/m5-author23-inputs/bundle-index.json`.

1. **Attempt `c098a3420d0a4c99b6d2b8d65c667af7`.**
   - The manifest records `status: failed`, `exit_code: 143`, duration 302.7 s and the failure "storage budget exceeded".
   - Its receipt lists no executed step (`steps: []`). The stop came before any environment, fit, prediction, scoring or protein step. No M5 fit was invoked.
   - Cause as recorded: the harness storage measure had counted preserved, read-only history against the 7 GiB study storage cap. The recovery approval (`evidence/reviews/m5-seed-repair-canonical-storage-recovery-approval.json`) restores the accounting to approved active working prefixes. Preserved read-only history is excluded, per `protocol/resume-plan-reviewed.md` §2. The cap stays 7 GiB.
   - The same approval file also records the M6 checksum-sidecar path binding change: identical sidecar bytes, moved so they no longer match the M5 path-token exclusion rule. That was a separate preflight binding repair, not the reason for the storage stop.
   - No scientific setting, fit count or runtime ledger changed.
2. **Attempt `3f18e178b78d4d75b595174cfa00cf99`.**
   - Its receipt records two executed steps: `env` (ok, 6.7 s) and `A_M5_fit` (ok, 744.1 s). This was the seed-0 Arm A fit: model sha256 `111e03c33dc7f8062fbb5106af155720852e2b95a0a067ad08c80836977ef11b`, step sha256 `7e52e4a650571bf4c0a82aa870db2efdcad1ffac9d8103a518825ebc626e802f`.
   - It then stopped (`status: stopped`) at the post-fit identity check, with the blocker "Scaler/genes/classes changed". The historical scaler digests had been computed over dtype, shape and bytes, whereas the checker hashed raw array bytes only.
   - A read-only comparison showed that the genes, classes and scalers matched exactly.
   - Recorded continuation approval: `evidence/reviews/m5-seed-repair-canonical-postfit-continuation-approval.json`. It permitted operational changes to `scripts/m5_seed_repair.py` and `scripts/build_m5_repair_inventory.py` only, so that the check uses the dtype+shape+bytes encoding. This allowed the completed Arm A fit to be retained without a refit. The approval permitted no additional fit and no change to model, data, parameters, tolerances or resources.
3. **Run `448f32386dfe45588fefa84c5d486703`.** Completed with exit code 0.
   - It retained the Arm A fit from attempt 2. The receipt records `executed: false`, the source run and the source step hash.
   - It executed the Arm B seed-0 fit: 501.2 s, model sha256 `15829b4c79f3c1ca510bcc2a7487501d25ca4656e1a88dcbf2916c87adbb2770`.
   - It then executed the M5 predictions, the Arm A M5 CITE predictions, scoring and the protein check.
   - The receipt records `random_state=0`, `solver=sag` and historical-equal identity hashes for both arms.
   - The non-M5 equality check passed.

Two of the four permitted M5 fits have been used.

Cumulative runtime ledger, as recorded:

| Quantity | Seconds | Source |
|---|---|---|
| Prior to the canonical stage (reproduction lineage) | 7,085.1 | c098 manifest `prior_seconds` |
| Attempt c098 | 302.7 | c098 manifest `duration_seconds` |
| Cumulative after c098 | 7,387.7 | c098 manifest `cumulative_seconds` |
| Attempt 3f18 (charged) | 1,187.7 | 8,575.5 − 7,387.7 |
| Prior to run 448f, including both failed attempts | 8,575.5 | 448f manifest `prior_seconds` |
| Run 448f | 1,914.1 | 448f manifest `duration_seconds` |
| Cumulative after completion | 10,489.6 | 448f manifest `cumulative_seconds` (10,489.604708539962) |

The 3f18 receipt itself records 8,144.3 s cumulative when it was written. The charged 1,187.7 s is the difference between the prior times of the following runs, as recorded in the continuation approval (`minimum_actual_prior_seconds`) and the 448f manifest. The effective ceiling of 53,970 s is unchanged.

## 5. Effect on reported results

- M5 values in the paper now come from the corrected run. This includes the per-class unknown-label distributions and the platform values. They are read from the corrected run's `unknowns_test.csv` and `platform.csv`, supplied for this revision in `evidence/reviews/m5-author23-inputs/canonical/`. Hashes are in `evidence/reviews/m5-author23-inputs/bundle-index.json`.
- Corrected and historical values are compared descriptively only in the paper's Section "M5 seed correction and versioning". There they are labelled with their source run and the date of the failure review.
- Arm A M5 natural-unknown acceptance across the three fits:
  - original unseeded fit: 6 of 20;
  - failed-reproduction unseeded fit: 3 of 20;
  - corrected seed-0 fit: 4 of 20.
- In the corrected seed-0 fit, the most frequent predicted label for the 20 erythroid cells was HSPC (0.60 of the cells; `unknowns_test.csv`).
- Arm B corrected M5 most frequent labels: ASC → B (0.853); MAIT → γδ T (0.595); pDC → B (0.509), narrowly ahead of cDC (0.455).
- Corrected M5 Arm A platform closed-set accuracy: Parse v2 0.434, ScaleBio 0.552. The historical unseeded original fit recorded 0.434 and 0.548 (failure review NB2).
- The other pooled M5 metrics moved by less than 0.01 between the unseeded fits.
- The corrected Arm A M5−M4 macro-F1 interval includes zero, as both unseeded intervals did.
- Claim mapping and relocated provenance/historical records: `evidence/claims-history/m5-seed0-v2-supersession.json`. The active ledger `evidence/claims.json` uses only the measurement, literature and interpretation kinds.

## 6. Unresolved and pending

- The cause of the earlier disagreement was not isolated beyond the missing seed. The following were not excluded:
  - `n_jobs=4` one-vs-rest parallelism;
  - BLAS threading;
  - an unrecorded historical environment.
- Seed-0 coefficients still depend on the seed. Some sub-problems may stop at `max_iter=500`. Three fits are not a seed-variance estimate.
- The seed-controlled reproduction of the corrected results, its comparison and the paper compile are separate later gates. They were **pending** when this record was written, and no outcome is predicted here.
  - Per the approved plan, the reproduction refits M5 in both arms in a separate checkout, without any canonical M5 artefact.
  - It adopts the other methods' completed fits from the failed reproduction lineage (`727c2514a006421286527ce1d2f22148` / `78542e9d412548edbfe42b38d452f7a8`). These are preserved earlier fits, not new fits.
  - If its comparison does not exit 0, the approved stopping rule applies: no further seeds, fits, solver or iteration changes, and no tolerance changes.
- No independent human scientific review or external replication has been performed.
- `evidence/paper-claim-inventory.json` (58 claims, sha256 `314aee11ac86b01fe92b896fa0af716e14eeaed4a1c13f09fc4ca76828c7b69e`) is preserved unchanged. It is not an owned output.
  - It predates `m5-seed0-v2` and is historical only. Its M5 literals are superseded.
  - Supersession metadata is recorded in `evidence/claims-history/m5-seed0-v2-supersession.json` (`historical_paper_claim_inventory`).

# Methods review: proposed protein-replacement amendment

Reviewer: methods-reviewer worker (claude-opus-5-5), 2026-10-06, snapshot `81e1f91d29990da243b16fdb32e6298f9449e527`.
Under review: `protocol/amendments/proposed-protein-replacement.md` (the "proposal").
Corrected text: `protocol/amendments/protein-replacement-reviewed.md` (the "reviewed amendment"). It is still only a PROPOSAL.

This is a pre-execution review. No experiment was run, no data were downloaded or opened, no input file was edited, and nothing was approved. This review does not claim that any harness check passed or that anything was scientifically verified.

## 0. What was read and what was observed

**Read (frozen inputs):**
- the proposal
- `protocol.md`
- `protocol/tolerances.json`
- `evidence/protein-replacement/{inspection.json, overlap-audit.json, pbmc_10k.py, pbmc_5k_v3.py}`

**Read for context:**
- `protocol/amendments/2026-10-06-approved-resumption.md`: two attempts per step, 7 GiB cap
- `protocol/resume-plan-reviewed.md` §3 and §5: guards of 3 GiB to start a step, 4 GiB for fits, and a kill at 1.5 GiB
- `evidence/cite-access-blocker.json`
- `companion/scripts/build_cite.py`
- `companion/scripts/protein_check.py`
- `evidence/protein-replacement/mapping-feasibility.json`, which is identical to the `mapping_feasibility` block in `inspection.json`

**External checks, both retrieved 2026-10-06:**
- `https://api.github.com/repos/YosefLab/totalVI_reproducibility/license` returned **HTTP 404**. GitHub detected no licence.
- `https://api.github.com/repos/YosefLab/totalVI_reproducibility/contents/?ref=27d65a9c49182f39df0c4325249bc7dc8e663dd0` lists `.gitignore`, `README.md`, `requirements.txt` and 8 directories. There is no LICENSE or COPYING file.
- Both were read through a summarising fetch tool, so the coordinator should confirm them.

**Facts supplied by the coordinator, not found in the frozen evidence files:**
- (C1) The commit-pinned `raw.githubusercontent.com` URLs served both files' bytes successfully, so no LFS fallback was needed. `inspection.json` does not record the URL that served the bytes.
- (C2) The original 403 used up R4 attempt 1 of the 2 approved.
- (C3) Free disk is now below 1 GiB after the task cache cleanup.
- (C4) The user said "sounds great, continue" after being shown the two candidates and the preprocessing limitations. The numerical eligibility floors were not shown.

The reviewed amendment labels all four as coordinator-reported.

**Checked by reading only, not executed:**
- **Coverage percentages.** All six in proposal §5 match the integer counts in `inspection.json`, e.g. 1565/2020 = 0.7748 and 13064/19331 = 0.6758.
- **ADT names against the gate patterns.** The `protein_check.MARKERS` patterns match the `inspection.json` names for CD3, CD4, CD8 (`CD8a_TotalSeqB`, case-insensitive), CD14, CD16, CD19 and CD56 in both files. CD20 is also matched in the 5k file.
  - `^CD4(_|$|-|\.)` does not match `CD45RA` or `CD45RO`.
  - So all six gates appear available. This is my reading, not an execution of E4.
- **Download size.** 18,294,964 + 24,937,137 bytes ≈ 43.2 MB, which matches the proposal.

## 1. Verdict

The design is defensible as a **descriptive, per-file, secondary** check, with the downgrades the proposal already makes. The proposal is not approvable as written, for two reasons:
- it has internal contradictions (B2, B3);
- it has wording the evidence does not support (B4–B6).

It also offers a retry budget larger than the approved one (B1). The reviewed amendment fixes all of these.

Separately from the text, **execution is blocked** for two reasons:
- **No approval.** No concrete approval of the reviewed text exists (B7).
- **Not enough free disk.** Free disk is reported below the approved guard (B8).

## 2. Blocking findings

| ID | Location | Finding | Correction in the reviewed amendment |
|---|---|---|---|
| B1 | §10, §2.2 | Offers an "alternative" of 2 new attempts for R4′. Also allows ≤3 transient retries inside the helper and a fallback to a second host (`media.githubusercontent.com`). Together these exceed the approved "at most two attempts per step", of which the 403 used one (C2). | R4′ is R4 attempt 2, the **last** one. Each file gets one GET from the pinned raw URL: no in-helper retries and no alternate host. The LFS fallback is removed because the raw URLs already served the correct bytes (C1). If R4′ fails for any reason, stop and go to the deferral. |
| B2 | §6 vs §7 and §8 | §6 stops per file ("if any criterion fails, the replacement stops for that file"). But tolerances v2 hard-codes `expected_query_files.CITE = 2` and "T1 adt tables 2 files", and E8 hashes tolerances v2 before R4′. If one file failed, the harness would then fail its own gate. | Per-file eligibility is kept. Tolerances v2 sets the expected CITE file count to `n_eligible` (0, 1 or 2) by rule, read from a hashed `eligibility.json` written in R4′ **before** any prediction. With 0 eligible files the check is "not run". Mode F must reproduce the same verdicts exactly (T1). |
| B3 | §8 E8 and steps vs §12 timing | The order of approval and E1–E8 contradicts itself: (1) E1–E6 are *inside* R4′, but E8 must be recorded "before R4′"; (2) R7 runs "only after E1–E8 pass"; (3) §12 needs the tolerances v2 hash *at approval*, but tolerances v2 is only written *after* approval. | One linear order (reviewed §8): approval record (amendment sha256) → write code, tests and tolerances v2 → E6-synthetic and E7 (no real data) → E8 hash record → disk guard → R4′ = E1–E5 → eligibility record → build eligible files and P1/P2 → R5 → R7. The tolerances v2 *content* is fully specified in the approved text. Its file hash is recorded at E8, not at approval. |
| B4 | §2.1, §11 item 1, §11 stop wording | "The four … files could not be used" and "pre-registered 10x files were unavailable (HTTP 403)" are not supported. Only the first file was requested, and it got one 403. Files 2–4 were never requested, so their availability is unknown. | The wording now states exactly that. It also discloses that the substitution was not forced by any demonstrated unavailability of files 2–4. |
| B5 | Title of §4.2; §11 item 5 | "Not independent donors" and "are not independent donors" assert something unknown. `overlap-audit.json` only says independence "cannot be established". | "Donor identity, and therefore donor independence, are unknown (they may or may not share donors)." |
| B6 | §11 items 1 and 2, §11 stop wording | "Pre-registered" overstates it. `protocol.md` v1.0 was frozen locally (freeze receipt in the repo) and was not registered externally. | "Pre-specified in the study's locally frozen protocol (v1.0, 2026-10-05; not externally registered)." |
| B7 | §12 | Asks for five separate user decisions (a)–(e) and calls the earlier "continue" agreement "in principle". The user did approve going ahead with the two candidates and their preprocessing limitations (C4). But the material numerical eligibility floors (§6.4–6.5 and the 99% QC retention floor), the eligibility rule, the attempt accounting and the tolerance changes were never shown. | One concrete approval of the reviewed amendment, recorded by the coordinator with that file's sha256, is sufficient and **required**. No separate approval per implementation detail. |
| B8 | Execution precondition (C3) | Free disk below 1 GiB is under the approved start guard of ≥3 GiB per step (≥4 GiB for fits) and under the 1.5 GiB kill threshold. | No E-step or R-step may start until free space is at least the guard. R5 needs ≥4 GiB because M6 query adaptation trains for 50 epochs. No study data, inputs, runs or evidence may be deleted to make room. This is not resolved by the amendment text. |

## 3. Non-blocking findings (fixed or disclosed in the reviewed text)

**N1. Gene coverage: observed vs inferred.**
- The feasibility counts are *observed* metadata, from a looser rule: uniqueness within G only.
- The frozen mapping is stricter (make-unique groups, Census-wide ambiguity, collisions), so realised coverage can only be equal or lower.
- The proposal says "symbol mismatch is the more plausible cause" of the F gap. Nothing measured supports that. The upstream `min_cells=4` filter could also remove reference-specific markers, for example of platelet or erythroid classes.
- Revised wording: the split between the two causes is unknown.
- For G, about 16.6–16.7k symbols survived from a full 10x reference, so the upstream gene filter alone already explains a large part of the loss. That is also an inference and is labelled as one.

**N2. Zero-filled features are not neutral for z-scored methods.**
- M1–M3 z-score each feature with the reference mean and SD (protocol §2).
- A zero-filled gene therefore becomes −mean/SD, a systematic negative value, rather than "missing".
- This bias is added to the confound already disclosed. scTab (P2) also gets about a third of G as zeros.
- It is disclosed. Nothing is changed, because the frozen pipeline also zero-fills missing genes.

**N3. Post-hoc floors.**
- F ≥ 0.75 sits only 2.5 percentage points below the observed 5k F_A of 77.5%. Since it was set after seeing the observed values, it has almost no power to fail.
- The rule that does the work is the "no more than 0.01 below feasibility" regression check.
- This is acceptable because no outcome had been seen, and it is disclosed as an engineering floor.
- The floors are kept, not tuned, and are now covered by the single approval (B7).

**N4. Gate rule is stricter than frozen §7.**
- Frozen §7 skips gates whose antibody is absent. The proposal makes all six gates an eligibility requirement.
- This is stricter and decided before outcomes, so it is acceptable. It is labelled as a change.

**N5. Preserve original results.** The proposal does not say outright that existing matched-track and practical-track runs, results and the frozen v1 tolerances stay untouched. The reviewed text says so explicitly:
- CITE outputs go only to new run directories;
- no core result is recomputed, overwritten or reinterpreted;
- a failure here never triggers a refit.

**N6. Cached inspection bytes.** The bytes inspected earlier may be reused only if they are still present unmodified and match the pinned sha256 and size. They must be labelled `cached` (OA-3). This happens inside the single R4′ attempt and is not an extra attempt.

**N7. Licence.** The proposal's "no LICENSE observed" is now supported by two GitHub API reads on 2026-10-06 (§0). The terms of the 10x source data remain unverified. The no-republication rule stands.

**N8. CLR reference.** Upstream removal of isotype controls changes the CLR row mean compared with the planned raw files. The proposal discloses this correctly. Neither the number of controls removed nor which ones is in the evidence, and the reviewed text does not state either.

**N9. QC re-application.** The two cell-loss mechanisms the proposal describes are correct:
- the 200-gene floor after the `min_cells=4` gene filter;
- in the 5k file, the mitochondrial fraction near 0.20 once the denominator shrinks.

In the 10k file, the upstream mitochondrial cut of 0.10 leaves margin below 0.20. The ≥99% retention floor is kept.

## 4. Assessment against the review dimensions

| Dimension | Assessment |
|---|---|
| Statistical validity | Per file, descriptive, no interval, no pooling. Correct for n = 2 samples with unknown donors. |
| Baseline fairness | Methods are unequally robust to roughly 20% of F being zero-filled (N2). Method differences on these files must not be read as method effects; disclosed. |
| Leakage / overlap | Unknown: the audit is metadata-only, 3 scTab IDs are unmapped, and the samples predate CellTypist v2. No holdout claim. |
| Upstream filters | Cannot be undone. They are fixed and disclosed. The likely direction is to inflate agreement (interpretation, not measured). |
| Uncertainty | None is quantified, and this is stated. |
| Reproducibility | Pinned commit, sha256 and bytes. Fixed mapping. T1 checks on the mapping CSV, the eligibility verdicts and the post-QC barcodes. |
| Budgets | Within the approved ceilings once B1 is fixed. Blocked by disk (B8). |
| Citation support | Repository, commit and licence check dated 2026-10-06. C1–C4 are coordinator-reported. |

## 5. What is needed before any execution

1. The coordinator records one explicit user approval of `protocol/amendments/protein-replacement-reviewed.md`, with its sha256, in a new dated file under `protocol/amendments/`. If the user prefers, they can instead approve `proposed-cite-deferral.md`.
2. Free disk reaches at least 3 GiB, and at least 4 GiB before R5, without deleting study data.
3. The reviewed §8 order is followed.

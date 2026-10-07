# M5 repair: execution and budget clarification

Status: user approved the repair scope with “approved” on 7 October 2026. Real-data execution still requires the tested driver, immutable inventories and approval binding. Read with the actual Opus proposal in `m5-seed-repair-proposal.md`.

The proposal's 47,847-second remainder was the budget at the start of the latest continuation. Its final cumulative time is 7,085.069447749978 seconds. The existing raw ceiling is 54,000 seconds. Preserve its single 30-second reserve: the effective ceiling is **53,970 seconds**, leaving **46,884.93055225002 seconds** after the recorded prior duration. Do not subtract another reserve per stage or ancestor. This plan requests no new runtime ledger: both repair stages, validation, copying, scoring and PDF compilation must fit in that remainder. Individual step ceilings cannot all be consumed at once; the remaining total takes precedence.

Exactly **four real-data M5 fits** are permitted: canonical A/B and independent reproduction A/B, each capped at 4,800 seconds. No fifth fit or automatic fit retry is permitted. Two full score/bootstrap stages retain the existing limits. Threads (four), process-group memory (12 GiB), guarded storage (7 GiB), scientific inputs, solver, iteration cap and comparison tolerances stay unchanged.

Execution order follows the research harness workflow: corrected canonical results; actual Opus paper/ledger authorship; freeze the corrected manuscript; independent M5 reproduction and comparison; regenerated PDF; final methods/PDF review. The paper must not predict the comparison outcome. Generated comparison tables record its actual outcome.

The proposed worker ceiling is **24 total calls**, increased from the approved 22. Call 21 produced the failure review and proposal. Call 22 authors the corrected manuscript; call 23 reviews methods and PDF; call 24 is one text-repair reserve. Scientific writing and reviews remain actual local Claude Opus.

The isolated candidate changes one argument: `random_state=0`. A synthetic engineering fixture using SAG with `max_iter=500` produced exactly equal coefficients, intercepts, probabilities, confidence values and labels for three ambient NumPy seeds. These are synthetic tests, not study findings or proof that the real-data repair will pass.

Before any real-data fit, the new selective-adoption driver must pass the proposal's V1–V5 checks and fail-closed engineering tests. The current prefix-only continuation driver cannot perform this repair. Canonical and reproduction M5 outputs must remain separate; no M5 artefact may be adopted. All other adopted outputs need immutable inventories, source identity checks and unchanged non-M5 score checks.

Existing strict claims validation requires active measurements to refer to the current canonical run. Preserve the old ledger unchanged in a versioned historical file, then maintain a separate current ledger and supersession mapping. Do not leave historical-run measurements in the active ledger and represent them as the new canonical run.

All historical results, failed runs and original receipts remain preserved. The current comparison remains failed. Approval must cover corrected, versioned M5 results; four fits and two score stages; validated selective adoption; this unchanged cumulative runtime/resource ceiling; and the worker extension to 24.

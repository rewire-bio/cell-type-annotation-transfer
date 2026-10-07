# One additional protein-build attempt after startup repairs

The clean reproduction has completed all twelve fits and both prediction arms. The stopped attempts and their files remain unchanged:

- `7860abd5206648fb87b5e5f30e16946d`: first CITE build stopped because the continuation copy omitted two pinned acquisition metadata files (16.3 seconds).
- `108dfa6e36394279931f372749ad6f6c`: metadata restoration passed its exact SHA256 checks; the second CITE build stopped at its initial disk check because the new output parent directory did not exist (0.04 seconds). No CITE processing ran.

The repair creates the new output parent before launching the unchanged builder. The next continuation copies the hash-verified completed fits, predictions and pinned inputs. It preserves previous receipts, failures, source revisions and cumulative runtime.

Requested allowance: exactly one additional guarded `cite_build` attempt, recorded as total attempt 3, with the existing 1,200-second step ceiling. No additional model fit is permitted. Downstream stages retain their existing two-attempt limits.

The overall 54,000-second reproduction limit includes the recorded 6,122.687 seconds plus the prior 30-second setup reserve, copied-file validation and new work. Four threads, 12 GiB process-group memory and the 7 GiB working-set limit remain in force. Scientific design, inputs, seeds, analysis and comparison tolerances remain unchanged.

After this attempt: remaining protein predictions, scoring, the unchanged comparison, PDF build, final model review, verification/archive and short blog draft PR.

Status: prepared; additional CITE attempt requires user approval. No additional attempt has been launched.

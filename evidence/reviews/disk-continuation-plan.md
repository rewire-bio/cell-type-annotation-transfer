# Bounded continuation after disk exhaustion

Status: prepared; the additional experiment attempt is awaiting approval.

The fresh run 727c2514a006421286527ce1d2f22148 completed setup, acquisition, the full data build, all six Arm A fits/predictions and five Arm B fits/predictions. B_M6_fit attempt 1 stopped for low disk after 523.787 seconds; attempt 2 failed its disk preflight without launching training. The original failed record and logs remain intact.

The entire study is now at `/Volumes/Extreme SSD/rewire-studies/cell-type-annotation-transfer`, with the old path preserved by a symlink. An rsync checksum comparison returned zero differences before the internal copy was removed. The SSD has approximately 1.2 TiB available. No scientific data or evidence was discarded.

## Proposed continuation

1. Permit one additional guarded attempt for B_M6_fit only, maximum 4,800 seconds, using the same frozen scientific code, data, seeds and training settings.
2. Before reusing completed fresh steps, freeze and verify their output hashes against this run's inventory. Preserve the stopped fit directories, and write the replacement fit to a new output directory.
3. Implement and test a recorded continuation that links to the failed run and verifies source/protocol identity. Retain the failed manifest; create a separate continuation record. Reuse only steps produced by this fresh run, with explicit provenance. Do not present cached historical Mode R outputs as fresh computation.
4. Finish B_M6 predictions, replacement CITE data/predictions, scoring, protein analysis, the unchanged tiered comparison, figures and PDF. Retain the original retry allowance for every remaining step.
5. Keep the cumulative 15-hour ceiling, including the recorded 4,727.451 seconds already used (including the prior setup reserve); no additional runtime budget is requested. Keep four threads, 12 GiB memory and 7 GiB study-storage cap. Use the SSD for this task's filesystem space.
6. Use the already approved remaining two Opus review calls for the regenerated evidence/PDF, then perform actual harness verification, portable archive and public study update. Prepare the short accessible blog draft PR afterward.

No changed scientific protocol, paid compute, relaxed tolerance, merge or deployment is proposed. No additional attempt has been launched.

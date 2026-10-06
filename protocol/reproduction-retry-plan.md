# Infrastructure recovery and final verification plan

Status: prepared; no further reproduction or worker-budget extension executed.

The recorded science run and both manuscript reviews are complete. Clean reproduction is incomplete.

## Preserved failures

- `086f481384e74a10968c1eade1d3b96c`, source `549b8b7`: storage scanner raised FileNotFoundError while uv removed a temporary directory.
- `ec6987480a2c45489e34088ea573efd3`, same source: the first patch handled disappearing files but missed disappearing directories during traversal.
- Both stopped during environment setup, before scientific input acquisition or fitting. The uv child processes subsequently finished; no live process remains. Their measured setup times were 12.20 and 12.27 seconds. Reserve 30 seconds of the existing cumulative reproduction budget for these attempts.
- Failed manifests, checkout sources, launch records, stdout/stderr and receipts remain. Only regenerable `.venv` and `.cache-study` directories were cleaned.

## Ready infrastructure fix

Research harness commit `b3af2bf` uses a single non-following stat per file and os.walk with explicit missing-directory handling. Other scan failures remain fatal. Four storage regression tests and fifteen core integration tests pass. A real temporary-directory churn test completed 52,682 scans without failure. Scientific code, data, tolerances and recorded results were unchanged.

## Requested bounded continuation

1. Permit one additional environment-setup attempt after the two infrastructure failures. All scientific steps retain their original maximum of two attempts.
2. Run one clean full reproduction including new inputs, fits, predictions, scoring, comparison, figures and PDF. Keep the original total 15-hour ceiling including the reserved 30 seconds, 7 GiB storage cap, 12 GiB memory cap and four threads. No paid compute, changed datasets or tolerance relaxation.
3. Allow up to two further actual local Claude Opus review calls, maximum 900 seconds each, beyond the current 20-call worker cap, solely to inspect the freshly regenerated paper and resolve any resulting text corrections. Retain all previous reviews and failures.
4. Complete verification, preserve portable evidence and update the public study repository. Only then prepare the short accessible blog draft PR. Do not merge or deploy it.

No approval for these extensions is asserted by this document.

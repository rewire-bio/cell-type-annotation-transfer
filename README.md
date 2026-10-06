# Cell-type annotation transfer

Study in progress. The recorded full experiment completed on 6 October 2026 (run `29879296d87343898100c190308744a1`). The [LaTeX manuscript](paper/main.tex) and [compiled draft PDF](evidence/reviews/paper-preview.pdf) are available. The methods and paper model reviews passed; clean full reproduction remains pending. This study has not passed the full verification gate.

The byte-verified migration inventory is in `evidence/migration-manifest.json`. Historical methods and evidence are under `historical/`; large cached runs are ignored locally pending a portable, licence-reviewed archive. The original workspace is retained unchanged.

Both matched arms have completed M1–M6. The original disk-space failure and successful recovery receipts are preserved. Two replacement paired RNA/protein datasets passed the approved eligibility checks; their secondary analysis completed under [the approved amendment](protocol/amendments/2026-10-06-approved-protein-replacement.md).

## Reviewed next step

Read [the reviewed recovery plan](protocol/resume-plan-reviewed.md), [the independent pre-execution critique](protocol/preexecution-review.md), and [the coordinator's execution note](protocol/coordinator-execution-note.md). The user approved execution and the replacement-protein amendment; approval records are retained locally by the harness. The plan retains the frozen study design and corrects the implementation to use natural-sample cells for natural-unknown metrics.

The planned order is recovery, paper draft, clean full reproduction including the PDF, final reviews and verification, then a short blog article. No blog or completed paper is claimed at this stage.

Run `python3 scripts/verify_migration.py` in the local migration checkout to verify the preserved archive. A public clone does not contain the ignored raw archive; the checker will correctly report those files missing there. Maintained code is under `companion/`. Original code and research records remain under `historical/`.

## Current completion checkpoint

- Recorded full experiment: `29879296d87343898100c190308744a1`.
- [Methods review](evidence/reviews/final-methods-r2.md) and [paper review](evidence/reviews/final-paper-r2.md): passed, using the actual local Claude Opus model. These are model reviews, not human review.
- Original migration: 613 files checked; zero changed or missing.
- Two clean reproduction launches stopped during environment setup because the harness storage scanner encountered disappearing uv cache directories. Neither reached input acquisition, model fitting or analysis. Failed records are preserved locally. The infrastructure fix passes 19 tests and a live directory-churn stress check.
- [Concrete retry plan](protocol/reproduction-retry-plan.md). The paper remains a draft and the accessible blog follows verified reproduction.

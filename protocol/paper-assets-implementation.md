# Paper assets generator: implementation note

Worker role: research-engineer. Snapshot `116cb9f57dee689da34d143376ce0799ddc00983`. Date: 2026-10-06.

**Status.** The code is implemented and tested on synthetic fixtures only.
- The active full run was **not** inspected.
- No real score, protein or comparison output was read.
- No manuscript text, results, experiments, network access or model runs were produced.

Every number in the tests is fabricated, and is labelled as such in `tests_paper_assets/_fixtures.py`. Nothing here is a study result. The protocol is unchanged.

## Files

| File | Role |
|---|---|
| `scripts/make_paper_assets.py` | Generator: LaTeX tables, figures (PDF), scalar macros and a provenance record |
| `paper/artifacts.json` | Fixed contract: the 22 `generated_inputs` that `scripts/build_paper.py` requires |
| `tests_paper_assets/` | Unit and integration tests (35) on tiny synthetic CSV/JSON fixtures, plus `run_tests.sh` |
| `protocol/paper-assets-implementation.md` | This note |

No dependency was added. The generator uses only:
- the standard library (`csv`, not pandas);
- `scripts/result_manifest.py` (shared CSV value semantics `_num`/`_ci`, `parse_eligibility`, `protein_check_summary`, `PROTEIN_LABEL`);
- matplotlib 3.9.2 and numpy 1.26.4, as pinned in `pyproject.toml`/`uv.lock`.

## Interface

`scripts/reproduce.py` (step 10) already calls this command. Its interface is matched exactly:

```
python scripts/make_paper_assets.py --score <score_all.py out dir> \
    (--protein <protein_check.py out dir> | --protein-not-run) \
    (--comparison <compare_runs.py report.json> | --no-comparison) \
    --output <root>/paper [--root <root>] [--eligibility <R4' dir>/eligibility.json]
```

**Mode F (fresh reproduction).** Called by `reproduce.py` as-is. `--root` defaults to the repository root.

**Recorded full run (Mode R).** The same script is used with the recorded run directories passed explicitly. There is normally no comparison report yet, so `--no-comparison` must be stated. Example (paths are placeholders, not discovered):

```
.venv/bin/python scripts/make_paper_assets.py --score runs/<R score dir> --protein <R7 dir> \
    --no-comparison --eligibility runs/<R4' dir>/eligibility.json --output paper
```

**Exit codes.**
- 0: success.
- 2: any input or contract error. In that case nothing is written to `paper/generated/` or `paper/figures/`; outputs are staged and moved only after every asset has been built.

## Input rules

- **Explicit inputs only.** Every input is given on the command line. The generator reads only fixed file names inside the given directories. It does no globbing, no "newest run" lookup and no directory scanning.
- **Root containment.** Every path, after symlinks are resolved, must lie inside `--root`; so must `--output`. A symlink that escapes the root is refused (this is tested).
- **Read once, hashed.** Each file is read once. Its sha256 and byte count are recorded in `paper/generated/asset_provenance.json`, with root-relative paths.
- **Score directory.**
  - Required: `summary_test.csv`, `paired_differences_vs_M4.csv`, `thresholds_validation.csv`, `calibration_test.csv`, `per_study_test.csv`, `risk_coverage_test.csv`, `platform.csv`, `cell_counts.csv`, `score_info.json`.
  - Optional: `bootstrap_nan_counts.csv`, `unknowns_allstrata_secondary.csv`, `scoring_scope.json`. An absent optional file is shown as "not available" and recorded as `absent (optional)`.
- **Protein directory.** `protein_agreement.csv` is required. `gates.json` is optional and is hashed only. The per-cell `protein_classes_*` files are never read.
- **Comparison report.** The schema must be `celltransfer-compare-report/1`.
- **Eligibility (optional).** It is parsed by `result_manifest.parse_eligibility`, which checks the sidecar hash and the builder pins. `protein_check_summary` must then agree with the protein option: 0 eligible means not run. When run, the protein files must equal the eligible files.

**Identity checks (fail closed):**
- Unrecognised arm (not `A`, `B` or `practical`).
- Duplicate identity rows.
- Different arm/method sets in thresholds and summary.
- Paired, calibration, per-study, platform or risk-coverage rows without a summary row.
- `score_info.json` `methods` that disagree with the summary rows.
- An empty `protein_agreement.csv` when the check is declared run.

An expected method with no row (e.g. B:M6) is still listed, with the explicit value `missing`.

## Value handling (re-formatting only; no metric is computed)

| Recorded value | Rendering |
|---|---|
| NaN, empty, ±inf | `undef.` |
| Absent row or column | `missing` |
| Empty `tau_err`, and NaN OP-err metrics of that arm/method | `not attainable` (protocol Sect. 5) |
| `tau_cov = -inf` | `-inf (all eligible accepted)`, shown next to the recorded validation cap |
| CI `"[lo, hi]"` with NaN | `[undef., …]` |

- Numbers are fixed-precision: 3 decimals for metrics and 4 for thresholds. Counts are exact integers; a non-integer count fails.
- All text identities (study, platform, file, comparator, report text) are LaTeX-escaped.
- No derived quantities are added. For example, "unassigned fraction" (1 − coverage) is not tabulated because it is not a recorded column.

## Outputs (fixed list = `paper/artifacts.json`)

- **`paper/generated/asset_preamble.tex`** (`\input` in the preamble). It loads `booktabs`/`graphicx` and defines `\ctres{group}{id}{metric}` and `\ctci{…}`. An undefined key is a LaTeX error, never a silent blank.
- **`paper/generated/results_macros.tex`.** One macro per recorded value, each preceded by a comment showing the exact call. Key mapping: `@`→`-at-`, `_`→`-`, `:`→`-`. Examples:
  - `\ctres{A}{M4}{coverage-at-OPcov}`, `\ctci{A}{M4}{coverage-at-OPcov}`;
  - `\ctres{A}{M4}{val-tau-cov}`;
  - `\ctres{B}{M1}{diff-vs-B-M4-macro-f1-closed}`;
  - `\ctres{protein-<file>}{A-M4}{agreement-accepted}`;
  - `\ctres{protein}{check}{status}`;
  - `\ctres{comparison}{report}{overall}`;
  - `\ctres{score}{info}{reps}`.
- **Tables** (bare `tabular` fragments with notes; the author supplies float, caption and label):
  - thresholds;
  - operating points;
  - closed set;
  - practical labels;
  - unknowns;
  - unknowns all-strata (secondary);
  - paired differences;
  - calibration (M1–M3 marked "uncalibrated score");
  - per study;
  - platform;
  - cell counts;
  - bootstrap NaN replicates;
  - protein;
  - reproduction.
- **Figures** (`paper/figures/*.pdf`):
  - operating points;
  - risk–coverage;
  - paired differences (forest);
  - unknown false acceptance;
  - protein agreement. When the check was not run, this figure is an explicit "Protein check not run" panel.
- **`paper/generated/asset_provenance.json`.** Contains generator and `result_manifest.py` sha256, the contract sha256 and check flag, Python/matplotlib/numpy versions, options, every input (path, sha256, bytes, or absent), and every output's sha256. It has no timestamps or absolute paths.

**Tracks.** The matched track (Arm A, Arm B) and the practical track (P1/P2) are separate table blocks and separate figure panels. Practical markers are hollow and practical curves are dashed. Practical paired rows keep their recorded comparator `A:M4`, with a note that they do not isolate architecture (protocol Sect. 1).

**Uncertainty** is drawn only from recorded intervals: the `*_ci95` summary columns and the paired `ci95_lo/hi`. Intervals are drawn literally from lo to hi, never re-centred on the point. Per-study, platform, risk–coverage, OP-err unknown and protein values have no recorded interval, and none is drawn.

**Protein.** Every protein asset carries `result_manifest.PROTEIN_LABEL` ("descriptive; replacement inputs (amendment …)"). Results are per file, with no pooling and no interval. With `--eligibility`, the first failing criterion of each ineligible file is listed. Without an eligibility record, the not-run reason states only that the caller declared it not run.

**Determinism.** The PDFs are written with CreationDate, ModDate, Producer and Creator removed. Identical inputs give byte-identical outputs, both across two roots and on a rerun in place (tested on one machine; cross-machine identity not tested). If `MPLCONFIGDIR` is unset, it defaults to `<root>/.cache-study/mpl`.

## Validation performed (observed)

1. `sh tests_paper_assets/run_tests.sh <main checkout>/.venv/bin/python` (Python 3.11.13, matplotlib 3.9.2, numpy 1.26.4; used read-only): **Ran 35 tests, OK.** Coverage:
   - escaping and number/flag formatting;
   - known values (0.91234→`0.912`; CI `[0.8506, 0.95049]`→`[0.851, 0.950]`; `-0.0123`→`$-$0.012`; `1234`→`1{,}234`);
   - not attainable, `-inf`, NaN;
   - track order and identities;
   - provenance hashes against the bytes on disk;
   - byte-identical determinism;
   - protein not run, no comparison, absent optional files;
   - eligibility consistent, contradictory and tampered;
   - path, symlink and output escape;
   - missing required input, duplicate rows, unknown arm, `score_info` mismatch, wrong report schema, contract mismatch, empty protein table.
2. **LaTeX smoke compile** (inside the tests): a local TeX Live `xelatex` (offline, `-no-shell-escape`) compiled a document that inputs every table, every figure and the macros. An undefined `\ctres` key raised an error, as designed. This is **not** the pinned Tectonic build: Tectonic and its web bundle are not installed in this worktree, and fetching them would need network access.
3. **CLI end to end**, as `reproduce.py` invokes it, on a fixture root: exit 0 with 22 assets. `--comparison /etc/hosts` gives exit 2 ("outside --root"). The `build_paper.py` artifact-path checks pass for all 22 contract entries.
4. `~/.matplotlib` was not modified, and no files outside the owned paths were written. The tests write only to `tests_paper_assets/_tmp`, which is removed after validation.

`scripts/build_paper.py` itself was not run, because `paper/main.tex` and `paper/references.bib` do not exist yet.

## Open items for the coordinator (not changed here; outside owned paths)

1. **`.gitignore` gap.** It ignores `paper/generated/*.tex` and `paper/figures/*.pdf`, but not `paper/generated/asset_provenance.json`. After a run, that file will appear untracked.
2. **No eligibility record in Mode F.** `reproduce.py` does not pass `--eligibility`. In Mode F, the protein not-run reason will therefore be the generic "declared not run by the caller" rather than the eligibility record's reason and failing criteria. If wanted, `reproduce.py` could append `--eligibility <ci>/eligibility.json` when amended.
3. **Not generated:**
   - per-class recall/precision (`per_class_test.csv`);
   - per-class unknowns (`unknowns_test.csv`);
   - reliability plots (`calibration_test.csv` `reliability`);
   - a platform figure;
   - runtime/peak memory (protocol Sect. 6), which is not in the score outputs;
   - the realised mapping-coverage percentages for amendment disclosure item 4, which come from E3 `mapping_<name>.json`.

   These can be added if the author needs them.
4. **Not real-data tested.** The generator has not been run on real recorded outputs. Its first real use will test column-schema assumptions against the actual `score_all.py` output; any mismatch fails closed with exit 2.

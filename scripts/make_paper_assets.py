#!/usr/bin/env python3
"""Deterministic paper assets (LaTeX tables, figures, scalar macros) from recorded score outputs.

  make_paper_assets.py --score SCORE_DIR (--protein PROTEIN_DIR | --protein-not-run)
                       (--comparison REPORT.json | --no-comparison) --output ROOT/paper
                       [--root ROOT] [--eligibility R4P_DIR/eligibility.json]

* Every input is named on the command line. Nothing is discovered (no globbing, no "newest run"):
  fixed file names are read inside the given directories, and every resolved path (symlinks followed)
  must lie inside ``--root`` (default: this repository). The output directory must also lie inside it.
* Each input file is read once; its sha256 and byte count are recorded in
  ``<output>/generated/asset_provenance.json`` together with the generator hash and library versions.
  No timestamps or absolute paths are written, so identical inputs give byte-identical outputs.
* Values are only re-formatted, never computed: undefined values (NaN/empty/inf in the recorded CSVs) are
  shown as "undef.", absent rows/columns as "missing", an unattainable OP-err as "not attainable", and
  ``tau_cov = -inf`` (validation cap below 90%) as "-inf (all eligible accepted)" with the recorded cap.
* Uncertainty is drawn only from recorded intervals (``*_ci95`` columns and paired ``ci95_lo/hi``).
  Per-study, platform, risk-coverage and protein values have no recorded interval and none is drawn.
* Matched track (Arms A and B) and practical track (released models P1/P2) are kept in separate table
  blocks and figure panels; practical markers are hollow.
* Protein check: ``--protein-not-run`` yields explicit "not run" assets (same file list).
  With ``--eligibility`` the hashed eligibility record is parsed by ``result_manifest.parse_eligibility``
  and must agree with the protein option (0 eligible <=> not run).

The set of generated files is fixed and must equal ``paper/artifacts.json`` "generated_inputs"
(checked whenever ``--output`` is ``<root>/paper``), which ``scripts/build_paper.py`` requires.
Exit status: 0 success, 2 input/contract error (nothing is written into generated/ or figures/).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import platform
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
import result_manifest as RM  # noqa: E402  (stdlib only; shared CSV value semantics)

CONTRACT = "paper/artifacts.json"
SCHEMA = "celltransfer-paper-assets/1"
REPORT_SCHEMA = "celltransfer-compare-report/1"

TABLES = (
    "table_thresholds.tex", "table_operating_points.tex", "table_closed_set.tex", "table_practical_labels.tex",
    "table_unknowns.tex", "table_unknowns_allstrata.tex", "table_paired_differences.tex",
    "table_calibration.tex", "table_per_study.tex", "table_platform.tex", "table_cell_counts.tex",
    "table_bootstrap_nan.tex", "table_protein.tex", "table_reproduction.tex",
)
FIGURES = ("fig_operating_points.pdf", "fig_risk_coverage.pdf", "fig_paired_differences.pdf",
           "fig_unknowns.pdf", "fig_protein.pdf")
GENERATED = ("asset_preamble.tex", "results_macros.tex") + TABLES + ("asset_provenance.json",)


def expected_inputs() -> list[str]:
    return [f"paper/generated/{n}" for n in GENERATED] + [f"paper/figures/{n}" for n in FIGURES]


# arm identity -> (track, display label); order is the display order
ARMS = (("A", "matched", "Matched track, Arm A (full reference)"),
        ("B", "matched", "Matched track, Arm B (pDC, ASC, MAIT removed)"),
        ("practical", "practical", "Practical track (released models; scored on Arm A classes)"))
ARM_LABEL = {a: lab for a, _, lab in ARMS}
TRACK = {a: t for a, t, _ in ARMS}
EXPECTED_METHODS = {"A": ("M1", "M2", "M3", "M4", "M5", "M6"), "B": ("M1", "M2", "M3", "M4", "M5", "M6"),
                    "practical": ("P1", "P2")}
UNCALIBRATED = ("M1", "M2", "M3")  # protocol Sect.~6: scores labelled uncalibrated
PAIRED_METRICS = ("coverage@OPcov", "accepted_error@OPcov", "coverage@OPerr", "accepted_error@OPerr",
                  "macro_f1_closed", "unknown_false_accept@OPcov", "cross_lineage_rate@OPcov")
SCORE_REQUIRED = ("summary_test.csv", "paired_differences_vs_M4.csv", "thresholds_validation.csv",
                  "calibration_test.csv", "per_study_test.csv", "risk_coverage_test.csv", "platform.csv",
                  "cell_counts.csv", "score_info.json")
SCORE_OPTIONAL = ("bootstrap_nan_counts.csv", "unknowns_allstrata_secondary.csv", "scoring_scope.json")
PROTEIN_REQUIRED = ("protein_agreement.csv",)
PROTEIN_OPTIONAL = ("gates.json",)


class AssetError(RuntimeError):
    pass


# ============================================================================ values
class _Flag:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return self.name


MISSING = _Flag("MISSING")      # row or column absent from the recorded output
UNDEF = _Flag("UNDEF")          # recorded but undefined (NaN / empty / +-inf other than tau_cov)
NOTATT = _Flag("NOTATT")        # OP-err threshold not attainable on validation
NEGINF = _Flag("NEGINF")        # tau_cov = -inf: cap below the 90% target, all eligible accepted


def value(row, col):
    """Parsed scalar: number, str, or one of the explicit flags."""
    if row is None or col not in row or row[col] is None:
        return MISSING
    raw = str(row[col]).strip()
    if raw.lower() in ("-inf", "-infinity"):
        return NEGINF
    v = RM._num(raw)
    return UNDEF if v is None else v


def ci(row, col):
    """Recorded 95% interval for ``col`` (``<col>_ci95``): (lo, hi) numbers/flags, or MISSING."""
    c = col + "_ci95"
    if row is None or c not in row:
        return MISSING
    raw = str(row[c]).strip()
    pair = RM._ci(raw)
    if pair is None:
        return UNDEF
    return tuple(UNDEF if x is None else x for x in pair)


def is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


# ============================================================================ LaTeX formatting
_TEX = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
        "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
        "<": r"\textless{}", ">": r"\textgreater{}", "|": r"\textbar{}"}


def tex(s) -> str:
    return "".join(_TEX.get(ch, ch) for ch in str(s))


FLAG_TEX = {MISSING: r"\textit{missing}", UNDEF: r"\textit{undef.}", NOTATT: r"\textit{not attainable}",
            NEGINF: r"$-\infty$ (all eligible accepted)"}


def num(v, digits=3, count=False) -> str:
    if isinstance(v, _Flag):
        return FLAG_TEX[v]
    if isinstance(v, str):
        return tex(v)
    if count:
        if isinstance(v, float) and not v.is_integer():
            raise AssetError(f"count value is not an integer: {v!r}")
        return f"{int(v):,}".replace(",", "{,}")
    s = f"{float(v):.{digits}f}"
    return s.replace("-", "$-$", 1) if s.startswith("-") else s


def interval(c, digits=3) -> str:
    if isinstance(c, _Flag):
        return r"[\textit{missing}]" if c is MISSING else r"[\textit{undef.}]"
    lo, hi = c
    return f"[{num(lo, digits)}, {num(hi, digits)}]"


FLAG_TXT = {MISSING: "missing", UNDEF: "undef.", NOTATT: "not attainable", NEGINF: "-inf"}

NOTE = (r"\textit{undef.}: recorded value undefined (NaN/empty); \textit{missing}: absent from the recorded "
        r"output; \textit{not attainable}: no validation threshold with accepted error $\le$5\%.")


def tabular(colspec: str, header: list[str], blocks: list[tuple[str | None, list[list[str]]]], notes: list[str]) -> str:
    ncol = len(header)
    out = ["% Generated by scripts/make_paper_assets.py from recorded outputs; do not edit by hand.",
           f"\\begin{{tabular}}{{{colspec}}}", r"\toprule", " & ".join(header) + r" \\", r"\midrule"]
    for i, (title, rows) in enumerate(blocks):
        if i:
            out.append(r"\midrule")
        if title:
            out.append(f"\\multicolumn{{{ncol}}}{{l}}{{\\textbf{{{tex(title)}}}}} \\\\")
        for r in rows:
            if len(r) != ncol:
                raise AssetError(f"internal: row width {len(r)} != {ncol}")
            out.append(" & ".join(r) + r" \\")
    out.append(r"\bottomrule")
    for n in notes:
        out.append(f"\\multicolumn{{{ncol}}}{{p{{0.95\\linewidth}}}}{{\\footnotesize {n}}} \\\\")
    out.append(r"\end{tabular}")
    return "\n".join(out) + "\n"


# ============================================================================ inputs
class Inputs:
    """Reads named files once, inside --root only, recording sha256/bytes for provenance."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.records: list[dict] = []

    def inside(self, p: Path, what: str) -> Path:
        r = Path(p).resolve()
        if not r.is_relative_to(self.root):
            raise AssetError(f"{what} {p} resolves outside --root {self.root}")
        return r

    def read(self, d: Path, name: str, role: str, required: bool) -> bytes | None:
        p = Path(d) / name
        if not p.exists():
            if required:
                raise AssetError(f"required input missing: {p}")
            self.records.append({"role": role, "path": None, "file": name, "status": "absent (optional)"})
            return None
        r = self.inside(p, "input")
        if not r.is_file():
            raise AssetError(f"input is not a file: {p}")
        b = r.read_bytes()
        self.records.append({"role": role, "path": r.relative_to(self.root).as_posix(), "file": name,
                             "status": "read", "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()})
        return b


def rows_of(b: bytes, name: str, key: tuple[str, ...]) -> list[dict]:
    rows = list(csv.DictReader(io.StringIO(b.decode("utf-8"))))
    if rows:
        absent = [k for k in key if k not in rows[0]]
        if absent:
            raise AssetError(f"{name}: identity column(s) {absent} absent")
    return rows


def index(rows: list[dict], key: tuple[str, ...], name: str) -> dict:
    out = {}
    for r in rows:
        k = tuple(str(r[c]) for c in key)
        if k in out:
            raise AssetError(f"{name}: duplicate row for {dict(zip(key, k))}")
        out[k] = r
    return out


def method_order(arm: str, present) -> list[str]:
    exp = list(EXPECTED_METHODS[arm])
    return exp + sorted(m for m in present if m not in exp)


def check_arms(keys, name: str):
    bad = sorted({k[0] for k in keys if k[0] not in ARM_LABEL})
    if bad:
        raise AssetError(f"{name}: unrecognised arm identities {bad} (expected {list(ARM_LABEL)})")


# ============================================================================ study model
class Study:
    def __init__(self, inp: Inputs, score: Path, protein: Path | None, comparison: Path | None,
                 eligibility: Path | None):
        g = lambda n, req=True: inp.read(score, n, "score", req)  # noqa: E731
        self.summary_rows = rows_of(g("summary_test.csv"), "summary_test.csv", ("arm", "method"))
        self.summary = index(self.summary_rows, ("arm", "method"), "summary_test.csv")
        if not self.summary:
            raise AssetError("summary_test.csv has no rows")
        check_arms(self.summary, "summary_test.csv")
        self.thr = index(rows_of(g("thresholds_validation.csv"), "thresholds_validation.csv", ("arm", "method")),
                         ("arm", "method"), "thresholds_validation.csv")
        check_arms(self.thr, "thresholds_validation.csv")
        if set(self.thr) != set(self.summary):
            raise AssetError(f"arm/method sets differ: thresholds {sorted(self.thr)} vs summary {sorted(self.summary)}")
        pk = ("arm", "method", "vs", "metric")
        self.paired = index(rows_of(g("paired_differences_vs_M4.csv"), "paired_differences_vs_M4.csv", pk), pk,
                            "paired_differences_vs_M4.csv")
        check_arms(self.paired, "paired_differences_vs_M4.csv")
        for k in self.paired:
            if k[:2] not in self.summary:
                raise AssetError(f"paired difference row {k} has no summary row")
        self.calib = index(rows_of(g("calibration_test.csv"), "calibration_test.csv", ("arm", "method")),
                           ("arm", "method"), "calibration_test.csv")
        check_arms(self.calib, "calibration_test.csv")
        sk = ("arm", "method", "study")
        self.per_study = index(rows_of(g("per_study_test.csv"), "per_study_test.csv", sk), sk, "per_study_test.csv")
        self.rc = rows_of(g("risk_coverage_test.csv"), "risk_coverage_test.csv", ("arm", "method", "coverage", "risk"))
        plk = ("arm", "method", "platform")
        self.platform = index(rows_of(g("platform.csv"), "platform.csv", plk), plk, "platform.csv")
        ck = ("role", "study", "stratum", "label_status")
        self.counts = index(rows_of(g("cell_counts.csv"), "cell_counts.csv", ck + ("cells",)), ck, "cell_counts.csv")
        self.info = json.loads(g("score_info.json").decode())
        methods = self.info.get("methods")
        if methods is not None and sorted(methods) != sorted(f"{a}:{m}" for a, m in self.summary):
            raise AssetError(f"score_info.json methods {sorted(methods)} != summary rows {sorted(self.summary)}")
        for name, keys in (("calibration_test.csv", self.calib), ("per_study_test.csv", self.per_study),
                           ("platform.csv", self.platform),
                           ("risk_coverage_test.csv", {(r["arm"], r["method"]) for r in self.rc})):
            orphan = sorted({tuple(k[:2]) for k in keys} - set(self.summary))
            if orphan:
                raise AssetError(f"{name}: arm/method rows {orphan} have no summary_test.csv row")
        b = g("bootstrap_nan_counts.csv", False)
        self.nan_counts = None if b is None else rows_of(b, "bootstrap_nan_counts.csv", ("arm", "method", "metric"))
        b = g("unknowns_allstrata_secondary.csv", False)
        self.secondary = None if b is None else index(
            rows_of(b, "unknowns_allstrata_secondary.csv", ("arm", "method")), ("arm", "method"),
            "unknowns_allstrata_secondary.csv")
        b = g("scoring_scope.json", False)
        self.scope = None if b is None else json.loads(b.decode())

        # protein
        self.protein_status = "not_run" if protein is None else "run"
        self.protein = None
        self.gates = None
        if protein is not None:
            pk = ("file", "arm", "method")
            self.protein = index(rows_of(inp.read(protein, "protein_agreement.csv", "protein", True),
                                         "protein_agreement.csv", pk), pk, "protein_agreement.csv")
            if not self.protein:
                raise AssetError("protein_agreement.csv has no rows although the protein check is declared run")
            check_arms({k[1:] for k in self.protein}, "protein_agreement.csv")
            b = inp.read(protein, "gates.json", "protein", False)
            self.gates = None if b is None else json.loads(b.decode())
        self.eligibility = None
        if eligibility is not None:
            p = inp.inside(eligibility, "eligibility")
            inp.read(p.parent, p.name, "eligibility", True)
            inp.read(p.parent, p.name + ".sha256", "eligibility", True)
            try:
                elig = RM.parse_eligibility(p)
                summ = RM.protein_check_summary(elig, protein)
            except RM.ManifestError as e:
                raise AssetError(f"eligibility: {e}") from e
            self.eligibility = {"verdicts": elig["verdicts"], "n_eligible": elig["n_eligible"],
                                "first_failing_criterion": elig["first_failing_criterion"], "summary": summ}
            if self.protein is not None:
                files = sorted({k[0] for k in self.protein})
                if files != sorted(elig["eligible"]):
                    raise AssetError(f"protein files {files} != eligible files {sorted(elig['eligible'])}")

        # comparison
        self.comparison = None
        if comparison is not None:
            p = inp.inside(comparison, "comparison report")
            rep = json.loads(inp.read(p.parent, p.name, "comparison", True).decode())
            if rep.get("schema") != REPORT_SCHEMA:
                raise AssetError(f"comparison report schema {rep.get('schema')!r} != {REPORT_SCHEMA!r}")
            if "overall" not in rep or "per_arm_method" not in rep:
                raise AssetError("comparison report lacks 'overall' or 'per_arm_method'")
            self.comparison = rep

    # helpers
    def not_run_reason(self) -> str:
        if self.eligibility is not None:
            return str(self.eligibility["summary"]["reason"])
        return "declared not run by the caller (--protein-not-run); no eligibility record supplied"

    def arms_present(self):
        return [a for a, _, _ in ARMS if any(k[0] == a for k in self.summary)]

    def methods(self, arm):
        return method_order(arm, {k[1] for k in self.summary if k[0] == arm})

    def opq(self, arm, mid, metric, v):
        """Replace UNDEF by NOTATT for OP-err metrics when tau_err is recorded as not attainable."""
        if v is UNDEF and "OPerr" in metric and value(self.thr.get((arm, mid)), "tau_err") is UNDEF:
            return NOTATT
        return v


# ============================================================================ tables
def ident(arm, mid):
    return tex(mid)


def table_thresholds(S: Study) -> str:
    cols = ("tau_cov", "eligible_cap_validation", "validation_coverage_at_tau_cov",
            "validation_error_at_tau_cov", "tau_err", "validation_cells")
    hdr = ["Method", r"$\tau_\mathrm{cov}$", "Val.\\ cap", "Val.\\ cov.\\ at $\\tau_\\mathrm{cov}$",
           "Val.\\ error at $\\tau_\\mathrm{cov}$", r"$\tau_\mathrm{err}$", "Val.\\ cells"]
    blocks = []
    for a in S.arms_present():
        rows = []
        for m in S.methods(a):
            r = S.thr.get((a, m))
            vals = []
            for c in cols:
                v = value(r, c)
                if c == "tau_err" and v is UNDEF:
                    v = NOTATT
                vals.append(num(v, 4 if c.startswith("tau") else 3, count=(c == "validation_cells")))
            rows.append([ident(a, m)] + vals)
        blocks.append((ARM_LABEL[a], rows))
    return tabular("l" + "r" * 6, hdr, blocks, [
        "Validation-only operating points (protocol Sect.~5). $-\\infty$: validation cap below the 90\\% coverage "
        "target, all eligible predictions accepted; the recorded cap is shown.", NOTE])


def stacked(S, metrics, digits=3, counts=(), with_ci=True):
    blocks = []
    for a in S.arms_present():
        rows = []
        for m in S.methods(a):
            r = S.summary.get((a, m))
            top = [ident(a, m)]
            bot = [""]
            for c in metrics:
                top.append(num(S.opq(a, m, c, value(r, c)), digits, count=c in counts))
                recorded = with_ci and r is not None and (c + "_ci95") in r
                bot.append(r"{\scriptsize " + interval(ci(r, c), digits) + "}" if recorded else "")
            rows.append(top)
            if any(bot[1:]):
                rows.append(bot)
        blocks.append((ARM_LABEL[a], rows))
    return blocks


def table_operating_points(S: Study) -> str:
    mets = ("coverage@OPcov", "accepted_error@OPcov", "coverage@OPerr", "accepted_error@OPerr", "test_scorable_natural")
    hdr = ["Method", "Coverage (OP-cov)", "Accepted error (OP-cov)", "Coverage (OP-err)",
           "Accepted error (OP-err)", "Scorable cells"]
    return tabular("l" + "r" * 5, hdr, stacked(S, mets, counts=("test_scorable_natural",)), [
        "Test set, natural stratum, scorable cells. Brackets: recorded 95\\% donor-cluster bootstrap "
        "percentile interval (score\\_all.py, 1{,}000 replicates when run as specified).", NOTE])


def table_closed_set(S: Study) -> str:
    mets = ("macro_f1_closed", "f1_classes", "aurc", "max_coverage", "cross_lineage_rate@OPcov",
            "cross_lineage_share@OPcov")
    hdr = ["Method", "Macro-F1 (closed)", "F1 classes", "AURC", "Max.\\ coverage", "Cross-lineage rate (OP-cov)",
           "Cross-lineage share (OP-cov)"]
    return tabular("l" + "r" * 6, hdr, stacked(S, mets, counts=("f1_classes",)), [
        "Brackets: recorded 95\\% bootstrap interval where score\\_all.py records one.", NOTE])


def table_practical_labels(S: Study) -> str:
    mets = ("coarser_fraction", "outside_fraction", "lineage_agreement_closed")
    hdr = ["Method", "Coarser fraction", "Outside fraction", "Lineage agreement"]
    rows = []
    for m in S.methods("practical") if "practical" in S.arms_present() else []:
        r = S.summary.get(("practical", m))
        rows.append([ident("practical", m)] + [num(value(r, c)) for c in mets])
    if not rows:
        rows = [[r"\textit{no practical-track rows in summary\_test.csv}", "", "", ""]]
    return tabular("lrrr", hdr, [(ARM_LABEL["practical"], rows)], [
        "Practical track only (protocol Sect.~6); point estimates, no interval recorded.", NOTE])


def table_unknowns(S: Study) -> str:
    hdr = ["Method", "Unknown kind", "Unknown cells", "False accept (OP-cov)", "False accept (OP-err)", "AUROC"]
    blocks = []
    for a in S.arms_present():
        rows = []
        for m in S.methods(a):
            r = S.summary.get((a, m))
            rows.append([ident(a, m), num(value(r, "unknown_kind")), num(value(r, "unknown_cells"), count=True),
                         num(value(r, "unknown_false_accept@OPcov")),
                         num(S.opq(a, m, "unknown_false_accept@OPerr", value(r, "unknown_false_accept@OPerr"))),
                         num(value(r, "unknown_auroc"))])
            if r is not None and "unknown_false_accept@OPcov_ci95" in r:
                rows.append(["", "", "", r"{\scriptsize " + interval(ci(r, "unknown_false_accept@OPcov")) + "}", "", ""])
        blocks.append((ARM_LABEL[a], rows))
    scope = S.scope.get("natural_unknown_scope") if isinstance(S.scope, dict) else None
    sn = (f"Natural-unknown scope recorded in scoring\\_scope.json: {tex(scope)}." if scope is not None
          else "Natural-unknown scope: \\textit{missing} (scoring\\_scope.json not supplied).")
    return tabular("llrrrr", hdr, blocks, [
        "Natural unknowns (Arm A, practical) and simulated unknowns (Arm B) are reported separately. "
        "Brackets: recorded 95\\% bootstrap interval (OP-cov only). " + sn, NOTE])


def table_unknowns_allstrata(S: Study) -> str:
    hdr = ["Method", "Unknown cells", "False accept (OP-cov)", "False accept (OP-err)", "AUROC"]
    if S.secondary is None:
        return tabular("lrrrr", hdr, [(None, [[r"\textit{not available: unknowns\_allstrata\_secondary.csv "
                                                r"not in the supplied score outputs}", "", "", "", ""]])], [])
    check_arms(S.secondary, "unknowns_allstrata_secondary.csv")
    blocks = []
    for a in [a for a, _, _ in ARMS if any(k[0] == a for k in S.secondary)]:
        rows = []
        for m in method_order(a, {k[1] for k in S.secondary if k[0] == a}):
            r = S.secondary.get((a, m))
            rows.append([ident(a, m), num(value(r, "unknown_cells"), count=True),
                         num(value(r, "unknown_false_accept@OPcov")),
                         num(S.opq(a, m, "x@OPerr", value(r, "unknown_false_accept@OPerr"))),
                         num(value(r, "unknown_auroc"))])
        blocks.append((ARM_LABEL[a], rows))
    return tabular("lrrrr", hdr, blocks, [
        "Secondary pre-specified sensitivity analysis: all strata including rare top-up cells; point estimates "
        "only.", NOTE])


def paired_metrics(S: Study):
    present = {k[3] for k in S.paired}
    return list(PAIRED_METRICS) + sorted(present - set(PAIRED_METRICS))


def table_paired(S: Study) -> str:
    mets = paired_metrics(S)
    hdr = ["Method", "vs"] + [tex(m).replace("@", " @ ") for m in mets]
    blocks = []
    for a in S.arms_present():
        rows = []
        keys = sorted({(k[1], k[2]) for k in S.paired if k[0] == a},
                      key=lambda t: (method_order(a, [t[0]]).index(t[0]), t[1]))
        for m, vs in keys:
            top, bot = [ident(a, m), tex(vs)], ["", ""]
            for met in mets:
                r = S.paired.get((a, m, vs, met))
                top.append(num(S.opq(a, m, met, value(r, "mean_diff"))))
                lo, hi = value(r, "ci95_lo"), value(r, "ci95_hi")
                bot.append(r"{\scriptsize " + interval(MISSING if r is None else (lo, hi)) + "}")
            rows += [top, bot]
        if rows:
            blocks.append((ARM_LABEL[a], rows))
    if not blocks:
        blocks = [(None, [[r"\textit{no rows in paired\_differences\_vs\_M4.csv}"] + [""] * (len(hdr) - 1)])]
    return tabular("ll" + "r" * len(mets), hdr, blocks, [
        "Mean of replicate-paired bootstrap differences (method minus comparator) with recorded 95\\% "
        "percentile interval. Practical-track rows are compared with Arm A M4 and do not isolate architecture "
        "(protocol Sect.~1).", NOTE])


def table_calibration(S: Study) -> str:
    hdr = ["Method", "Brier", "ECE (15 bins)", "Score type"]
    blocks = []
    for a in S.arms_present():
        rows = []
        for m in S.methods(a):
            r = S.calib.get((a, m))
            kind = "uncalibrated score" if m in UNCALIBRATED else "probability"
            rows.append([ident(a, m), num(value(r, "brier")), num(value(r, "ece")), kind])
        blocks.append((ARM_LABEL[a], rows))
    return tabular("lrrl", hdr, blocks, [
        "M1--M3 confidence scores are labelled uncalibrated (protocol Sect.~6); their values are shown as recorded.",
        NOTE])


def table_per_study(S: Study) -> str:
    hdr = ["Method", "Study", "Cells", "Macro-F1", "Coverage (OP-cov)", "Accepted error (OP-cov)",
           "Coverage (OP-err)", "Accepted error (OP-err)"]
    cols = ("macro_f1_closed", "coverage@OPcov", "accepted_error@OPcov", "coverage@OPerr", "accepted_error@OPerr")
    check_arms(S.per_study, "per_study_test.csv")
    blocks = []
    for a in S.arms_present():
        rows = []
        for m in S.methods(a):
            studies = sorted(k[2] for k in S.per_study if k[0] == a and k[1] == m)
            if not studies:
                rows.append([ident(a, m), r"\textit{missing}"] + [""] * 6)
            for s in studies:
                r = S.per_study[(a, m, s)]
                rows.append([ident(a, m), tex(s), num(value(r, "cells"), count=True)]
                            + [num(S.opq(a, m, c, value(r, c))) for c in cols])
        blocks.append((ARM_LABEL[a], rows))
    return tabular("ll" + "r" * 6, hdr, blocks, [
        "Per held-out test study, natural stratum; no study-level interval (four test studies, protocol Sect.~6).", NOTE])


def table_platform(S: Study) -> str:
    hdr = ["Method", "Platform dataset", "Assay", "Cells", "Coverage (OP-cov)", "Accepted error (OP-cov)",
           "Closed-set accuracy"]
    check_arms(S.platform, "platform.csv")
    blocks = []
    for a in S.arms_present():
        rows = []
        for m in S.methods(a):
            for p in sorted(k[2] for k in S.platform if k[0] == a and k[1] == m):
                r = S.platform[(a, m, p)]
                rows.append([ident(a, m), tex(p), num(value(r, "assay")), num(value(r, "cells"), count=True),
                             num(value(r, "coverage")), num(value(r, "accepted_error")),
                             num(value(r, "closed_set_accuracy"))])
        if rows:
            blocks.append((ARM_LABEL[a], rows))
    if not blocks:
        blocks = [(None, [[r"\textit{no rows in platform.csv}"] + [""] * 6])]
    return tabular("lllrrrr", hdr, blocks, [
        "Descriptive platform comparison (one donor; protocol Sect.~7); no interval.", NOTE])


def table_cell_counts(S: Study) -> str:
    hdr = ["Role", "Study", "Stratum", "Label status", "Cells"]
    rows = [[tex(k[0]), tex(k[1]), tex(k[2]), tex(k[3]), num(value(S.counts[k], "cells"), count=True)]
            for k in sorted(S.counts)]
    extra = []
    for k in ("reps", "seed", "test_donors"):
        v = S.info.get(k, MISSING)
        extra.append(f"{tex(k)} = {num(v, count=True) if is_num(v) else num(v)}")
    return tabular("llllr", hdr, [(None, rows)], [
        "Sampled cells per role, study, stratum and label status (cell\\_counts.csv). score\\_info.json: "
        + "; ".join(extra) + ". Cells are never the unit of uncertainty."])


def table_bootstrap_nan(S: Study) -> str:
    hdr = ["Arm", "Method", "Metric", "NaN replicates"]
    if S.nan_counts is None:
        return tabular("lllr", hdr, [(None, [[r"\textit{not available: bootstrap\_nan\_counts.csv not in the "
                                              r"supplied score outputs}", "", "", ""]])], [])
    nz = [r for r in S.nan_counts if not (is_num(value(r, "nan_replicates")) and value(r, "nan_replicates") == 0)]
    reps = S.info.get("reps")
    rows = [[tex(r["arm"]), tex(r["method"]), tex(r["metric"]), num(value(r, "nan_replicates"), count=True)]
            for r in sorted(nz, key=lambda r: (r["arm"], r["method"], r["metric"]))]
    if not rows:
        rows = [[r"\textit{none: every metric defined in every replicate}", "", "", ""]]
    return tabular("lllr", hdr, [(None, rows)], [
        f"Bootstrap replicates with an undefined metric (of {num(reps, count=True) if is_num(reps) else 'missing'} "
        "replicates); intervals use the defined replicates (nanpercentile). Rows with zero omitted."])


def table_protein(S: Study) -> str:
    hdr = ["Method", r"$\tau_\mathrm{cov}$", "Resolved cells", "Accepted among resolved", "Accepted \\& resolved",
           "Agreement", "Agreement (gateable preds)"]
    label = tex(RM.PROTEIN_LABEL)
    if S.protein is None:
        reason = tex(S.not_run_reason())
        lines = [r"\textit{Protein check not run}: " + reason + "."]
        if S.eligibility is not None:
            for n, crit in sorted(S.eligibility["first_failing_criterion"].items()):
                c = crit if isinstance(crit, dict) else {"name": crit}
                lines.append(f"{tex(n)}: ineligible, first failing criterion {tex(c.get('number', ''))} "
                             f"({tex(c.get('name', ''))}).")
        rows = [[ln] + [""] * 6 for ln in lines]
        return tabular("l" + "r" * 6, hdr, [(None, rows)], [f"Status: not run. {label}."])
    blocks = []
    for f in sorted({k[0] for k in S.protein}):
        for a in [a for a, _, _ in ARMS if any(k[0] == f and k[1] == a for k in S.protein)]:
            rows = []
            for m in method_order(a, {k[2] for k in S.protein if k[0] == f and k[1] == a}):
                r = S.protein.get((f, a, m))
                rows.append([ident(a, m), num(value(r, "tau_cov"), 4), num(value(r, "protein_resolved_cells"), count=True),
                             num(value(r, "accepted_among_resolved")), num(value(r, "n_accepted_resolved"), count=True),
                             num(value(r, "agreement_accepted")), num(value(r, "agreement_accepted_gateable_preds"))])
            blocks.append((f"File {f}; {ARM_LABEL[a]}", rows))
    notes = [f"{label}. Per file; no pooling and no interval. Protein gates are a coarse orthogonal check, "
             "not ground truth."]
    if S.eligibility is not None:
        for n, crit in sorted(S.eligibility["first_failing_criterion"].items()):
            c = crit if isinstance(crit, dict) else {"name": crit}
            notes.append(f"{tex(n)}: ineligible, first failing criterion {tex(c.get('number', ''))} "
                         f"({tex(c.get('name', ''))}).")
    notes.append(NOTE)
    return tabular("l" + "r" * 6, hdr, blocks, notes)


def table_reproduction(S: Study) -> str:
    hdr = ["Arm:method", "Outcome", "Gated breaches", "Unsupported"]
    rep = S.comparison
    if rep is None:
        return tabular("llrr", hdr, [(None, [[r"\textit{not available: no comparison report supplied}", "", "", ""]])],
                       ["No tiered reproduction comparison was supplied to the generator."])
    rows = []
    for k in sorted(rep["per_arm_method"]):
        o = rep["per_arm_method"][k]
        rows.append([tex(k), tex(o.get("outcome", "missing")), num(o.get("breaches", MISSING), count=True),
                     num(o.get("unsupported", MISSING), count=True)])
    if not rows:
        rows = [[r"\textit{no per-arm/method outcomes in report}", "", "", ""]]
    notes = [f"Overall: {tex(rep['overall'])}.", f"Protein check: {tex(rep.get('protein_check') or 'not stated')}.",
             f"Result of record: {tex(rep.get('result_of_record', 'missing'))}."]
    if rep.get("m6_only_breach"):
        notes.append(f"M6-only breach wording: {tex(rep.get('m6_only_wording'))}")
    return tabular("llrr", hdr, [(None, rows)], notes)


PREAMBLE = r"""% Generated by scripts/make_paper_assets.py. \input this file in the document preamble.
\usepackage{booktabs}
\usepackage{graphicx}
% Result lookup: \ctres{group}{id}{metric} and \ctci{group}{id}{metric}; see results_macros.tex.
\newcommand{\ctres}[3]{\ifcsname ctv@#1@#2@#3\endcsname\csname ctv@#1@#2@#3\endcsname\else\PackageError{paperassets}{undefined result #1/#2/#3}{Check results_macros.tex}\fi}
\newcommand{\ctci}[3]{\ifcsname ctci@#1@#2@#3\endcsname\csname ctci@#1@#2@#3\endcsname\else\PackageError{paperassets}{undefined interval #1/#2/#3}{Check results_macros.tex}\fi}
"""


def macro_key(s: str) -> str:
    out = str(s).replace("@", "-at-").replace("_", "-").replace(":", "-")
    if not out or any(not (ch.isascii() and (ch.isalnum() or ch in "-.")) for ch in out):
        raise AssetError(f"cannot form a macro key from {s!r}")
    return out


def macros(S: Study) -> str:
    defs: dict[tuple[str, str, str, str], str] = {}

    def put(kind, g, i, m, txt):
        k = (kind, macro_key(g), macro_key(i), macro_key(m))
        if k in defs:
            raise AssetError(f"macro key collision {k}")
        defs[k] = txt

    for (a, m), r in S.summary.items():
        for c in r:
            if c in ("arm", "method") or c is None:
                continue
            if c.endswith("_ci95"):
                put("ctci", a, m, c[:-5], interval(ci(r, c[:-5])))
            else:
                put("ctv", a, m, c, num(S.opq(a, m, c, value(r, c)), 4 if c.startswith("tau") else 3,
                                         count=isinstance(value(r, c), int)))
    for (a, m), r in S.thr.items():
        for c in r:
            if c in ("arm", "method") or c is None:
                continue
            v = value(r, c)
            v = NOTATT if (c == "tau_err" and v is UNDEF) else v
            put("ctv", a, m, "val-" + c, num(v, 4 if c.startswith("tau") else 3, count=isinstance(v, int)))
    for (a, m, vs, met), r in S.paired.items():
        put("ctv", a, m, f"diff-vs-{vs}-{met}", num(S.opq(a, m, met, value(r, "mean_diff"))))
        put("ctci", a, m, f"diff-vs-{vs}-{met}", interval((value(r, "ci95_lo"), value(r, "ci95_hi"))))
    for k in sorted(S.info):
        v = S.info[k]
        if isinstance(v, (int, float, str)) and not isinstance(v, bool):
            put("ctv", "score", "info", k, num(v, count=isinstance(v, int)))
    put("ctv", "protein", "check", "status", "run" if S.protein is not None else "not run")
    if S.protein is not None:
        for (f, a, m), r in S.protein.items():
            for c in r:
                if c in ("file", "arm", "method") or c is None:
                    continue
                v = value(r, c)
                put("ctv", f"protein-{f}", f"{a}-{m}", c, num(v, 4 if c == "tau_cov" else 3, count=isinstance(v, int)))
    if S.comparison is not None:
        put("ctv", "comparison", "report", "overall", tex(S.comparison["overall"]))
    else:
        put("ctv", "comparison", "report", "overall", r"\textit{not available}")
    lines = ["% Generated by scripts/make_paper_assets.py; requires asset_preamble.tex.",
             "% Usage: \\ctres{group}{id}{metric} / \\ctci{group}{id}{metric}; keys: '@'->'-at-', '_'->'-', ':'->'-'.",
             "\\makeatletter"]
    for (kind, g, i, m) in sorted(defs):
        call = "ctres" if kind == "ctv" else "ctci"
        lines.append(f"% \\{call}{{{g}}}{{{i}}}{{{m}}}")
        lines.append(f"\\expandafter\\def\\csname {kind}@{g}@{i}@{m}\\endcsname{{{defs[(kind, g, i, m)]}}}")
    lines.append("\\makeatother")
    return "\n".join(lines) + "\n"


# ============================================================================ figures
def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    matplotlib.rcParams.update({"font.size": 8, "axes.titlesize": 8, "svg.hashsalt": "paper-assets",
                                "pdf.compression": 6, "path.simplify": False})
    return plt


COLORS = {"M1": "#1b9e77", "M2": "#d95f02", "M3": "#7570b3", "M4": "#e7298a", "M5": "#66a61e", "M6": "#e6ab02",
          "P1": "#377eb8", "P2": "#a6761d"}


def panel_title(a):
    return ARM_LABEL[a].replace(" (", "\n(", 1)


def color(m):
    return COLORS.get(m, "#555555")


def marker_kw(arm, shape="o"):
    practical = TRACK.get(arm) == "practical"
    return {"marker": shape, "markersize": 5, "linestyle": "none",
            "markerfacecolor": "white" if practical else None}


def save(fig, path: Path):
    fig.savefig(path, format="pdf", metadata={"CreationDate": None, "ModDate": None, "Producer": None,
                                               "Creator": None})
    import matplotlib.pyplot as plt
    plt.close(fig)


def seg(ax, c, at, axis, col):
    """Draw a recorded interval literally from lo to hi (never re-centred on the point estimate)."""
    if isinstance(c, _Flag) or not (is_num(c[0]) and is_num(c[1])) or not is_num(at):
        return False
    if axis == "x":
        ax.plot([c[0], c[1]], [at, at], color=col, linewidth=0.8, marker="|", markersize=4)
    else:
        ax.plot([at, at], [c[0], c[1]], color=col, linewidth=0.8, marker="_", markersize=4)
    return True


def fig_operating_points(S: Study, path: Path):
    plt = _plt()
    arms = S.arms_present()
    fig, axes = plt.subplots(1, len(arms), figsize=(3.2 * len(arms), 3.6), squeeze=False)
    for ax, a in zip(axes[0], arms):
        skipped = []
        for m in S.methods(a):
            r = S.summary.get((a, m))
            for op, shape in (("cov", "o"), ("err", "s")):
                x, y = value(r, f"coverage@OP{op}"), value(r, f"accepted_error@OP{op}")
                if not (is_num(x) and is_num(y)):
                    why = S.opq(a, m, f"x@OP{op}", x if not is_num(x) else y)
                    skipped.append(f"{m} OP-{op}: {FLAG_TXT.get(why, 'non-numeric')}")
                    continue
                seg(ax, ci(r, f"coverage@OP{op}"), y, "x", color(m))
                seg(ax, ci(r, f"accepted_error@OP{op}"), x, "y", color(m))
                ax.plot([x], [y], color=color(m), label=f"{m} OP-{op}", zorder=3, **marker_kw(a, shape))
        ax.set_title(panel_title(a), fontsize=7)
        ax.set_xlabel("Test coverage")
        ax.set_ylabel("Accepted error")
        ax.grid(alpha=0.3, linewidth=0.5)
        if skipped:
            ax.text(0.01, 0.99, "not plotted:\n" + "\n".join(skipped), transform=ax.transAxes, va="top", fontsize=5)
        h, lab = ax.get_legend_handles_labels()
        if h:
            ax.legend(fontsize=5, ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.22), frameon=False)
    fig.suptitle("Circles OP-cov, squares OP-err; lines: recorded 95% bootstrap intervals (lo to hi); "
                 "hollow: practical track",
                 fontsize=7)
    fig.tight_layout()
    save(fig, path)


def fig_risk_coverage(S: Study, path: Path):
    plt = _plt()
    arms = S.arms_present()
    fig, axes = plt.subplots(1, len(arms), figsize=(3.0 * len(arms), 2.6), squeeze=False)
    curves: dict = {}
    for i, r in enumerate(S.rc):
        if r["arm"] not in ARM_LABEL:
            raise AssetError(f"risk_coverage_test.csv: unrecognised arm {r['arm']!r}")
        x, y = value(r, "coverage"), value(r, "risk")
        if is_num(x) and is_num(y):
            curves.setdefault((r["arm"], r["method"]), []).append((x, y))
    for ax, a in zip(axes[0], arms):
        missing = []
        for m in S.methods(a):
            pts = curves.get((a, m))
            if not pts:
                missing.append(m)
                continue
            ax.plot([p[0] for p in pts], [p[1] for p in pts], color=color(m), linewidth=1,
                    linestyle="--" if TRACK[a] == "practical" else "-", label=m)
        ax.set_title(panel_title(a), fontsize=7)
        ax.set_xlabel("Coverage")
        ax.set_ylabel("Risk (error among accepted)")
        ax.grid(alpha=0.3, linewidth=0.5)
        if missing:
            ax.text(0.01, 0.99, "no curve: " + ", ".join(missing), transform=ax.transAxes, va="top", fontsize=5)
        if ax.get_legend_handles_labels()[0]:
            ax.legend(fontsize=5)
    fig.suptitle("Recorded risk-coverage points (no interval recorded); dashed: practical track", fontsize=7)
    fig.tight_layout()
    save(fig, path)


def fig_paired(S: Study, path: Path):
    plt = _plt()
    mets = paired_metrics(S)
    comps = []
    for a in S.arms_present():
        keys = sorted({(k[1], k[2]) for k in S.paired if k[0] == a}, key=lambda t: (method_order(a, [t[0]]).index(t[0]), t[1]))
        comps += [(a, m, vs) for m, vs in keys]
    ncol = 4
    nrow = max(1, math.ceil(len(mets) / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(10, 0.25 * max(len(comps), 4) * nrow + 1), squeeze=False)
    labels = [f"{a}:{m} vs {vs}" for a, m, vs in comps]
    for j, ax in enumerate(axes.flat):
        if j >= len(mets):
            ax.axis("off")
            continue
        met = mets[j]
        for i, (a, m, vs) in enumerate(comps):
            r = S.paired.get((a, m, vs, met))
            v = value(r, "mean_diff")
            yi = len(comps) - 1 - i
            if not is_num(v):
                ax.text(0.98, yi, FLAG_TXT.get(S.opq(a, m, met, v), "non-numeric"), fontsize=5,
                        va="center", ha="right", transform=ax.get_yaxis_transform())
                continue
            seg(ax, (value(r, "ci95_lo"), value(r, "ci95_hi")), yi, "x", color(m))
            ax.plot([v], [yi], color=color(m), zorder=3, **marker_kw(a))
        ax.axvline(0, color="black", linewidth=0.6)
        for i in range(1, len(comps)):
            if comps[i][0] != comps[i - 1][0]:
                ax.axhline(len(comps) - i - 0.5, color="grey", linewidth=0.5, linestyle=":")
        ax.set_yticks(range(len(comps)))
        ax.set_yticklabels(list(reversed(labels)) if j % ncol == 0 else [], fontsize=5)
        ax.set_ylim(-0.5, max(len(comps), 1) - 0.5)
        ax.set_title(met, fontsize=7)
        ax.grid(alpha=0.3, linewidth=0.5, axis="x")
    fig.suptitle("Paired bootstrap differences vs M4 (mean, recorded 95% interval); hollow: practical vs A:M4",
                 fontsize=7)
    fig.tight_layout()
    save(fig, path)


def fig_unknowns(S: Study, path: Path):
    plt = _plt()
    arms = S.arms_present()
    fig, axes = plt.subplots(1, len(arms), figsize=(3.0 * len(arms), 2.4), squeeze=False)
    for ax, a in zip(axes[0], arms):
        ms = S.methods(a)
        kinds = sorted({str(value(S.summary.get((a, m)), "unknown_kind")) for m in ms})
        for i, m in enumerate(ms):
            r = S.summary.get((a, m))
            for op, dx, shape in (("cov", -0.12, "o"), ("err", 0.12, "s")):
                c = f"unknown_false_accept@OP{op}"
                v = S.opq(a, m, c, value(r, c))
                if not is_num(v):
                    ax.text(i + dx, 0.02, FLAG_TXT.get(v, "non-numeric"), fontsize=5, rotation=90,
                            ha="center", va="bottom")
                    continue
                if op == "cov":
                    seg(ax, ci(r, c), i + dx, "y", color(m))
                ax.plot([i + dx], [v], color=color(m), zorder=3, **marker_kw(a, shape))
        ax.set_xticks(range(len(ms)))
        ax.set_xticklabels(ms)
        ax.set_ylim(0, 1)
        ax.set_ylabel("Unknown false acceptance")
        ax.set_title(f"{panel_title(a)}\nunknown kind: {', '.join(kinds)}", fontsize=6)
        ax.grid(alpha=0.3, linewidth=0.5, axis="y")
    fig.suptitle("Circles OP-cov (bars: recorded 95% interval), squares OP-err (no interval recorded)", fontsize=7)
    fig.tight_layout()
    save(fig, path)


def fig_protein(S: Study, path: Path):
    plt = _plt()
    if S.protein is None:
        fig, ax = plt.subplots(figsize=(4, 1.2))
        ax.axis("off")
        ax.text(0.5, 0.5, "Protein check not run\n(" + S.not_run_reason() + ")", ha="center", va="center",
                fontsize=8, wrap=True)
        save(fig, path)
        return
    files = sorted({k[0] for k in S.protein})
    fig, axes = plt.subplots(1, len(files), figsize=(max(5.5, 3.4 * len(files)), 3.0), squeeze=False)
    for ax, f in zip(axes[0], files):
        ks = [(a, m) for a, _, _ in ARMS for m in method_order(a, {k[2] for k in S.protein if k[0] == f and k[1] == a})
              if (f, a, m) in S.protein]
        for i, (a, m) in enumerate(ks):
            v = value(S.protein[(f, a, m)], "agreement_accepted")
            if not is_num(v):
                ax.text(i, 0.02, "undef.", fontsize=5, rotation=90, ha="center", va="bottom")
                continue
            ax.plot([i], [v], color=color(m), **marker_kw(a))
        ax.set_xticks(range(len(ks)))
        ax.set_xticklabels([f"{a}:{m}" for a, m in ks], rotation=45, fontsize=6)
        ax.set_ylim(0, 1)
        ax.set_ylabel("Agreement with protein class (OP-cov)")
        ax.set_title(f"File {f}", fontsize=7)
        ax.grid(alpha=0.3, linewidth=0.5, axis="y")
    fig.suptitle("Descriptive; replacement inputs; per file, no pooling, no interval\nhollow: practical track",
                 fontsize=7)
    fig.tight_layout()
    save(fig, path)


# ============================================================================ driver
def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def build(args) -> dict:
    root = Path(args.root).resolve()
    if not root.is_dir():
        raise AssetError(f"--root is not a directory: {root}")
    inp = Inputs(root)
    score = inp.inside(args.score, "--score")
    protein = inp.inside(args.protein, "--protein") if args.protein else None
    comparison = inp.inside(args.comparison, "--comparison") if args.comparison else None
    eligibility = inp.inside(args.eligibility, "--eligibility") if args.eligibility else None
    out = Path(args.output).resolve()
    if not out.is_relative_to(root):
        raise AssetError(f"--output {out} is outside --root {root}")
    for d, what in ((score, "--score"), (protein, "--protein")):
        if d is not None and not d.is_dir():
            raise AssetError(f"{what} is not a directory: {d}")

    contract = root / CONTRACT
    contract_checked = False
    contract_sha = None
    if out == (root / "paper").resolve():
        if not contract.is_file():
            raise AssetError(f"{CONTRACT} missing under --root")
        cb = contract.read_bytes()
        c = json.loads(cb)
        if c.get("generated_inputs") != expected_inputs():
            raise AssetError(f"{CONTRACT} generated_inputs differ from the generator's fixed asset list")
        contract_checked, contract_sha = True, sha_bytes(cb)

    mpl_cache = os.environ.get("MPLCONFIGDIR")
    if not mpl_cache:
        os.environ["MPLCONFIGDIR"] = str(root / ".cache-study" / "mpl")
    S = Study(inp, score, protein, comparison, eligibility)

    stage = out / ".paper-assets-staging"
    if stage.exists():
        shutil.rmtree(stage)
    try:
        return _write(S, stage, out, root, inp, protein, comparison, eligibility, contract_checked, contract_sha)
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def _write(S, stage, out, root, inp, protein, comparison, eligibility, contract_checked, contract_sha) -> dict:
    (stage / "generated").mkdir(parents=True)
    (stage / "figures").mkdir(parents=True)
    texts = {"asset_preamble.tex": PREAMBLE, "results_macros.tex": macros(S),
             "table_thresholds.tex": table_thresholds(S), "table_operating_points.tex": table_operating_points(S),
             "table_closed_set.tex": table_closed_set(S), "table_practical_labels.tex": table_practical_labels(S),
             "table_unknowns.tex": table_unknowns(S), "table_unknowns_allstrata.tex": table_unknowns_allstrata(S),
             "table_paired_differences.tex": table_paired(S), "table_calibration.tex": table_calibration(S),
             "table_per_study.tex": table_per_study(S), "table_platform.tex": table_platform(S),
             "table_cell_counts.tex": table_cell_counts(S), "table_bootstrap_nan.tex": table_bootstrap_nan(S),
             "table_protein.tex": table_protein(S), "table_reproduction.tex": table_reproduction(S)}
    for n, t in texts.items():
        (stage / "generated" / n).write_text(t, encoding="utf-8")
    for n, fn in (("fig_operating_points.pdf", fig_operating_points), ("fig_risk_coverage.pdf", fig_risk_coverage),
                  ("fig_paired_differences.pdf", fig_paired), ("fig_unknowns.pdf", fig_unknowns),
                  ("fig_protein.pdf", fig_protein)):
        fn(S, stage / "figures" / n)

    import matplotlib
    import numpy
    outputs = []
    for sub, names in (("generated", GENERATED[:-1]), ("figures", FIGURES)):
        for n in names:
            p = stage / sub / n
            if not p.is_file():
                raise AssetError(f"internal: asset not produced: {sub}/{n}")
            outputs.append({"path": f"{(out / sub / n).relative_to(root).as_posix()}", "sha256": sha_bytes(p.read_bytes())})
    prov = {"schema": SCHEMA,
            "generator": {"path": "scripts/make_paper_assets.py", "sha256": sha_bytes(Path(__file__).read_bytes()),
                          "result_manifest_sha256": sha_bytes((HERE / "result_manifest.py").read_bytes())},
            "contract": {"path": CONTRACT, "checked": contract_checked, "sha256": contract_sha},
            "environment": {"python": platform.python_version(), "matplotlib": matplotlib.__version__,
                            "numpy": numpy.__version__},
            "options": {"protein": "run" if protein else "not_run (--protein-not-run)",
                        "comparison": "provided" if comparison else "not provided (--no-comparison)",
                        "eligibility": "provided" if eligibility else "not provided"},
            "inputs": inp.records,
            "outputs": outputs,
            "notes": ["Values re-formatted from recorded outputs only; no metric is computed here.",
                      "Intervals drawn only where recorded (*_ci95 columns, paired ci95_lo/ci95_hi)."]}
    (stage / "generated" / "asset_provenance.json").write_text(json.dumps(prov, indent=1, sort_keys=True) + "\n")
    for sub, names in (("generated", GENERATED), ("figures", FIGURES)):
        (out / sub).mkdir(parents=True, exist_ok=True)
        for n in names:
            os.replace(stage / sub / n, out / sub / n)
    return prov


def parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(REPO), help="all inputs and the output must resolve inside this directory")
    ap.add_argument("--score", required=True, help="score_all.py output directory")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--protein", help="protein_check.py output directory")
    g.add_argument("--protein-not-run", action="store_true", help="protein check recorded as not run")
    c = ap.add_mutually_exclusive_group(required=True)
    c.add_argument("--comparison", help="compare_runs.py report.json")
    c.add_argument("--no-comparison", action="store_true", help="no tiered comparison report exists (e.g. Mode R)")
    ap.add_argument("--eligibility", help="optional hashed eligibility.json of the R4' replacement build")
    ap.add_argument("--output", required=True, help="paper directory (generated/ and figures/ are written)")
    return ap


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        prov = build(args)
    except (AssetError, json.JSONDecodeError, UnicodeDecodeError, OSError) as e:
        print(f"make_paper_assets: error: {e}", file=sys.stderr)
        return 2
    print(json.dumps({"status": "ok", "outputs": [o["path"] for o in prov["outputs"]]
                      + ["paper/generated/asset_provenance.json"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

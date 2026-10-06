"""Tiny SYNTHETIC fixtures for make_paper_assets.py tests. Every value here is fabricated for testing
formatting and data handling; none is a study result. Files mimic the column schema of
companion/scripts/score_all.py, protein_check.py and scripts/compare_runs.py."""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
TMP = HERE / "_tmp"
TMP.mkdir(exist_ok=True)
tempfile.tempdir = str(TMP)
os.environ.setdefault("MPLCONFIGDIR", str(TMP / "mpl"))
os.environ.setdefault("XDG_CACHE_HOME", str(TMP / "xdg"))
sys.dont_write_bytecode = True

_spec = importlib.util.spec_from_file_location("make_paper_assets", REPO / "scripts/make_paper_assets.py")
MPA = importlib.util.module_from_spec(_spec)
sys.modules["make_paper_assets"] = MPA
_spec.loader.exec_module(MPA)

ARMS = {"A": ["M1", "M2", "M3", "M4", "M5", "M6"], "B": ["M1", "M2", "M3", "M4", "M5", "M6"], "practical": ["P1", "P2"]}
CI_METRICS = ["coverage@OPcov", "accepted_error@OPcov", "coverage@OPerr", "accepted_error@OPerr", "macro_f1_closed",
              "unknown_false_accept@OPcov", "cross_lineage_rate@OPcov"]
STUDY = "RA_study&1%"  # deliberately LaTeX-hostile identity


def write_csv(p: Path, rows: list[dict]):
    cols = []
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    with open(p, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def ci(lo, hi):
    return f"[{lo}, {hi}]"  # pandas list repr as written by score_all.py


def summary_rows():
    rows = []
    i = 0
    for arm, ms in ARMS.items():
        for m in ms:
            i += 1
            base = round(0.5 + 0.01 * i, 4)
            r = {"arm": arm, "method": m, "test_scorable_natural": 1000 + i, "f1_classes": 12,
                 "macro_f1_closed": base, "coarser_fraction": 0.0, "outside_fraction": 0.0,
                 "coverage@OPcov": base, "accepted_error@OPcov": 0.05, "cross_lineage_share@OPcov": 0.2,
                 "cross_lineage_rate@OPcov": 0.01, "coverage@OPerr": 0.4, "accepted_error@OPerr": 0.04,
                 "cross_lineage_share@OPerr": 0.1, "cross_lineage_rate@OPerr": 0.004, "aurc": 0.03,
                 "max_coverage": 1.0, "risk@0.50": 0.01, "lineage_agreement_closed": 0.9,
                 "unknown_kind": "simulated" if arm == "B" else "natural", "unknown_cells": 50 + i,
                 "unknown_false_accept@OPcov": 0.3, "unknown_false_accept@OPerr": 0.1, "unknown_auroc": 0.8}
            for k in CI_METRICS:
                r[k + "_ci95"] = ci(0.1, 0.2)
            rows.append(r)
    # known numerical case: A:M4
    a4 = next(r for r in rows if r["arm"] == "A" and r["method"] == "M4")
    a4.update({"coverage@OPcov": 0.91234, "coverage@OPcov_ci95": ci(0.8506, 0.95049),
               "accepted_error@OPcov": 0.0423, "macro_f1_closed": 0.7777, "unknown_cells": 1234})
    # OP-err not attainable for B:M3 (empty values, nan intervals)
    b3 = next(r for r in rows if r["arm"] == "B" and r["method"] == "M3")
    b3.update({"coverage@OPerr": "", "accepted_error@OPerr": "", "unknown_false_accept@OPerr": "",
               "coverage@OPerr_ci95": ci("nan", "nan"), "accepted_error@OPerr_ci95": ci("nan", "nan")})
    # undefined (NaN) AUROC for practical P2
    p2 = next(r for r in rows if r["method"] == "P2")
    p2.update({"unknown_auroc": "nan", "coarser_fraction": 0.125})
    return rows


def thresholds_rows():
    rows = []
    for arm, ms in ARMS.items():
        for m in ms:
            rows.append({"arm": arm, "method": m, "tau_cov": 0.61, "eligible_cap_validation": 1.0, "tau_err": 0.72,
                         "validation_cells": 500, "validation_coverage_at_tau_cov": 0.9,
                         "validation_error_at_tau_cov": 0.06})
    for r in rows:
        if r["arm"] == "B" and r["method"] == "M3":
            r["tau_err"] = ""
        if r["arm"] == "practical" and r["method"] == "P1":
            r.update({"tau_cov": "-inf", "eligible_cap_validation": 0.83})
    return rows


def paired_rows():
    rows = []
    for arm, ms in ARMS.items():
        ref = "A:M4" if arm == "practical" else f"{arm}:M4"
        for m in ms:
            if (arm, m) in (("A", "M4"), ("B", "M4")):
                continue
            for k in CI_METRICS:
                rows.append({"arm": arm, "method": m, "vs": ref, "metric": k, "mean_diff": -0.0123,
                             "ci95_lo": -0.03, "ci95_hi": 0.004})
    for r in rows:
        if r["arm"] == "B" and r["method"] == "M3" and "OPerr" in r["metric"]:
            r.update({"mean_diff": "", "ci95_lo": "", "ci95_hi": ""})
    return rows


def make_score(d: Path, *, optional=True, info_methods=True):
    d.mkdir(parents=True, exist_ok=True)
    write_csv(d / "summary_test.csv", summary_rows())
    write_csv(d / "thresholds_validation.csv", thresholds_rows())
    write_csv(d / "paired_differences_vs_M4.csv", paired_rows())
    write_csv(d / "calibration_test.csv", [{"arm": a, "method": m, "brier": 0.2, "ece": 0.05, "reliability": "[]"}
                                           for a, ms in ARMS.items() for m in ms])
    write_csv(d / "per_study_test.csv", [{"arm": a, "method": m, "study": s, "cells": 600, "macro_f1_closed": 0.7,
                                          "coverage@OPcov": 0.9, "accepted_error@OPcov": 0.05,
                                          "coverage@OPerr": 0.5, "accepted_error@OPerr": 0.03}
                                         for a, ms in ARMS.items() for m in ms for s in (STUDY, "HIHA")])
    write_csv(d / "risk_coverage_test.csv", [{"coverage": c / 4, "risk": 0.01 * c, "arm": a, "method": m}
                                             for a, ms in ARMS.items() for m in ms for c in (1, 2, 3, 4)])
    write_csv(d / "platform.csv", [{"arm": a, "method": m, "platform": "plat_1", "assay": "10x 3' v3", "cells": 1000,
                                    "coverage": 0.9, "accepted_error": 0.08, "cross_lineage_share": 0.1,
                                    "cross_lineage_rate": 0.01, "closed_set_accuracy": 0.85}
                                   for a, ms in ARMS.items() for m in ms])
    write_csv(d / "cell_counts.csv", [{"role": "test", "study": STUDY, "stratum": "natural", "label_status": "mapped",
                                       "cells": 7200},
                                      {"role": "test", "study": STUDY, "stratum": "rare_topup",
                                       "label_status": "mapped", "cells": 310}])
    info = {"reps": 1000, "seed": 20261005, "test_donors": 48}
    if info_methods:
        info["methods"] = sorted(f"{a}:{m}" for a, ms in ARMS.items() for m in ms)
    (d / "score_info.json").write_text(json.dumps(info))
    if optional:
        write_csv(d / "bootstrap_nan_counts.csv", [{"arm": a, "method": m, "metric": k,
                                                    "nan_replicates": 7 if (a, m, k) == ("B", "M3", "coverage@OPerr") else 0}
                                                   for a, ms in ARMS.items() for m in ms for k in CI_METRICS])
        write_csv(d / "unknowns_allstrata_secondary.csv", [{"arm": a, "method": m, "analysis": "secondary-sensitivity-all-strata",
                                                            "unknown_cells": 80, "unknown_false_accept@OPcov": 0.31,
                                                            "unknown_false_accept@OPerr": 0.11, "unknown_auroc": 0.79}
                                                           for a in ("A", "practical") for m in ARMS[a]])
        (d / "scoring_scope.json").write_text(json.dumps({"natural_unknown_scope": "natural", "decision": "D-1a"}))
    return d


def make_protein(d: Path, files=("totalvi_pbmc5k_protein_v3",)):
    d.mkdir(parents=True, exist_ok=True)
    rows = []
    for f in files:
        for a, ms in (("practical", ["P1", "P2"]), ("A", ARMS["A"])):
            for m in ms:
                rows.append({"file": f, "arm": a, "method": m, "tau_cov": 0.61, "protein_resolved_cells": 2500,
                             "accepted_among_resolved": 0.9, "agreement_accepted": 0.876 if m == "M4" else 0.8,
                             "agreement_accepted_gateable_preds": 0.95 if m != "M1" else "nan",
                             "n_accepted_resolved": 2250})
    write_csv(d / "protein_agreement.csv", rows)
    (d / "gates.json").write_text(json.dumps({f: {"cells": 3994} for f in files}))
    return d


def make_report(p: Path, schema="celltransfer-compare-report/1"):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"schema": schema, "overall": "reproduced within tolerance (synthetic)",
                             "protein_check": "run on 1 eligible replacement file(s)",
                             "result_of_record": "Mode R (original)", "m6_only_breach": False,
                             "per_arm_method": {f"{a}:{m}": {"outcome": "reproduced", "breaches": 0, "unsupported": 0}
                                                for a, ms in ARMS.items() for m in ms}}))
    return p


def make_eligibility(d: Path, eligible=()):
    """Synthetic eligibility.json + sidecar in the builder's record format."""
    d.mkdir(parents=True, exist_ok=True)
    names = ["totalvi_pbmc5k_protein_v3", "totalvi_pbmc10k_protein_v3"]
    files = {n: ({"verdict": "eligible", "first_failing_criterion": None} if n in eligible else
                 {"verdict": "ineligible", "first_failing_criterion": {"number": 4, "name": "coverage"}})
             for n in names}
    el = sorted(eligible)
    rec = {"files": files, "eligible_files": el, "n_eligible": len(el), "outcome": "run" if el else "not_run"}
    b = json.dumps(rec, sort_keys=True).encode()
    (d / "eligibility.json").write_bytes(b)
    (d / "eligibility.json.sha256").write_text(f"{hashlib.sha256(b).hexdigest()}  eligibility.json\n")
    return d / "eligibility.json"


def new_root(name: str) -> Path:
    root = TMP / name
    if root.exists():
        shutil.rmtree(root)
    (root / "paper").mkdir(parents=True)
    shutil.copy(REPO / "paper/artifacts.json", root / "paper/artifacts.json")
    return root


def run(root: Path, *extra) -> int:
    return MPA.main(["--root", str(root), "--output", str(root / "paper"), *extra])

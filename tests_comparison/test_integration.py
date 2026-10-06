"""End-to-end tests of compare_runs.py on entirely synthetic Mode R / Mode F trees.

Needs pandas+pyarrow+numpy (parquet/npy, as written by the real pipeline); skipped otherwise.
All files are written under tests_comparison/_tmp and removed afterwards.
Expected outcomes are derived by hand from the section 7 rules, not from the comparator.
"""
import copy
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import compare_runs as C  # noqa: E402

try:
    import numpy as np
    import pandas as pd
    import pyarrow  # noqa: F401
    HAVE = True
except ImportError:  # pragma: no cover
    HAVE = False

TOL = HERE.parent / "protocol/tolerances.json"
D_FILES = [f"D{i:02d}" for i in range(1, 16)]
C_FILES = ["C1", "C2", "C3", "C4"]
N = 20  # cells per file -> allowed disagreements = max(1, floor(0.02)) = 1


def base_spec():
    s = {"features": {"K": ["B", "NK", "T"], "K_B": ["NK", "T"], "F_A": ["g1", "g2"], "F_B": ["g1"],
                      "markers_A": {"B": ["g1"]}, "markers_B": {"T": ["g1"]}, "hvg_A": ["g1"]},
         "sampled": [{"study": f, "role": "test" if i % 2 else "validation", "stratum": "natural", "soma_joinid": i * 100 + j}
                     for i, f in enumerate(D_FILES) for j in range(N)],
         "released": {}, "pred": {}, "fit": {"A": {"chosen_C": 0.1, "validation_macro_f1_by_C": {"0.01": 0.5, "0.1": 0.6, "1.0": 0.55}},
                                              "B": {"chosen_C": 1.0, "validation_macro_f1_by_C": {"0.01": 0.5, "0.1": 0.6, "1.0": 0.65}}},
         "adt": {}, "pclass": {}, "boot": np.arange(12, dtype=np.float32).reshape(3, 4)}
    for i, f in enumerate(D_FILES + C_FILES):
        ids = list(range(N)) if f in C_FILES else [i * 100 + j for j in range(N)]
        s["released"][f] = pd.DataFrame({"soma_joinid": ids,
                                         "P1_celltypist_target": ["B"] * (N - 1) + [None], "P1_celltypist_status": ["mapped"] * (N - 1) + ["outside"],
                                         "P1_celltypist_lineage": ["lymphoid"] * N, "P1_celltypist_conf": [0.8] * N,
                                         "P2_sctab_target": ["T"] * N, "P2_sctab_status": ["mapped"] * N,
                                         "P2_sctab_lineage": ["lymphoid"] * N, "P2_sctab_conf": [0.7] * N})
        for arm in ("A", "B"):
            if arm == "B" and f in C_FILES:
                continue
            for m in C.METHODS_M:
                s["pred"][(arm, m, f)] = pd.DataFrame({"soma_joinid": ids, "pred": ["NK"] * N, "conf": [0.6] * N})
    for f in C_FILES:
        s["adt"][f] = pd.DataFrame({"barcode": [f"bc{j}" for j in range(N)], "CD3": np.arange(N, dtype=float), "CD19": np.ones(N)})
        s["pclass"][f] = [{"barcode": f"bc{j}", "protein_class": "B" if j < 10 else ""} for j in range(N)]
    rows = []
    for arm, ms in (("A", C.METHODS_M), ("B", C.METHODS_M), ("practical", ["P1", "P2"])):
        for m in ms:
            r = {"arm": arm, "method": m, "test_scorable_natural": 150, "f1_classes": 3, "macro_f1_closed": 0.8,
                 "coarser_fraction": 0.0, "outside_fraction": 0.0, "aurc": 0.1, "max_coverage": 1.0,
                 "lineage_agreement_closed": 0.95, "unknown_kind": "natural" if arm != "B" else "simulated",
                 "unknown_cells": 12, "unknown_false_accept@OPcov": 0.5, "unknown_false_accept@OPerr": "",
                 "unknown_auroc": 0.7}
            for op in ("cov", "err"):
                r.update({f"coverage@OP{op}": 0.25, f"accepted_error@OP{op}": 0.05,
                          f"cross_lineage_share@OP{op}": 0.2, f"cross_lineage_rate@OP{op}": 0.01})
            for lv in ("0.50", "0.60", "0.70", "0.80", "0.90", "0.95", "1.00"):
                r[f"risk@{lv}"] = 0.1
            for k in ("coverage@OPcov", "accepted_error@OPcov", "coverage@OPerr", "accepted_error@OPerr",
                      "macro_f1_closed", "unknown_false_accept@OPcov", "cross_lineage_rate@OPcov"):
                r[f"{k}_ci95"] = "[0.2, 0.3]"
            rows.append(r)
    s["summary"] = rows
    s["calib"] = [{"arm": r["arm"], "method": r["method"], "brier": "" if r["method"] in ("M1", "M2", "M3") else 0.3,
                   "ece": "" if r["method"] in ("M1", "M2", "M3") else 0.05,
                   "reliability": json.dumps([[0.0, 0.5, 3, 0.4, 0.3]])} for r in rows]
    s["thr"] = [{"arm": r["arm"], "method": r["method"], "tau_cov": "-inf" if r["method"] == "M1" else 0.42,
                 "eligible_cap_validation": 1.0, "tau_err": "" if r["method"] == "M2" else 0.9, "validation_cells": 50,
                 "validation_coverage_at_tau_cov": 0.9, "validation_error_at_tau_cov": 0.04} for r in rows]
    s["paired"] = [{"arm": "A", "method": "M5", "vs": "A:M4", "metric": "coverage@OPcov", "mean_diff": 0.02, "ci95_lo": 0.005, "ci95_hi": 0.035},
                   {"arm": "A", "method": "M3", "vs": "A:M4", "metric": "coverage@OPcov", "mean_diff": 0.005, "ci95_lo": 0.001, "ci95_hi": 0.009}]
    s["per_study"] = [{"arm": "A", "method": "M4", "study": "D02", "cells": 20, "macro_f1_closed": 0.7}]
    s["per_class"] = [{"arm": "A", "method": "M4", "class": "B", "n_natural": 5, "precision_natural": 0.6}]
    s["platform"] = [{"arm": "A", "method": "M4", "platform": "Platform_x", "assay": "x", "cells": 5, "coverage": 0.5}]
    s["unknowns"] = [{"arm": "A", "method": "M4", "kind": "natural", "class": "erythroid", "cells": 3, "false_accept@OPcov": 0.3}]
    s["rc"] = [{"coverage": 0.1 * k, "risk": 0.01 * k, "arm": "A", "method": "M4"} for k in range(1, 4)]
    s["counts"] = [{"role": "test", "study": "D02", "stratum": "natural", "label_status": "mapped", "cells": 20}]
    s["info"] = {"reps": 3, "seed": 20261005, "methods": ["A:M4"], "test_donors": 9}
    s["protein"] = [{"file": f, "arm": a, "method": m, "tau_cov": 0.4, "agreement_accepted": 0.9,
                     "agreement_accepted_gateable_preds": 0.95} for f in C_FILES for a, m in [("A", x) for x in C.METHODS_M] + [("practical", "P1"), ("practical", "P2")]]
    s["gates"] = {f: {"cells": N, "resolved": 10} for f in C_FILES}
    s["resources"] = {"F1": {"seconds": 100.0, "peak_memory_bytes": 1e9}}
    return s


def write_csv(path, rows):
    pd.DataFrame(rows).to_csv(path, index=False)


def write_run(root: Path, s, mode, unsupported=False, fresh=True):
    root.mkdir(parents=True)
    data, cite, score, prot = root / "data", root / "cite", root / "score", root / "protein"
    for d in (data, cite, score, prot):
        d.mkdir()
    json.dump(s["features"], open(data / "features_and_classes.json", "w"))
    write_csv(data / "sampled_ids.csv", s["sampled"])
    for f, df in s["released"].items():
        df.to_parquet((cite if f in C_FILES else data) / f"released_predictions_{f}.parquet")
    for f, df in s["adt"].items():
        df.to_parquet(cite / f"adt_{f}.parquet")
    for (arm, m, f), df in s["pred"].items():
        d = root / f"arm{arm}" / m
        d.mkdir(parents=True, exist_ok=True)
        df.to_parquet(d / f"predictions_{f}.parquet")
    for arm, info in s["fit"].items():
        json.dump(info, open(root / f"arm{arm}" / "M4" / "fit_info.json", "w"))
    write_csv(score / "summary_test.csv", s["summary"])
    write_csv(score / "calibration_test.csv", s["calib"])
    write_csv(score / "thresholds_validation.csv", s["thr"])
    write_csv(score / "paired_differences_vs_M4.csv", s["paired"])
    write_csv(score / "per_study_test.csv", s["per_study"])
    write_csv(score / "per_class_test.csv", s["per_class"])
    write_csv(score / "platform.csv", s["platform"])
    write_csv(score / "unknowns_test.csv", s["unknowns"])
    write_csv(score / "risk_coverage_test.csv", s["rc"])
    write_csv(score / "cell_counts.csv", s["counts"])
    json.dump(s["info"], open(score / "score_info.json", "w"))
    write_csv(prot / "protein_agreement.csv", s["protein"])
    json.dump(s["gates"], open(prot / "gates.json", "w"))
    m = {"schema": C.MANIFEST_SCHEMA, "mode": mode, "data": "data", "cite": "cite", "score": {"primary": "score"},
         "protein": "protein", "arms": {"A": ["armA"], "B": ["armB"]}, "sampled_ids": "data/sampled_ids.csv",
         "resources": s["resources"]}
    if mode == "F" and fresh:
        m["fresh_execution"] = True
    if not unsupported:
        np.save(root / "boot.npy", s["boot"])
        m["bootstrap_weights"] = "boot.npy"
        m["d03_features"] = "data/features_and_classes.json"
        pcs = {}
        for f, rows in s["pclass"].items():
            write_csv(prot / f"protein_classes_{f}.csv", rows)
            pcs[f] = f"protein/protein_classes_{f}.csv"
        m["protein_classes"] = pcs
    json.dump(m, open(root / "manifest.json", "w"))
    return root / "manifest.json"


@unittest.skipUnless(HAVE, "pandas/pyarrow/numpy not available")
class TestCompare(unittest.TestCase):
    def setUp(self):
        (HERE / "_tmp").mkdir(exist_ok=True)
        self.tmp = Path(tempfile.mkdtemp(dir=HERE / "_tmp"))

    def tearDown(self):
        shutil.rmtree(self.tmp)
        try:
            (HERE / "_tmp").rmdir()
        except OSError:
            pass

    def go(self, mutate=None, unsupported=False, fresh=True):
        s = base_spec()
        base = Path(tempfile.mkdtemp(dir=self.tmp))
        o = write_run(base / "R", s, "R", unsupported)
        s2 = copy.deepcopy(s)
        if mutate:
            mutate(s2)
        f = write_run(base / "F", s2, "F", unsupported, fresh)
        out = base / "report.json"
        code = C.run(o, f, TOL, out)
        return code, json.load(open(out))

    def failed(self, rep):
        return {(c["tier"], c["check"], c["arm"], c["method"], c["file"]) for c in rep["failures"]}

    def test_identical_passes(self):
        code, rep = self.go()
        self.assertEqual(code, 0, rep["failures"][:3] + rep["unsupported"][:3])
        self.assertEqual(rep["overall"], "reproduced within pre-specified tolerance")
        self.assertEqual(rep["per_arm_method"]["practical:P2"]["outcome"], "reproduced within pre-specified tolerance")

    def test_unsupported_artifacts_not_passed(self):
        code, rep = self.go(unsupported=True)
        self.assertEqual(code, 3)
        self.assertTrue(rep["overall"].startswith("not assessable"))
        self.assertEqual({c["check"] for c in rep["unsupported"]},
                         {"bootstrap_weights", "protein_gating_per_cell", "features_equal_D03"})

    def test_label_boundary(self):
        def one(s):
            s["pred"][("A", "M4", "D03")].loc[0, "pred"] = "T"
            s["pred"][("A", "M4", "D03")].loc[1, "conf"] = 0.6 + 1.5e-5  # allowed 1e-5+1e-5*0.600015=1.6e-5
        code, rep = self.go(one)
        self.assertEqual(code, 0, rep["failures"][:2])

        def two(s):
            s["pred"][("A", "M4", "D03")].loc[[0, 1], "pred"] = "T"
        code, rep = self.go(two)
        self.assertEqual(code, 1)
        self.assertEqual(self.failed(rep), {("T2", "labels", "A", "M4", "D03")})
        self.assertEqual(rep["per_arm_method"]["A:M4"]["outcome"], "partially reproduced")
        self.assertEqual(rep["per_arm_method"]["A:M3"]["outcome"], "reproduced within pre-specified tolerance")

    def test_conf_breach(self):
        def f(s):
            s["pred"][("B", "M2", "D01")].loc[4, "conf"] = 0.6 + 2e-5
        code, rep = self.go(f)
        self.assertEqual(self.failed(rep), {("T2", "conf", "B", "M2", "D01")})
        det = rep["failures"][0]["details"]["conf_breaches"][0]
        self.assertEqual(det["id"], "4")
        self.assertAlmostEqual(det["abs_diff"], 2e-5, places=12)

    def test_m6_labels_diagnostic_only(self):
        def f(s):
            s["pred"][("A", "M6", "C2")].loc[:9, "pred"] = "B"
        code, rep = self.go(f)
        self.assertEqual(code, 0)
        diag = [c for c in rep["checks"] if c["check"] == "M6_labels_conf" and c["file"] == "C2" and c["arm"] == "A"][0]
        self.assertEqual(diag["details"]["agreement"], 0.5)
        self.assertFalse(diag["details"]["heuristic_met"])

    def test_p1_labels_exact(self):
        def f(s):
            s["released"]["D07"].loc[19, "P1_celltypist_status"] = "coarser"
        code, rep = self.go(f)
        self.assertEqual(code, 1)
        self.assertIn(("T1", "P1_labels", "practical", "P1", "D07"), self.failed(rep))
        self.assertEqual(rep["overall"], "not reproduced at the data level")

    def test_metric_boundary_and_state(self):
        def ok(s):
            s["summary"][0]["coverage@OPcov"] = 0.25 + 0.0078125  # <= 0.01
            s["summary"][0]["aurc"] = 0.1 + 0.0048828125          # <= 0.005
        self.assertEqual(self.go(ok)[0], 0)

        def bad(s):
            s["summary"][0]["coverage@OPcov"] = 0.2625               # 0.0125 > 0.01
            s["summary"][1]["aurc"] = 0.1 + 0.0051                  # > 0.005
            s["summary"][2]["unknown_false_accept@OPerr"] = 0.0     # None -> finite: state breach
        code, rep = self.go(bad)
        fl = self.failed(rep)
        self.assertIn(("M", "summary_test:coverage@OPcov[primary]", "A", "M1", None), fl)
        self.assertIn(("M", "summary_test:unassigned@OPcov[primary]", "A", "M1", None), fl)
        self.assertIn(("M", "summary_test:aurc[primary]", "A", "M2", None), fl)
        self.assertIn(("M", "summary_test:unknown_false_accept@OPerr[primary]", "A", "M3", None), fl)
        self.assertEqual(len(fl), 4)
        cov = [c for c in rep["failures"] if c["check"] == "summary_test:coverage@OPcov[primary]"][0]
        self.assertAlmostEqual(cov["details"]["abs_diff"], 0.0125, places=12)

    def test_ci_change(self):
        def f(s):
            s["summary"][5]["macro_f1_closed_ci95"] = "[0.2, 0.32]"
        code, rep = self.go(f)
        self.assertEqual(self.failed(rep), {("M", "summary_test:macro_f1_closed_ci95.hi[primary]", "A", "M6", None)})
        self.assertEqual(rep["per_arm_method"]["A:M6"]["outcome"], "partially reproduced")
        self.assertTrue(rep["m6_only_breach"])  # wording offered, not a waiver
        self.assertEqual(code, 1)

    def test_threshold_states(self):
        def f(s):
            s["thr"][1]["tau_err"] = 0.5        # A:M2 None -> finite
            s["thr"][2]["tau_cov"] = 0.0        # A:M3 finite 0.42 -> finite 0.0: no numeric tolerance
        code, rep = self.go(f)
        self.assertEqual(self.failed(rep), {("T2", "thresholds:tau_err[primary]", "A", "M2", None)})
        d = [c for c in rep["checks"] if c["check"] == "thresholds:tau_cov[primary]" and c["method"] == "M3" and c["arm"] == "A"][0]
        self.assertEqual(d["status"], "pass")
        self.assertAlmostEqual(d["details"]["abs_delta_tau"], 0.42)

    def test_sampled_id_join_change(self):
        def f(s):
            s["sampled"][3]["soma_joinid"] = 999999
        code, rep = self.go(f)
        self.assertEqual(code, 1)
        self.assertEqual(rep["overall"], "not reproduced at the data level")
        self.assertEqual(rep["per_arm_method"]["A:M1"]["outcome"], "not reproduced at the data level")

    def test_study_swap_detected(self):
        def f(s):
            s["sampled"][0]["study"] = "D02"
        code, rep = self.go(f)
        self.assertIn(("T1", "sampled_soma_joinid", None, None, None), self.failed(rep))

    def test_missing_row_and_file(self):
        def f(s):
            del s["summary"][3]
            del s["pred"][("B", "M5", "D09")]
        code, rep = self.go(f)
        self.assertEqual(code, 1)
        st = {(c["check"], c["arm"], c["method"], c["file"]) for c in rep["failures"] if c["status"] == "structural_failure"}
        self.assertIn(("summary_test[primary]", None, None, None), st)
        self.assertIn(("predictions", "B", "M5", "D09"), st)

    def test_chosen_c(self):
        def f(s):
            s["fit"]["B"]["chosen_C"] = 0.1
        code, rep = self.go(f)
        c = [x for x in rep["failures"] if x["check"] == "M4_chosen_C"][0]
        self.assertEqual((c["arm"], c["details"]["original"], c["details"]["reproduction"]), ("B", 1.0, 0.1))
        self.assertIn("validation_macro_f1_by_C", c["details"])
        self.assertEqual(rep["overall"], "not reproduced at the data level")

    def test_sign_rule(self):
        def f(s):
            # all within 0.01 of R, but CI now includes zero: sign breach for headline
            s["paired"][0].update(mean_diff=0.015, ci95_lo=-0.004, ci95_hi=0.03)
            # near-zero: |mean| <= 0.01 both, exclusion status changes -> note only
            s["paired"][1].update(mean_diff=0.004, ci95_lo=-0.001, ci95_hi=0.009)
        code, rep = self.go(f)
        self.assertEqual(self.failed(rep), {("S", "sign:coverage@OPcov[primary]", "A", "M5", None)})
        note = [c for c in rep["checks"] if c["tier"] == "S" and c["method"] == "M3"][0]
        self.assertEqual(note["status"], "near_zero_note")
        self.assertFalse(note["gated"])

    def test_protein_gating_and_agreement(self):
        def f(s):
            s["pclass"]["C1"][0]["protein_class"] = "NK"
            s["pclass"]["C1"][1]["protein_class"] = "NK"
            s["protein"][0]["agreement_accepted"] = 0.8
        code, rep = self.go(f)
        fl = self.failed(rep)
        self.assertIn(("T2", "protein_gating_per_cell", None, None, "C1"), fl)
        self.assertIn(("M", "protein:agreement_accepted", "A", "M1", "C1"), fl)

    def test_adt_and_bootstrap_exact(self):
        def f(s):
            s["adt"]["C3"].loc[2, "CD3"] = 2.0000001
            s["boot"][0, 0] = 1
        code, rep = self.go(f)
        fl = self.failed(rep)
        self.assertIn(("T1", "adt_counts", None, None, "C3"), fl)
        self.assertIn(("T1", "bootstrap_weights", None, None, None), fl)

    def test_descriptive_not_gated_and_resources(self):
        def f(s):
            s["per_study"][0]["macro_f1_closed"] = 0.2
            s["calib"][0]["brier"] = 0.9   # M1 calibration: descriptive
            s["resources"]["F1"]["seconds"] = 250.0
        code, rep = self.go(f)
        self.assertEqual(code, 0)
        ps = [c for c in rep["checks"] if c["check"] == "per_study_test.csv[primary]"][0]
        self.assertAlmostEqual(ps["details"]["max_abs_diff"]["macro_f1_closed"], 0.5)
        r = [c for c in rep["checks"] if c["check"] == "resource:F1:seconds"][0]
        self.assertEqual((r["status"], r["details"]["ratio"]), ("flag_over_2x", 2.5))

    def test_cached_outputs_rejected(self):
        s = base_spec()
        o = write_run(self.tmp / "R", s, "R")
        m = json.load(open(o))
        m.update(mode="F", fresh_execution=True)
        for k in ("data", "cite", "protein", "sampled_ids", "bootstrap_weights", "d03_features"):
            m[k] = str((self.tmp / "R" / m[k]).resolve())
        m["score"] = {"primary": str(self.tmp / "R/score")}
        m["arms"] = {a: [str(self.tmp / "R" / d[0])] for a, d in m["arms"].items()}
        m["protein_classes"] = {k: str(self.tmp / "R" / v) for k, v in m["protein_classes"].items()}
        fp = self.tmp / "F.json"
        json.dump(m, open(fp, "w"))
        code = C.run(o, fp, TOL, self.tmp / "rep.json")
        rep = json.load(open(self.tmp / "rep.json"))
        self.assertEqual(code, 1)
        self.assertTrue(all(c["check"] == "fresh_execution" for c in rep["failures"]))
        self.assertTrue(rep["overall"].startswith("not compared"))

    def test_missing_fresh_flag(self):
        code, rep = self.go(fresh=False)
        self.assertEqual(code, 1)
        self.assertIn("fresh_execution", {c["check"] for c in rep["failures"]})

    def test_cli_exit_code(self):
        s = base_spec()
        o = write_run(self.tmp / "R", s, "R")
        f = write_run(self.tmp / "F", s, "F")
        code = C.main(["--original", str(o), "--reproduction", str(f), "--tolerances", str(TOL), "--out", str(self.tmp / "r.json")])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()

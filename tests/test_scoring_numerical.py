"""Numerical D-1a test: synthetic fixture scored by the real companion/scripts/score_all.py in the
pinned study venv (numpy/pandas/anndata/sklearn). Skipped only if that venv is absent."""
import csv
import json
import os
import shutil
import subprocess
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV_PY = Path(os.environ.get("STUDY_VENV_PYTHON",
                              "/Users/timrichardson/Documents/projects/personal/blog/cell-type-annotation-transfer/.venv/bin/python"))
TMP = ROOT / "tests" / "_tmp_num"


def rows(p):
    with open(p) as fh:
        return list(csv.DictReader(fh))


@unittest.skipUnless(VENV_PY.exists(), "pinned study venv not present")
class TestD1aNumerical(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = TMP / str(time.time_ns())
        cls.d.mkdir(parents=True)
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", MPLCONFIGDIR=str(cls.d / "mpl"),
                   XDG_CACHE_HOME=str(cls.d / "xdg"), TMPDIR=str(cls.d))
        subprocess.run([str(VENV_PY), str(ROOT / "tests/d1a_fixture.py"), str(cls.d)], check=True, env=env)
        cls.out = {}
        for scope in ("natural", "all"):
            o = cls.d / f"score_{scope}"
            r = subprocess.run([str(VENV_PY), str(ROOT / "companion/scripts/score_all.py"), "--workspace", str(ROOT),
                                "--data", str(cls.d / "data"), "--matched", f"A={cls.d / 'armA'}",
                                f"B={cls.d / 'armB'}", "--out", str(o), "--reps", "5",
                                "--natural-unknown-scope", scope], capture_output=True, text=True, env=env)
            if r.returncode:
                raise AssertionError(r.stderr[-3000:])
            cls.out[scope] = o

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TMP, ignore_errors=True)

    def summary(self, scope):
        return {(r["arm"], r["method"]): r for r in rows(self.out[scope] / "summary_test.csv")}

    def test_primary_natural_excludes_topup_for_A_and_practical(self):
        s = self.summary("natural")
        for key in (("A", "M4"), ("practical", "P1"), ("practical", "P2")):
            self.assertEqual(s[key]["unknown_kind"], "natural")
            self.assertEqual(int(float(s[key]["unknown_cells"])), 10, key)  # 7 top-up erythroid excluded
            self.assertAlmostEqual(float(s[key]["unknown_false_accept@OPcov"]), 1.0, places=12)
            # known natural: 48 at conf 0.9 (< 0.99) + 6 in-K removed-type cells tied at 0.99 -> AUROC = 0.5*6/54
            self.assertAlmostEqual(float(s[key]["unknown_auroc"]), 3 / 54, places=12)
        u = [r for r in rows(self.out["natural"] / "unknowns_test.csv") if r["arm"] in ("A", "practical")]
        self.assertEqual({r["class"] for r in u}, {"neutrophil"})

    def test_armB_removed_types_all_strata_preserved(self):
        for scope in ("natural", "all"):
            b = self.summary(scope)[("B", "M4")]
            self.assertEqual(b["unknown_kind"], "simulated")
            self.assertEqual(int(float(b["unknown_cells"])), 9)  # 6 natural + 3 top-up
            self.assertAlmostEqual(float(b["unknown_false_accept@OPcov"]), 6 / 9, places=12)

    def test_allstrata_secondary_retained_and_named(self):
        sec = rows(self.out["natural"] / "unknowns_allstrata_secondary.csv")
        self.assertEqual({(r["arm"], r["method"]) for r in sec}, {("A", "M4"), ("practical", "P1"), ("practical", "P2")})
        for r in sec:
            self.assertEqual(r["analysis"], "secondary-sensitivity-all-strata")
            self.assertEqual(int(float(r["unknown_cells"])), 17)
            self.assertAlmostEqual(float(r["unknown_false_accept@OPcov"]), 10 / 17, places=12)
        self.assertEqual(json.loads((self.out["natural"] / "scoring_scope.json").read_text())["natural_unknown_scope"],
                         "natural")

    def test_scope_all_reproduces_historical_definition(self):
        a = self.summary("all")[("A", "M4")]
        self.assertEqual(a["unknown_kind"], "natural-allstrata")
        self.assertEqual(int(float(a["unknown_cells"])), 17)
        self.assertAlmostEqual(float(a["unknown_false_accept@OPcov"]), 10 / 17, places=12)

    def test_known_metrics_unchanged_by_scope(self):
        n, a = self.summary("natural")[("A", "M4")], self.summary("all")[("A", "M4")]
        for k in ("test_scorable_natural", "coverage@OPcov", "accepted_error@OPcov", "macro_f1_closed"):
            self.assertEqual(n[k], a[k], k)
        self.assertEqual(int(float(n["test_scorable_natural"])), 54)  # 48 known + 6 pDC/ASC/MAIT natural (in K for A)


if __name__ == "__main__":
    unittest.main()

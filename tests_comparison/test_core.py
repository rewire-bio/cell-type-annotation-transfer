"""Stdlib-only unit tests for scripts/compare_runs.py core rules (synthetic values only).

Run:  PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests_comparison -v
"""
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import compare_runs as C  # noqa: E402

TOL = {"max_disagree_fraction": 0.001, "min_disagree_allowed": 1, "conf_abs": 1e-5, "conf_rel": 1e-5}


class TestClose(unittest.TestCase):
    def test_boundary_inclusive(self):
        # |0.51-0.50| = 0.01 (floating 0.010000000000000009) -> use exactly representable values
        ok, d, *_ = C.close(0.5, 0.5 + 0.0078125, 0.0078125, 0)
        self.assertTrue(ok)
        self.assertEqual(d, 0.0078125)
        ok, *_ = C.close(0.5, 0.5 + 0.0078125 + 2 ** -20, 0.0078125, 0)
        self.assertFalse(ok)

    def test_m_tier_0p01(self):
        self.assertTrue(C.close(0.200, 0.209, 0.01, 0)[0])
        self.assertFalse(C.close(0.200, 0.2101, 0.01, 0)[0])
        self.assertTrue(C.close(0.100, 0.1049, 0.005, 0)[0])   # AURC tier
        self.assertFalse(C.close(0.100, 0.1051, 0.005, 0)[0])

    def test_relative_part(self):
        # abs 1e-5 + rel 1e-5*max(|a|,|b|): a=1000 -> allowed 0.01001
        self.assertTrue(C.close(1000.0, 1000.01, 1e-5, 1e-5)[0])
        self.assertFalse(C.close(1000.0, 1000.011, 1e-5, 1e-5)[0])

    def test_states(self):
        nan, inf = float("nan"), float("inf")
        self.assertTrue(C.close(nan, nan, 0.01, 0)[0])
        self.assertTrue(C.close(None, None, 0.01, 0)[0])
        self.assertTrue(C.close(-inf, -inf, 0.01, 0)[0])
        self.assertFalse(C.close(-inf, inf, 0.01, 0)[0])
        self.assertFalse(C.close(nan, None, 0.01, 0)[0])
        self.assertFalse(C.close(nan, 0.5, 0.01, 0)[0])
        self.assertFalse(C.close(None, 0.0, 0.01, 0)[0])
        self.assertFalse(C.close(-inf, -1e300, 0.01, 0)[0])

    def test_csv_parsing(self):
        self.assertIsNone(C.parse_value(""))
        self.assertEqual(C.state(C.parse_value("-inf")), "-inf")
        self.assertEqual(C.state(C.parse_value("nan")), "nan")
        self.assertEqual(C.parse_ci("[0.1, 0.2]"), (0.1, 0.2))
        lo, hi = C.parse_ci("[nan, nan]")
        self.assertTrue(math.isnan(lo) and math.isnan(hi))
        with self.assertRaises(C.StructuralError):
            C.parse_ci("[0.1]")


class TestAllowed(unittest.TestCase):
    def test_formula(self):
        # max(1, floor(0.001 n)) computed by hand
        self.assertEqual(C.allowed_disagreements(10, 0.001, 1), 1)
        self.assertEqual(C.allowed_disagreements(999, 0.001, 1), 1)
        self.assertEqual(C.allowed_disagreements(2000, 0.001, 1), 2)
        self.assertEqual(C.allowed_disagreements(2999, 0.001, 1), 2)
        self.assertEqual(C.allowed_disagreements(3000, 0.001, 1), 3)


class TestLabels(unittest.TestCase):
    def rows(self, labels, confs):
        return [{"soma_joinid": i, "pred": l, "conf": c} for i, (l, c) in enumerate(zip(labels, confs))]

    def test_one_change_allowed_two_not(self):
        n = 1500  # allowed = 1
        o = self.rows(["B"] * n, [0.9] * n)
        f1 = self.rows(["T"] + ["B"] * (n - 1), [0.9] * n)
        f2 = self.rows(["T", "T"] + ["B"] * (n - 2), [0.9] * n)
        d1 = C.compare_labels(o, f1, lambda r: C.norm_label(r["pred"]), "conf", TOL)
        d2 = C.compare_labels(o, f2, lambda r: C.norm_label(r["pred"]), "conf", TOL)
        self.assertEqual((d1["disagreements"], d1["allowed"]), (1, 1))
        self.assertEqual((d2["disagreements"], d2["allowed"]), (2, 1))

    def test_conf_only_on_agreeing(self):
        o = self.rows(["B", "T", "NK"], [0.5, 0.5, 0.5])
        f = self.rows(["B", "B", "NK"], [0.500004, 0.1, 0.50003])
        d = C.compare_labels(o, f, lambda r: C.norm_label(r["pred"]), "conf", TOL)
        # cell 1 disagrees (conf ignored); cell 0 diff 4e-6 <= 1e-5+5e-6; cell 2 diff 3e-5 > 1.5e-5
        self.assertEqual(d["disagreements"], 1)
        self.assertEqual([b["id"] for b in d["conf_breaches"]], ["2"])

    def test_missing_label_states(self):
        o = self.rows([None, float("nan")], [float("-inf"), 0.2])
        f = self.rows([None, None], [float("-inf"), 0.2])
        d = C.compare_labels(o, f, lambda r: C.norm_label(r["pred"]), "conf", TOL)
        self.assertEqual(d["disagreements"], 0)
        self.assertEqual(d["conf_breaches"], [])

    def test_missing_and_duplicate_rows_fatal(self):
        o = self.rows(["B", "T"], [0.5, 0.5])
        with self.assertRaises(C.StructuralError):
            C.compare_labels(o, o[:1], lambda r: r["pred"], "conf", TOL)
        with self.assertRaises(C.StructuralError):
            C.compare_labels(o, o + o[:1], lambda r: r["pred"], "conf", TOL)
        moved = [dict(o[0]), dict(o[1], soma_joinid=7)]
        with self.assertRaises(C.StructuralError):
            C.compare_labels(o, moved, lambda r: r["pred"], "conf", TOL)


class TestSign(unittest.TestCase):
    def test_headline(self):
        self.assertTrue(C.is_headline(0.02, 0.05, 0.03, 0.01))
        self.assertFalse(C.is_headline(0.002, 0.02, 0.01, 0.01))   # |mean| not > 0.01
        self.assertFalse(C.is_headline(-0.01, 0.05, 0.03, 0.01))   # CI includes 0
        self.assertTrue(C.is_headline(-0.05, -0.02, -0.03, 0.01))
        self.assertFalse(C.is_headline(float("nan"), 0.05, 0.03, 0.01))


if __name__ == "__main__":
    unittest.main()

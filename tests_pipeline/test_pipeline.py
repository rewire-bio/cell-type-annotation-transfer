"""Synthetic/mock tests for pipeline integration (no real data, no network)."""
import json, os, sys, tempfile, unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import result_manifest as RM  # noqa: E402
import reproduce as RP  # noqa: E402


def w(p, s):
    p.parent.mkdir(parents=True, exist_ok=True); p.write_text(s); return p


def score_dir(d):
    w(d / "summary_test.csv", "arm,method,macro_f1,coverage,macro_f1_ci95,seconds\nA,M1,0.5,1.0,\"[0.4, 0.6]\",12.3\nA,M4,nan,0.9,,1\n")
    w(d / "paired_differences_vs_M4.csv", "arm,method,vs,metric,mean\nA,M1,M4,macro_f1,0.1\n")
    w(d / "thresholds_validation.csv", "arm,method,tau_cov\nA,M4,inf\n")
    w(d / "cell_counts.csv", "role,study,n_cells\ntest,S1,1000\n")
    w(d / "score_info.json", json.dumps({"reps": 1000, "seed": 20261005, "created_utc": "x"}))
    return d


class Results(unittest.TestCase):
    def test_aggregate(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t); s = score_dir(t / "s"); w(t / "p/protein_agreement.csv", "file,arm,method,agree\nC1,A,M1,0.9\n")
            r = RM.aggregate_results(s, t / "p")
            st = r["summary_test"]["arm=A|method=M1"]
            self.assertEqual(st["macro_f1"], 0.5); self.assertEqual(st["macro_f1_ci95_lo"], 0.4)
            self.assertNotIn("seconds", st)
            self.assertIsNone(r["summary_test"]["arm=A|method=M4"]["macro_f1"])
            self.assertIsNone(r["thresholds_validation"]["arm=A|method=M4"]["tau_cov"])
            self.assertIs(type(r["cell_counts"]["study=S1|role=test"]["n_cells"]), int)
            self.assertEqual(r["score_info"], {"reps": 1000, "seed": 20261005})
            json.dumps(r, allow_nan=False)
            self.assertNotIn("mode", r)

    def test_missing_and_duplicate(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            with self.assertRaises(RM.ManifestError):
                RM.aggregate_results(t, None)
            s = score_dir(t / "s"); w(s / "summary_test.csv", "arm,method,x\nA,M1,1\nA,M1,2\n")
            with self.assertRaises(RM.ManifestError):
                RM.aggregate_results(s, None)

    def test_check_results(self):
        with self.assertRaises(RM.ManifestError):
            RM.check_results({"a": float("nan")})
        with self.assertRaises(RM.ManifestError):
            RM.check_results({"wall_seconds": 1})


class Arms(unittest.TestCase):
    def test_assemble_and_manifest(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t); src = {}
            for m in RM.METHODS:
                p, f = t / "pred" / m, t / "fit" / m
                w(p / "predictions_S1.parquet", "x"); w(f / "model.pkl", "m")
                if m == "M4":
                    w(f / "fit_info.json", "{}")
                src[m] = [p, f]
            arm = RM.assemble_arm(t / "arm", src)
            self.assertTrue((arm / "M4/fit_info.json").is_symlink())
            m = RM.write_compare_manifest(t / "out/man.json", mode="F", data=t, cite=t, arms={"A": [arm]},
                                          score={"primary": t}, protein=t, fresh=True,
                                          d03_features=t / "fit/M4/fit_info.json")
            self.assertEqual(m["arms"]["A"], ["../arm"]); self.assertEqual(m["d03_features_role"], "reference-check-only")
            with self.assertRaises(RM.ManifestError):
                RM.write_compare_manifest(t / "out/m2.json", mode="F", data=t, cite=t, arms={"A": [arm]},
                                          score={"primary": t}, protein=t, fresh=False)

    def test_duplicate_prediction_fatal(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t); a, b = t / "a", t / "b"
            w(a / "predictions_S1.parquet", "x"); w(b / "predictions_S1.parquet", "x")
            with self.assertRaises(RM.ManifestError):
                RM.assemble_arm(t / "arm", {"M1": [a, b]})


def cfg():
    return json.loads((Path(__file__).resolve().parents[1] / "configs/full.json").read_text())


class Reproduce(unittest.TestCase):
    def make(self, t, statuses=None):
        calls = []
        def runner(argv, name, timeout, cwd):
            calls.append(name)
            if name.endswith("_M6_fit"):
                w(Path(argv[argv.index("--out") + 1]) / "scanvi/model.pt", "synthetic-checkpoint")
            return {"status": (statuses or {}).get(name, "ok"), "returncode": 0}
        r = RP.Repro(Path(t), cfg(), runner=runner)
        return r, calls

    def test_preflight_fail_closed(self):
        with tempfile.TemporaryDirectory() as t:
            r, calls = self.make(t)
            with self.assertRaises(RP.Stop):
                r.run(None)  # no baseline
            w(Path(t) / "base.json", json.dumps({"schema": RM.MANIFEST_SCHEMA, "mode": "F"}))
            with self.assertRaises(RP.Stop):
                r.run(str(Path(t) / "base.json"))
            w(Path(t) / "results/full/results.json", "{}")
            with self.assertRaises(RP.Stop):
                r.run(str(Path(t) / "base.json"))
            self.assertEqual(calls, [])

    def test_baseline_inside_outputs_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            r, _ = self.make(t)
            b = w(Path(t) / "runs/x/base.json", json.dumps({"schema": RM.MANIFEST_SCHEMA, "mode": "R"}))
            with self.assertRaises(RP.Stop):
                r.preflight(str(b))

    def test_order_until_assembly(self):
        with tempfile.TemporaryDirectory() as t:
            r, calls = self.make(t)
            b = w(Path(t) / "ext/base.json", json.dumps({"schema": RM.MANIFEST_SCHEMA, "mode": "R"}))
            with self.assertRaises(RM.ManifestError):  # mocks write no predictions -> fail closed
                r.run(str(b))
            exp = ["env", "acquire", "data"] + [f"{a}_{m}_{s}" for a in "AB" for m in RM.METHODS
                                                for s in ("fit", "predict")]
            self.assertEqual(calls, exp)
            self.assertFalse((Path(t) / "results/full/results.json").exists())
            rec = json.loads((r.run_dir / "generation_receipt.json").read_text())
            self.assertTrue(rec["fresh_execution"]); self.assertEqual(rec["baseline_manifest"]["used_for"], "comparison-only")

    def test_deterministic_failure_stops_no_retry(self):
        with tempfile.TemporaryDirectory() as t:
            r, calls = self.make(t, {"data": "failed"})
            b = w(Path(t) / "ext/base.json", json.dumps({"schema": RM.MANIFEST_SCHEMA, "mode": "R"}))
            with self.assertRaises(RP.Stop):
                r.run(str(b))
            self.assertEqual(calls, ["env", "acquire", "data"])

    def test_infra_retry_bounded(self):
        with tempfile.TemporaryDirectory() as t:
            r, calls = self.make(t, {"env": "timeout"})
            b = w(Path(t) / "ext/base.json", json.dumps({"schema": RM.MANIFEST_SCHEMA, "mode": "R"}))
            with self.assertRaises(RP.Stop):
                r.run(str(b))
            self.assertEqual(calls, ["env", "env"])

    def test_budget(self):
        c = cfg()
        self.assertLessEqual(c["mode_f"]["stage_ceiling_s"], 14 * 3600)
        self.assertEqual(c["budgets"]["reproduction_seconds"], 15 * 3600)
        self.assertEqual(c["guard"]["threads"], 4); self.assertEqual(c["guard"]["storage_cap_gib"], 7.0)


class Experiment(unittest.TestCase):
    def test_missing_manifest_blocks(self):
        import experiment as EX
        with tempfile.TemporaryDirectory() as t:
            import recover
            fixture = cfg()
            fixture["mode_r"]["historical_manifest"] = str(Path(t) / "absent-manifest.json")
            config_path = w(Path(t) / "config.json", json.dumps(fixture))
            with patch.dict(os.environ, {"CELLTRANSFER_HISTORICAL_MANIFEST": ""}), patch.object(recover, "main", side_effect=AssertionError("Unit test must never launch recovery")):
                self.assertEqual(EX.main(["--config", str(config_path), "--output", str(Path(t) / "o")]), 3)
            self.assertFalse((Path(t) / "o/results.json").exists())


if __name__ == "__main__":
    unittest.main()

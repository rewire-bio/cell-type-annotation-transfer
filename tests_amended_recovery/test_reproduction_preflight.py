"""Configuration and budget regressions; no scientific execution."""
import json
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from reproduce import Repro, Stop

class ReproductionPreflight(unittest.TestCase):
    def test_recorded_config_resolves_approved_v2_without_mutation(self):
        cfg = json.loads((ROOT / "configs/full.json").read_text())
        before = json.dumps(cfg, sort_keys=True)
        r = Repro(ROOT, cfg)
        self.assertEqual(r.amendment["tolerances"], "protocol/tolerances-v2.json")
        self.assertEqual(json.dumps(cfg, sort_keys=True), before)

    def test_explicit_original_tolerances_rejected(self):
        cfg = json.loads((ROOT / "configs/full.json").read_text())
        cfg["amendment"]["tolerances"] = "protocol/tolerances.json"
        with self.assertRaises(Stop):
            Repro(ROOT, cfg)

    def test_combined_paper_budget_limits_next_step(self):
        cfg = json.loads((ROOT / "configs/full.json").read_text())
        seen = []
        r = Repro(ROOT, cfg, runner=lambda argv, name, timeout, cwd: seen.append(timeout) or {"status":"ok"}, now=lambda: 0)
        r.save = lambda: None
        r.paper_used = 1750
        r.step("paper_build", "paper", lambda _: ["synthetic"], mode_f=False, out=False)
        self.assertEqual(seen, [50])
        r.paper_used = 1800
        with self.assertRaises(Stop):
            r.step("paper_build", "paper", lambda _: ["synthetic"], mode_f=False, out=False)

    def test_comparison_consumes_remaining_f_budget(self):
        cfg = json.loads((ROOT / "configs/full.json").read_text())
        seen = []
        clock = [0.0]
        def runner(argv, name, timeout, cwd):
            seen.append(timeout)
            clock[0] += 2
            return {"status": "ok", "returncode": 0}
        r = Repro(ROOT, cfg, runner=runner, now=lambda: clock[0])
        r.save = lambda: None
        r.f_used = r.ceiling_f - 30
        r.step("compare", "compare", lambda _: ["synthetic"], out=False)
        self.assertEqual(seen, [30])
        self.assertEqual(r.f_used, r.ceiling_f - 28)

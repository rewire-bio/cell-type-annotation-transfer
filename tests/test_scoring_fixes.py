"""Stdlib tests for the M6 checkpoint relocation (run_matched.py) and the D-1a wiring (score_all.py)."""
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import ast
import types

# run_matched.py imports numpy/pandas at module level; extract the two stdlib helpers via ast so
# this test runs on the system python without the companion venv.
_src = (ROOT / "companion/scripts/run_matched.py").read_text()
_mod = ast.parse(_src)
_fns = [n for n in _mod.body if isinstance(n, ast.FunctionDef) and n.name in ("sha256_file", "relocate_scanvi_dir")]
RM = types.ModuleType("rm_helpers")
RM.__dict__.update({"json": json, "Path": Path})
exec(compile(ast.Module(body=_fns, type_ignores=[]), "run_matched.py", "exec"), RM.__dict__)


class TestM6Relocation(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp(dir=ROOT / "tests"))
        (self.d / "scanvi").mkdir()
        (self.d / "scanvi" / "model.pt").write_bytes(b"ckpt")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_uses_supplied_dir_and_verifies(self):
        hp = self.d / "exp.json"
        hp.write_text(json.dumps({"model.pt": hashlib.sha256(b"ckpt").hexdigest()}))
        info = {}
        got = RM.relocate_scanvi_dir(self.d, str(hp), info)
        self.assertEqual(got, self.d / "scanvi")
        self.assertTrue(info["scanvi_hashes_verified"])

    def test_mismatch_raises(self):
        hp = self.d / "exp.json"
        hp.write_text(json.dumps({"model.pt": "0" * 64}))
        with self.assertRaises(RuntimeError):
            RM.relocate_scanvi_dir(self.d, str(hp), {})

    def test_missing_dir_raises(self):
        shutil.rmtree(self.d / "scanvi")
        with self.assertRaises(FileNotFoundError):
            RM.relocate_scanvi_dir(self.d, None, {})


class TestD1aWiring(unittest.TestCase):
    """Static checks only: the numerical scoring path needs the companion venv and the data run."""

    def test_default_scope_natural_and_secondary_output(self):
        s = (ROOT / "companion/scripts/score_all.py").read_text()
        self.assertIn('"--natural-unknown-scope", choices=["natural", "all"], default="natural"', s)
        self.assertIn('unk_all[(unk_all.stratum == "natural").to_numpy()]', s)
        self.assertIn("unknowns_allstrata_secondary.csv", s)
        # Arm B simulated unknowns unchanged (all strata)
        self.assertIn('unk = tt[(tt.label_status == "mapped").to_numpy() & tt.target.isin(REMOVED_B).to_numpy()]', s)

    def test_historical_preserved(self):
        h = (ROOT / "historical/companion/scripts/score_all.py").read_text()
        self.assertNotIn("natural-unknown-scope", h)


if __name__ == "__main__":
    unittest.main()

"""Cross-component SYNTHETIC tests: the real build_cite_totalvi.py (acquire/eligibility/build with mocked
network, reference, loader and predictors) feeding result_manifest.parse_eligibility, recover.py's eligibility
reader and compare_runs' dynamic CITE expectation + T1 replacement checks.

No real inputs, predictions, network or model runs. All values are fabricated. Scratch lives in
tests_amended_recovery/_tmp and is deleted. Real-builder classes need numpy/pandas/scipy/pyarrow/anndata
(the pinned study venv); they are skipped otherwise and the skip is reported by unittest.
"""
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests_amended_recovery._support import HERE, ROOT, NAMES, PriorRunFixture, write_builder_records
import result_manifest as RM  # noqa: E402
import compare_runs as CR  # noqa: E402

B = RM.builder()
TMP = HERE / "_tmp"


def have(*mods):
    try:
        for m in mods:
            __import__(m)
        return True
    except Exception:
        return False


SCI = have("numpy", "pandas", "scipy", "pyarrow", "anndata")
PROT10K = B.PINS["totalvi_pbmc10k_protein_v3"]["proteins"]


def body(n, seed):
    return (b"\x89HDF\r\n\x1a\n" + hashlib.sha256(str(seed).encode()).digest() * (n // 32 + 1))[:n]


def syn_pins():
    out = {}
    for i, nb in enumerate((4096, 5120)):
        b = body(nb, i)
        out[f"syn{i}"] = {"file": f"syn{i}.h5ad", "sha256": hashlib.sha256(b).hexdigest(), "bytes": nb,
                          "shape": (100, 257), "proteins": PROT10K,
                          "feasibility": {"G": (255, 300), "F_A": (100, 100), "F_B": (120, 120)}, "_body": b}
    return out


class Resp:
    def __init__(self, b):
        self.b, self.status, self.headers = b, 200, {"Content-Type": "application/octet-stream",
                                                     "Content-Length": str(len(b))}

    def getcode(self):
        return 200

    def read(self, n=-1):
        r, self.b = (self.b, b"") if n is None or n < 0 else (self.b[:n], self.b[n:])
        return r

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def world(n_fail=(1, 1)):
    """Synthetic data run, census var and loader (same construction as the builder's own unit tests)."""
    import numpy as np
    import pandas as pd
    import scipy.sparse as sp
    eids = [f"ENSG{i:011d}" for i in range(1, 302)]
    census = pd.DataFrame({"soma_joinid": np.arange(301), "feature_id": [e + ".1" for e in eids],
                           "feature_name": [f"GENE{i}" for i in range(1, 301)] + ["MT-CO1"]})
    G = pd.DataFrame({"feature_id": eids[:300], "feature_name": [f"GENE{i}" for i in range(1, 301)]})
    mk = {c: eids[j * 3: j * 3 + 6] + eids[290:294] for j, c in enumerate(B.GATE_CLASSES)}
    meta = {"K": list(B.GATE_CLASSES) + ["pDC"], "K_B": list(B.GATE_CLASSES), "F_A": eids[:100],
            "F_B": eids[:120], "markers_A": {**mk, "pDC": eids[:10]}, "markers_B": mk}
    var = [f"GENE{i}" for i in range(1, 256)] + ["MT-CO1", "NOVEL"]
    rng = np.random.default_rng(7)
    data = {}
    for i in range(2):
        X = rng.poisson(3, (100, len(var))) + 1
        X[:, 255] = 1
        X[: n_fail[i], 5:] = 0
        obs = [f"cell{i}_{j:03d}-1" for j in range(100)]
        prot = pd.DataFrame(rng.poisson(20, (100, len(PROT10K))), index=obs, columns=PROT10K)
        data[f"syn{i}"] = {"X": sp.csr_matrix(X), "var_names": list(var), "obs_names": obs, "protein": prot,
                           "protein_key": "protein_expression"}
    return census, G, meta, data


def mock_predictors(calls):
    import numpy as np
    import pandas as pd

    def p1(X, syms):
        calls.append("P1")
        n = X.shape[0]
        return pd.DataFrame({"P1_celltypist_label": ["x"] * n, "P1_celltypist_conf": np.full(n, 0.9, np.float32),
                             "P1_celltypist_status": ["mapped"] * n, "P1_celltypist_target": ["NK"] * n,
                             "P1_celltypist_lineage": ["NK/ILC"] * n})

    def p2(XG):
        calls.append("P2")
        n = XG.shape[0]
        return pd.DataFrame({"P2_sctab_label": ["y"] * n, "P2_sctab_conf": np.full(n, 0.8, np.float32),
                             "P2_sctab_status": ["mapped"] * n, "P2_sctab_target": ["B"] * n,
                             "P2_sctab_lineage": ["B lineage"] * n})
    return p1, p2


def load_protein_check():
    import importlib.util
    s = importlib.util.spec_from_file_location("protein_check_frozen_it", ROOT / "companion/scripts/protein_check.py")
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def t1(o_dir, f_dir):
    """compare_runs T1 replacement items for two R4' directories (as wired in compare_runs.run)."""
    rep = CR.Report()
    eo, ef = CR.load_eligibility({"cite": o_dir}, "original"), CR.load_eligibility({"cite": f_dir}, "reproduction")
    CR.t1_eligibility(rep, {"cite": o_dir}, {"cite": f_dir}, eo, ef)
    return rep, eo, ef


def statuses(rep, tier="T1"):
    return {(c["check"], c["file"], c.get("details", {}).get("side") if isinstance(c.get("details"), dict)
             else c.get("side")): c["status"] for c in rep.checks if c["tier"] == tier}


@unittest.skipUnless(SCI, "pinned scientific stack (numpy/pandas/scipy/pyarrow/anndata) unavailable")
class RealBuilderIntoComparison(unittest.TestCase):
    """Real builder (mocked predictors) -> result_manifest/compare_runs; dynamic 0/1/2 and exact T1."""

    def setUp(self):
        TMP.mkdir(exist_ok=True)
        self.tmp = Path(tempfile.mkdtemp(prefix="builder-int-", dir=TMP))
        self.pins = syn_pins()
        self.patches = [mock.patch.object(B, "PINS", self.pins), mock.patch.object(B, "NAMES", list(self.pins))]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_builder(self, tag, n_fail):
        census, G, meta, data = world(n_fail)
        dr = self.tmp / f"data_{tag}"
        dr.mkdir()
        G.to_csv(dr / "gene_universe_G.csv", index=False)
        (dr / "features_and_classes.json").write_text(json.dumps(meta))
        out = self.tmp / f"r4_{tag}"
        out.mkdir()
        resp = [Resp(p["_body"]) for p in self.pins.values()]
        B.acquire(out, opener=lambda req, timeout=None: resp.pop(0))
        with mock.patch.object(B, "CENSUS_VAR_LOGICAL_SHA256", B.logical_var_digest(census)):
            B.eligibility(ROOT, dr, out, loader=lambda n: data[n], reference=census, pc=load_protein_check())
        calls = []
        B.build(ROOT, dr, out, loader=lambda n: data[n], predictors=mock_predictors(calls),
                write_query=B.real_write_query(ROOT), read_query=B.real_read_query)
        return out, calls

    def test_tolerances_v2_is_dynamic(self):
        tol = json.loads((ROOT / "protocol/tolerances-v2.json").read_text())
        self.assertEqual(CR.cite_expectation(tol), ("dynamic", None))

    def check_dynamic(self, n_fail, n_expected):
        o, calls = self.run_builder("o", n_fail)
        f, _ = self.run_builder("f", n_fail)
        el = RM.parse_eligibility(o / RM.ELIGIBILITY_FILE)
        self.assertEqual(el["n_eligible"], n_expected)
        self.assertEqual(el, RM.parse_eligibility(o))  # dir or file path
        exp = B.expected_cite_files(o)
        self.assertEqual((el["n_eligible"], el["eligible"], el["sha256"]),
                         (exp["n_eligible"], exp["eligible_files"], exp["eligibility_sha256"]))
        # the CITE file set compare_runs lists equals the eligible verdicts exactly
        self.assertEqual(CR.list_files(o, "released_predictions_"), el["eligible"])
        self.assertEqual(len(calls), 2 * n_expected)
        rep, eo, ef = t1(o, f)
        st = [c["status"] for c in rep.checks if c["tier"] == "T1"]
        self.assertTrue(st and all(s == "pass" for s in st), rep.checks)
        items = {c["check"] for c in rep.checks if c["tier"] == "T1"}
        self.assertTrue({"input_sha256_equals_pin", "eligibility_verdicts", "mapping_csv"} <= items)
        self.assertEqual("post_qc_barcodes" in items, n_expected > 0 or any(
            (o / f"barcodes_qc_{n}.txt").exists() for n in self.pins))
        summ = RM.protein_check_summary(el, self.tmp if n_expected else None)
        self.assertEqual(summ["status"], "run" if n_expected else "not_run")
        return o, f

    def test_dynamic_two_eligible(self):
        self.check_dynamic((1, 1), 2)

    def test_dynamic_one_eligible(self):
        self.check_dynamic((1, 3), 1)

    def test_dynamic_zero_eligible(self):
        self.check_dynamic((5, 5), 0)

    def test_verdict_difference_is_t1_breach(self):
        o, _ = self.run_builder("o", (1, 1))
        f, _ = self.run_builder("f", (1, 3))
        rep, _, _ = t1(o, f)
        bad = {c["check"] for c in rep.checks if c["tier"] == "T1" and c["status"] == "breach"}
        self.assertIn("eligibility_verdicts", bad)
        self.assertIn("post_qc_barcodes", bad)  # barcodes_qc_syn1 present in only one mode

    def test_barcode_mapping_and_pin_tamper_are_t1_breaches(self):
        o, _ = self.run_builder("o", (1, 1))
        f, _ = self.run_builder("f", (1, 1))
        (f / "barcodes_qc_syn0.txt").write_text((f / "barcodes_qc_syn0.txt").read_text().replace("cell0_001", "cellX"))
        with open(f / "mapping_syn1.csv", "a") as fh:
            fh.write("\n")
        acq = json.loads((o / "acquisition.json").read_text())
        acq["files"]["syn1"]["identity"]["sha256"] = "0" * 64
        (o / "acquisition.json").write_text(json.dumps(acq))
        rep, _, _ = t1(o, f)
        bad = {(c["check"], c["file"]) for c in rep.checks if c["tier"] == "T1" and c["status"] == "breach"}
        self.assertIn(("post_qc_barcodes", "syn0"), bad)
        self.assertIn(("mapping_csv", "syn1"), bad)
        self.assertIn(("input_sha256_equals_pin", "syn1"), bad)
        self.assertNotIn(("post_qc_barcodes", "syn1"), bad)

    def test_tampered_or_missing_record_is_structural(self):
        o, _ = self.run_builder("o", (1, 1))
        f, _ = self.run_builder("f", (1, 1))
        p = f / "eligibility.json"
        p.write_bytes(p.read_bytes().replace(b'"eligible"', b'"ineligible"', 1))
        with self.assertRaises(RM.ManifestError):
            RM.parse_eligibility(p)
        with self.assertRaises(CR.StructuralError):
            CR.load_eligibility({"cite": f}, "reproduction")
        (o / "eligibility.json.sha256").unlink()
        with self.assertRaises(CR.StructuralError):
            CR.load_eligibility({"cite": o}, "original")
        # the builder's own T1 helper (used by compare_runs) reports breaches, never skips
        rep = CR.Report()
        CR.t1_eligibility(rep, {"cite": o}, {"cite": f}, {"first_failing_criterion": {}},
                          {"first_failing_criterion": {}})
        recs = [c for c in rep.checks if c["check"] == "eligibility_record"]
        self.assertEqual(len(recs), 2)
        self.assertTrue(all(c["status"] == "breach" for c in recs))


class ExactSchemaRecords(unittest.TestCase):
    """Stdlib-only: records written in the exact builder schema by the shared fixture (real pins)."""

    def setUp(self):
        TMP.mkdir(exist_ok=True)
        self.d = Path(tempfile.mkdtemp(prefix="schema-", dir=TMP))

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_verdicts_and_criterion_shape(self):
        write_builder_records(self.d, {NAMES[0]: "ineligible:7"})
        el = RM.parse_eligibility(self.d / "eligibility.json")
        self.assertEqual(el["eligible"], [NAMES[1]])
        self.assertEqual(el["first_failing_criterion"], {NAMES[0]: {"number": 7, "name": B.CRITERIA[7]}})
        self.assertEqual(RM.postqc_barcodes_name(NAMES[1]), f"barcodes_qc_{NAMES[1]}.txt")
        self.assertTrue((self.d / RM.postqc_barcodes_name(NAMES[1])).is_file())

    def test_sidecar_required_and_bytes_checked(self):
        write_builder_records(self.d, {}, tamper="no_sidecar")
        with self.assertRaisesRegex(RM.ManifestError, "sha256"):
            RM.parse_eligibility(self.d / "eligibility.json")
        d2 = self.d / "b"
        d2.mkdir()
        write_builder_records(d2, {}, tamper="bytes")
        with self.assertRaisesRegex(RM.ManifestError, "does not match"):
            RM.parse_eligibility(d2)

    def test_missing_record(self):
        with self.assertRaises(RM.ManifestError):
            RM.parse_eligibility(self.d / "eligibility.json")


class RecoverUsesBuilderContract(PriorRunFixture):
    """recover.py invokes `build_cite_totalvi.py r4prime --workspace --data --out` and blocks on bad records."""

    def _run(self, elig, extra=()):
        import recover as R
        fake, st = self.fake_python(elig=elig)
        rc = R.main(self.args(fake, extra=extra))
        return rc, self.manifest(), [c for c in self.calls(st) if Path(c[0]).name == "build_cite_totalvi.py"]

    def test_cache_dir_is_forwarded(self):
        cache = self.d / "cache"
        cache.mkdir()
        rc, man, calls = self._run({}, extra=["--builder-cache-dir", str(cache)])
        self.assertEqual(man["status"], "complete")
        self.assertEqual(calls[0][1], "r4prime")
        self.assertEqual(calls[0][-2:], ["--cache-dir", str(cache.resolve())])

    def test_tampered_record_blocks(self):
        rc, man, _ = self._run({"__tamper__": "bytes"})
        self.assertNotEqual(man["status"], "complete")
        self.assertIn("no valid eligibility.json", man["blocker"])
        self.assertFalse(any(s["name"].startswith("A_M") and s["name"].endswith("_cite") for s in man["steps"]))

    def test_missing_sidecar_blocks(self):
        rc, man, _ = self._run({"__tamper__": "no_sidecar"})
        self.assertIn("no valid eligibility.json", man["blocker"])


if __name__ == "__main__":
    unittest.main()

"""E7 flow tests: acquisition (mocked network), eligibility-before-prediction, build schema, tolerances v2.

Every array and byte string is synthetic. The network is a recording mock; predictors are mocks.
No real model, data file or pipeline script is invoked.
"""
import hashlib
import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from _support import B, REPO, FakeResponse, Opener, have, load_protein_check, synthetic_bytes

NP = have("numpy", "pandas", "scipy", "pyarrow")
AD = NP and have("anndata")
PROT10K = B.PINS["totalvi_pbmc10k_protein_v3"]["proteins"]


def syn_pins(n_bytes=(4096, 5120), shapes=((100, 257), (100, 257)), feas=None):
    """Two synthetic files with the real 10k ADT names; feasibility totals match the synthetic data run."""
    feas = feas or {"G": (255, 300), "F_A": (100, 100), "F_B": (120, 120)}
    out = {}
    for i, (nb, sh) in enumerate(zip(n_bytes, shapes)):
        body = synthetic_bytes(nb, seed=i)
        out[f"syn{i}"] = {"file": f"syn{i}.h5ad", "sha256": hashlib.sha256(body).hexdigest(), "bytes": nb,
                          "shape": sh, "proteins": PROT10K, "feasibility": dict(feas), "_body": body}
    return out


class Patched(unittest.TestCase):
    """Swap the module pins for synthetic ones for the duration of each test."""

    pins_kwargs = {}

    def setUp(self):
        self.pins = syn_pins(**self.pins_kwargs)
        self.p1 = mock.patch.object(B, "PINS", self.pins)
        self.p2 = mock.patch.object(B, "NAMES", list(self.pins))
        self.p1.start()
        self.p2.start()
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name) / "r4"
        self.out.mkdir()

    def tearDown(self):
        self.p1.stop()
        self.p2.stop()
        self.tmp.cleanup()

    def ok_opener(self, ctype="application/octet-stream"):
        return Opener([FakeResponse(p["_body"], ctype=ctype) for p in self.pins.values()])


class Acquisition(Patched):
    def test_single_get_each_success(self):
        op = self.ok_opener()
        m = B.acquire(self.out, opener=op)
        self.assertEqual(op.calls, [B.url_for(n) for n in self.pins])  # exactly one request per file
        self.assertEqual(m["status"], "complete")
        self.assertEqual(m["retries"], 0)
        for n in self.pins:
            self.assertTrue(m["files"][n]["identity"]["pass"])
            self.assertEqual(m["files"][n]["requests"], 1)
        self.assertFalse(list(self.out.rglob("*.part")))
        self.assertEqual(json.loads((self.out / "acquisition.json").read_text())["status"], "complete")

    def test_hash_mismatch_fails_closed_for_that_file(self):
        bad = bytearray(self.pins["syn0"]["_body"])
        bad[100] ^= 1
        op = Opener([FakeResponse(bytes(bad)), FakeResponse(self.pins["syn1"]["_body"])])
        m = B.acquire(self.out, opener=op)
        i0 = m["files"]["syn0"]["identity"]
        self.assertFalse(i0["pass"])
        self.assertIn("sha256", i0["reason"])
        self.assertTrue(m["files"]["syn1"]["identity"]["pass"])
        self.assertEqual(len(op.calls), 2)  # no retry of the mismatching file

    def test_size_mismatch(self):
        op = Opener([FakeResponse(self.pins["syn0"]["_body"][:-1]), FakeResponse(self.pins["syn1"]["_body"])])
        m = B.acquire(self.out, opener=op)
        self.assertIn("byte count", m["files"]["syn0"]["identity"]["reason"])

    def test_html_response_fails(self):
        m = B.acquire(self.out, opener=self.ok_opener(ctype="text/html; charset=utf-8"))
        for n in self.pins:  # correct bytes but HTML content type: still never accepted
            self.assertFalse(m["files"][n]["identity"]["pass"])
            self.assertIn("HTML", m["files"][n]["identity"]["reason"])

    def test_html_body_and_lfs_pointer_fail(self):
        html = b"<!DOCTYPE html><html>challenge</html>"
        lfs = b"version https://git-lfs.github.com/spec/v1\noid sha256:abc\nsize 4096\n"
        m = B.acquire(self.out, opener=Opener([FakeResponse(html), FakeResponse(lfs)]))
        self.assertIn("HTML", m["files"]["syn0"]["identity"]["reason"])
        self.assertIn("LFS", m["files"]["syn1"]["identity"]["reason"])

    def test_http_error_ends_replacement_without_further_requests(self):
        err = urllib.error.HTTPError(B.url_for("syn0"), 403, "Forbidden", {}, None)
        op = Opener([err, FakeResponse(self.pins["syn1"]["_body"])])
        with self.assertRaises(B.R4Failure):
            B.acquire(self.out, opener=op)
        self.assertEqual(len(op.calls), 1)  # no retry, second file not requested, no alternate host
        m = json.loads((self.out / "acquisition.json").read_text())
        self.assertEqual(m["status"], "failed")
        self.assertIn("403", m["error"])
        self.assertFalse((self.out / "eligibility.json").exists())

    def test_non_200_and_timeout(self):
        with self.assertRaises(B.R4Failure):
            B.acquire(self.out, opener=Opener([FakeResponse(b"", status=206)]))
        out2 = self.out.parent / "r4b"
        out2.mkdir()
        with self.assertRaises(B.R4Failure):
            B.acquire(out2, opener=Opener([TimeoutError("timed out")]))

    def test_byte_cap(self):
        with mock.patch.object(B, "BYTE_CAP", 1000):
            with self.assertRaises(B.R4Failure):
                B.acquire(self.out, opener=self.ok_opener())
            out2 = self.out.parent / "r4c"
            out2.mkdir()
            with self.assertRaises(B.R4Failure):  # no Content-Length: enforced while streaming
                B.acquire(out2, opener=Opener([FakeResponse(self.pins["syn0"]["_body"], clen=False)]))
            self.assertFalse(list(out2.rglob("*.part")))

    def test_cached_bytes_no_network(self):
        cache = self.out.parent / "cache"
        cache.mkdir()
        for p in self.pins.values():
            (cache / p["file"]).write_bytes(p["_body"])
        op = Opener([])
        m = B.acquire(self.out, cache_dir=cache, opener=op)
        self.assertEqual(op.calls, [])
        for n, p in self.pins.items():
            r = m["files"][n]
            self.assertEqual((r["source"], r["requests"]), ("cached", 0))
            self.assertEqual(r["cache_path"], str(cache / p["file"]))
            self.assertTrue(r["identity"]["pass"])

    def test_cached_mismatch_fails_closed_without_get(self):
        cache = self.out.parent / "cache"
        cache.mkdir()
        (cache / "syn0.h5ad").write_bytes(b"x" + self.pins["syn0"]["_body"][1:])
        op = Opener([])
        with self.assertRaises(B.R4Failure):
            B.acquire(self.out, cache_dir=cache, opener=op)
        self.assertEqual(op.calls, [])
        self.assertFalse((self.out / "inputs/syn0.h5ad").exists())

    def test_refuses_existing_input(self):
        (self.out / "inputs").mkdir()
        (self.out / "inputs/syn0.h5ad").write_bytes(b"old")
        with self.assertRaises(B.R4Failure):
            B.acquire(self.out, opener=self.ok_opener())
        self.assertEqual((self.out / "inputs/syn0.h5ad").read_bytes(), b"old")


# ----------------------------------------------------------------------------- synthetic world
def world(n_cells=100, n_fail=(1, 1), drop_prot=None, marker_hits=6):
    """Synthetic data run + census var + loader. All values fabricated."""
    import numpy as np
    import pandas as pd
    import scipy.sparse as sp
    eids = [f"ENSG{i:011d}" for i in range(1, 302)]
    census = pd.DataFrame({"soma_joinid": np.arange(301), "feature_id": [e + ".1" for e in eids],
                           "feature_name": [f"GENE{i}" for i in range(1, 301)] + ["MT-CO1"]})
    G = pd.DataFrame({"feature_id": eids[:300], "feature_name": [f"GENE{i}" for i in range(1, 301)]})
    mk = {c: eids[j * 3: j * 3 + marker_hits] + eids[290:290 + 10 - marker_hits] for j, c in enumerate(B.GATE_CLASSES)}
    meta = {"K": list(B.GATE_CLASSES) + ["pDC"], "K_B": list(B.GATE_CLASSES), "F_A": eids[:100], "F_B": eids[:120],
            "markers_A": {**mk, "pDC": eids[:10]}, "markers_B": mk}
    var = [f"GENE{i}" for i in range(1, 256)] + ["MT-CO1", "NOVEL"]
    rng = np.random.default_rng(7)

    def loader_for(i):
        X = rng.poisson(3, (n_cells, len(var))) + 1
        X[:, 255] = 1
        X[: n_fail[i], 5:] = 0  # QC failures: too few detected genes
        obs = [f"cell{i}_{j:03d}-1" for j in range(n_cells)]
        cols = [c for c in PROT10K if c != drop_prot] if drop_prot else PROT10K
        prot = pd.DataFrame(rng.poisson(20, (n_cells, len(cols))), index=obs, columns=cols)
        return {"X": sp.csr_matrix(X), "var_names": list(var), "obs_names": obs, "protein": prot,
                "protein_key": "protein_expression"}

    data = {f"syn{i}": loader_for(i) for i in range(2)}
    return census, G, meta, data


def write_data_run(d: Path, G, meta):
    d.mkdir(parents=True, exist_ok=True)
    G.to_csv(d / "gene_universe_G.csv", index=False)
    (d / "features_and_classes.json").write_text(json.dumps(meta))


def mock_predictors(calls):
    import numpy as np
    import pandas as pd

    def p1(X, syms):
        calls.append(("P1", X.shape, len(syms)))
        n = X.shape[0]
        return pd.DataFrame({"P1_celltypist_label": ["x"] * n, "P1_celltypist_conf": np.full(n, 0.9, np.float32),
                             "P1_celltypist_status": ["mapped"] * n, "P1_celltypist_target": ["NK"] * n,
                             "P1_celltypist_lineage": ["NK/ILC"] * n})

    def p2(XG):
        calls.append(("P2", XG.shape, float(XG.sum())))
        n = XG.shape[0]
        return pd.DataFrame({"P2_sctab_label": ["y"] * n, "P2_sctab_conf": np.full(n, 0.8, np.float32),
                             "P2_sctab_status": ["mapped"] * n, "P2_sctab_target": ["B"] * n,
                             "P2_sctab_lineage": ["B lineage"] * n})
    return p1, p2


class EligBase(Patched):
    def run_elig(self, census, G, meta, data, digest_ok=True, acq_opener=None):
        dr = self.out.parent / "data"
        write_data_run(dr, G, meta)
        B.acquire(self.out, opener=acq_opener or self.ok_opener())
        pc = load_protein_check()
        dig = B.logical_var_digest(census) if digest_ok else "0" * 64
        with mock.patch.object(B, "CENSUS_VAR_LOGICAL_SHA256", dig):
            rec = B.eligibility(REPO, dr, self.out, loader=lambda n: data[n], reference=census, pc=pc)
        return dr, rec


@unittest.skipUnless(NP, "numpy/pandas/scipy/pyarrow unavailable")
class Eligibility(EligBase):
    def test_eligible_record_written_and_hashed_before_outputs(self):
        census, G, meta, data = world()
        before = set(sys.modules)
        dr, rec = self.run_elig(census, G, meta, data)
        self.assertNotIn("celltransfer.released", set(sys.modules) - before)
        self.assertNotIn("celltypist", set(sys.modules) - before)
        self.assertEqual(rec["n_eligible"], 2)
        self.assertEqual(rec["outcome"], "run")
        e = (self.out / "eligibility.json").read_bytes()
        self.assertEqual((self.out / "eligibility.json.sha256").read_text().split()[0], hashlib.sha256(e).hexdigest())
        # pre-outcome only: no query file, released prediction, adt table, gate or agreement
        for pat in ("query_*", "released_predictions_*", "adt_*", "protein_*", "gates.json"):
            self.assertEqual(list(self.out.glob(pat)), [], pat)
        r0 = rec["files"]["syn0"]
        self.assertEqual(r0["criteria"]["qc_retention"]["lost"], 1)
        self.assertEqual(r0["criteria"]["qc_retention"]["lost_barcodes"], ["cell0_000-1"])
        self.assertEqual(r0["criteria"]["coverage"]["G"]["fraction_exact"], "255/300")
        m = json.loads((self.out / "mapping_syn0.json").read_text())
        self.assertEqual(m["status_counts"]["mapped"], 256)  # GENE1..255 + MT-CO1
        self.assertEqual(m["status_counts"]["unmapped"], 1)
        self.assertEqual(m["difference_from_feasibility"]["G"]["present_minus_feasibility"], 0)
        bq = (self.out / "barcodes_qc_syn0.txt").read_text().splitlines()
        self.assertEqual(len(bq), 99)
        self.assertEqual(rec["deviation_log_lines"], [])

    def test_identity_failure_is_per_file(self):
        census, G, meta, data = world()
        bad = Opener([FakeResponse(b"\x89HDF\r\n\x1a\n" + b"0" * 100), FakeResponse(self.pins["syn1"]["_body"])])
        _, rec = self.run_elig(census, G, meta, data, acq_opener=bad)
        self.assertEqual(rec["files"]["syn0"]["first_failing_criterion"], {"number": 1, "name": "identity"})
        self.assertEqual(rec["files"]["syn0"]["criteria"]["structure"], {"pass": None, "not_evaluated": True})
        self.assertEqual(rec["eligible_files"], ["syn1"])
        self.assertEqual(rec["deviation_log_lines"], ["replacement ineligible: syn0.h5ad, criterion 1 (identity)"])
        self.assertFalse((self.out / "mapping_syn0.csv").exists())

    def test_input_changed_after_acquisition(self):
        census, G, meta, data = world()
        dr = self.out.parent / "data"
        write_data_run(dr, G, meta)
        B.acquire(self.out, opener=self.ok_opener())
        (self.out / "inputs/syn1.h5ad").write_bytes(b"tampered")
        with mock.patch.object(B, "CENSUS_VAR_LOGICAL_SHA256", B.logical_var_digest(census)):
            rec = B.eligibility(REPO, dr, self.out, loader=lambda n: data[n], reference=census, pc=load_protein_check())
        self.assertEqual(rec["files"]["syn1"]["first_failing_criterion"]["number"], 1)

    def test_reference_digest_failure_stops_both(self):
        census, G, meta, data = world()
        _, rec = self.run_elig(census, G, meta, data, digest_ok=False)
        for n in self.pins:
            self.assertEqual(rec["files"][n]["first_failing_criterion"]["number"], 3)
        self.assertEqual(rec["n_eligible"], 0)
        self.assertEqual(rec["outcome"], "not_run")

    def test_structure_failure(self):
        census, G, meta, data = world()
        data["syn1"]["obs_names"][1] = data["syn1"]["obs_names"][0]
        _, rec = self.run_elig(census, G, meta, data)
        self.assertEqual(rec["files"]["syn1"]["first_failing_criterion"]["number"], 2)
        self.assertFalse(rec["files"]["syn1"]["criteria"]["structure"]["checks"]["unique_barcodes"])

    def test_coverage_regression_failure(self):
        census, G, meta, data = world()
        # 1 G gene lost vs feasibility 255/300 is fine; drop 4 -> 251/300 < 255/300 - 0.01 = 252/300
        for i in range(4):
            data["syn0"]["var_names"][i] = f"RENAMED{i}"
        _, rec = self.run_elig(census, G, meta, data)
        r = rec["files"]["syn0"]
        self.assertEqual(r["first_failing_criterion"]["number"], 4)
        self.assertFalse(r["criteria"]["coverage"]["G"]["regression_ok"])
        self.assertTrue((self.out / "mapping_syn0.csv").exists())  # mapping recorded even when ineligible

    def test_marker_failure(self):
        census, G, meta, data = world(marker_hits=4)
        _, rec = self.run_elig(census, G, meta, data)
        self.assertEqual(rec["files"]["syn0"]["first_failing_criterion"]["number"], 5)

    def test_gate_failure(self):
        census, G, meta, data = world(drop_prot="CD56_TotalSeqB")
        for p in self.pins.values():
            p["proteins"] = [c for c in PROT10K if c != "CD56_TotalSeqB"]
        _, rec = self.run_elig(census, G, meta, data)
        r = rec["files"]["syn0"]
        self.assertEqual(r["first_failing_criterion"]["number"], 6)
        self.assertNotIn("NK", r["criteria"]["gate_availability"]["gates_available"])

    def test_qc_failure(self):
        census, G, meta, data = world(n_fail=(2, 1))
        _, rec = self.run_elig(census, G, meta, data)
        self.assertEqual(rec["files"]["syn0"]["first_failing_criterion"]["number"], 7)
        self.assertEqual(rec["files"]["syn0"]["criteria"]["qc_retention"]["max_lost_allowed"], 1)
        self.assertEqual(rec["eligible_files"], ["syn1"])

    def test_wrong_data_run_is_config_error(self):
        census, G, meta, data = world()
        meta["F_A"] = meta["F_A"][:-1]
        dr = self.out.parent / "data"
        write_data_run(dr, G, meta)
        B.acquire(self.out, opener=self.ok_opener())
        with self.assertRaises(B.ConfigError):
            B.eligibility(REPO, dr, self.out, loader=lambda n: data[n], reference=census, pc=load_protein_check())
        self.assertFalse((self.out / "eligibility.json").exists())

    def test_written_once(self):
        census, G, meta, data = world()
        dr, _ = self.run_elig(census, G, meta, data)
        with mock.patch.object(B, "CENSUS_VAR_LOGICAL_SHA256", B.logical_var_digest(census)):
            with self.assertRaises(B.R4Failure):
                B.eligibility(REPO, dr, self.out, loader=lambda n: data[n], reference=census, pc=load_protein_check())


@unittest.skipUnless(AD, "anndata unavailable")
class Build(EligBase):
    def build(self, dr, data, calls):
        return B.build(REPO, dr, self.out, loader=lambda n: data[n], predictors=mock_predictors(calls),
                       write_query=B.real_write_query(REPO), read_query=B.real_read_query)

    def test_no_prediction_when_none_eligible(self):
        census, G, meta, data = world(n_fail=(5, 5))
        dr, rec = self.run_elig(census, G, meta, data)
        self.assertEqual(rec["n_eligible"], 0)
        calls = []
        r = self.build(dr, data, calls)
        self.assertEqual(calls, [])
        self.assertEqual(r["outcome"], "not_run")
        self.assertEqual(list(self.out.glob("query_*")) + list(self.out.glob("released_*")), [])
        self.assertEqual(json.loads((self.out / "coverage.json").read_text())["n_eligible"], 0)

    def test_tampered_eligibility_blocks_build(self):
        census, G, meta, data = world()
        dr, _ = self.run_elig(census, G, meta, data)
        p = self.out / "eligibility.json"
        p.write_text(p.read_text().replace('"ineligible"', '"eligible"').replace('"n_eligible": 2', '"n_eligible": 2 '))
        calls = []
        with self.assertRaises(B.EligibilityRecordError):
            self.build(dr, data, calls)
        self.assertEqual(calls, [])
        (self.out / "eligibility.json.sha256").unlink()
        with self.assertRaises(B.EligibilityRecordError):
            self.build(dr, data, calls)

    def test_build_outputs_schema_and_alignment(self):
        import anndata as ad
        import numpy as np
        import pandas as pd
        census, G, meta, data = world(n_fail=(1, 3))  # syn1 ineligible (QC)
        dr, rec = self.run_elig(census, G, meta, data)
        self.assertEqual(rec["eligible_files"], ["syn0"])
        calls = []
        r = self.build(dr, data, calls)
        self.assertEqual(r["outcome"], "run")
        self.assertEqual(r["schema_errors"], [])
        # predictors called once, eligible file only; P1 gets all h5ad symbols, P2 the G-ordered matrix
        self.assertEqual([c[0] for c in calls], ["P2", "P1"])
        self.assertEqual(calls[1][1:], ((99, 257), 257))
        self.assertEqual(calls[0][1], (99, 300))
        self.assertFalse(list(self.out.glob("*syn1*.parquet")) + list(self.out.glob("query_syn1*")))
        q = ad.read_h5ad(self.out / "query_syn0_F.h5ad")
        F = sorted(set(meta["F_A"]) | set(meta["F_B"]))
        self.assertEqual(list(q.var_names), F)
        self.assertEqual(list(q.obs.columns), B.QUERY_OBS_COLUMNS)
        self.assertEqual(set(q.obs.assay), {"10x CITE-seq (totalVI-processed)"})
        keep = B.qc_mask(data["syn0"]["X"], data["syn0"]["var_names"])
        X = data["syn0"]["X"][keep].toarray()
        # raw counts preserved: query column for eid i == h5ad column GENE(i)
        self.assertTrue(np.array_equal(q.X.toarray()[:, 4], X[:, 4]))
        self.assertTrue(np.allclose(q.obs.total_counts_all.to_numpy(), X.sum(1)))
        self.assertTrue(np.allclose(q.obs.total_counts_G.to_numpy(), X[:, :255].sum(1)))  # MT-CO1/NOVEL not in G
        adt = pd.read_parquet(self.out / "adt_syn0.parquet")
        self.assertEqual(list(adt.columns), ["barcode"] + PROT10K)
        self.assertTrue(all(adt[c].dtype == np.int64 for c in PROT10K))
        self.assertEqual(adt.barcode.tolist(), q.obs.barcode.tolist())
        rp = pd.read_parquet(self.out / "released_predictions_syn0.parquet")
        self.assertEqual(rp.soma_joinid.tolist(), list(range(99)))
        rc = json.loads((self.out / "receipt.json").read_text())
        self.assertEqual(rc["files"]["syn0"]["source"], "get")
        self.assertEqual(rc["eligibility_sha256"], hashlib.sha256((self.out / "eligibility.json").read_bytes()).hexdigest())
        cov = json.loads((self.out / "coverage.json").read_text())
        self.assertEqual(cov["files"]["syn1"]["first_failing_criterion"]["number"], 7)
        self.assertEqual(cov["files"]["syn0"]["mapping"]["coverage"]["F_A"]["fraction_exact"], "100/100")
        self.assertTrue((self.out / "features_and_classes.json").exists())

    @unittest.skipUnless(have("sklearn"), "sklearn unavailable")
    def test_unchanged_protein_check_reads_outputs(self):
        """E6-synthetic subset: protein_check.py main() reads the synthetic builder outputs unmodified."""
        census, G, meta, data = world()
        dr, _ = self.run_elig(census, G, meta, data)
        self.build(dr, data, [])
        pc = load_protein_check()
        thr = self.out.parent / "thr.csv"
        thr.write_text("arm,method,tau_cov\npractical,P1,0.5\npractical,P2,0.5\n")
        empty = self.out.parent / "armA"
        empty.mkdir()
        pout = self.out.parent / "protein"
        argv = ["protein_check.py", "--workspace", str(REPO), "--cite", str(self.out), "--matched", f"A={empty}",
                "--thresholds", str(thr), "--out", str(pout)]
        with mock.patch.object(sys, "argv", argv), mock.patch("builtins.print"):
            pc.main()
        rows = pd_read(pout / "protein_agreement.csv")
        self.assertEqual(sorted(set(rows.file)), ["syn0", "syn1"])
        g = json.loads((pout / "gates.json").read_text())
        self.assertEqual(len(g["syn0"]["gates_available"]), 6)  # synthetic: values are meaningless, structure only

    def test_comparison_helpers(self):
        census, G, meta, data = world(n_fail=(1, 3))
        dr, _ = self.run_elig(census, G, meta, data)
        e = B.expected_cite_files(self.out)
        self.assertEqual((e["n_eligible"], e["eligible_files"]), (1, ["syn0"]))
        import shutil
        twin = self.out.parent / "twin"
        shutil.copytree(self.out, twin)
        res = B.t1_replacement_checks(self.out, twin)
        self.assertTrue(res and all(c["status"] == "pass" for c in res), res)
        # different post-QC barcodes -> T1 breach
        p = twin / "barcodes_qc_syn0.txt"
        p.write_text(p.read_text().replace("cell0_001-1", "cell0_xxx-1"))
        res = B.t1_replacement_checks(self.out, twin)
        self.assertEqual([c["item"] for c in res if c["status"] == "breach"], ["post_qc_barcodes"])
        # different verdict -> T1 breach (rewrite twin record consistently and re-hash it)
        rec = json.loads((twin / "eligibility.json").read_text())
        rec["files"]["syn0"]["verdict"] = "ineligible"
        rec["files"]["syn0"]["first_failing_criterion"] = {"number": 7, "name": "qc_retention"}
        rec["eligible_files"], rec["n_eligible"] = [], 0
        d = B.write_atomic(twin / "eligibility.json", B.canonical_json(rec))
        (twin / "eligibility.json.sha256").write_text(d + "  eligibility.json\n")
        res = B.t1_replacement_checks(self.out, twin)
        self.assertIn("eligibility_verdicts", [c["item"] for c in res if c["status"] == "breach"])
        # tampered record -> breach, never a silent skip
        (twin / "eligibility.json").write_text("{}")
        res = B.t1_replacement_checks(self.out, twin)
        self.assertEqual([(c["item"], c["status"]) for c in res], [("eligibility_record", "breach")])


def pd_read(p):
    import pandas as pd
    return pd.read_csv(p)


class Cli(unittest.TestCase):
    def test_plan_no_writes(self):
        with mock.patch("builtins.print") as pr:
            self.assertEqual(B.main(["plan"]), 0)
        self.assertIn("raw.githubusercontent.com", pr.call_args[0][0])

    @unittest.skipUnless(NP, "pandas unavailable")
    def test_config_error_before_any_request(self):
        import pandas as pd
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            (t / "data").mkdir()
            pd.DataFrame({"feature_id": ["E1"]}).to_csv(t / "data/gene_universe_G.csv", index=False)
            (t / "data/features_and_classes.json").write_text(json.dumps(
                {"K": [], "K_B": [], "F_A": [], "F_B": [], "markers_A": {}, "markers_B": {}}))
            with mock.patch.object(B.urllib.request, "urlopen", side_effect=AssertionError("network used")), \
                    mock.patch("sys.stderr"):
                rc = B.main(["r4prime", "--workspace", str(REPO), "--data", str(t / "data"), "--out", str(t / "r4"),
                             "--min-free-gib", "0"])
            self.assertEqual(rc, 3)
            self.assertFalse((t / "r4").exists())

    def test_disk_guard_before_any_request(self):
        with tempfile.TemporaryDirectory() as t, mock.patch("sys.stderr"):
            rc = B.main(["acquire", "--data", t, "--out", str(Path(t) / "r4"), "--min-free-gib", "1e9"])
        self.assertEqual(rc, 3)


class TolerancesV2(unittest.TestCase):
    def setUp(self):
        self.v1b = (REPO / "protocol/tolerances.json").read_bytes()
        self.v1 = json.loads(self.v1b)
        self.v2 = json.loads((REPO / "protocol/tolerances-v2.json").read_text())

    def test_v1_retained(self):
        self.assertEqual(hashlib.sha256(self.v1b).hexdigest(), self.v2["supersedes"]["sha256"])
        self.assertEqual(self.v1["T2_labels"]["expected_query_files"]["CITE"], 4)

    def test_only_specified_fields_change(self):
        allowed = {("schema",), ("source",), ("note",), ("T1_exact", "items"),
                   ("T2_labels", "expected_query_files", "CITE")}
        diffs = []

        def walk(a, b, p=()):
            if isinstance(a, dict):
                for k in a:
                    walk(a[k], b[k], p + (k,))
            elif a != b:
                diffs.append(p)
        walk(self.v1, self.v2)
        self.assertTrue(set(diffs) <= allowed, diffs)
        self.assertEqual(self.v2["T1_exact"]["items"][:len(self.v1["T1_exact"]["items"])], self.v1["T1_exact"]["items"])
        for it in ("replacement_input_sha256_equals_pins", "eligibility_verdicts", "mapping_csv", "post_qc_barcodes"):
            self.assertIn(it, self.v2["T1_exact"]["items"])
        self.assertEqual(self.v2["T2_labels"]["expected_query_files"]["CITE"]["rule"], "n_eligible")
        self.assertEqual(self.v2["T2_labels"]["expected_query_files"]["D"], 15)
        # no tier widened: every v1 numeric tolerance is present unchanged (walk above covers all v1 keys)
        self.assertEqual(self.v2["T2_protein_gating"]["allowed_formula"], self.v1["T2_protein_gating"]["allowed_formula"])


if __name__ == "__main__":
    unittest.main()

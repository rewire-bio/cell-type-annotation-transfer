"""E7 unit tests: pins, identities, mapping rules, criteria boundaries. Synthetic data only."""
import hashlib
import importlib.util
import json
import re
import unittest
import unittest.mock
from fractions import Fraction

from _support import B, REPO, have, load_protein_check

NP = have("numpy", "pandas", "scipy")


class Pins(unittest.TestCase):
    def test_amendment_hash_and_approval_record(self):
        got = hashlib.sha256((REPO / B.AMENDMENT_PATH).read_bytes()).hexdigest()
        self.assertEqual(got, B.AMENDMENT_SHA256)
        self.assertIn(B.AMENDMENT_SHA256, (REPO / B.APPROVAL_RECORD).read_text())

    def test_pins_equal_inspection_json(self):
        ins = json.loads((REPO / "evidence/protein-replacement/inspection.json").read_text())
        self.assertEqual(ins["revision"], B.COMMIT)
        by_file = {f["file"]: f for f in ins["files"]}
        feas = {f["file"]: f for f in ins["mapping_feasibility"]}
        for name, p in B.PINS.items():
            f = by_file[p["file"]]
            self.assertEqual(f["sha256"], p["sha256"])
            self.assertEqual(f["bytes"], p["bytes"])
            self.assertEqual((f["cells"], f["genes"]), p["shape"])
            self.assertEqual(f["proteins"], p["proteins"])
            self.assertEqual(tuple(f["protein_shape"]), (p["shape"][0], len(p["proteins"])))
            fz = feas[p["file"]]
            for k in ("G", "F_A", "F_B"):
                self.assertEqual(p["feasibility"][k], (fz[f"{k}_present"], fz[f"{k}_total"]))

    def test_pins_in_amendment_text(self):
        txt = (REPO / B.AMENDMENT_PATH).read_text()
        self.assertIn(B.COMMIT, txt)
        for name, p in B.PINS.items():
            self.assertIn(f"`{name}`", txt)
            self.assertIn(p["sha256"], txt)
            self.assertIn(f"{p['bytes']:,}", txt)
        self.assertEqual(len([p for p in B.PINS.values() if not any(c.startswith("IgG") for c in p["proteins"])]), 2)

    def test_url_is_commit_pinned_raw_only(self):
        for name, p in B.PINS.items():
            u = B.url_for(name)
            self.assertEqual(u, f"https://raw.githubusercontent.com/YosefLab/totalVI_reproducibility/"
                                f"{B.COMMIT}/data/{p['file']}")
        src = (REPO / "companion/scripts/build_cite_totalvi.py").read_text()
        self.assertNotIn("media.githubusercontent", src)

    def test_census_digest_constant_matches_acquire_inputs(self):
        src = (REPO / "scripts/acquire_inputs.py").read_text()
        self.assertIn(f'expected_logical = "{B.CENSUS_VAR_LOGICAL_SHA256}"', src)

    @unittest.skipUnless(NP, "numpy/pandas/scipy unavailable")
    def test_logical_digest_equals_acquire_inputs_function(self):
        import pandas as pd
        spec = importlib.util.spec_from_file_location("acq_t", REPO / "scripts/acquire_inputs.py")
        acq = importlib.util.module_from_spec(spec)
        import sys
        sys.modules["acq_t"] = acq
        spec.loader.exec_module(acq)
        df = pd.DataFrame({"soma_joinid": [2, 0, 1], "feature_id": ["ENSG3.1", "ENSG1.4", "ENSG2"],
                           "feature_name": ["C", "A", "B"], "extra": [1, 2, 3]})
        self.assertEqual(B.logical_var_digest(df), acq.logical_var_digest(df))

    def test_originals_untouched_by_builder(self):
        src = (REPO / "companion/scripts/build_cite_totalvi.py").read_text()
        for f in ("build_cite.py", "protein_check.py", "tolerances.json"):
            self.assertNotRegex(src, rf"open\([^)]*{re.escape(f)}[^)]*['\"]w")


@unittest.skipUnless(NP, "numpy/pandas/scipy unavailable")
class Mapping(unittest.TestCase):
    def idx(self, rows):
        import pandas as pd
        df = pd.DataFrame(rows, columns=["feature_id", "feature_name"])
        return B.census_symbol_index(df)

    def test_statuses(self):
        ix = self.idx([("ENSG1.3", "AAA"), ("ENSG2.1", "BBB"), ("ENSG3.1", "BBB"), ("ENSG4.1", "ccc"),
                       ("ENSG5.1", "EEE"), ("ENSG5.2", "EEE")])
        r = {x["var_name"]: x for x in B.map_symbols(["AAA", "BBB", "CCC", "ZZZ", "EEE"], ix)}
        self.assertEqual((r["AAA"]["status"], r["AAA"]["eid"]), ("mapped", "ENSG1"))  # version stripped
        self.assertEqual(r["BBB"]["status"], "ambiguous_census")
        self.assertEqual(r["BBB"]["census_eids"], "ENSG2;ENSG3")
        self.assertEqual(r["CCC"]["status"], "unmapped")  # case-sensitive: 'ccc' != 'CCC'
        self.assertEqual(r["ZZZ"]["status"], "unmapped")
        self.assertEqual((r["EEE"]["status"], r["EEE"]["eid"]), ("mapped", "ENSG5"))  # same eid, two versions

    def test_make_unique_groups(self):
        ix = self.idx([("ENSG1", "TBCE"), ("ENSG2", "TBCE-1"), ("ENSG3", "NKX2-1"), ("ENSG4", "LONE-1"),
                       ("ENSG5", "HLA-A"), ("ENSG6", "X"), ("ENSG7", "X-1-1")])
        names = ["TBCE", "TBCE-1", "TBCE-2", "NKX2-1", "LONE-1", "HLA-A", "X", "X-1", "X-1-1"]
        r = {x["var_name"]: x["status"] for x in B.map_symbols(names, ix)}
        for v in ("TBCE", "TBCE-1", "TBCE-2", "X", "X-1", "X-1-1"):
            self.assertEqual(r[v], "ambiguous_make_unique", v)
        self.assertEqual(r["NKX2-1"], "mapped")   # base 'NKX2' absent from the file
        self.assertEqual(r["LONE-1"], "mapped")   # lone suffix without its base: kept (residual risk, §5)
        self.assertEqual(r["HLA-A"], "mapped")    # non-digit suffix

    def test_collisions(self):
        ix = self.idx([("ENSG1", "OLD"), ("ENSG1", "NEW"), ("ENSG2", "OK")])
        r = {x["var_name"]: x for x in B.map_symbols(["OLD", "NEW", "OK"], ix)}
        self.assertEqual(r["OLD"]["status"], "ambiguous_collision")
        self.assertEqual(r["NEW"]["status"], "ambiguous_collision")
        self.assertEqual(r["OK"]["status"], "mapped")
        self.assertEqual(B.mapped_positions(list(r.values())), {"ENSG2": 2})

    def test_csv_deterministic_and_coverage(self):
        ix = self.idx([("E1", "A"), ("E2", "B"), ("E3", "C"), ("E4", 'Q,"x')])
        recs = B.map_symbols(["A", "B", "C", "D", 'Q,"x'], ix)
        meta = {"F_A": ["E1", "E9"], "F_B": ["E2"], "K": ["NK"], "K_B": ["NK"],
                "markers_A": {"NK": ["E1", "E2", "E9"]}, "markers_B": {"NK": ["E3"]}}
        a = B.mapping_csv(recs, meta, ["E1", "E2", "E3", "E9"])
        self.assertEqual(a, B.mapping_csv(B.map_symbols(["A", "B", "C", "D", 'Q,"x'], ix), meta, ["E1", "E2", "E3", "E9"]))
        lines = a.decode().splitlines()
        self.assertEqual(lines[0], "index,var_name,status,eid,census_eids,in_G,in_F_A,in_F_B")
        self.assertEqual(lines[1], "0,A,mapped,E1,E1,1,1,0")
        self.assertEqual(lines[4], "3,D,unmapped,,,0,0,0")
        self.assertEqual(lines[5], '4,"Q,""x",mapped,E4,E4,0,0,0')
        with unittest.mock.patch.dict(B.PINS, {"syn": {"feasibility": {"G": (3, 4), "F_A": (1, 2), "F_B": (1, 1)}}}):
            cov = B.coverage(recs, meta, ["E1", "E2", "E3", "E9"], "syn")
        self.assertEqual(cov["coverage"]["G"]["fraction_exact"], "3/4")
        self.assertEqual(cov["coverage"]["F_A"]["fraction_exact"], "1/2")
        self.assertEqual(cov["per_class_marker_coverage"]["K"]["NK"], {"mapped": 2, "listed": 3})
        self.assertEqual(cov["status_counts"]["unmapped"], 1)
        self.assertEqual(cov["excluded_var_names"]["unmapped"], ["D"])

    def test_mapping_csv_roundtrip(self):
        import tempfile
        from pathlib import Path
        ix = self.idx([("E1", "A"), ("E2", "B"), ("E2", "C")])
        recs = B.map_symbols(["A", "B", "C", "Z"], ix)
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "m.csv"
            p.write_bytes(B.mapping_csv(recs, {"F_A": [], "F_B": []}, ["E1"]))
            back = B.mapping_from_csv(p)
        self.assertEqual(B.mapped_positions(back), B.mapped_positions(recs))
        self.assertEqual([r["status"] for r in back], [r["status"] for r in recs])


class Criteria(unittest.TestCase):
    def cov(self, name, **present):
        tot = {k: v[1] for k, v in B.PINS[name]["feasibility"].items()}
        c = {k: {"present": present.get(k, B.PINS[name]["feasibility"][k][0]), "total": tot[k]} for k in tot}
        return {"coverage": c}

    def test_feasibility_counts_pass(self):
        for name in B.PINS:
            ok, _ = B.check_coverage(self.cov(name), name)
            self.assertTrue(ok, name)

    def test_regression_boundary_exact(self):
        n = "totalvi_pbmc5k_protein_v3"  # F_A 1565/2020: limit 1544.8/2020
        self.assertTrue(B.check_coverage(self.cov(n, F_A=1545), n)[0])
        ok, d = B.check_coverage(self.cov(n, F_A=1544), n)
        self.assertFalse(ok)
        self.assertTrue(d["F_A"]["floor_ok"])
        self.assertFalse(d["F_A"]["regression_ok"])
        # G 12957/19331: limit 12763.69
        self.assertTrue(B.check_coverage(self.cov(n, G=12764), n)[0])
        self.assertFalse(B.check_coverage(self.cov(n, G=12763), n)[0])

    def test_floor_boundary_exact(self):
        # floors applied with feasibility patched low so only the floor binds
        with unittest.mock.patch.dict(B.PINS, {"syn": {"feasibility": {"G": (1, 100), "F_A": (1, 100), "F_B": (1, 100)}}}):
            c = lambda fa, g: {"coverage": {"F_A": {"present": fa, "total": 2020}, "F_B": {"present": 1512, "total": 2016},  # noqa
                                            "G": {"present": g, "total": 19331}}}
            self.assertTrue(B.check_coverage(c(1515, 11599), "syn")[0])   # 1515/2020 == 0.75 exactly
            self.assertFalse(B.check_coverage(c(1514, 11599), "syn")[0])
            self.assertFalse(B.check_coverage(c(1515, 11598), "syn")[0])  # 0.6*19331 = 11598.6
        self.assertEqual(B.COVERAGE_FLOORS, {"F_A": Fraction(3, 4), "F_B": Fraction(3, 4), "G": Fraction(3, 5)})
        self.assertEqual(B.MAX_DROP_BELOW_FEASIBILITY, Fraction(1, 100))

    def test_marker_coverage(self):
        recs = [{"index": i, "var_name": f"S{i}", "status": "mapped", "eid": f"E{i}"} for i in range(5)]
        mk = {c: [f"E{i}" for i in range(10)] for c in B.GATE_CLASSES}
        meta = {"K": list(B.GATE_CLASSES) + ["pDC"], "markers_A": {**mk, "pDC": ["X"]}}
        ok, d = B.check_markers(recs, meta)
        self.assertTrue(ok)  # 5 of 10 mapped; pDC is not a gate class
        self.assertFalse(B.check_markers(recs[:4], meta)[0])
        meta2 = {"K": [c for c in B.GATE_CLASSES if c != "NK"], "markers_A": mk}
        ok, d = B.check_markers(recs, meta2)
        self.assertFalse(ok)
        self.assertFalse(d["NK"]["pass"])

    @unittest.skipUnless(NP, "numpy/pandas unavailable")
    def test_gate_availability_real_names(self):
        pc = load_protein_check()
        for name, p in B.PINS.items():
            ok, d = B.gate_availability(p["proteins"], pc.MARKERS, pc.find)
            self.assertTrue(ok, name)
            self.assertEqual(d["antibodies_found"]["CD8"], "CD8a_TotalSeqB")
            self.assertEqual(d["antibodies_found"]["CD4"], "CD4_TotalSeqB")  # not CD45RA/RO
        cols = [c for c in B.PINS["totalvi_pbmc10k_protein_v3"]["proteins"] if not c.startswith("CD14")]
        ok, d = B.gate_availability(cols, pc.MARKERS, pc.find)
        self.assertFalse(ok)
        self.assertEqual(d["gates_available"], ["CD4 T", "CD8 T", "B"])
        cols = [c for c in B.PINS["totalvi_pbmc5k_protein_v3"]["proteins"] if not c.startswith("CD19")]
        ok, d = B.gate_availability(cols, pc.MARKERS, pc.find)
        self.assertTrue(ok)
        self.assertIn("CD20 substitute", d["antibodies_found"]["CD19"])

    @unittest.skipUnless(have("numpy", "pandas", "sklearn"), "sklearn unavailable")
    def test_gate_requirements_equal_protein_check(self):
        """Transcribed GATE_REQUIRES must equal protein_check.gate_cells on synthetic counts."""
        import itertools
        import numpy as np
        import pandas as pd
        pc = load_protein_check()
        base = ["CD3_x", "CD4_x", "CD8a_x", "CD14_x", "CD16_x", "CD19_x", "CD56_x"]
        rng = np.random.default_rng(0)
        for drop in itertools.chain([()], itertools.combinations(base, 1), itertools.combinations(base, 2)):
            cols = [c for c in base if c not in drop] + ["OTHER"]
            adt = pd.DataFrame(rng.poisson(5, (60, len(cols))) * rng.integers(0, 2, (60, len(cols))), columns=cols)
            adt.insert(0, "barcode", [f"b{i}" for i in range(60)])
            _, _, gates = pc.gate_cells(adt)
            _, d = B.gate_availability(cols, pc.MARKERS, pc.find)
            self.assertEqual(d["gates_available"], gates, drop)


@unittest.skipUnless(NP, "numpy/scipy unavailable")
class QCAndStructure(unittest.TestCase):
    def matrix(self, n_cells, n_fail, n_genes=210):
        import numpy as np
        import scipy.sparse as sp
        X = np.ones((n_cells, n_genes), dtype=np.int64)
        X[:n_fail, 10:] = 0  # 10 detected genes < 200
        return sp.csr_matrix(X), [f"G{i}" for i in range(n_genes)]

    def test_qc_retention_boundary_5k(self):
        X, v = self.matrix(3994, 39)
        keep = B.qc_mask(X, v)
        self.assertEqual(int(keep.sum()), 3955)
        self.assertGreaterEqual(Fraction(int(keep.sum()), 3994), B.QC_MIN_RETENTION)
        X, v = self.matrix(3994, 40)
        self.assertLess(Fraction(int(B.qc_mask(X, v).sum()), 3994), B.QC_MIN_RETENTION)

    def test_qc_retention_boundary_10k(self):
        X, v = self.matrix(6855, 68)
        self.assertGreaterEqual(Fraction(int(B.qc_mask(X, v).sum()), 6855), B.QC_MIN_RETENTION)
        X, v = self.matrix(6855, 69)
        self.assertLess(Fraction(int(B.qc_mask(X, v).sum()), 6855), B.QC_MIN_RETENTION)

    def test_qc_genes_and_mito(self):
        import numpy as np
        import scipy.sparse as sp
        v = ["MT-CO1", "mt-nd1"] + [f"G{i}" for i in range(250)]
        X = np.zeros((4, 252))
        X[:, 2:202] = 1  # 200 detected non-MT genes, 200 counts
        X[1, 0] = 49     # 49/249 = 0.197 -> kept
        X[2, 0] = 25
        X[2, 1] = 25     # 50/250 = 0.20 -> dropped (strict <)
        X[3, 2] = 0      # 199 detected genes -> dropped
        self.assertEqual(B.qc_mask(sp.csr_matrix(X), v).tolist(), [True, True, False, False])

    def test_integer_checks_and_counts(self):
        import numpy as np
        import scipy.sparse as sp
        self.assertTrue(B.is_nonneg_integer(sp.csr_matrix(np.array([[0, 2.0], [3, 0]]))))
        self.assertFalse(B.is_nonneg_integer(sp.csr_matrix(np.array([[0, 2.5]]))))
        self.assertFalse(B.is_nonneg_integer(np.array([[-1, 2]])))
        self.assertFalse(B.is_nonneg_integer(np.array([[np.nan, 2]])))
        c = B.to_counts(np.array([[0, 2], [3, 0]], dtype=np.int64))
        self.assertEqual(c.dtype, np.float32)
        self.assertEqual(c.toarray().tolist(), [[0, 2], [3, 0]])
        with self.assertRaises(ValueError):
            B.to_counts(np.array([[0.5]]))

    def test_g_matrix_zero_fill_order(self):
        import numpy as np
        import scipy.sparse as sp
        recs = [{"index": 0, "status": "mapped", "eid": "E2"}, {"index": 1, "status": "unmapped", "eid": None},
                {"index": 2, "status": "mapped", "eid": "E1"}, {"index": 3, "status": "ambiguous_collision", "eid": "E3"}]
        X = sp.csr_matrix(np.array([[1, 2, 3, 4], [5, 6, 7, 8]], dtype=np.float32))
        XG, n = B.g_matrix(X, recs, ["E1", "E2", "E3", "E4"])
        self.assertEqual(n, 2)
        self.assertEqual(XG.toarray().tolist(), [[3, 1, 0, 0], [7, 5, 0, 0]])

    def _data(self, **over):
        import numpy as np
        import pandas as pd
        import scipy.sparse as sp
        prot = ["CD3_TotalSeqB", "CD4_TotalSeqB"]
        obs = ["a", "b", "c"]
        d = {"X": sp.csr_matrix(np.ones((3, 4))), "var_names": ["A", "B", "C", "D"], "obs_names": obs,
             "protein": pd.DataFrame(np.ones((3, 2), dtype=int), index=obs, columns=prot), "protein_key": "k"}
        d.update(over)
        return d

    def test_structure_checks(self):
        import numpy as np
        import pandas as pd
        pin = {"syn": {"shape": (3, 4), "proteins": ["CD3_TotalSeqB", "CD4_TotalSeqB"]}}
        with unittest.mock.patch.dict(B.PINS, pin):
            self.assertTrue(B.check_structure(self._data(), "syn")[0])
            bad = {
                "rna_shape": self._data(var_names=["A", "B", "C"], X=self._data()["X"][:, :3]),
                "unique_barcodes": self._data(obs_names=["a", "a", "c"]),
                "protein_names_in_order": self._data(protein=pd.DataFrame(np.ones((3, 2), dtype=int), index=["a", "b", "c"],
                                                                          columns=["CD4_TotalSeqB", "CD3_TotalSeqB"])),
                "protein_nonnegative_integer": self._data(protein=pd.DataFrame(np.full((3, 2), 0.5), index=["a", "b", "c"],
                                                                               columns=pin["syn"]["proteins"])),
                "rna_nonnegative_integer": self._data(X=self._data()["X"] * 0.5),
            }
            for key, d in bad.items():
                ok, det = B.check_structure(d, "syn")
                self.assertFalse(ok, key)
                self.assertFalse(det["checks"][key], key)
        pin_igg = {"syn": {"shape": (3, 4), "proteins": ["CD3_TotalSeqB", "IgG1_ctrl"]}}
        with unittest.mock.patch.dict(B.PINS, pin_igg):
            d = self._data(protein=pd.DataFrame(np.ones((3, 2), dtype=int), index=["a", "b", "c"],
                                                columns=["CD3_TotalSeqB", "IgG1_ctrl"]))
            ok, det = B.check_structure(d, "syn")
            self.assertFalse(det["checks"]["no_IgG"])

    @unittest.skipUnless(have("anndata"), "anndata unavailable")
    def test_locate_protein_by_names_only(self):
        import anndata as ad
        import numpy as np
        import pandas as pd
        names = ["CD3_TotalSeqB", "CD4_TotalSeqB"]
        obs = pd.DataFrame(index=["a", "b", "c"])
        with unittest.mock.patch.dict(B.PINS, {"syn": {"proteins": names}}):
            a = ad.AnnData(np.ones((3, 2)), obs=obs)
            a.obsm["protein_expression"] = pd.DataFrame(np.arange(6).reshape(3, 2), index=obs.index, columns=names)
            p, k = B.locate_protein(a, "syn")
            self.assertEqual(k, "protein_expression")
            self.assertEqual(p.to_numpy().tolist(), [[0, 1], [2, 3], [4, 5]])
            a.obsm["copy"] = a.obsm["protein_expression"].copy()  # two candidates -> fail closed
            p, k = B.locate_protein(a, "syn")
            self.assertIsNone(p)
            b = ad.AnnData(np.ones((3, 2)), obs=obs)
            b.obsm["prot"] = np.ones((3, 2))
            b.uns["protein_names"] = names
            p, k = B.locate_protein(b, "syn")
            self.assertEqual(k, "prot")
            b.uns["protein_names"] = names[::-1]  # wrong order -> not found
            self.assertIsNone(B.locate_protein(b, "syn")[0])


if __name__ == "__main__":
    unittest.main()

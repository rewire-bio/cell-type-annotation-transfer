"""Standard-library tests for scripts/acquire_inputs.py. No network: retrieval is mocked.
Run: python -m unittest discover -s tests_acquisition -v
Temporary files are created under tests_acquisition/.tmp (removed afterwards)."""
import dataclasses
import hashlib
import io
import json
import shutil
import sys
import unittest
import urllib.error
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import acquire_inputs as A  # noqa: E402

PAYLOAD = b"hello pinned world\n" * 100
SHA = hashlib.sha256(PAYLOAD).hexdigest()


class Resp:
    def __init__(self, body, status=200, ctype="application/octet-stream", clen=True):
        self._b = io.BytesIO(body)
        self.status = status
        self.headers = {"Content-Type": ctype}
        if clen:
            self.headers["Content-Length"] = str(len(body))

    def read(self, n=-1):
        return self._b.read(n)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def opener_seq(*responses):
    calls = []

    def op(url, timeout):
        calls.append(url)
        r = responses[min(len(calls) - 1, len(responses) - 1)]
        if isinstance(r, Exception):
            raise r
        return r
    op.calls = calls
    return op


def item(**kw):
    base = dict(id="t", dest="runs/data/x.bin", kind="url", url="https://example.org/x.bin", sha256=SHA,
                size=len(PAYLOAD), max_bytes=10_000, url_provenance="test", hash_provenance="test",
                licence="unknown", cache_relpath="c/x.bin")
    base.update(kw)
    return A.Item(**base)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = HERE / ".tmp" / self._testMethodName
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = self.tmp / "root"
        self.cache = self.tmp / "cache"
        self.root.mkdir(parents=True)
        self.cache.mkdir(parents=True)
        A.ITEMS_BY_ID.setdefault("t", item())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        try:
            (HERE / ".tmp").rmdir()
        except OSError:
            pass


class TestHashing(Base):
    def test_sha256_known_vector(self):
        p = self.tmp / "abc"
        p.write_bytes(b"abc")
        self.assertEqual(A.sha256_file(p),
                         "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")


class TestDownload(Base):
    def test_success_atomic(self):
        dest = self.root / "a/b.bin"
        n, errs = A.download("https://x/y", dest, SHA, len(PAYLOAD), 10_000, opener=opener_seq(Resp(PAYLOAD)))
        self.assertEqual((n, errs), (1, []))
        self.assertEqual(dest.read_bytes(), PAYLOAD)
        self.assertFalse(dest.with_name("b.bin.part").exists())

    def test_hash_mismatch_no_file_no_retry(self):
        dest = self.root / "b.bin"
        op = opener_seq(Resp(PAYLOAD + b"x"))
        with self.assertRaises(A.AcquireError):
            A.download("https://x/y", dest, SHA, None, 10_000, opener=op, sleep=lambda s: None)
        self.assertFalse(dest.exists())
        self.assertFalse(dest.with_name("b.bin.part").exists())
        self.assertEqual(len(op.calls), 1)

    def test_bounded_retry_then_success(self):
        dest = self.root / "c.bin"
        sleeps = []
        op = opener_seq(urllib.error.URLError("boom"), Resp(PAYLOAD))
        n, errs = A.download("https://x/y", dest, SHA, len(PAYLOAD), 10_000, opener=op, sleep=sleeps.append)
        self.assertEqual(n, 2)
        self.assertEqual(len(errs), 1)
        self.assertEqual(sleeps, [2.0])

    def test_retries_exhausted(self):
        op = opener_seq(urllib.error.URLError("down"))
        with self.assertRaises(A.AcquireError):
            A.download("https://x/y", self.root / "d", SHA, None, 10_000, attempts=3, opener=op,
                       sleep=lambda s: None)
        self.assertEqual(len(op.calls), 3)

    def test_size_cap_content_length_and_stream(self):
        with self.assertRaises(A.AcquireError):
            A.download("https://x/y", self.root / "e", SHA, None, 10, attempts=1, opener=opener_seq(Resp(PAYLOAD)))
        with self.assertRaises(A.AcquireError):
            A.download("https://x/y", self.root / "f", SHA, None, 10, attempts=1,
                       opener=opener_seq(Resp(PAYLOAD, clen=False)))
        self.assertFalse((self.root / "f.part").exists())

    def test_html_challenge_not_bypassed(self):
        op = opener_seq(Resp(b"<html>challenge</html>", ctype="text/html"))
        with self.assertRaises(A.AcquireError) as cm:
            A.download("https://x/y", self.root / "g", SHA, None, 10_000, opener=op, sleep=lambda s: None)
        self.assertIn("not bypassed", str(cm.exception))
        self.assertEqual(len(op.calls), 1)

    def test_http_404_not_retried(self):
        op = opener_seq(urllib.error.HTTPError("https://x/y", 404, "nf", {}, None))
        with self.assertRaises(A.AcquireError):
            A.download("https://x/y", self.root / "h", SHA, None, 10_000, opener=op, sleep=lambda s: None)
        self.assertEqual(len(op.calls), 1)

    def test_only_https(self):
        with self.assertRaises(A.AcquireError):
            A._open("http://example.org/x", 1)


class TestAcquire(Base):
    def test_cache_fallback_labelled(self):
        (self.cache / "c").mkdir()
        (self.cache / "c/x.bin").write_bytes(PAYLOAD)
        recs = A.acquire(self.root, [item()], HERE, self.cache, allow_cache=True,
                         opener=opener_seq(urllib.error.URLError("down")), sleep=lambda s: None)
        self.assertEqual(recs[0].status, "cached-third-party-fallback")
        self.assertTrue(recs[0].source.startswith("cache:"))
        self.assertEqual((self.root / "runs/data/x.bin").read_bytes(), PAYLOAD)

    def test_cache_fallback_requires_flag_and_hash(self):
        (self.cache / "c").mkdir()
        (self.cache / "c/x.bin").write_bytes(b"tampered")
        recs = A.acquire(self.root, [item()], HERE, self.cache, allow_cache=False,
                         opener=opener_seq(urllib.error.URLError("down")), sleep=lambda s: None)
        self.assertEqual(recs[0].status, "failed")
        recs = A.acquire(self.root, [item()], HERE, self.cache, allow_cache=True,
                         opener=opener_seq(urllib.error.URLError("down")), sleep=lambda s: None)
        self.assertEqual(recs[0].status, "failed")
        self.assertFalse((self.root / "runs/data/x.bin").exists())

    def test_dry_run_no_writes_no_network(self):
        op = opener_seq(AssertionError("network used"))
        recs = A.acquire(self.root, [item()], HERE, dry_run=True, opener=op)
        self.assertEqual(recs[0].status, "planned")
        self.assertEqual(op.calls, [])
        self.assertEqual(list(self.root.iterdir()), [])

    def test_verified_existing_skips_network(self):
        d = self.root / "runs/data/x.bin"
        d.parent.mkdir(parents=True)
        d.write_bytes(PAYLOAD)
        op = opener_seq(AssertionError("network used"))
        recs = A.acquire(self.root, [item()], HERE, opener=op)
        self.assertEqual(recs[0].status, "verified-existing")

    def test_dest_escape_rejected(self):
        with self.assertRaises(A.AcquireError):
            A.safe_dest(self.root, "../outside")

    def test_cache_inside_root_rejected(self):
        with self.assertRaises(A.AcquireError):
            A.acquire(self.root, [item()], HERE, self.root / "cache", allow_cache=True)

    def test_storage_cap(self):
        with self.assertRaises(A.AcquireError):
            A.acquire(self.root, [item(size=A.STORAGE_CAP_BYTES + 1)], HERE, dry_run=True)

    def test_repo_copy_label_map(self):
        repo = self.tmp / "repo"
        (repo / "m").mkdir(parents=True)
        (repo / "m/l.csv").write_bytes(PAYLOAD)
        it = item(kind="repo-copy", url=None, dest="evidence/label-maps/l.csv", source_relpath="m/l.csv")
        recs = A.acquire(self.root, [it], repo)
        self.assertEqual(recs[0].status, "copied")

    def test_manifest_written_atomically(self):
        recs = A.acquire(self.root, [item()], HERE, dry_run=True)
        p = A.write_manifest(self.root, recs, dry_run=True)
        doc = json.loads(p.read_text())
        self.assertTrue(doc["dry_run"])
        self.assertEqual(doc["items"][0]["url"], "https://example.org/x.bin")


class TestRegistry(unittest.TestCase):
    def test_required_build_data_paths_present(self):
        dests = {i.dest for i in A.ITEMS}
        for p in ["evidence/label-maps/census_blood_author_labels.csv", "evidence/label-maps/sctab_164_labels.csv",
                  "evidence/label-maps/celltypist_immune_all_low_v2.csv", "runs/data/census_2025-11-08_var.parquet",
                  "evidence/probes/P01-census-blood-obs-20261005/sctab_var.parquet",
                  "runs/data/downloads/sctab_val_f1_macro_epoch41.ckpt",
                  "evidence/probes/P00-metadata-20261005/hf-hparams.yaml",
                  "runs/data/models/celltypist/Immune_All_Low.pkl"]:
            self.assertIn(p, dests)

    def test_pins_well_formed(self):
        for i in A.ITEMS:
            if i.kind != "census-var":
                self.assertRegex(i.sha256, r"^[0-9a-f]{64}$")
            if i.kind == "url":
                self.assertTrue(i.url.startswith("https://"))
                self.assertIn(A.HF_REV, i.url) if i.third_party else None
            self.assertTrue(i.licence)
            self.assertLessEqual(i.size or 0, i.max_bytes)

    def test_repo_label_maps_match_pins(self):
        repo = HERE.parent
        for i in A.ITEMS:
            if i.kind == "repo-copy":
                self.assertEqual(A.sha256_file(repo / i.source_relpath), i.sha256, i.id)

    def test_logical_digest_order_invariant(self):
        try:
            import pandas as pd
        except ImportError:
            self.skipTest("pandas not available")
        a = pd.DataFrame({"soma_joinid": [1, 0], "feature_id": ["E1", "E0"], "feature_name": ["b", "a"],
                          "extra": [1, 2]})
        b = a.iloc[::-1].drop(columns="extra")
        self.assertEqual(A.logical_var_digest(a), A.logical_var_digest(b))

    def test_cli_list(self):
        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            self.assertEqual(A.main(["list"]), 0)
        finally:
            sys.stdout = old
        self.assertEqual(len(json.loads(buf.getvalue())), len(A.ITEMS))


if __name__ == "__main__":
    unittest.main()

"""Synthetic tests for scripts/resource_guard.py and scripts/recover.py (stdlib only).

Run: python3 -m unittest discover -s tests -v
All scratch output goes under tests/_tmp/ (removed on success).
"""
import hashlib
import json
import os
import shutil
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import resource_guard as RG  # noqa: E402
import recover as R  # noqa: E402

TMP = ROOT / "tests" / "_tmp"
PY = sys.executable
MiB = 1 << 20
ALLOC = ("import sys,time\nn=int(sys.argv[1]);b=bytearray(n)\n"
         "for i in range(0,n,4096): b[i]=1\ntime.sleep(float(sys.argv[2]))\n")
NOSPACE = dict(disk_start_min=0, disk_run_min=0)


class Base(unittest.TestCase):
    def setUp(self):
        self.d = TMP / f"{self.id().split('.')[-1]}-{time.time_ns()}"
        self.d.mkdir(parents=True)

    def guard(self, cmd, **kw):
        k = dict(attempt_root=self.d / "att", name="s", mem_poll=0.2, disk_poll=0.2, timeout=30, **NOSPACE)
        k.update(kw)
        return RG.run_guarded(cmd, **k)


class TestGuard(Base):
    def test_ok_env_threads_and_temp(self):
        rec = self.guard([PY, "-c", "import os,tempfile;print(os.environ['OMP_NUM_THREADS'],tempfile.gettempdir())"])
        self.assertEqual(rec["status"], "ok")
        out = (Path(rec["attempt_dir"]) / "stdout.log").read_text().split()
        self.assertEqual(out[0], "4")
        self.assertTrue(out[1].startswith(rec["attempt_dir"]))
        self.assertTrue(rec["scratch_deleted"])
        self.assertTrue((Path(rec["attempt_dir"]) / "attempt.json").is_file())

    def test_low_limit_allocator_memory_stop(self):
        # 400 MiB allocator vs 100 MiB test threshold (stand-in for the R0 1 GiB check)
        rec = self.guard([PY, "-c", ALLOC, str(400 * MiB), "20"], mem_limit=100 * MiB)
        self.assertIn(rec["status"], ("memory-stop", "memory-watchdog-rss"))
        if sys.platform == "darwin":
            self.assertEqual(rec["status"], "memory-stop", "phys_footprint path should be primary on macOS")
            self.assertGreater(rec["peak_phys_footprint_bytes"], 100 * MiB)
        self.assertLess(rec["wall_seconds"], 15)

    def test_descendant_memory_counted_and_killed(self):
        # parent is tiny; child (which leaves the process group via setsid) allocates
        pidfile = self.d / "child.pid"
        code = ("import subprocess,sys,os,time\n"
                f"p=subprocess.Popen([sys.executable,'-c',{ALLOC!r},str(300*{MiB}),'30'],start_new_session=True)\n"
                f"open({str(pidfile)!r},'w').write(str(p.pid));time.sleep(30)\n")
        rec = self.guard([PY, "-c", code], mem_limit=150 * MiB)
        self.assertIn(rec["status"], ("memory-stop", "memory-watchdog-rss"))
        time.sleep(0.5)
        cpid = int(pidfile.read_text())
        with self.assertRaises(ProcessLookupError):
            os.kill(cpid, 0)

    def test_timeout_kills_group(self):
        rec = self.guard([PY, "-c", "import time;time.sleep(60)"], timeout=1.0)
        self.assertEqual(rec["status"], "timeout")
        self.assertLess(rec["wall_seconds"], 10)

    def test_disk_start_floor(self):
        free = RG.free_bytes(self.d)
        rec = self.guard([PY, "-c", "print(1)"], disk_start_min=free * 4, disk_path=self.d)
        self.assertEqual(rec["status"], "disk-start")
        self.assertIsNone(rec["returncode"])

    def test_disk_running_floor(self):
        free = RG.free_bytes(self.d)
        # start floor satisfied, running floor impossible -> disk-stop at first disk poll
        rec = self.guard([PY, "-c", "import time;time.sleep(20)"], disk_start_min=0, disk_run_min=free * 4,
                         disk_path=self.d)
        self.assertEqual(rec["status"], "disk-stop")

    def test_storage_cap(self):
        cap = self.d / "cap"
        cap.mkdir()
        code = f"import time;open({str(cap / 'big')!r},'wb').write(b'x'*{8 * MiB});time.sleep(20)"
        rec = self.guard([PY, "-c", code], storage_cap=2 * MiB, cap_paths=[cap])
        self.assertEqual(rec["status"], "storage-cap")

    def test_failure_and_immutable_attempts(self):
        r1 = self.guard([PY, "-c", "import sys;sys.exit(7)"])
        r2 = self.guard([PY, "-c", "print('ok')"])
        self.assertEqual((r1["status"], r1["returncode"]), ("failed", 7))
        self.assertEqual(r2["status"], "ok")
        self.assertNotEqual(r1["attempt_dir"], r2["attempt_dir"])
        self.assertEqual(json.loads((Path(r1["attempt_dir"]) / "attempt.json").read_text())["status"], "failed")

    def test_cli_exit_codes(self):
        rc = RG.main(["--attempt-root", str(self.d / "cli"), "--name", "x", "--disk-start-gib", "0",
                      "--disk-run-gib", "0", "--timeout", "1", "--mem-poll", "0.2", "--", PY, "-c",
                      "import time;time.sleep(10)"])
        self.assertEqual(rc, 2)  # infrastructure status
        rec = json.loads(next((self.d / "cli" / "x").glob("attempt-*/attempt.json")).read_text())
        self.assertLess(rec["returncode"], 0)  # killed by signal, returncode not masked


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


class TestRecover(Base):
    def make_hist(self, extra_unlisted=False, corrupt=False):
        h = self.d / "hist"
        lay = {"data": "runs/D05", "armA": "runs/T01-matched-armA-x", "armB": "runs/T02-matched-armB-x"}
        (h / lay["data"]).mkdir(parents=True)
        (h / lay["data"] / "receipt.json").write_text("{}")
        (h / lay["data"] / "features_and_classes.json").write_text("{}")
        for m in R.ALL_M:
            (h / lay["armA"] / m).mkdir(parents=True)
            (h / lay["armA"] / m / "model.pkl").write_bytes(m.encode())
        (h / lay["armA"] / "M6" / "scanvi").mkdir()
        (h / lay["armA"] / "M6" / "scanvi" / "model.pt").write_bytes(b"ckpt")
        for m in R.CACHED_B:
            (h / lay["armB"] / m).mkdir(parents=True)
            (h / lay["armB"] / m / "predictions_s.parquet").write_bytes(m.encode())
        files = [{"path": str(p.relative_to(h)), "sha256": sha(p)} for p in sorted(h.rglob("*")) if p.is_file()]
        if corrupt:
            (h / lay["armA"] / "M1" / "model.pkl").write_bytes(b"tampered")
        if extra_unlisted:
            (h / lay["armA"] / "M2" / "stray.txt").write_text("x")
        mp = self.d / "hist_manifest.json"
        mp.write_text(json.dumps({"root_layout": lay, "files": files}))
        return h, mp

    def fake_python(self, fail_on=None, infra_once=None):
        """Script standing in for the companion python: records argv, writes expected outputs."""
        st = self.d / "fake_state"
        st.mkdir(exist_ok=True)
        code = f'''#!{PY}
import sys,os,json,time
from pathlib import Path
a=sys.argv[1:]; st=Path({str(st)!r})
script=Path(a[0]).name; out=Path(a[a.index("--out")+1]); out.mkdir(parents=True,exist_ok=True)
tag=script+":"+(a[a.index("--arm")+1]+a[a.index("--method")+1]+a[a.index("--stage")+1] if "--arm" in a else "")
open(st/"calls.log","a").write(json.dumps(a)+"\\n")
if {fail_on!r} and {fail_on!r} in tag: sys.exit(5)
if {infra_once!r} and {infra_once!r} in tag and not (st/"infra_done").exists():
    (st/"infra_done").write_text("1"); time.sleep(60)
if "fit" in tag: (out/"model.pkl").write_text("m")
if script=="score_all.py": (out/"thresholds_validation.csv").write_text("x")
'''
        p = self.d / "fakepy"
        p.write_text(code)
        p.chmod(0o755)
        return p, st

    def args(self, h, mp, fake, **kw):
        a = ["--workspace", str(self.d / "ws"), "--historical-root", str(h), "--historical-manifest", str(mp),
             "--run-dir", str(self.d / "run"), "--python", str(fake), "--mem-poll", "0.2",
             "--guard-overrides", json.dumps({"disk_start_min": 0, "disk_run_min": 0, "disk_path": str(self.d),
                                              "cap_paths": [], "disk_poll": 0.2})]
        for k, v in kw.items():
            a += [f"--{k.replace('_', '-')}", v]
        (self.d / "ws" / "companion/scripts").mkdir(parents=True, exist_ok=True)
        (self.d / "ws" / "companion/scripts/score_all.py").write_text("# fixture")
        return a

    def manifest(self):
        return json.loads((self.d / "run" / "recovery_manifest.json").read_text())

    def test_full_sequence_order_and_args(self):
        h, mp = self.make_hist()
        fake, st = self.fake_python()
        self.assertEqual(R.main(self.args(h, mp, fake)), 0)
        calls = [json.loads(l) for l in (st / "calls.log").read_text().splitlines()]
        tags = [(Path(c[0]).name, c[c.index("--arm") + 1] + c[c.index("--method") + 1] + c[c.index("--stage") + 1]
                 if "--arm" in c else "") for c in calls]
        expect = [("run_matched.py", f"B{m}{s}") for m in R.RESUME_B for s in ("fit", "predict")]
        expect += [("build_cite.py", "")] + [("run_matched.py", f"A{m}predict") for m in R.ALL_M]
        expect += [("score_all.py", ""), ("protein_check.py", "")]
        self.assertEqual(tags, expect)
        score = calls[-2]
        self.assertIn("1000", score)
        self.assertEqual(score[score.index("--natural-unknown-scope") + 1], "natural")
        m6 = calls[-3]
        self.assertIn("--expected-hashes", m6)
        exp = json.loads(Path(m6[m6.index("--expected-hashes") + 1]).read_text())
        self.assertEqual(exp, {"model.pt": hashlib.sha256(b"ckpt").hexdigest()})
        self.assertTrue(m6[m6.index("--model-dir") + 1].endswith("T01-matched-armA-x/M6"))
        armB = self.d / "run" / "armB"
        self.assertEqual(sorted(p.name for p in armB.iterdir()), list(R.ALL_M))
        man = self.manifest()
        self.assertEqual(man["status"], "complete")
        self.assertTrue(all(s["status"] == "ok" for s in man["steps"]))
        self.assertIn("git_rev", man["source"])
        self.assertTrue(any(k.endswith("M1/predictions_s.parquet") for k in man["cached"]))

    def test_deterministic_failure_stops_without_retry(self):
        h, mp = self.make_hist()
        fake, st = self.fake_python(fail_on="BM5fit")
        self.assertEqual(R.main(self.args(h, mp, fake)), 3)
        man = self.manifest()
        self.assertEqual(man["status"], "blocked")
        m5 = [s for s in man["steps"] if s["name"] == "B_M5_fit"]
        self.assertEqual(len(m5), 1)
        self.assertEqual(m5[0]["status"], "failed")
        self.assertTrue(Path(m5[0]["attempt_dir"], "attempt.json").is_file())  # failed attempt preserved

    def test_infra_failure_retried_once_and_preserved(self):
        h, mp = self.make_hist()
        fake, st = self.fake_python(infra_once="build_cite")
        self.assertEqual(R.main(self.args(h, mp, fake, ceilings=json.dumps({"cite_build": 2}))), 0)
        cb = [s for s in self.manifest()["steps"] if s["name"] == "cite_build"]
        self.assertEqual([s["status"] for s in cb], ["timeout", "ok"])
        self.assertNotEqual(cb[0]["attempt_dir"], cb[1]["attempt_dir"])
        self.assertTrue(Path(cb[0]["attempt_dir"], "stdout.log").exists())

    def test_stage_ceiling_counts_retries(self):
        h, mp = self.make_hist()
        fake, st = self.fake_python(infra_once="BM4fit")
        rc = R.main(self.args(h, mp, fake, stage_ceiling="1.5"))
        self.assertEqual(rc, 3)
        man = self.manifest()
        self.assertIn("stage ceiling", man["blocker"])
        self.assertLessEqual(man["steps"][0]["timeout_s"], 1.5)

    def test_hash_mismatch_blocks_before_launch(self):
        h, mp = self.make_hist(corrupt=True)
        fake, st = self.fake_python()
        self.assertEqual(R.main(self.args(h, mp, fake)), 3)
        self.assertIn("sha256 mismatch", self.manifest()["blocker"])
        self.assertFalse((st / "calls.log").exists())

    def test_unlisted_file_blocks(self):
        h, mp = self.make_hist(extra_unlisted=True)
        fake, st = self.fake_python()
        self.assertEqual(R.main(self.args(h, mp, fake)), 3)
        self.assertIn("not covered by manifest", self.manifest()["blocker"])


def tearDownModule():
    shutil.rmtree(TMP, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

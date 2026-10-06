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

    def fake_python(self, fail_on=None, infra_once=None, sleep_on=None, kill_driver_on=None):
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
if {sleep_on!r} and {sleep_on!r} in tag: time.sleep(0.7)
if {kill_driver_on!r} and {kill_driver_on!r} in tag and not (st/"killed").exists():
    import subprocess, signal
    (st/"killed").write_text("1"); pid=os.getppid()
    while pid > 1:
        cmd=subprocess.run(["ps","-o","command=","-p",str(pid)],capture_output=True,text=True).stdout
        if "recover.py" in cmd:
            os.kill(pid, signal.SIGKILL); break
        pid=int(subprocess.run(["ps","-o","ppid=","-p",str(pid)],capture_output=True,text=True).stdout.strip() or 1)
    time.sleep(0.5); sys.exit(9)
if "fit" in tag: (out/"model.pkl").write_text("m")
if "M6fit" in tag: (out/"scanvi").mkdir(); (out/"scanvi"/"model.pt").write_bytes(b"bckpt")
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
        bm6 = calls[5]
        self.assertIn("--expected-hashes", bm6)  # relocated B_M6 predict verifies its own fit checkpoint
        self.assertEqual(json.loads(Path(bm6[bm6.index("--expected-hashes") + 1]).read_text()),
                         {"model.pt": hashlib.sha256(b"bckpt").hexdigest()})
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
        # method-specific reviewed caps (seconds)
        to = {s["name"]: s["timeout_s"] for s in man["steps"]}
        self.assertEqual([to[f"B_{m}_{k}"] for m in R.RESUME_B for k in ("fit", "predict")],
                         [1200, 300, 3000, 600, 3600, 1200])
        self.assertEqual((to["cite_build"], to["score"], to["protein"]), (1200, 7200, 900))
        self.assertLessEqual(to["A_M1_cite"], 1800)
        self.assertLess(to["A_M6_cite"], 1800)  # shared 30 min pool already partly consumed
        # receipts + assembly with fit artifact paths
        for s in man["steps"]:
            self.assertTrue(Path(s["receipt"]).is_file())
        asm = json.loads((self.d / "run" / "assembly.json").read_text())
        self.assertEqual(asm["armB"]["M1"]["provenance"], "cached")
        self.assertTrue(asm["armB"]["M1"]["source_sha256"])
        b4 = asm["armB"]["M4"]
        self.assertTrue(Path(b4["fit_dir"], "model.pkl").is_file())
        self.assertIn("model.pkl", b4["fit_files_sha256"])
        self.assertIn("git_rev", b4["source"])
        self.assertIn("model.pkl", asm["armA_cite"]["M4"]["fit_source_sha256"])
        if sys.platform == "darwin":  # every real step timed by /usr/bin/time -l
            aj = json.loads(Path(man["steps"][0]["attempt_dir"], "attempt.json").read_text())
            self.assertEqual(aj["exec_command"][:2], ["/usr/bin/time", "-l"])
            self.assertIsNotNone(aj["postrun_time_l"]["peak_memory_footprint_bytes"])
            self.assertFalse(aj["postrun_time_l"]["exceeds_limit"])

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


    def test_cite_pool_is_total_not_each(self):
        h, mp = self.make_hist()
        fake, st = self.fake_python(sleep_on="run_matched.py:A")
        rc = R.main(self.args(h, mp, fake, pools=json.dumps({"cite_predict": 1.5})))
        self.assertEqual(rc, 3)
        man = self.manifest()
        self.assertIn("cite_predict pool", man["blocker"])
        cite = [s for s in man["steps"] if s.get("pool") == "cite_predict"]
        self.assertLess(len({s["name"] for s in cite}), 6)
        self.assertLessEqual(man["pool_seconds_used"]["cite_predict"], 1.5 + 2.0)

    def run_cli(self, args):
        import subprocess
        return subprocess.run([PY, str(ROOT / "scripts/recover.py")] + args, capture_output=True, text=True,
                              env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))

    def test_resume_after_driver_kill_reuses_receipts(self):
        h, mp = self.make_hist()
        fake, st = self.fake_python(kill_driver_on="AM3predict")
        a = self.args(h, mp, fake)
        r1 = self.run_cli(a)
        self.assertEqual(r1.returncode, -9, r1.stderr[-1500:])  # driver SIGKILLed mid-step (infrastructure interruption)
        man1 = self.manifest()
        used1 = man1["stage_seconds_used"]
        n_calls1 = len((st / "calls.log").read_text().splitlines())
        lj = next((self.d / "run" / "attempts" / "A_M3_cite").glob("attempt-*/launch.json"))
        for _ in range(100):  # operator step: wait until the orphaned step group has exited
            if not RG.group_alive(json.loads(lj.read_text())["pgid"]):
                break
            time.sleep(0.1)
        r2 = self.run_cli(a + ["--resume"])
        self.assertEqual(r2.returncode, 0, r2.stderr)
        man = self.manifest()
        self.assertEqual(man["status"], "complete")
        calls = [json.loads(l) for l in (st / "calls.log").read_text().splitlines()][n_calls1:]
        tags = [c[c.index("--arm") + 1] + c[c.index("--method") + 1] + c[c.index("--stage") + 1]
                for c in calls if "--arm" in c]
        self.assertEqual(tags, ["AM3predict", "AM4predict", "AM5predict", "AM6predict"])  # no B refits
        reused = [s["name"] for s in man["steps"] if s["status"] == "reused-from-receipt"]
        self.assertIn("B_M4_fit", reused)
        self.assertIn("A_M2_cite", reused)
        a3 = [s for s in man["steps"] if s["name"] == "A_M3_cite" and s["status"] != "reused-from-receipt"]
        self.assertEqual([s["attempt"] for s in a3], [2])  # attempt count not reset
        charged = man["resumes"][0]["unrecorded_attempts_charged"]
        self.assertEqual([c["name"] for c in charged], ["A_M3_cite"])
        self.assertGreaterEqual(man["stage_seconds_used"], used1 + charged[0]["charged_seconds"])
        self.assertGreater(man["pool_seconds_used"]["cite_predict"], 0)

    def test_resume_blocks_while_orphan_group_alive(self):
        h, mp = self.make_hist()
        fake, st = self.fake_python(kill_driver_on="AM3predict")
        a = self.args(h, mp, fake)
        self.run_cli(a)
        import subprocess
        orphan = subprocess.Popen([PY, "-c", "import time;time.sleep(30)"], start_new_session=True)
        try:
            adir = next((self.d / "run" / "attempts" / "A_M3_cite").glob("attempt-*"))
            (adir / "launch.json").write_text(json.dumps({"pid": orphan.pid, "pgid": orphan.pid}))
            r2 = self.run_cli(a + ["--resume"])
            self.assertEqual(r2.returncode, 3)
            self.assertIn("still running", r2.stderr + self.manifest().get("blocker", ""))
        finally:
            orphan.kill(); orphan.wait()

    def test_resume_blocks_if_completed_output_changed(self):
        h, mp = self.make_hist()
        fake, st = self.fake_python(kill_driver_on="AM3predict")
        a = self.args(h, mp, fake)
        self.run_cli(a)
        rcpt = json.loads((self.d / "run" / "receipts" / "B_M4_fit.json").read_text())
        Path(rcpt["out_dir"], "model.pkl").write_text("tampered")
        r2 = self.run_cli(a + ["--resume"])
        self.assertEqual(r2.returncode, 3)
        self.assertIn("no longer matches its receipt", self.manifest()["blocker"])

    def test_resume_does_not_reset_attempts(self):
        h, mp = self.make_hist()
        fake, st = self.fake_python(kill_driver_on="AM3predict", fail_on="AM3predict")
        a = self.args(h, mp, fake)
        # first run: fail_on fires before the kill, so the step fails deterministically
        self.assertEqual(self.run_cli(a).returncode, 3)
        r2 = self.run_cli(a + ["--resume"])
        self.assertEqual(r2.returncode, 3)
        self.assertIn("earlier deterministic", self.manifest()["blocker"])

    def test_cap_paths_include_env_tools_rundir_without_double_count(self):
        h, mp = self.make_hist()
        fake, _ = self.fake_python()
        ws = self.d / "ws"
        a = self.args(h, mp, fake)
        i = a.index("--guard-overrides")
        del a[i:i + 2]
        a += ["--study-root", str(ws)]
        ns = __import__("argparse").Namespace
        p = R.main.__globals__["argparse"].ArgumentParser
        (self.d / "run").mkdir()
        for sub in (".venv", ".tools", "runs", "companion"):
            (ws / sub).mkdir(parents=True, exist_ok=True)
        args = dict(workspace=str(ws), study_root=str(ws), historical_root=str(h), run_dir=str(self.d / "run"),
                    python=str(fake), ceilings=None, pools=None, stage_ceiling=10.0, no_time_l=False,
                    cap_path=[str(ws / "runs" / "nested"), str(ws / ".venv")], mem_limit_gib=12.0, mem_poll=5.0,
                    guard_overrides=None, fit_disk_gib=4.0, historical_manifest=str(mp))
        d = R.Driver(ns(**args))
        cp = [str(x) for x in d.guard_kw["cap_paths"]]
        real = lambda q: os.path.realpath(q)
        for want in (".venv", ".tools", "runs", "companion", ".cache-study", "paper/build"):
            self.assertIn(real(ws / want), cp)
        self.assertIn(real(self.d / "run"), cp)
        self.assertEqual(len(cp), len(set(cp)))
        self.assertNotIn(real(ws / "runs" / "nested"), cp)  # nested in runs/: not counted twice
        # inode de-duplication: a hard link (uv cache -> venv) is counted once
        f = ws / ".venv" / "big"
        f.write_bytes(b"x" * (2 * MiB))
        os.link(f, ws / ".tools" / "big-link")
        u = RG.tree_usage([ws / ".venv", ws / ".tools", ws / ".venv"])
        self.assertLess(u["total_bytes"], 3 * MiB)
        self.assertGreaterEqual(u["total_bytes"], 2 * MiB)

    def test_preflight_readonly(self):
        h, mp = self.make_hist()
        (h / "runs/D05/features_and_classes.json").write_text(json.dumps({"K": ["B"], "K_B": ["B"]}))
        files = [{"path": str(p.relative_to(h)), "sha256": sha(p)} for p in sorted(h.rglob("*")) if p.is_file()]
        mp.write_text(json.dumps({"root_layout": json.loads(mp.read_text())["root_layout"], "files": files}))
        before = {str(p): sha(p) for p in h.rglob("*") if p.is_file()}
        fake, st = self.fake_python()
        py = VENV_PY if VENV_PY.exists() else Path(PY)
        a = self.args(h, mp, py) + ["--preflight"]
        rc = R.main(a)
        pf = json.loads((self.d / "run" / "preflight.json").read_text())
        self.assertFalse(pf["labels_read"])
        self.assertEqual(pf["K"], ["B"])
        self.assertTrue(pf["checks"]["historical_inputs_verified"])
        self.assertEqual(len(pf["environment"]["dists_sha256"]), 64)
        if VENV_PY.exists():
            self.assertTrue(pf["checks"]["celltypist_folder_env_honoured"])
            self.assertEqual(rc, 0)
        self.assertEqual(before, {str(p): sha(p) for p in h.rglob("*") if p.is_file()})
        self.assertFalse((st / "calls.log").exists())


VENV_PY = Path("/Users/timrichardson/Documents/projects/personal/blog/cell-type-annotation-transfer/.venv/bin/python")


class TestPostrunTimeParser(Base):
    LIM = 12 * (1 << 30)

    def fixture(self, peak):
        return ("child stderr line\n        0.50 real         0.10 user         0.01 sys\n"
                f"            70000000  maximum resident set size\n"
                f"           {peak}  peak memory footprint\n")

    def test_boundaries(self):
        for peak, flag in ((self.LIM - 1, False), (self.LIM, False), (self.LIM + 1, True), (0, False)):
            t = RG.parse_time_l(self.fixture(peak))
            self.assertEqual(t["peak_memory_footprint_bytes"], peak)
            self.assertEqual(RG.postrun_exceeds(t["peak_memory_footprint_bytes"], self.LIM), flag, peak)
        t = RG.parse_time_l(self.fixture(5))
        self.assertEqual((t["max_rss_bytes"], t["real_seconds"]), (70000000, 0.5))

    def test_missing_malformed_and_last_wins(self):
        t = RG.parse_time_l("Traceback...\nMemoryError\n")
        self.assertIsNone(t["peak_memory_footprint_bytes"])
        self.assertFalse(RG.postrun_exceeds(None, self.LIM))
        t = RG.parse_time_l("  12.5GB  peak memory footprint\n  abc  peak memory footprint\n")
        self.assertIsNone(t["peak_memory_footprint_bytes"])
        t = RG.parse_time_l("  99  peak memory footprint\n" + self.fixture(7))
        self.assertEqual(t["peak_memory_footprint_bytes"], 7)

    def fake_time(self, peak):
        p = self.d / "faketime"
        p.write_text(f"#!/bin/sh\nshift\n\"$@\"\nrc=$?\necho '           {peak}  peak memory footprint' >&2\nexit $rc\n")
        p.chmod(0o755)
        return str(p)

    def test_postrun_flag_marks_attempt(self):
        lim = 12 * (1 << 30)
        r = self.guard([PY, "-c", "print(1)"], time_l=True, time_bin=self.fake_time(lim), mem_limit=lim)
        self.assertEqual(r["status"], "ok")
        r = self.guard([PY, "-c", "print(1)"], time_l=True, time_bin=self.fake_time(lim + 1), mem_limit=lim)
        self.assertEqual((r["status"], r["status_before_postrun"]), ("memory-stop-postrun", "ok"))
        self.assertIn("memory-stop-postrun", RG.MEMORY_STATUSES & RG.INFRA_STATUSES)
        self.assertTrue((Path(r["attempt_dir"]) / "stderr.log").read_text().strip().endswith("footprint"))

    @unittest.skipUnless(os.access("/usr/bin/time", os.X_OK) and sys.platform == "darwin", "macOS /usr/bin/time")
    def test_real_usr_bin_time(self):
        r = self.guard([PY, "-c", "b=bytearray(80<<20)\nfor i in range(0,len(b),4096): b[i]=1"], time_l=True)
        self.assertEqual(r["status"], "ok")
        self.assertGreater(r["postrun_time_l"]["peak_memory_footprint_bytes"], 80 * MiB)
        self.assertFalse(r["postrun_time_l"]["exceeds_limit"])


@unittest.skipUnless(sys.platform == "darwin", "phys_footprint watchdog is macOS")
class TestOneGiBProductionThreshold(Base):
    def test_cli_launcher_1gib(self):
        # production CLI path, actual 1 GiB threshold, time -l on: 1.5 GiB allocator is killed
        rc = RG.main(["--attempt-root", str(self.d / "cli"), "--name", "over", "--disk-start-gib", "0",
                      "--disk-run-gib", "0", "--mem-limit-gib", "1", "--mem-poll", "0.5", "--timeout", "60",
                      "--time-l", "--", PY, "-c", ALLOC, str(int(1.5 * 1024) * MiB), "60"])
        rec = json.loads(next((self.d / "cli" / "over").glob("attempt-*/attempt.json")).read_text())
        self.assertEqual((rc, rec["status"]), (2, "memory-stop"))
        self.assertGreater(rec["peak_phys_footprint_bytes"], 1 << 30)
        self.assertLess(rec["wall_seconds"], 30)

    def test_preflight_selftest_function(self):
        st = R.watchdog_selftest_run(self.d / "st", dict(disk_start_min=0, disk_run_min=0, disk_path=self.d,
                                                         mem_poll=0.5, disk_poll=5.0))
        self.assertTrue(st["passed"], st)
        self.assertEqual(st["threshold_bytes"], 1 << 30)
        self.assertEqual(st["under"]["status"], "ok")


def tearDownModule():
    shutil.rmtree(TMP, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

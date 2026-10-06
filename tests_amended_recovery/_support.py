"""Shared SYNTHETIC fixtures for the amended-recovery tests.

Nothing here reads configs/full.json, the historical root, the real prior run or any study data, and nothing
launches a real pipeline step: the "python" handed to recover.py is a fake script that only writes
placeholder files. All scratch output lives under tests_amended_recovery/_tmp/ and is deleted afterwards.
"""
import hashlib
import json
import os
import shutil
import sys
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "scripts"))
import recover as R  # noqa: E402
import result_manifest as RM  # noqa: E402

TMP = HERE / "_tmp"
PY = sys.executable
NAMES = sorted(RM.REPLACEMENT_FILES)  # totalvi_pbmc10k_protein_v3, totalvi_pbmc5k_protein_v3
SCI_FILES = ("companion/scripts/run_matched.py", "companion/scripts/score_all.py", "companion/scripts/build_cite.py",
             "companion/scripts/protein_check.py", "companion/src/celltransfer/methods.py",
             "companion/src/celltransfer/evaluate.py")


def sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def w(p, s):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(s, bytes):
        p.write_bytes(s)
    else:
        p.write_text(s)
    return p


def snapshot(root: Path) -> dict:
    """Content, mode and mtime of every entry (no symlink following) - proves the original run is untouched."""
    out = {}
    for p in sorted(root.rglob("*")):
        st = p.lstat()
        out[str(p.relative_to(root))] = (sha(p) if p.is_file() and not p.is_symlink() else None,
                                         st.st_mode, st.st_mtime_ns)
    return out


BUILDER = ROOT / "companion/scripts/build_cite_totalvi.py"


def write_builder_records(out: Path, spec: dict, B=None, tamper: str | None = None) -> None:
    """Write SYNTHETIC R4' records in the exact builder schema (celltransfer-totalvi-eligibility/1).

    spec: {name: "eligible" | "ineligible:<criterion number>"}. Uses the builder's own canonical_json /
    write_atomic so the hashed record and sidecar are byte-compatible with read_eligibility.
    """
    B = B or RM.builder()
    out = Path(out)
    acq = {"status": "complete", "files": {n: {"source": "cached", "identity": {
        "pass": True, "sha256": B.PINS[n]["sha256"], "bytes": B.PINS[n]["bytes"]}} for n in B.NAMES}}
    B.write_atomic(out / "acquisition.json", B.canonical_json(acq))
    files = {}
    for n in B.NAMES:
        v = spec.get(n, "eligible")
        B.write_atomic(out / f"mapping_{n}.csv", f"index,var_name,status,eid,census_eids\n0,SYN,{n},,\n".encode())
        if v == "eligible":
            files[n] = {"verdict": "eligible", "first_failing_criterion": None}
            B.write_atomic(out / f"barcodes_qc_{n}.txt", f"syn_{n}_0\nsyn_{n}_1\n".encode())
            for f in (f"query_{n}_F.h5ad", f"adt_{n}.parquet", f"released_predictions_{n}.parquet"):
                (out / f).write_text("synthetic " + n)
        else:
            k = int(v.split(":", 1)[1])
            files[n] = {"verdict": "ineligible", "first_failing_criterion": {"number": k, "name": B.CRITERIA[k]}}
    elig = sorted(n for n, r in files.items() if r["verdict"] == "eligible")
    rec = {"schema": "celltransfer-totalvi-eligibility/1", "files": files, "eligible_files": elig,
           "n_eligible": len(elig), "outcome": "run" if elig else "not_run"}
    d = B.write_atomic(out / "eligibility.json", B.canonical_json(rec))
    if tamper != "no_sidecar":
        B.write_atomic(out / "eligibility.json.sha256", f"{d}  eligibility.json\n".encode())
    if tamper == "bytes":
        (out / "eligibility.json").write_bytes((out / "eligibility.json").read_bytes() + b" ")


class Scratch(unittest.TestCase):
    def setUp(self):
        self.d = TMP / f"{self.id().split('.')[-1]}-{time.time_ns()}"
        self.d.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)
        try:
            TMP.rmdir()
        except OSError:
            pass


class PriorRunFixture(Scratch):
    """Synthetic workspace + historical root + a completed, paused prior recovery run (B M4-M6 done)."""
    PRIOR_STAGE = 1000.0
    R4_SECONDS = 50.0

    def setUp(self):
        super().setUp()
        self._patch = R.AMENDMENT_SHA256
        self.ws = self.d / "ws"
        for f in SCI_FILES:
            w(self.ws / f, f"# synthetic fixture {f}\n")
        w(self.ws / R.REPLACEMENT_BUILDER, "# synthetic replacement builder stand-in\n")
        w(self.ws / "scripts/resource_guard.py", "# synthetic guard stand-in\n")
        rv = w(self.ws / R.AMENDMENT_REVIEWED, "synthetic reviewed amendment text\n")
        R.AMENDMENT_SHA256 = sha(rv)  # restored in tearDown
        self.hist, self.hman, self.lay = self.make_hist()
        self.prior_run, self.prior_manifest, self.evidence = self.make_prior()

    def tearDown(self):
        R.AMENDMENT_SHA256 = self._patch
        super().tearDown()

    # ------------------------------------------------------------ historical (cached) inputs
    def make_hist(self):
        h = self.d / "hist"
        lay = {"data": "runs/D05", "armA": "runs/T01-matched-armA-x", "armB": "runs/T02-matched-armB-x"}
        w(h / lay["data"] / "receipt.json", "{}")
        w(h / lay["data"] / "features_and_classes.json", "{}")
        for m in R.ALL_M:
            w(h / lay["armA"] / m / "model.pkl", m)
        w(h / lay["armA"] / "M6" / "scanvi" / "model.pt", b"ckpt")
        for m in R.CACHED_B:
            w(h / lay["armB"] / m / "predictions_s.parquet", m)
        files = [{"path": str(p.relative_to(h)), "sha256": sha(p)} for p in sorted(h.rglob("*")) if p.is_file()]
        mp = w(self.d / "hist_manifest.json", json.dumps({"root_layout": lay, "files": files}))
        return h, mp, lay

    # ------------------------------------------------------------ prior run (immutable original)
    def make_prior(self, code_override=None):
        P = self.d / "prior" / "recovery"
        D = str(self.hist / self.lay["data"])
        src = {"git_rev": "synthetic-rev", "dirty": False,
               "code_sha256": dict({f: sha(self.ws / f) for f in SCI_FILES},
                                   **{"scripts/recover.py": "0" * 64,  # driver: allowed to differ
                                      "scripts/resource_guard.py": sha(self.ws / "scripts/resource_guard.py")})}
        if code_override:
            src["code_sha256"].update(code_override)
        steps, asm, walls = [], {"armB": {}}, iter([11.0, 2.0, 13.0, 3.0, 17.0, 5.0])
        rm = ["/fake/python", "/fake/companion/scripts/run_matched.py", "--workspace", "/fake/ws"]
        for m in R.ALL_M:
            if m in R.CACHED_B:
                asm["armB"][m] = {"provenance": "cached"}
        fit_out = {}
        for i, (m, k) in enumerate((m, k) for m in R.RESUME_B for k in ("fit", "predict")):
            name = f"B_{m}_{k}"
            att = 2 if name == "B_M4_fit" else 1
            stamp = f"20261006T17{i:02d}00000000Z"
            adir = P / "attempts" / name / f"attempt-1-{stamp}"
            out = P / "attempts" / name / f"out-{att}-{stamp[:-1]}"
            wall = next(walls)
            w(adir / "attempt.json", json.dumps({"status": "ok", "wall_seconds": wall}))
            w(adir / "stdout.log", "")
            if k == "fit":
                w(out / "model.pkl", f"model-{m}")
                w(out / "fit_info.json", json.dumps({"chosen_C": 0.1} if m == "M4" else {}))
                if m == "M6":
                    w(out / "scanvi" / "model.pt", b"bckpt")
                cmd = rm + ["--data", D, "--arm", "B", "--method", m, "--stage", "fit", "--out", str(out)]
                fit_out[m] = out
            else:
                w(out / "predictions_s.parquet", f"pred-{m}")
                w(out / "predict_info.json", "{}")
                cmd = rm + ["--data", D, "--arm", "B", "--method", m, "--stage", "predict",
                            "--model-dir", str(fit_out[m]), "--out", str(out)]
                if m == "M6":
                    hp = w(P / "armB_M6_scanvi_expected_sha256.json",
                           json.dumps({"model.pt": hashlib.sha256(b"bckpt").hexdigest()}, indent=1, sort_keys=True))
                    cmd += ["--expected-hashes", str(hp)]
            rp = P / "receipts" / f"{name}.json"
            files = R.dir_hashes(out)
            w(rp, json.dumps({"name": name, "out_dir": str(out), "attempt_dir": str(adir), "command": cmd,
                              "created_utc": "x", "source": src, "files_sha256": files}, indent=1, sort_keys=True))
            steps.append({"name": name, "kind": k, "attempt": att, "out_dir": str(out), "attempt_dir": str(adir),
                          "status": "ok", "returncode": 0, "wall_seconds": wall, "timeout_s": 1200, "command": cmd,
                          "pool": None, "provenance": "recomputed", "receipt": str(rp)})
            entry = asm["armB"].setdefault(m, {"provenance": "recomputed"})
            if k == "fit":
                entry.update(fit_dir=str(out), fit_files_sha256=files)
            else:
                entry.update(predictions_dir=str(out), predictions_sha256=files)
        man = {"driver": "scripts/recover.py", "created_utc": "x", "source": src,
               "historical_root": str(self.hist), "historical_manifest": str(self.hman),
               "historical_manifest_sha256": sha(self.hman), "stage_ceiling_s": 28800.0, "max_attempts": 2,
               "steps": steps, "assembly": asm, "status": "interrupted",
               "historical_layout": {"data": D, "armA": str(self.hist / self.lay["armA"]),
                                     "armB": str(self.hist / self.lay["armB"])},
               "stage_seconds_used": self.PRIOR_STAGE, "pool_seconds_used": {"cite_predict": 0.0},
               "blocker": "Matched recovery complete; paused before secondary protein data and scoring"}
        mp = w(P / "recovery_manifest.json", json.dumps(man, indent=1))
        w(P / "assembly.json", json.dumps(asm, indent=1, sort_keys=True))
        E = self.d / "evidence"
        E.mkdir(parents=True, exist_ok=True)
        for f in (P / "receipts").iterdir():
            shutil.copy2(f, E / f.name)
        shutil.copy2(P / "assembly.json", E / "assembly.json")
        shutil.copy2(mp, E / "recovery_manifest.json")
        return P, E / "recovery_manifest.json", E

    def rewrite_prior(self, mutate):
        """Mutate the prior manifest consistently in both the live run and the evidence copy."""
        man = json.loads(self.prior_manifest.read_text())
        mutate(man)
        txt = json.dumps(man, indent=1)
        (self.prior_run / "recovery_manifest.json").write_text(txt)
        self.prior_manifest.write_text(txt)

    # ------------------------------------------------------------ fake interpreter (no real step ever runs)
    def fake_python(self, elig=None, fail_on=None, sleep_on=None):
        st = self.d / "fake_state"
        st.mkdir(exist_ok=True)
        (st / "elig.json").write_text(json.dumps(elig if elig is not None else {}))
        code = f'''#!{PY}
import sys, os, json, time
from pathlib import Path
a = sys.argv[1:]; st = Path({str(st)!r})
script = Path(a[0]).name; out = Path(a[a.index("--out") + 1]); out.mkdir(parents=True, exist_ok=True)
tag = script + ":" + (a[a.index("--arm") + 1] + a[a.index("--method") + 1] + a[a.index("--stage") + 1]
                      if "--arm" in a else "")
open(st / "calls.log", "a").write(json.dumps(a) + "\\n")
if {fail_on!r} and {fail_on!r} in tag: sys.exit(5)
if {sleep_on!r} and {sleep_on!r} in tag: time.sleep(30)
if script == "build_cite_totalvi.py":
    assert a[1] == "r4prime" and a[2] == "--workspace" and "--data" in a, a
    spec = json.loads((st / "elig.json").read_text())
    if spec.get("__missing__"):
        sys.exit(0)
    sys.path.insert(0, {str(HERE)!r}); sys.path.insert(0, {str(ROOT / "scripts")!r})
    import _support
    _support.write_builder_records(out, spec, tamper=spec.get("__tamper__"))
if script == "score_all.py": (out / "thresholds_validation.csv").write_text("x")
if "predict" in tag: (out / "predictions_x.parquet").write_text("p")
'''
        p = w(self.d / "fakepy", code)
        p.chmod(0o755)
        return p, st

    def calls(self, st):
        f = st / "calls.log"
        return [json.loads(x) for x in f.read_text().splitlines()] if f.exists() else []

    def args(self, fake, run="run", r4=None, adopt=True, extra=(), guard=None):
        g = {"disk_start_min": 0, "disk_run_min": 0, "disk_path": str(self.d), "cap_paths": [], "disk_poll": 0.2}
        g.update(guard or {})
        a = ["--workspace", str(self.ws), "--historical-root", str(self.hist), "--historical-manifest",
             str(self.hman), "--run-dir", str(self.d / run), "--python", str(fake), "--mem-poll", "0.1",
             "--no-time-l", "--guard-overrides", json.dumps(g), "--fit-disk-gib", "0", "--r5-disk-gib", "0",
             "--amendment", R.AMENDMENT_ID]
        if adopt:
            a += ["--adopt-from", str(self.prior_manifest), "--adopt-receipts-dir", str(self.evidence)]
        if r4 is not False:
            a += ["--prior-r4-seconds", str(self.R4_SECONDS if r4 is None else r4)]
        return a + list(extra)

    def manifest(self, run="run"):
        return json.loads((self.d / run / "recovery_manifest.json").read_text())

#!/usr/bin/env python3
"""Mode R cached-recovery driver (standard library only).

Reproduces the step layout of historical/companion/scripts/queue_main.sh, but:
  * reuses historical outputs under $HISTORICAL_RUNS_ROOT only after sha256 verification
    against a supplied manifest (read-only; never written);
  * re-runs ONLY Arm B M4, M5, M6 (fit + predict), then the CITE build (4 frozen 10x files),
    Arm A CITE predictions for M1..M6 (models loaded from the verified historical Arm A dirs,
    M6 checkpoint hash-verified via run_matched.py --expected-hashes), scoring
    (score_all.py, --reps 1000, D-1a natural scope) and protein_check.py;
  * runs each attempt through scripts/resource_guard.py in an immutable attempt dir;
  * max 2 attempts per step; only infrastructure statuses are retried; deterministic failures
    stop; all attempt wall time counts against the 8 h stage ceiling;
  * writes a run manifest (command, config, input hashes, source revision, logs, time, status,
    provenance cached|recomputed) after every attempt.

It does not read prediction-vs-label comparisons itself; scoring is delegated to score_all.py.

Historical manifest format (JSON):
  {"root_layout": {"data": "runs/D05-...", "armA": "runs/T01-matched-armA-...",
                   "armB": "runs/T02-matched-armB-..."},
   "files": [{"path": "<relative to HISTORICAL_RUNS_ROOT>", "sha256": "...", "bytes": N}, ...]}
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import resource_guard as RG  # noqa: E402

GiB = RG.GiB
STAGE_CEILING_S = 8 * 3600
MAX_ATTEMPTS = 2
RESUME_B = ("M4", "M5", "M6")
CACHED_B = ("M1", "M2", "M3")
ALL_M = ("M1", "M2", "M3", "M4", "M5", "M6")
MIN = 60
# Per-attempt step ceilings (seconds), resume-plan-reviewed s6 Mode R:
#   R1 = B M4 20+5, R2 = B M5 50+10, R3 = B M6 60+20, R4 cite build 20, R5 A CITE predict 30 (POOL),
#   R6 score 120, R7 protein 15, R0 preflight 30.
STEP_CEILINGS = {"B_M4_fit": 20 * MIN, "B_M4_predict": 5 * MIN, "B_M5_fit": 50 * MIN, "B_M5_predict": 10 * MIN,
                 "B_M6_fit": 60 * MIN, "B_M6_predict": 20 * MIN, "cite_build": 20 * MIN,
                 "score": 120 * MIN, "protein": 15 * MIN, "preflight": 30 * MIN}
STEP_CEILINGS.update({f"A_{m}_cite": 30 * MIN for m in ("M1", "M2", "M3", "M4", "M5", "M6")})  # capped by pool too
# R5: the six Arm A CITE predictions share ONE 30 min budget (total, not each). Conservative reading:
# the pool is cumulative over all A_M*_cite attempts, retries included (never reset on resume).
POOLS = {"cite_predict": 30 * MIN}
STEP_POOL = {f"A_{m}_cite": "cite_predict" for m in ALL_M}
DEFAULT_CAP_RELPATHS = ("companion", "runs", ".cache-study", "paper/build", ".venv", ".tools")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


class Blocked(RuntimeError):
    pass


def verify_historical(root: Path, manifest: dict, subdirs: list[str]) -> dict[str, str]:
    """Verify every manifest file under the given subdirs; every file present must be listed."""
    listed = {f["path"]: f["sha256"] for f in manifest["files"]}
    verified = {}
    for sub in subdirs:
        base = root / sub
        if not base.is_dir():
            raise Blocked(f"historical dir missing: {base}")
        present = {str(p.relative_to(root)) for p in base.rglob("*") if p.is_file()}
        wanted = {k for k in listed if k == sub or k.startswith(sub.rstrip("/") + "/")}
        missing = wanted - present
        unlisted = present - wanted
        if missing:
            raise Blocked(f"manifest files missing on disk: {sorted(missing)[:5]}")
        if unlisted:
            raise Blocked(f"files not covered by manifest (cannot reuse unverified): {sorted(unlisted)[:5]}")
        for rel in sorted(wanted):
            got = sha256_file(root / rel)
            if got != listed[rel]:
                raise Blocked(f"sha256 mismatch for historical {rel}")
            verified[rel] = got
    return verified


def source_revision(repo: Path) -> dict:
    try:
        rev = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "-C", str(repo), "status", "--porcelain"], capture_output=True,
                                    text=True).stdout.strip())
    except OSError:
        rev, dirty = None, None
    return {"git_rev": rev, "dirty": dirty}


class Interrupted(RuntimeError):
    pass


CODE_FILES = ("companion/scripts/run_matched.py", "companion/scripts/score_all.py",
              "companion/scripts/build_cite.py", "companion/scripts/protein_check.py",
              "companion/src/celltransfer/methods.py", "companion/src/celltransfer/evaluate.py",
              "scripts/recover.py", "scripts/resource_guard.py")


def code_hashes(repo: Path) -> dict:
    return {r: sha256_file(repo / r) for r in CODE_FILES if (repo / r).is_file()}


def dir_hashes(d: Path) -> dict:
    return {str(p.relative_to(d)): sha256_file(p) for p in sorted(d.rglob("*")) if p.is_file()}


def _attempt_start(adir: Path) -> float | None:
    """Start time encoded in attempt-<n>-<UTC%f>Z directory names."""
    try:
        stamp = adir.name.split("-", 2)[2]
        return dt.datetime.strptime(stamp, "%Y%m%dT%H%M%S%fZ").replace(tzinfo=dt.timezone.utc).timestamp()
    except (IndexError, ValueError):
        return None


def estimate_interrupted_seconds(adir: Path) -> float:
    """Conservative wall time of an attempt with no attempt.json: start (dir name) -> newest mtime."""
    t0 = _attempt_start(adir)
    mt = max([p.stat().st_mtime for p in adir.rglob("*") if p.exists()] + [adir.stat().st_mtime])
    if t0 is None:
        return 0.0
    return max(0.0, mt - t0)


class Driver:
    def __init__(self, a, resume: bool = False):
        self.repo = Path(a.workspace).resolve()
        self.study_root = Path(a.study_root).resolve() if a.study_root else self.repo
        self.hist = Path(a.historical_root or os.environ.get("HISTORICAL_RUNS_ROOT", "")).resolve()
        self.run_dir = Path(a.run_dir).resolve()
        self.python = a.python
        self.stop_after_matched = getattr(a, "stop_after_matched", False)
        self.ceilings = dict(STEP_CEILINGS, **json.loads(a.ceilings or "{}"))
        self.pools = dict(POOLS, **json.loads(a.pools or "{}"))
        self.stage_ceiling = a.stage_ceiling
        self.external_prior_attempts = json.loads(getattr(a, "prior_attempts", "{}"))
        self.external_prior_seconds = float(getattr(a, "prior_seconds", 0))
        self.time_l = not a.no_time_l
        cap = [b / r for b in {self.repo, self.study_root} for r in DEFAULT_CAP_RELPATHS]
        cap += [self.run_dir] + [Path(p) for p in a.cap_path]
        self.guard_kw = dict(mem_limit=int(a.mem_limit_gib * GiB), swap_growth_limit=int(4 * GiB),
                             disk_start_min=int(3 * GiB), disk_run_min=int(1.5 * GiB), storage_cap=int(7 * GiB),
                             mem_poll=a.mem_poll, disk_poll=30.0, threads=4, disk_path=self.repo,
                             cap_paths=RG.normalize_cap_paths(cap))
        self.guard_kw.update(json.loads(a.guard_overrides or "{}"))
        self.guard_kw["disk_path"] = Path(self.guard_kw["disk_path"])
        self.guard_kw["cap_paths"] = RG.normalize_cap_paths([Path(p) for p in self.guard_kw["cap_paths"]])
        self.fit_disk_min = int(a.fit_disk_gib * GiB)
        cache = self.study_root / ".cache-study"
        # CELLTYPIST_FOLDER: verified in celltypist 1.7.1 models.py (os.getenv('CELLTYPIST_FOLDER', ...)),
        # read at import time, so it must be in the child env (it is: extra_env).
        self.env = {"UV_CACHE_DIR": str(cache / "uv"), "HF_HOME": str(cache / "hf"),
                    "XDG_CACHE_HOME": str(cache / "xdg"), "CELLTYPIST_FOLDER": str(cache / "celltypist"),
                    "MPLCONFIGDIR": str(cache / "mpl"), "PYTHONWARNINGS": "ignore"}
        self.manifest_path = Path(a.historical_manifest).resolve()
        self.manifest = json.loads(self.manifest_path.read_text())
        src = dict(source_revision(self.repo), code_sha256=code_hashes(self.repo))
        mp = self.run_dir / "recovery_manifest.json"
        if resume:
            if not mp.is_file():
                raise Blocked(f"--resume: no recovery_manifest.json in {self.run_dir}")
            self.record = json.loads(mp.read_text())
            if self.record.get("historical_manifest_sha256") != sha256_file(self.manifest_path):
                raise Blocked("--resume: historical manifest differs from the interrupted run")
            old = self.record["source"]
            if old.get("git_rev") != src["git_rev"] or old.get("code_sha256") != src["code_sha256"]:
                raise Blocked("--resume: source revision/code hashes differ from the interrupted run; "
                              "mixing code versions within one Mode R run is not allowed")
            self.used_s = float(self.record.get("stage_seconds_used", 0.0))
            self.pool_used = {k: float(v) for k, v in self.record.get("pool_seconds_used", {}).items()}
            known = {s["attempt_dir"] for s in self.record["steps"]}
            extra = []
            for adir in sorted((self.run_dir / "attempts").glob("*/attempt-*")):
                if str(adir) in known:
                    continue
                aj = adir / "attempt.json"
                secs = (json.loads(aj.read_text()).get("wall_seconds", 0.0) if aj.is_file()
                        else estimate_interrupted_seconds(adir))
                extra.append({"name": adir.parent.name, "attempt_dir": str(adir), "charged_seconds": round(secs, 3),
                              "had_attempt_json": aj.is_file()})
                self.used_s += secs
                pool = STEP_POOL.get(adir.parent.name)
                if pool:
                    self.pool_used[pool] = self.pool_used.get(pool, 0.0) + secs
            self.record.setdefault("resumes", []).append({"utc": utc(), "source": src,
                                                          "unrecorded_attempts_charged": extra})
            self.record["status"] = "running"
            self.record.pop("blocker", None)
        else:
            self.used_s = self.external_prior_seconds
            self.pool_used = {k: 0.0 for k in self.pools}
            self.record = {"driver": "scripts/recover.py", "created_utc": utc(), "source": src,
                           "historical_root": str(self.hist), "historical_manifest": str(self.manifest_path),
                           "historical_manifest_sha256": sha256_file(self.manifest_path),
                           "stage_ceiling_s": self.stage_ceiling, "max_attempts": MAX_ATTEMPTS,
                           "ceilings_s": self.ceilings, "pools_s": self.pools, "step_pool": STEP_POOL,
                           "cap_paths": [str(p) for p in self.guard_kw["cap_paths"]], "time_l": self.time_l,
                           "env": self.env, "cached": {}, "steps": [], "assembly": {}, "status": "running"}

    # -------------------------------------------------------------- bookkeeping
    def save(self):
        self.record["stage_seconds_used"] = round(self.used_s, 3)
        self.record["pool_seconds_used"] = {k: round(v, 3) for k, v in self.pool_used.items()}
        p = self.run_dir / "recovery_manifest.json"
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.record, indent=1, default=str))
        tmp.replace(p)

    def input_hashes(self, paths: list[Path]) -> dict:
        return {str(p): sha256_file(p) for p in paths if p.is_file()}

    def write_once_json(self, path: Path, obj) -> Path:
        txt = json.dumps(obj, indent=1, sort_keys=True)
        if path.exists():
            if path.read_text() != txt:
                raise Blocked(f"immutable file differs on resume: {path}")
            return path
        path.write_text(txt)
        return path

    def link(self, src: Path, dst: Path):
        if dst.is_symlink():
            if os.readlink(dst) != str(src):
                raise Blocked(f"existing link {dst} -> {os.readlink(dst)} != {src}")
            return
        if dst.exists():
            raise Blocked(f"{dst} exists and is not the expected symlink")
        os.symlink(src, dst)

    def receipt_path(self, name: str) -> Path:
        return self.run_dir / "receipts" / f"{name}.json"

    def write_receipt(self, name: str, out: Path, entry: dict) -> dict:
        rp = self.receipt_path(name)
        rp.parent.mkdir(exist_ok=True)
        r = {"name": name, "out_dir": str(out), "attempt_dir": entry["attempt_dir"], "command": entry["command"],
             "created_utc": utc(), "source": self.record["source"], "files_sha256": dir_hashes(out)}
        with open(rp, "x") as fh:  # immutable: exclusive create
            json.dump(r, fh, indent=1, sort_keys=True)
        os.chmod(rp, 0o444)
        return r

    def reuse_receipt(self, name: str) -> tuple[Path, dict]:
        r = json.loads(self.receipt_path(name).read_text())
        out = Path(r["out_dir"])
        if not out.is_dir() or dir_hashes(out) != r["files_sha256"]:
            raise Blocked(f"{name}: completed output no longer matches its receipt ({out}); not rerunning")
        self.record["steps"].append({"name": name, "status": "reused-from-receipt", "out_dir": str(out),
                                     "attempt_dir": r["attempt_dir"], "receipt": str(self.receipt_path(name)),
                                     "provenance": "recomputed", "utc": utc()})
        self.save()
        return out, r

    def prior_statuses(self, name: str) -> list[str]:
        """Statuses of earlier attempts of this step on disk (resume). No attempt.json, or 'ok' without a
        receipt (driver died before hashing), counts as an infrastructure 'driver-interrupted' attempt."""
        out = []
        for adir in sorted((self.run_dir / "attempts" / name).glob("attempt-*")):
            aj = adir / "attempt.json"
            lj = adir / "launch.json"
            if not aj.is_file() and lj.is_file() and RG.group_alive(json.loads(lj.read_text())["pgid"]):
                raise Blocked(f"{name}: process group of interrupted attempt {adir.name} is still running; "
                              "stop it before --resume")
            st = json.loads(aj.read_text())["status"] if aj.is_file() else "driver-interrupted"
            out.append("driver-interrupted" if st in ("ok", "interrupted") else st)
        return out

    def step(self, name: str, kind: str, cmd_fn, inputs: list[Path] = ()) -> tuple[Path, dict]:
        """Run up to MAX_ATTEMPTS (counted across resumes); returns (out_dir, receipt)."""
        if self.receipt_path(name).is_file():
            return self.reuse_receipt(name)
        prior = ["driver-interrupted"] * int(self.external_prior_attempts.get(name, 0)) + self.prior_statuses(name)
        bad = [s for s in prior if s not in RG.INFRA_STATUSES]
        if bad:
            raise Blocked(f"{name}: earlier deterministic/non-infrastructure status {bad[0]}")
        mem = sum(s in RG.MEMORY_STATUSES for s in prior)
        if mem >= 2:
            raise Blocked(f"{name}: two memory-stops")
        pool = STEP_POOL.get(name)
        ceiling = self.ceilings[name]
        for attempt in range(len(prior) + 1, MAX_ATTEMPTS + 1):
            remaining = self.stage_ceiling - self.used_s
            if remaining <= 0:
                raise Blocked(f"stage ceiling reached before {name} attempt {attempt}")
            timeout = min(ceiling, remaining)
            if pool:
                prem = self.pools[pool] - self.pool_used.get(pool, 0.0)
                if prem <= 0:
                    raise Blocked(f"{pool} pool ({self.pools[pool]} s total) exhausted before {name} attempt {attempt}")
                timeout = min(timeout, prem)
            kw = dict(self.guard_kw)
            if kind == "fit":
                kw["disk_start_min"] = max(kw["disk_start_min"], self.fit_disk_min)
            base = self.run_dir / "attempts" / name
            t0 = time.time()
            pending_out = base / f"out-{attempt}-{RG.utc()}"
            argv = cmd_fn(pending_out)
            rec = RG.run_guarded(argv, attempt_root=self.run_dir / "attempts", name=name, timeout=timeout,
                                 extra_env=self.env, cwd=self.repo, time_l=self.time_l,
                                 meta={"kind": kind, "pool": pool, "out_dir": str(pending_out),
                                       "input_sha256": self.input_hashes(list(inputs))}, **kw)
            el = time.time() - t0
            self.used_s += el
            if pool:
                self.pool_used[pool] = self.pool_used.get(pool, 0.0) + el
            entry = {"name": name, "kind": kind, "attempt": attempt, "out_dir": str(pending_out),
                     "attempt_dir": rec["attempt_dir"], "status": rec["status"], "returncode": rec["returncode"],
                     "wall_seconds": rec["wall_seconds"], "timeout_s": timeout, "command": argv, "pool": pool,
                     "postrun_time_l": rec.get("postrun_time_l"), "provenance": "recomputed",
                     "stdout": str(Path(rec["attempt_dir"]) / "stdout.log"),
                     "stderr": str(Path(rec["attempt_dir"]) / "stderr.log")}
            self.record["steps"].append(entry)
            self.save()
            if rec["status"] == "ok":
                r = self.write_receipt(name, pending_out, entry)
                entry["receipt"] = str(self.receipt_path(name))
                self.save()
                return pending_out, r
            if rec["status"] == "interrupted":
                raise Interrupted(f"{name}: interrupted; resume with --resume")
            if rec["status"] not in RG.INFRA_STATUSES:
                raise Blocked(f"{name}: deterministic/non-infrastructure status {rec['status']} "
                              f"(rc={rec['returncode']}); see {rec['attempt_dir']}")
            if rec["status"] in RG.MEMORY_STATUSES:
                mem += 1
                if mem >= 2:
                    raise Blocked(f"{name}: two memory-stops")
        raise Blocked(f"{name}: failed after {MAX_ATTEMPTS} attempts")

    # -------------------------------------------------------------- inputs
    def layout(self):
        lay = self.manifest["root_layout"]
        return lay, tuple(self.hist / lay[k] for k in ("data", "armA", "armB"))

    def verify_inputs(self):
        lay, (D, TA, TB) = self.layout()
        self.record["historical_layout"] = {"data": str(D), "armA": str(TA), "armB": str(TB)}
        rels = [lay["data"], lay["armA"]] + [f"{lay['armB']}/{m}" for m in CACHED_B]
        self.record["cached"] = verify_historical(self.hist, self.manifest, rels)
        if not (D / "receipt.json").is_file():
            raise Blocked(f"historical data run incomplete (no receipt.json): {D}")
        for m in ALL_M:
            if not (TA / m / "model.pkl").is_file():
                raise Blocked(f"historical Arm A model missing: {TA / m / 'model.pkl'}")
        self.save()

    def cached_under(self, rel_dir: str) -> dict:
        pre = rel_dir.rstrip("/") + "/"
        return {k[len(pre):]: v for k, v in self.record["cached"].items() if k.startswith(pre)}

    def save_assembly(self):
        self.write_json_atomic(self.run_dir / "assembly.json", self.record["assembly"])
        self.save()

    def write_json_atomic(self, p: Path, obj):
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(obj, indent=1, sort_keys=True, default=str))
        tmp.replace(p)

    # -------------------------------------------------------------- plan
    def run(self, dry_run: bool = False):
        lay, (D, TA, TB) = self.layout()
        self.verify_inputs()
        py, sc = self.python, self.repo / "companion/scripts"
        rm = [py, str(sc / "run_matched.py"), "--workspace", str(self.repo)]
        if dry_run:
            self.record["status"] = "dry-run-verified"
            self.save()
            return
        asm = self.record.setdefault("assembly", {})
        armB = self.run_dir / "armB"
        armB.mkdir(parents=True, exist_ok=True)
        asm.setdefault("armB", {})
        for m in CACHED_B:
            self.link(TB / m, armB / m)
            asm["armB"][m] = {"provenance": "cached", "predictions_dir": str(TB / m), "fit_dir": str(TB / m),
                              "fit_info": str(TB / m / "fit_info.json"),
                              "source_sha256": self.cached_under(f"{lay['armB']}/{m}"),
                              "historical_manifest_sha256": self.record["historical_manifest_sha256"]}
        self.save_assembly()
        for m in RESUME_B:
            fit, fr = self.step(f"B_{m}_fit", "fit", lambda o, m=m: rm + ["--data", str(D), "--arm", "B",
                                                                       "--method", m, "--stage", "fit", "--out", str(o)],
                                inputs=[D / "features_and_classes.json", D / "reference_F.h5ad"])
            extra = []
            if m == "M6":  # relocated B checkpoint: hashes come from the fit receipt, verified at predict
                exp = {k[len("scanvi/"):]: v for k, v in fr["files_sha256"].items() if k.startswith("scanvi/")}
                if not exp:
                    raise Blocked("B_M6 fit receipt lists no scanvi/ checkpoint files")
                hp = self.write_once_json(self.run_dir / "armB_M6_scanvi_expected_sha256.json", exp)
                extra = ["--expected-hashes", str(hp)]
            pred, pr = self.step(f"B_{m}_predict", "predict",
                                 lambda o, m=m, fit=fit, extra=extra: rm + ["--data", str(D), "--arm", "B", "--method",
                                                                            m, "--stage", "predict", "--model-dir",
                                                                            str(fit), "--out", str(o)] + extra,
                                 inputs=[fit / "model.pkl"])
            self.link(pred, armB / m)
            asm["armB"][m] = {"provenance": "recomputed", "fit_dir": str(fit), "fit_info": str(fit / "fit_info.json"),
                              "fit_receipt": str(self.receipt_path(f"B_{m}_fit")),
                              "fit_files_sha256": fr["files_sha256"], "predictions_dir": str(pred),
                              "predict_receipt": str(self.receipt_path(f"B_{m}_predict")),
                              "predictions_sha256": pr["files_sha256"], "source": self.record["source"]}
            if m == "M4":
                asm["armB"][m]["note"] = ("chosen_C and validation_macro_f1_by_C are in fit_info.json "
                                          "(T1 exact comparison; model export uses fit_dir/model.pkl)")
            self.save_assembly()
        if self.stop_after_matched:
            raise Interrupted("Matched recovery complete; paused before secondary protein data and scoring")
        ci, _ = self.step("cite_build", "cite_build",
                          lambda o: [py, str(sc / "build_cite.py"), "--workspace", str(self.repo), "--data", str(D),
                                     "--out", str(o)])
        tc = self.run_dir / "armA_cite"
        tc.mkdir(exist_ok=True)
        asm.setdefault("armA_cite", {})
        for m in ALL_M:
            extra = []
            if m == "M6":
                exp = self.cached_under(f"{lay['armA']}/M6/scanvi")
                if not exp:
                    raise Blocked("no manifest hashes for historical Arm A M6 scanvi checkpoint")
                hp = self.write_once_json(self.run_dir / "armA_M6_scanvi_expected_sha256.json", exp)
                extra = ["--expected-hashes", str(hp)]
            o, pr = self.step(f"A_{m}_cite", "cite_predict",
                              lambda o, m=m, extra=extra: rm + ["--data", str(ci), "--arm", "A", "--method", m,
                                                                "--stage", "predict", "--model-dir", str(TA / m),
                                                                "--out", str(o)] + extra, inputs=[TA / m / "model.pkl"])
            self.link(o, tc / m)
            asm["armA_cite"][m] = {"provenance": "recomputed-predictions-from-cached-fit", "fit_dir": str(TA / m),
                                   "fit_info": str(TA / m / "fit_info.json"),
                                   "fit_source_sha256": {k: v for k, v in self.cached_under(f"{lay['armA']}/{m}").items()
                                                         if k in ("model.pkl", "fit_info.json") or k.startswith("scanvi/")},
                                   "predictions_dir": str(o), "predictions_sha256": pr["files_sha256"],
                                   "source": self.record["source"]}
            self.save_assembly()
        scd, _ = self.step("score", "score",
                           lambda o: [py, str(sc / "score_all.py"), "--workspace", str(self.repo), "--data", str(D),
                                      "--matched", f"A={TA}", f"B={armB}", "--reps", "1000",
                                      "--natural-unknown-scope", "natural", "--out", str(o)],
                           inputs=[sc / "score_all.py"])
        self.step("protein", "protein",
                  lambda o: [py, str(sc / "protein_check.py"), "--workspace", str(self.repo), "--cite", str(ci),
                             "--matched", f"A={tc}", "--thresholds", str(scd / "thresholds_validation.csv"),
                             "--out", str(o)])
        self.record["status"] = "complete"
        self.save()

    # -------------------------------------------------------------- R0 preflight (read-only on inputs)
    def preflight(self, watchdog_selftest: bool) -> bool:
        pf = {"utc": utc(), "mode": "preflight", "labels_read": False, "checks": {}}
        ok = True
        pf["cap_usage"] = RG.tree_usage(self.guard_kw["cap_paths"])
        pf["storage_cap_bytes"] = self.guard_kw["storage_cap"]
        pf["checks"]["storage_within_cap"] = pf["cap_usage"]["total_bytes"] <= self.guard_kw["storage_cap"]
        pf["free_bytes"] = RG.free_bytes(self.guard_kw["disk_path"])
        pf["checks"]["free_disk_ge_start_floor"] = pf["free_bytes"] >= self.guard_kw["disk_start_min"]
        pf["checks"]["usr_bin_time_present"] = os.access(RG.TIME_BIN, os.X_OK)
        try:
            self.verify_inputs()
            pf["checks"]["historical_inputs_verified"] = True
            pf["historical_files_verified"] = len(self.record["cached"])
        except Blocked as e:
            pf["checks"]["historical_inputs_verified"] = False
            pf["historical_error"] = str(e)
        _, (D, _, _) = self.layout()
        fc = D / "features_and_classes.json"
        if fc.is_file():  # reference-only class lists; no query labels are read
            meta = json.loads(fc.read_text())
            pf["features_and_classes_sha256"] = sha256_file(fc)
            pf["K"] = meta.get("K")
            pf["K_B"] = meta.get("K_B")
            pf["topup_related_keys"] = {k: meta[k] for k in meta if "top" in k.lower() or "rare" in k.lower()}
        env_code = ("import sys,json,importlib.metadata as md,importlib.util as u;"
                    "d=sorted(f\"{x.metadata['Name']}=={x.version}\" for x in md.distributions());"
                    "s=u.find_spec('celltypist');"
                    "print(json.dumps({'python':sys.version,'executable':sys.executable,'dists':d,"
                    "'celltypist_origin':s.origin if s else None}))")
        r = subprocess.run([self.python, "-I", "-c", env_code], capture_output=True, text=True,
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        if r.returncode == 0:
            e = json.loads(r.stdout)
            pf["environment"] = {"python": e["python"], "executable": e["executable"], "n_dists": len(e["dists"]),
                                 "dists": e["dists"],
                                 "dists_sha256": hashlib.sha256("\n".join(e["dists"]).encode()).hexdigest()}
            ct = Path(e["celltypist_origin"]).parent / "models.py" if e["celltypist_origin"] else None
            src = ct.read_text() if ct and ct.is_file() else ""
            pf["checks"]["celltypist_folder_env_honoured"] = "os.getenv('CELLTYPIST_FOLDER'" in src or \
                'os.getenv("CELLTYPIST_FOLDER"' in src
            pf["celltypist_models_py"] = str(ct) if ct else None
        else:
            pf["checks"]["environment_listed"] = False
            pf["environment_error"] = r.stderr[-2000:]
        if watchdog_selftest:
            pf["watchdog_selftest"] = st = watchdog_selftest_run(self.run_dir / "preflight-selftest", self.guard_kw)
            pf["checks"]["watchdog_1GiB_selftest"] = st["passed"]
        ok = all(pf["checks"].values())
        pf["status"] = "pass" if ok else "fail"
        self.write_json_atomic(self.run_dir / "preflight.json", pf)
        self.record["preflight"] = {"status": pf["status"], "file": str(self.run_dir / "preflight.json")}
        self.record["status"] = "preflight-" + pf["status"]
        self.save()
        return ok


ALLOC_CODE = ("import sys,time\nn=int(sys.argv[1]);b=bytearray(n)\n"
              "for i in range(0,n,4096): b[i]=1\ntime.sleep(float(sys.argv[2]))\n")


def watchdog_selftest_run(root: Path, guard_kw: dict, threshold: int = 1 * GiB) -> dict:
    """R0 OA-5 item 6: production launcher (run_guarded, time -l on) with a 1 GiB threshold.
    Over: 1.5 GiB allocator must be killed as memory-stop (phys_footprint). Under: 256 MiB must pass."""
    kw = dict(guard_kw, mem_limit=threshold, cap_paths=[], timeout=120)
    over = RG.run_guarded([sys.executable, "-c", ALLOC_CODE, str(int(1.5 * GiB)), "60"], attempt_root=root,
                          name="over-1GiB", time_l=True, **kw)
    under = RG.run_guarded([sys.executable, "-c", ALLOC_CODE, str(256 << 20), "2"], attempt_root=root,
                           name="under-1GiB", time_l=True, **kw)
    want_over = {"memory-stop"} if sys.platform == "darwin" else {"memory-stop", "memory-watchdog-rss"}
    passed = (over["status"] in want_over and over["wall_seconds"] < 60 and under["status"] == "ok")
    return {"threshold_bytes": threshold, "passed": passed,
            "over": {k: over.get(k) for k in ("status", "wall_seconds", "peak_phys_footprint_bytes", "attempt_dir")},
            "under": {k: under.get(k) for k in ("status", "wall_seconds", "peak_phys_footprint_bytes",
                                                 "postrun_time_l", "attempt_dir")}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workspace", required=True, help="study repo root (worktree)")
    ap.add_argument("--study-root", default=None, help="root holding .venv/.tools/.cache-study (default: workspace)")
    ap.add_argument("--historical-root", default=None, help="default: $HISTORICAL_RUNS_ROOT")
    ap.add_argument("--historical-manifest", required=True)
    ap.add_argument("--run-dir", required=True, help="new Mode R run dir (must not exist unless --resume)")
    ap.add_argument("--python", required=True, help="pinned study venv python")
    ap.add_argument("--prior-attempts", default="{}", help="Recorded prior attempts outside this recovery directory; count toward limits")
    ap.add_argument("--prior-seconds", type=float, default=0, help="Previously consumed approved stage budget")
    ap.add_argument("--stage-ceiling", type=float, default=STAGE_CEILING_S)
    ap.add_argument("--ceilings", default=None, help="JSON overrides of per-step ceilings (tests only)")
    ap.add_argument("--pools", default=None, help="JSON overrides of pooled ceilings (tests only)")
    ap.add_argument("--guard-overrides", default=None, help="JSON overrides of guard limits (tests only)")
    ap.add_argument("--cap-path", action="append", default=[], help="extra storage-cap path")
    ap.add_argument("--mem-limit-gib", type=float, default=12.0)
    ap.add_argument("--mem-poll", type=float, default=5.0)
    ap.add_argument("--fit-disk-gib", type=float, default=4.0)
    ap.add_argument("--no-time-l", action="store_true", help="tests only: do not wrap steps in /usr/bin/time -l")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", help="verify historical inputs only; launch nothing")
    g.add_argument("--preflight", action="store_true", help="R0 read-only measurements; launch no study step")
    g.add_argument("--resume", action="store_true", help="resume an interrupted run in --run-dir")
    ap.add_argument("--stop-after-matched", action="store_true", help="Operational checkpoint: finish B M4–M6, then pause without scoring")
    ap.add_argument("--watchdog-selftest", action="store_true", help="with --preflight: 1 GiB synthetic check")
    a = ap.parse_args(argv)
    run_dir = Path(a.run_dir)
    if not a.resume:
        run_dir.mkdir(parents=True, exist_ok=False)
    try:
        d = Driver(a, resume=a.resume)
    except Blocked as e:
        print(f"BLOCKED: {e}", file=sys.stderr)
        return 3
    try:
        if a.preflight:
            return 0 if d.preflight(a.watchdog_selftest) else 3
        d.run(dry_run=a.dry_run)
    except Interrupted as e:
        d.record["status"] = "interrupted"
        d.record["blocker"] = str(e)
        d.save()
        print(f"INTERRUPTED: {e}", file=sys.stderr)
        return 4
    except Blocked as e:
        d.record["status"] = "blocked"
        d.record["blocker"] = str(e)
        d.save()
        print(f"BLOCKED: {e}", file=sys.stderr)
        return 3
    print(json.dumps({"status": d.record["status"], "stage_seconds_used": round(d.used_s, 1)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

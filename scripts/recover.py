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

Amended continuation (--amendment 2026-10-06-approved-protein-replacement; protocol/amendments/
protein-replacement-reviewed.md, approved by the user, sha256 pinned below):
  * NEW run dir only. Completed Arm B M4/M5/M6 fit+predict are ADOPTED (never refit) from an explicit prior
    recovery_manifest.json (--adopt-from): every adopted output dir must hash-match its receipt exactly, the
    receipts must match the manifest/assembly (and the --adopt-receipts-dir evidence copies byte-for-byte),
    the prior source must be clean and its scientific code hashes must equal the current checkout (only
    scripts/recover.py may differ). Any mismatch blocks; there is no fallback to refitting.
  * The original run dir is read only; adopted steps keep their original source provenance, receipts and
    attempt dirs. Stage seconds, pool seconds and attempt statuses are carried forward exactly once
    (prior stage_seconds_used already contains the earlier --prior-seconds charge; it is not re-added).
  * R4' = cite_build with companion/scripts/build_cite_totalvi.py --workspace --data --out. R4 attempt 1
    (HTTP 403) is counted, so exactly one attempt remains; its time (--prior-r4-seconds) counts against the
    8 h stage ceiling. Any R4' failure ends the replacement (no retry).
  * eligibility.json (written by the builder) decides 0/1/2 eligible files. Zero eligible: R5/R7 are
    recorded explicitly as not run (protein_check.status = "not_run"); scoring still runs.
  * R5 (Arm A CITE predict incl. M6 query adaptation) keeps the shared 30 min pool and starts only with
    >= 4 GiB free disk (--r5-disk-gib).

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
import result_manifest as RM  # noqa: E402

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

# ---- approved protein-replacement amendment (protocol/amendments/2026-10-06-approved-protein-replacement.md)
AMENDMENT_ID = RM.AMENDMENT_ID
AMENDMENT_REVIEWED = "protocol/amendments/protein-replacement-reviewed.md"
AMENDMENT_SHA256 = "e5ba0c347b66cba1c76dd249e386789c26e1916a95bc9c82a0208a696c89eae1"
REPLACEMENT_BUILDER = "companion/scripts/build_cite_totalvi.py"
R4_ATTEMPTS_USED = 1          # C2: the 10x HTTP 403 was R4 attempt 1 of 2; R4' is the last
COUNTED = "prior-attempt-counted"  # counts toward MAX_ATTEMPTS without being a deterministic-failure verdict
ADOPTABLE = tuple(f"B_{m}_{k}" for m in RESUME_B for k in ("fit", "predict"))
# scientific training/prediction code must be byte-identical to the adopted run; only this driver may differ
ADOPTION_MAY_DIFFER = ("scripts/recover.py",)
ADOPTION_REQUIRED_CODE = ("companion/scripts/run_matched.py", "companion/src/celltransfer/methods.py",
                          "companion/src/celltransfer/evaluate.py")
R5_DISK_GIB = 4.0


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
              "scripts/recover.py", "scripts/resource_guard.py", REPLACEMENT_BUILDER)


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


def _cmd_arg(cmd: list, flag: str):
    return cmd[cmd.index(flag) + 1] if flag in cmd else None


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
        self.amendment = getattr(a, "amendment", None)
        self.adopt_from = Path(a.adopt_from).resolve() if getattr(a, "adopt_from", None) else None
        self.adopt_receipts_dir = (Path(a.adopt_receipts_dir).resolve() if getattr(a, "adopt_receipts_dir", None)
                                   else None)
        self.prior_r4_seconds = getattr(a, "prior_r4_seconds", None)
        self.r5_disk_min = int(getattr(a, "r5_disk_gib", R5_DISK_GIB) * GiB) if self.amendment else 0
        self.counted_prior = {}     # name -> attempts counted (no status verdict), e.g. R4 attempt 1 (403)
        self.carried_statuses = {}  # name -> statuses of attempts recorded in the adopted prior run
        self._adopted = None
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
        if self.amendment:
            self.check_amendment_args()
        elif self.adopt_from or self.adopt_receipts_dir or self.prior_r4_seconds is not None:
            raise Blocked("--adopt-from/--adopt-receipts-dir/--prior-r4-seconds are only valid with --amendment")
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
            if self.record.get("amendment", {}).get("id") != self.amendment:
                raise Blocked("--resume: amendment differs from the interrupted run "
                              f"({self.record.get('amendment', {}).get('id')!r} vs {self.amendment!r})")
            if self.amendment:
                ad = self.record["adoption"]
                if ad["prior_manifest_sha256"] != sha256_file(self.adopt_from):
                    raise Blocked("--resume: --adopt-from manifest differs from the one adopted by this run")
                if float(ad["carried"]["prior_r4_seconds"]) != float(self.prior_r4_seconds):
                    raise Blocked("--resume: --prior-r4-seconds differs from the value recorded at adoption")
                self.counted_prior = dict(ad["carried"]["counted_prior_attempts"])
                self.carried_statuses = {k: list(v) for k, v in ad["carried"]["prior_statuses"].items()}
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
            if self.amendment:
                self.start_amended_run()

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
        prior = (["driver-interrupted"] * int(self.external_prior_attempts.get(name, 0))
                 + [COUNTED] * int(self.counted_prior.get(name, 0))
                 + list(self.carried_statuses.get(name, [])) + self.prior_statuses(name))
        bad = [s for s in prior if s not in RG.INFRA_STATUSES and s != COUNTED]
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
            if kind == "cite_predict" and self.r5_disk_min:  # amendment s8: R5 (M6 query adaptation) >= 4 GiB
                kw["disk_start_min"] = max(kw["disk_start_min"], self.r5_disk_min)
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

    # -------------------------------------------------------------- amendment: adoption + carry-forward
    def check_amendment_args(self):
        if self.amendment != AMENDMENT_ID:
            raise Blocked(f"unknown amendment {self.amendment!r}; only {AMENDMENT_ID!r} is approved")
        rv = self.repo / AMENDMENT_REVIEWED
        if not rv.is_file() or sha256_file(rv) != AMENDMENT_SHA256:
            raise Blocked(f"{AMENDMENT_REVIEWED} missing or not the approved text (sha256 {AMENDMENT_SHA256})")
        if not self.adopt_from:
            raise Blocked("--amendment requires --adopt-from: no refit of Arm B M4-M6 is authorised")
        if self.prior_r4_seconds is None or not float(self.prior_r4_seconds) >= 0:
            raise Blocked("--amendment requires --prior-r4-seconds (measured time of R4 attempt 1, the HTTP 403); "
                          "it counts against the 8 h stage ceiling and is never estimated by this driver")
        if self.external_prior_seconds:
            raise Blocked("--prior-seconds must be 0 with --adopt-from: the adopted manifest's stage_seconds_used "
                          "already contains earlier charges (double counting refused)")
        if self.external_prior_attempts:
            raise Blocked("--prior-attempts must be empty with --adopt-from: attempts are carried from the adopted "
                          "manifest and R4 attempt 1 is fixed by the amendment (double counting refused)")

    def load_prior(self) -> tuple[dict, str, Path]:
        if not self.adopt_from.is_file():
            raise Blocked(f"--adopt-from manifest not found: {self.adopt_from}")
        sha = sha256_file(self.adopt_from)
        prior = json.loads(self.adopt_from.read_text())
        if prior.get("driver") != "scripts/recover.py":
            raise Blocked("adopted manifest was not written by scripts/recover.py")
        receipts = {Path(st["receipt"]).parent for st in prior.get("steps", []) if st.get("receipt")}
        if len(receipts) != 1:
            raise Blocked(f"adopted manifest receipts are not in exactly one run dir: {sorted(map(str, receipts))}")
        prior_run = next(iter(receipts)).parent
        if prior_run.resolve() == self.run_dir.resolve():
            raise Blocked("adoption must target a NEW run dir; the original run is immutable")
        live = prior_run / "recovery_manifest.json"
        if not live.is_file() or json.loads(live.read_text()) != prior:
            raise Blocked(f"supplied prior manifest does not match the original run's own manifest ({live})")
        return prior, sha, prior_run

    def start_amended_run(self):
        """New run: carry time, pool and attempt accounting forward exactly once."""
        prior, sha, prior_run = self.load_prior()
        if prior.get("status") not in ("interrupted", "blocked"):
            raise Blocked(f"adopted run status {prior.get('status')!r}; only a paused/blocked run can be continued")
        if "stage_seconds_used" not in prior or "pool_seconds_used" not in prior:
            raise Blocked("adopted manifest lacks stage/pool seconds; time cannot be carried forward")
        recorded = {st["attempt_dir"] for st in prior["steps"] if st.get("attempt_dir")}
        statuses, unrecorded, extra_s, extra_pool = {}, [], 0.0, {}
        for st in prior["steps"]:
            if "attempt" not in st:  # reused-from-receipt entries are not attempts
                continue
            if st["status"] == "ok" and st["name"] not in ADOPTABLE:
                raise Blocked(f"prior completed step {st['name']} is not adoptable under the amendment; not repeating")
            statuses.setdefault(st["name"], []).append(st["status"])
        for adir in sorted((prior_run / "attempts").glob("*/attempt-*")):
            if str(adir) in recorded:
                continue
            aj = adir / "attempt.json"
            secs = json.loads(aj.read_text()).get("wall_seconds", 0.0) if aj.is_file() else \
                estimate_interrupted_seconds(adir)
            stt = json.loads(aj.read_text())["status"] if aj.is_file() else "driver-interrupted"
            stt = "driver-interrupted" if stt in ("ok", "interrupted") else stt
            statuses.setdefault(adir.parent.name, []).append(stt)
            unrecorded.append({"name": adir.parent.name, "attempt_dir": str(adir), "charged_seconds": round(secs, 3)})
            extra_s += secs
            if STEP_POOL.get(adir.parent.name):
                extra_pool[STEP_POOL[adir.parent.name]] = extra_pool.get(STEP_POOL[adir.parent.name], 0.0) + secs
        if any(n in ADOPTABLE for n in (u["name"] for u in unrecorded)):
            raise Blocked("prior run has unrecorded attempts of an adoptable step; adoption is ambiguous")
        prior_stage = float(prior["stage_seconds_used"])
        self.used_s = prior_stage + extra_s + float(self.prior_r4_seconds)
        self.pool_used = {k: 0.0 for k in self.pools}
        for k, v in prior["pool_seconds_used"].items():
            self.pool_used[k] = self.pool_used.get(k, 0.0) + float(v)
        for k, v in extra_pool.items():
            self.pool_used[k] = self.pool_used.get(k, 0.0) + v
        self.counted_prior = {"cite_build": R4_ATTEMPTS_USED}
        self.carried_statuses = {k: v for k, v in statuses.items() if k not in ADOPTABLE}
        self.record["amendment"] = {"id": AMENDMENT_ID, "reviewed": AMENDMENT_REVIEWED,
                                    "reviewed_sha256": AMENDMENT_SHA256, "cite_builder": REPLACEMENT_BUILDER,
                                    "r5_disk_start_min_bytes": self.r5_disk_min}
        self.record["adoption"] = {
            "prior_manifest": str(self.adopt_from), "prior_manifest_sha256": sha, "prior_run_dir": str(prior_run),
            "prior_source": prior["source"], "receipts_evidence_dir": str(self.adopt_receipts_dir)
            if self.adopt_receipts_dir else None,
            "carried": {"prior_stage_seconds_used": prior_stage,
                        "prior_stage_seconds_note": "includes the prior run's own --prior-seconds charge; not re-added",
                        "unrecorded_prior_attempts_charged": unrecorded, "prior_r4_seconds": float(self.prior_r4_seconds),
                        "r4_attempts_used_before_this_run": R4_ATTEMPTS_USED,
                        "prior_pool_seconds_used": prior["pool_seconds_used"],
                        "start_stage_seconds_used": round(self.used_s, 3),
                        "counted_prior_attempts": self.counted_prior, "prior_statuses": self.carried_statuses}}

    def verify_adoption(self) -> dict:
        """Read-only re-verification (every run and resume) of the adopted B M4-M6 outputs."""
        prior, sha, prior_run = self.load_prior()
        ad = self.record["adoption"]
        if sha != ad["prior_manifest_sha256"] or str(prior_run) != ad["prior_run_dir"]:
            raise Blocked("adopted manifest changed since adoption was recorded")
        psrc = prior.get("source") or {}
        if psrc.get("dirty") is not False or not psrc.get("git_rev"):
            raise Blocked("adopted run source is not a clean recorded revision")
        if prior.get("historical_manifest_sha256") != self.record["historical_manifest_sha256"]:
            raise Blocked("adopted run used a different historical manifest")
        if prior.get("historical_layout", {}).get("data") != self.record["historical_layout"]["data"]:
            raise Blocked("adopted run used a different historical data dir")
        pcode, ccode = psrc.get("code_sha256", {}), self.record["source"]["code_sha256"]
        missing = [f for f in ADOPTION_REQUIRED_CODE if f not in pcode]
        if missing:
            raise Blocked(f"adopted run did not record hashes for scientific code {missing}")
        changed = sorted(f for f, h in pcode.items() if f not in ADOPTION_MAY_DIFFER and ccode.get(f) != h)
        if changed:
            raise Blocked(f"scientific code differs from the adopted run: {changed}; adoption refused, no refit")
        asm_b = (prior.get("assembly") or {}).get("armB", {})
        if self.adopt_receipts_dir:
            ea = self.adopt_receipts_dir / "assembly.json"
            if ea.is_file() and json.loads(ea.read_text()) != prior.get("assembly"):
                raise Blocked("evidence assembly.json differs from the adopted manifest's assembly")
        out = {}
        for name in ADOPTABLE:
            oks = [st for st in prior["steps"] if st["name"] == name and st["status"] == "ok"]
            if len(oks) != 1:
                raise Blocked(f"{name}: adopted manifest has {len(oks)} ok attempts (need exactly 1)")
            st = oks[0]
            rp = Path(st["receipt"])
            if not rp.is_file():
                raise Blocked(f"{name}: receipt missing {rp}")
            rb = rp.read_bytes()
            if self.adopt_receipts_dir:
                ev = self.adopt_receipts_dir / f"{name}.json"
                if not ev.is_file() or ev.read_bytes() != rb:
                    raise Blocked(f"{name}: receipt differs from evidence copy {ev}")
            r = json.loads(rb)
            for k in ("name", "out_dir", "attempt_dir", "command"):
                if r.get(k) != (name if k == "name" else st.get(k)):
                    raise Blocked(f"{name}: receipt field {k} does not match the adopted manifest")
            if r.get("source") != psrc:
                raise Blocked(f"{name}: receipt source differs from the adopted run source")
            aj = Path(st["attempt_dir"]) / "attempt.json"
            if not aj.is_file() or json.loads(aj.read_text()).get("status") != "ok":
                raise Blocked(f"{name}: original attempt record missing or not ok ({aj})")
            od = Path(st["out_dir"])
            if not r.get("files_sha256"):
                raise Blocked(f"{name}: receipt lists no files")
            if not od.is_dir() or dir_hashes(od) != r["files_sha256"]:
                raise Blocked(f"{name}: adopted output does not hash-match its receipt ({od}); not refitting")
            if _cmd_arg(st["command"], "--data") != self.record["historical_layout"]["data"]:
                raise Blocked(f"{name}: adopted command used different --data")
            out[name] = {"step": st, "receipt": r, "receipt_path": str(rp),
                         "receipt_sha256": hashlib.sha256(rb).hexdigest()}
        for m in RESUME_B:
            fit, pred = out[f"B_{m}_fit"], out[f"B_{m}_predict"]
            if _cmd_arg(pred["step"]["command"], "--model-dir") != fit["step"]["out_dir"]:
                raise Blocked(f"B_{m}_predict did not use the adopted B_{m}_fit model dir")
            a = asm_b.get(m, {})
            if (a.get("fit_dir") != fit["step"]["out_dir"] or a.get("predictions_dir") != pred["step"]["out_dir"]
                    or a.get("fit_files_sha256") != fit["receipt"]["files_sha256"]
                    or a.get("predictions_sha256") != pred["receipt"]["files_sha256"]):
                raise Blocked(f"B_{m}: adopted assembly entry does not match its receipts")
            if m == "M6":
                hp = _cmd_arg(pred["step"]["command"], "--expected-hashes")
                exp = {k[len("scanvi/"):]: v for k, v in fit["receipt"]["files_sha256"].items()
                       if k.startswith("scanvi/")}
                if not hp or not exp or not Path(hp).is_file() or json.loads(Path(hp).read_text()) != exp:
                    raise Blocked("B_M6: predict checkpoint-hash file missing or differs from the fit receipt")
        return out

    def record_adopted(self, name: str, a: dict):
        st = a["step"]
        entry = {"name": name, "kind": st.get("kind"), "status": "adopted", "attempt": st.get("attempt"),
                 "out_dir": st["out_dir"], "attempt_dir": st["attempt_dir"], "receipt": a["receipt_path"],
                 "receipt_sha256": a["receipt_sha256"], "command": st["command"],
                 "wall_seconds": st.get("wall_seconds"),
                 "charged": "in carried prior stage_seconds_used (not re-charged)",
                 "provenance": "recomputed-in-prior-run-adopted", "source": self.record["adoption"]["prior_source"]}
        old = [e for e in self.record["steps"] if e["name"] == name and e.get("status") == "adopted"]
        if old:
            if any({k: v for k, v in e.items() if k != "utc"} != entry for e in old):
                raise Blocked(f"{name}: adopted record changed on resume")
            return
        entry["utc"] = utc()
        self.record["steps"].append(entry)

    def read_eligibility(self, ci: Path, receipt: dict) -> dict:
        p = ci / RM.ELIGIBILITY_FILE
        try:
            el = RM.parse_eligibility(p)
        except (RM.ManifestError, OSError, ValueError) as e:
            raise Blocked(f"R4' output has no valid {RM.ELIGIBILITY_FILE}: {e}") from e
        if receipt["files_sha256"].get(RM.ELIGIBILITY_FILE) != el["sha256"]:
            raise Blocked("eligibility.json differs from the hash recorded in the R4' receipt")
        for n in RM.REPLACEMENT_FILES:
            need = [f"query_{n}_F.h5ad", f"adt_{n}.parquet", f"released_predictions_{n}.parquet"]
            have = [f for f in need if (ci / f).exists()]
            if n in el["eligible"] and have != need:
                raise Blocked(f"eligible file {n}: R4' outputs missing {sorted(set(need) - set(have))}")
            if n not in el["eligible"] and have:
                raise Blocked(f"ineligible file {n}: R4' built query outputs {have}")
        rec = {"path": str(p), "sha256": el["sha256"], "verdicts": el["verdicts"], "eligible": el["eligible"],
               "n_eligible": el["n_eligible"], "first_failing_criterion": el["first_failing_criterion"]}
        self.record["eligibility"] = rec
        return rec

    # -------------------------------------------------------------- plan
    def run(self, dry_run: bool = False):
        lay, (D, TA, TB) = self.layout()
        self.verify_inputs()
        if self.amendment:
            self._adopted = self.verify_adoption()
            self.record["adoption"]["verified_utc"] = utc()
            self.save()
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
            if self._adopted is not None:
                self.adopt_b(m, armB, asm)
                continue
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
        if self.amendment:
            return self.run_amended_secondary(D, TA, armB, lay, py, sc, rm)
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

    def adopt_b(self, m: str, armB: Path, asm: dict):
        fit, pred = self._adopted[f"B_{m}_fit"], self._adopted[f"B_{m}_predict"]
        self.record_adopted(f"B_{m}_fit", fit)
        self.record_adopted(f"B_{m}_predict", pred)
        fd, pd_ = Path(fit["step"]["out_dir"]), Path(pred["step"]["out_dir"])
        self.link(pd_, armB / m)
        ad = self.record["adoption"]
        asm["armB"][m] = {"provenance": "adopted-recomputed", "fit_dir": str(fd), "fit_info": str(fd / "fit_info.json"),
                          "fit_receipt": fit["receipt_path"], "fit_receipt_sha256": fit["receipt_sha256"],
                          "fit_files_sha256": fit["receipt"]["files_sha256"], "predictions_dir": str(pd_),
                          "predict_receipt": pred["receipt_path"], "predict_receipt_sha256": pred["receipt_sha256"],
                          "predictions_sha256": pred["receipt"]["files_sha256"], "source": ad["prior_source"],
                          "adopted_from": {"prior_manifest": ad["prior_manifest"],
                                           "prior_manifest_sha256": ad["prior_manifest_sha256"],
                                           "prior_run_dir": ad["prior_run_dir"]},
                          "adopted_by_source": self.record["source"]}
        if m == "M4":
            asm["armB"][m]["note"] = ("chosen_C and validation_macro_f1_by_C are in fit_info.json "
                                      "(T1 exact comparison; model export uses fit_dir/model.pkl)")
        self.save_assembly()

    def run_amended_secondary(self, D: Path, TA: Path, armB: Path, lay: dict, py: str, sc: Path, rm: list):
        asm = self.record["assembly"]
        builder = self.repo / REPLACEMENT_BUILDER
        if not builder.is_file():  # checked before launch: never consume the last R4 attempt on a missing file
            raise Blocked(f"replacement builder missing: {builder}")
        try:
            ci, cr = self.step("cite_build", "cite_build",
                               lambda o: [py, str(builder), "--workspace", str(self.repo), "--data", str(D),
                                          "--out", str(o)])
            el = self.read_eligibility(ci, cr)
        except Blocked as e:
            self.record["protein_check"] = {"status": "not_run", "reason": f"R4' (final R4 attempt) failed: {e}",
                                            "n_eligible": None, "label": RM.PROTEIN_LABEL}
            raise Blocked(f"replacement ended in R4' ({e}); amendment s11 stop wording applies; returning to the user")
        asm["cite"] = {"provenance": "recomputed", "dir": str(ci), "eligibility": self.record["eligibility"]}
        self.save_assembly()
        tc = self.run_dir / "armA_cite"
        if el["n_eligible"]:
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
                                                                    "--out", str(o)] + extra,
                                  inputs=[TA / m / "model.pkl"])
                self.link(o, tc / m)
                asm["armA_cite"][m] = {"provenance": "recomputed-predictions-from-cached-fit", "fit_dir": str(TA / m),
                                       "fit_info": str(TA / m / "fit_info.json"),
                                       "fit_source_sha256": {k: v for k, v in
                                                             self.cached_under(f"{lay['armA']}/{m}").items()
                                                             if k in ("model.pkl", "fit_info.json")
                                                             or k.startswith("scanvi/")},
                                       "predictions_dir": str(o), "predictions_sha256": pr["files_sha256"],
                                       "eligible_files": el["eligible"], "source": self.record["source"]}
                self.save_assembly()
        else:
            self.record["protein_check"] = {
                "status": "not_run", "reason": "no eligible replacement file (eligibility.json)", "n_eligible": 0,
                "first_failing_criterion": el["first_failing_criterion"], "label": RM.PROTEIN_LABEL,
                "steps_not_run": [f"A_{m}_cite" for m in ALL_M] + ["protein"]}
            self.save()
        scd, _ = self.step("score", "score",
                           lambda o: [py, str(sc / "score_all.py"), "--workspace", str(self.repo), "--data", str(D),
                                      "--matched", f"A={TA}", f"B={armB}", "--reps", "1000",
                                      "--natural-unknown-scope", "natural", "--out", str(o)],
                           inputs=[sc / "score_all.py"])
        if el["n_eligible"]:
            self.step("protein", "protein",
                      lambda o: [py, str(sc / "protein_check.py"), "--workspace", str(self.repo), "--cite", str(ci),
                                 "--matched", f"A={tc}", "--thresholds", str(scd / "thresholds_validation.csv"),
                                 "--out", str(o)])
            self.record["protein_check"] = {"status": "run", "n_eligible": el["n_eligible"],
                                            "eligible_files": el["eligible"], "label": RM.PROTEIN_LABEL,
                                            "first_failing_criterion": el["first_failing_criterion"]}
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
    ap.add_argument("--amendment", default=None, choices=[AMENDMENT_ID],
                    help="approved protein-replacement continuation (requires --adopt-from, --prior-r4-seconds)")
    ap.add_argument("--adopt-from", default=None, help="prior recovery_manifest.json whose B M4-M6 are adopted")
    ap.add_argument("--adopt-receipts-dir", default=None,
                    help="evidence copies of the prior receipts/assembly; must match byte-for-byte")
    ap.add_argument("--prior-r4-seconds", type=float, default=None,
                    help="measured wall time of R4 attempt 1 (HTTP 403); charged to the stage ceiling")
    ap.add_argument("--r5-disk-gib", type=float, default=R5_DISK_GIB, help="R5 free-disk start floor (amendment s8)")
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

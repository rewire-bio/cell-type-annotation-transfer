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
# per-attempt ceilings (seconds); mapped from plan s6 Mode R step ceilings (R3 fits incl. +20 min,
# R4 cite build, R5 A CITE predict, R6 score, R7 protein). Fits share R3; per-step values are caps.
DEFAULT_CEILINGS = {"fit": 80 * 60, "predict": 20 * 60, "cite_build": 20 * 60, "cite_predict": 30 * 60,
                    "score": 120 * 60, "protein": 15 * 60}


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


class Driver:
    def __init__(self, a):
        self.repo = Path(a.workspace).resolve()
        self.hist = Path(a.historical_root or os.environ.get("HISTORICAL_RUNS_ROOT", "")).resolve()
        self.run_dir = Path(a.run_dir).resolve()
        self.python = a.python
        self.ceilings = dict(DEFAULT_CEILINGS, **json.loads(a.ceilings or "{}"))
        self.stage_ceiling = a.stage_ceiling
        self.guard_kw = dict(mem_limit=int(a.mem_limit_gib * GiB), swap_growth_limit=int(4 * GiB),
                             disk_start_min=int(3 * GiB), disk_run_min=int(1.5 * GiB), storage_cap=int(7 * GiB),
                             mem_poll=a.mem_poll, disk_poll=30.0, threads=4, disk_path=self.repo,
                             cap_paths=[self.repo / p for p in ("companion", "runs", ".cache-study", "paper/build")])
        self.guard_kw.update(json.loads(a.guard_overrides or "{}"))
        if "disk_path" in self.guard_kw:
            self.guard_kw["disk_path"] = Path(self.guard_kw["disk_path"])
        self.guard_kw["cap_paths"] = [Path(p) for p in self.guard_kw["cap_paths"]]
        self.fit_disk_min = int(a.fit_disk_gib * GiB)
        cache = self.repo / ".cache-study"
        self.env = {"UV_CACHE_DIR": str(cache / "uv"), "HF_HOME": str(cache / "hf"),
                    "XDG_CACHE_HOME": str(cache / "xdg"), "CELLTYPIST_FOLDER": str(cache / "celltypist"),
                    "MPLCONFIGDIR": str(cache / "mpl"), "PYTHONWARNINGS": "ignore"}
        self.manifest_path = Path(a.historical_manifest).resolve()
        self.manifest = json.loads(self.manifest_path.read_text())
        self.used_s = 0.0
        self.record = {"driver": "scripts/recover.py", "created_utc": utc(), "source": source_revision(self.repo),
                       "historical_root": str(self.hist), "historical_manifest": str(self.manifest_path),
                       "historical_manifest_sha256": sha256_file(self.manifest_path),
                       "stage_ceiling_s": self.stage_ceiling, "max_attempts": MAX_ATTEMPTS,
                       "ceilings_s": self.ceilings, "env": self.env, "cached": {}, "steps": [], "status": "running"}

    # -------------------------------------------------------------- bookkeeping
    def save(self):
        self.record["stage_seconds_used"] = round(self.used_s, 3)
        p = self.run_dir / "recovery_manifest.json"
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.record, indent=1, default=str))
        tmp.replace(p)

    def input_hashes(self, paths: list[Path]) -> dict:
        out = {}
        for p in paths:
            if p.is_file():
                out[str(p)] = sha256_file(p)
        return out

    def step(self, name: str, kind: str, cmd_fn, inputs: list[Path] = ()) -> Path:
        """Run up to MAX_ATTEMPTS; cmd_fn(out_dir) -> argv. Returns the successful out dir."""
        for attempt in range(1, MAX_ATTEMPTS + 1):
            remaining = self.stage_ceiling - self.used_s
            if remaining <= 0:
                raise Blocked(f"stage ceiling reached before {name} attempt {attempt}")
            timeout = min(self.ceilings[kind], remaining)
            kw = dict(self.guard_kw)
            if kind == "fit":
                kw["disk_start_min"] = max(kw["disk_start_min"], self.fit_disk_min)
            # each attempt writes to a fresh, never-reused output dir next to its attempt dirs
            base = self.run_dir / "attempts" / name
            n_existing = len([p for p in base.iterdir() if p.name.startswith("attempt-")]) if base.exists() else 0
            t0 = time.time()
            pending_out = base / f"out-{n_existing + 1}-{RG.utc()}"
            argv = cmd_fn(pending_out)
            rec = RG.run_guarded(argv, attempt_root=self.run_dir / "attempts", name=name, timeout=timeout,
                                 extra_env=self.env, cwd=self.repo,
                                 meta={"kind": kind, "out_dir": str(pending_out),
                                       "input_sha256": self.input_hashes(list(inputs))}, **kw)
            self.used_s += time.time() - t0
            entry = {"name": name, "kind": kind, "attempt": attempt, "out_dir": str(pending_out),
                     "attempt_dir": rec["attempt_dir"], "status": rec["status"], "returncode": rec["returncode"],
                     "wall_seconds": rec["wall_seconds"], "timeout_s": timeout, "command": argv,
                     "provenance": "recomputed"}
            self.record["steps"].append(entry)
            self.save()
            if rec["status"] == "ok":
                return pending_out
            if rec["status"] not in RG.INFRA_STATUSES:
                raise Blocked(f"{name}: deterministic/non-infrastructure status {rec['status']} "
                              f"(rc={rec['returncode']}); see {rec['attempt_dir']}")
            if rec["status"] in ("memory-stop", "memory-watchdog-rss") and attempt == MAX_ATTEMPTS:
                raise Blocked(f"{name}: two memory-stops")
        raise Blocked(f"{name}: failed after {MAX_ATTEMPTS} attempts")

    # -------------------------------------------------------------- plan
    def run(self, dry_run: bool = False):
        lay = self.manifest["root_layout"]
        D, TA, TB = (self.hist / lay[k] for k in ("data", "armA", "armB"))
        self.record["historical_layout"] = {"data": str(D), "armA": str(TA), "armB": str(TB)}
        rels = [lay["data"], lay["armA"]] + [f"{lay['armB']}/{m}" for m in CACHED_B]
        self.record["cached"] = verify_historical(self.hist, self.manifest, rels)
        if not (D / "receipt.json").is_file():
            raise Blocked(f"historical data run incomplete (no receipt.json): {D}")
        for m in ALL_M:
            if not (TA / m / "model.pkl").is_file():
                raise Blocked(f"historical Arm A model missing: {TA / m / 'model.pkl'}")
        self.save()
        py, sc = self.python, self.repo / "companion/scripts"
        rm = [py, str(sc / "run_matched.py"), "--workspace", str(self.repo)]
        if dry_run:
            self.record["status"] = "dry-run-verified"
            self.save()
            return
        # Arm B: assemble M1..M6 dir (symlinks named exactly M1..M6, OA-9)
        armB = self.run_dir / "armB"
        armB.mkdir(parents=True, exist_ok=False)
        for m in CACHED_B:
            os.symlink(TB / m, armB / m)
        for m in RESUME_B:
            fit = self.step(f"B_{m}_fit", "fit", lambda o, m=m: rm + ["--data", str(D), "--arm", "B", "--method", m,
                                                                     "--stage", "fit", "--out", str(o)],
                            inputs=[D / "features_and_classes.json", D / "reference_F.h5ad"])
            pred = self.step(f"B_{m}_predict", "predict",
                             lambda o, m=m, fit=fit: rm + ["--data", str(D), "--arm", "B", "--method", m, "--stage",
                                                           "predict", "--model-dir", str(fit), "--out", str(o)],
                             inputs=[fit / "model.pkl"])
            os.symlink(pred, armB / m)
        # CITE build (four frozen 10x files)
        ci = self.step("cite_build", "cite_build",
                       lambda o: [py, str(sc / "build_cite.py"), "--workspace", str(self.repo), "--data", str(D),
                                  "--out", str(o)])
        # Arm A CITE predictions from verified historical Arm A models
        tc = self.run_dir / "armA_cite"
        tc.mkdir()
        for m in ALL_M:
            extra = []
            if m == "M6":
                exp = {k[len(f"{lay['armA']}/M6/scanvi/"):]: v for k, v in self.record["cached"].items()
                       if k.startswith(f"{lay['armA']}/M6/scanvi/")}
                if not exp:
                    raise Blocked("no manifest hashes for historical Arm A M6 scanvi checkpoint")
                hp = self.run_dir / "armA_M6_scanvi_expected_sha256.json"
                hp.write_text(json.dumps(exp, indent=1, sort_keys=True))
                extra = ["--expected-hashes", str(hp)]
            o = self.step(f"A_{m}_cite", "cite_predict",
                          lambda o, m=m, extra=extra: rm + ["--data", str(ci), "--arm", "A", "--method", m, "--stage",
                                                            "predict", "--model-dir", str(TA / m), "--out", str(o)]
                          + extra, inputs=[TA / m / "model.pkl"])
            os.symlink(o, tc / m)
        # scoring (1000 donor bootstraps, D-1a natural scope)
        scd = self.step("score", "score",
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workspace", required=True, help="study repo root (worktree)")
    ap.add_argument("--historical-root", default=None, help="default: $HISTORICAL_RUNS_ROOT")
    ap.add_argument("--historical-manifest", required=True)
    ap.add_argument("--run-dir", required=True, help="new Mode R run dir (must not exist)")
    ap.add_argument("--python", required=True, help="pinned companion venv python")
    ap.add_argument("--stage-ceiling", type=float, default=STAGE_CEILING_S)
    ap.add_argument("--ceilings", default=None, help="JSON overrides of per-kind ceilings (tests only)")
    ap.add_argument("--guard-overrides", default=None, help="JSON overrides of guard limits (tests only)")
    ap.add_argument("--mem-limit-gib", type=float, default=12.0)
    ap.add_argument("--mem-poll", type=float, default=5.0)
    ap.add_argument("--fit-disk-gib", type=float, default=4.0)
    ap.add_argument("--dry-run", action="store_true", help="verify historical inputs only; launch nothing")
    a = ap.parse_args(argv)
    run_dir = Path(a.run_dir)
    run_dir.mkdir(parents=True, exist_ok=False)
    d = Driver(a)
    try:
        d.run(dry_run=a.dry_run)
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

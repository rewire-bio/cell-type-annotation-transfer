#!/usr/bin/env python3
"""Stage H: full clean reproduction (Mode F + tiered comparison + paper), run by `make reproduce`.

Order (each external step runs via resource_guard.run_guarded, 4 threads, 12 GiB group memory,
7 GiB storage cap over .venv/.cache-study/runs/results/paper/build/.tools):

  0 preflight     no pre-existing outputs at results/full/results.json or paper/build/main.pdf;
                  baseline manifest ($CELLTRANSFER_BASELINE_MANIFEST) readable, mode R.
  1 env           uv sync --frozen (new locked env inside the checkout)
  2 acquire       scripts/acquire_inputs.py acquire (live, hash-verified; optional hash-identical
                  external third-party cache only via $CELLTRANSFER_EXTERNAL_CACHE, marked in receipt)
  3 data          companion/scripts/build_data.py -> new expression data
  4 arms          run_matched.py fit+predict, Arms A and B, M1..M6 (protocol methods/seeds)
  5 cite          build_cite.py (4 frozen 10x files); Arm A CITE predictions M1..M6 from fresh models
  6 score         score_all.py --reps 1000 --natural-unknown-scope natural
  7 protein       protein_check.py
  8 results       results/full/results.json + Mode F comparison manifest (fresh_execution true)
  9 compare       compare_runs.py vs baseline manifest (READ ONLY; comparison only) -> must exit 0
 10 paper         scripts/make_paper_assets.py then scripts/build_paper.py -> paper/build/main.pdf

No historical derived output is read for steps 3-8; the baseline manifest is only passed to
compare_runs.py. Mode F wall ceiling 14 h within the 15 h H budget; infrastructure-status retries
(max 1 per step) count against it; deterministic failures stop. A receipt is written after every step.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import resource_guard as RG  # noqa: E402
import result_manifest as RM  # noqa: E402

REPO = HERE.parent
METHODS = ("M1", "M2", "M3", "M4", "M5", "M6")
RESULTS = Path("results/full/results.json")
PDF = Path("paper/build/main.pdf")
CAP_DIRS = (".venv", ".cache-study", "runs", "results", "paper/build", ".tools")


class Stop(RuntimeError):
    pass


def utc() -> str:
    return RG.utc()


class Repro:
    def __init__(self, repo: Path, cfg: dict, runner=None, now=time.time):
        self.repo = repo
        self.cfg = cfg
        f = cfg["mode_f"]
        self.ceiling_f = float(f["stage_ceiling_s"])
        self.ceiling_h = float(cfg["budgets"]["reproduction_seconds"])
        if self.ceiling_f > self.ceiling_h:
            raise Stop("Mode F ceiling exceeds H budget")
        self.step_ceil = f["step_ceilings_s"]
        self.max_attempts = int(f["max_attempts"])
        self.now = now
        self.t0 = now()
        self.f_used = 0.0
        self.pool_used = {}
        self.runner = runner or self._guarded
        self.run_dir = repo / "runs" / f"F-{utc()}"
        cache = repo / ".cache-study"
        self.env = {"UV_CACHE_DIR": str(cache / "uv"), "UV_PROJECT_ENVIRONMENT": str(repo / ".venv"),
                    "HF_HOME": str(cache / "hf"), "XDG_CACHE_HOME": str(cache / "xdg"),
                    "CELLTYPIST_FOLDER": str(cache / "celltypist"), "MPLCONFIGDIR": str(cache / "mpl"),
                    "PYTHONDONTWRITEBYTECODE": "1", "PYTHONWARNINGS": "ignore"}
        self.receipt = {"driver": "scripts/reproduce.py", "created_utc": utc(), "mode": "F",
                        "fresh_execution": True, "config": cfg, "steps": [], "status": "running",
                        "external_cache": None}
        self.python = str(repo / ".venv" / "bin" / "python")

    # ---------------------------------------------------------------- bookkeeping
    def save(self):
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.receipt["h_seconds_used"] = round(self.now() - self.t0, 3)
        self.receipt["f_seconds_used"] = round(self.f_used, 3)
        RM.write_json(self.run_dir / "generation_receipt.json", self.receipt)

    def _guarded(self, argv, name, timeout, cwd):
        g = self.cfg["guard"]
        return RG.run_guarded(argv, attempt_root=self.run_dir / "attempts", name=name, timeout=timeout,
                              extra_env=self.env, cwd=cwd, mem_limit=int(g["mem_limit_gib"] * RG.GiB),
                              swap_growth_limit=int(4 * RG.GiB), disk_start_min=int((4 if name.endswith("_fit") else 3) * RG.GiB),
                              disk_run_min=int(1.5 * RG.GiB), storage_cap=int(g["storage_cap_gib"] * RG.GiB),
                              threads=int(g["threads"]), disk_path=self.repo,
                              cap_paths=[self.repo / p for p in CAP_DIRS], time_l=True)

    def step(self, name, kind, argv_fn, mode_f=True, out=True):
        for attempt in range(1, self.max_attempts + 1):
            h_left = self.ceiling_h - (self.now() - self.t0)
            f_left = self.ceiling_f - self.f_used if mode_f else h_left
            left = min(h_left, f_left)
            if left <= 0:
                raise Stop(f"budget exhausted before {name} attempt {attempt}")
            pool = (name[:1] + "_arm") if name.startswith(("A_M", "B_M")) and not name.endswith("_cite") else ("cite" if name == "cite_build" or name.endswith("_cite") else ("score_protein" if name in ("score", "protein") else None))
            if name in ("acquire", "data"):
                pool = "data_acquisition"
            pool_limit = 3600 if pool == "cite" else (7200 if pool == "data_acquisition" else 9000)
            if pool:
                left = min(left, pool_limit - self.pool_used.get(pool, 0.0))
                if left <= 0:
                    raise Stop(f"approved pooled budget exhausted: {pool}")
            explicit = {"compare": 1200, "paper_assets": 1200, "paper_build": 900}
            timeout = min(float(explicit.get(name, self.step_ceil[kind])), left)
            od = self.run_dir / "out" / f"{name}-{attempt}" if out else None
            argv = argv_fn(od)
            t = self.now()
            rec = self.runner(argv, name, timeout, self.repo)
            dt_ = self.now() - t
            if mode_f:
                self.f_used += dt_
            if pool:
                self.pool_used[pool] = self.pool_used.get(pool, 0.0) + dt_
            self.receipt["steps"].append({"name": name, "kind": kind, "attempt": attempt, "command": argv,
                                          "status": rec["status"], "returncode": rec.get("returncode"),
                                          "wall_seconds": dt_, "pool": pool, "timeout_s": timeout, "out_dir": str(od) if od else None,
                                          "provenance": "recomputed"})
            self.save()
            if rec["status"] == "ok":
                return od
            if rec["status"] not in RG.INFRA_STATUSES:
                raise Stop(f"{name}: status {rec['status']} rc={rec.get('returncode')}")
        raise Stop(f"{name}: failed after {self.max_attempts} attempts")

    # ---------------------------------------------------------------- stages
    def preflight(self, baseline: str | None):
        for rel in (RESULTS, PDF):
            if (self.repo / rel).exists():
                raise Stop(f"pre-existing output {rel} would be counted as fresh; refusing")
        if not baseline:
            raise Stop("CELLTRANSFER_BASELINE_MANIFEST not set (required for the tiered comparison)")
        bp = Path(baseline).resolve()
        try:
            b = json.loads(bp.read_text())
        except (OSError, ValueError) as e:
            raise Stop(f"baseline manifest unreadable: {e}") from e
        if b.get("schema") != RM.MANIFEST_SCHEMA or b.get("mode") != "R":
            raise Stop("baseline manifest must be celltransfer-compare-manifest/1 with mode R")
        if any(bp.is_relative_to((self.repo / d).resolve()) for d in CAP_DIRS):
            raise Stop("baseline manifest must not live inside reproduction output paths")
        self.receipt["baseline_manifest"] = {"sha256": sha256(bp), "used_for": "comparison-only"}
        self.baseline = bp
        ext = os.environ.get("CELLTRANSFER_EXTERNAL_CACHE")
        self.ext_cache = Path(ext).resolve() if ext else None
        self.receipt["external_cache"] = ("hash-identical third-party inputs only (acquire_inputs.py "
                                          "verifies sha256)") if ext else None
        self.save()

    def run(self, baseline):
        self.preflight(baseline)
        py, sc, R = self.python, str(self.repo / "companion/scripts"), str(self.repo)
        self.step("env", "env", lambda o: ["uv", "sync", "--frozen"], out=False)
        inputs = self.repo  # input destinations are relative to --workspace used by the scientific scripts
        acq = [py, str(HERE / "acquire_inputs.py"), "acquire", "--root", str(inputs), "--repo", R]
        if self.ext_cache:
            acq += ["--cache-root", str(self.ext_cache), "--allow-cache-fallback"]
        self.step("acquire", "acquire", lambda o: acq, out=False)
        D = self.step("data", "data", lambda o: [py, f"{sc}/build_data.py", "--workspace", R, "--out", str(o)])
        rm = [py, f"{sc}/run_matched.py", "--workspace", R]
        fits, preds, checkpoint_hash_args = {}, {}, {}
        for arm in ("A", "B"):
            for m in METHODS:
                fits[arm, m] = f = self.step(f"{arm}_{m}_fit", "fit", lambda o, a=arm, m=m: rm + [
                    "--data", str(D), "--arm", a, "--method", m, "--stage", "fit", "--out", str(o)])
                extra = []
                if m == "M6":
                    import hashlib
                    hashes = {str(p.relative_to(f / "scanvi")): hashlib.sha256(p.read_bytes()).hexdigest() for p in (f / "scanvi").rglob("*") if p.is_file()}
                    if not hashes:
                        raise Stop("M6 fit produced no checkpoint files")
                    hp = self.run_dir / f"{arm}_M6_checkpoint_sha256.json"
                    RM.write_json(hp, hashes)
                    extra = ["--expected-hashes", str(hp)]
                checkpoint_hash_args[arm, m] = extra
                preds[arm, m] = self.step(f"{arm}_{m}_predict", "predict", lambda o, a=arm, m=m, f=f, extra=extra: rm + [
                    "--data", str(D), "--arm", a, "--method", m, "--stage", "predict", "--model-dir", str(f),
                    "--out", str(o)] + extra)
        arms = {a: RM.assemble_arm(self.run_dir / "arms" / a, {m: [preds[a, m], fits[a, m]] for m in METHODS})
                for a in ("A", "B")}
        ci = self.step("cite_build", "cite_build", lambda o: [py, f"{sc}/build_cite.py", "--workspace", R,
                                                               "--data", str(D), "--out", str(o)])
        cp = {m: self.step(f"A_{m}_cite", "cite_predict", lambda o, m=m: rm + [
            "--data", str(ci), "--arm", "A", "--method", m, "--stage", "predict", "--model-dir",
            str(fits["A", m]), "--out", str(o)] + checkpoint_hash_args["A", m]) for m in METHODS}
        tc = self.run_dir / "armA_cite"
        tc.mkdir()
        for m in METHODS:
            os.symlink(cp[m], tc / m)
        scd = self.step("score", "score", lambda o: [py, f"{sc}/score_all.py", "--workspace", R, "--data", str(D),
                                                      "--matched", f"A={arms['A']}", f"B={arms['B']}", "--reps",
                                                      "1000", "--natural-unknown-scope", "natural", "--out", str(o)])
        prd = self.step("protein", "protein", lambda o: [py, f"{sc}/protein_check.py", "--workspace", R, "--cite",
                                                          str(ci), "--matched", f"A={tc}", "--thresholds",
                                                          str(scd / "thresholds_validation.csv"), "--out", str(o)])
        # results + Mode F manifest (fresh outputs only)
        ev = RM.find_optional_evidence(scd, prd)
        man = self.run_dir / "comparison_manifest.json"
        RM.write_compare_manifest(man, mode="F", data=D, cite=ci, arms={"A": [arms["A"], tc], "B": [arms["B"]]},
                                  score={"primary": scd}, protein=prd, fresh=True, d03_features=baseline_d03(self.baseline), **ev)
        res = RM.aggregate_results(scd, prd)
        (self.repo / RESULTS).parent.mkdir(parents=True, exist_ok=True)
        RM.write_json(self.repo / RESULTS, res)
        self.receipt["results"] = str(RESULTS)
        report = self.run_dir / "compare" / "report.json"
        report.parent.mkdir(parents=True)
        tol = str(self.repo / "protocol/tolerances.json")
        rec = self.runner([py, str(HERE / "compare_runs.py"), "--original", str(self.baseline), "--reproduction",
                           str(man), "--tolerances", tol, "--out", str(report)], "compare",
                          float(self.step_ceil["compare"]), self.repo)
        self.receipt["comparison"] = {"returncode": rec.get("returncode"), "status": rec["status"],
                                      "report": str(report)}
        self.save()
        if rec.get("returncode") != 0:
            raise Stop(f"tiered comparison did not pass (exit {rec.get('returncode')}; 1=breach, "
                       f"3=not assessable); see {report}")
        paper = self.repo / "paper"
        self.step("paper_assets", "paper", lambda o: [py, str(HERE / "make_paper_assets.py"), "--score", str(scd),
                                                      "--protein", str(prd), "--comparison", str(report),
                                                      "--output", str(paper)], mode_f=False, out=False)
        self.step("paper_build", "paper", lambda o: [py, str(HERE / "build_paper.py")], mode_f=False, out=False)
        if not (self.repo / PDF).is_file():
            raise Stop("paper build reported success but paper/build/main.pdf is missing")
        self.receipt["status"] = "complete"
        self.save()


def baseline_d03(manifest: Path):
    b = json.loads(manifest.read_text())
    value = b.get("d03_features")
    if not value:
        raise Stop("Baseline is missing D03 reference feature evidence")
    return (manifest.parent / value).resolve()


def sha256(p: Path) -> str:
    import hashlib
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", type=Path, default=REPO / "configs/full.json")
    a = ap.parse_args(argv)
    if shutil.which("uv") is None:
        print("BLOCKED: uv not on PATH", file=sys.stderr)
        return 3
    r = Repro(REPO, json.loads(a.config.read_text()))
    try:
        r.run(os.environ.get("CELLTRANSFER_BASELINE_MANIFEST"))
    except (Stop, RM.ManifestError) as e:
        r.receipt["status"] = "stopped"
        r.receipt["blocker"] = str(e)
        r.save()
        print(f"STOPPED: {e}", file=sys.stderr)
        return 1
    print(json.dumps({"status": "complete", "results": str(RESULTS), "pdf": str(PDF)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

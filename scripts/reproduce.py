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

Amended (config "amendment": {"id": "2026-10-06-approved-protein-replacement", "tolerances": <v2 path>,
"cite_builder": "companion/scripts/build_cite_totalvi.py"}): Mode F stays fully fresh (no adoption, no cached
fits; a mode_f "adopt" key is refused). Step 5 runs the replacement builder (r4prime --workspace --data --out) and
reads its eligibility.json: 0 eligible -> Arm A CITE predictions and protein_check are recorded as not run
(results.json protein_check.status "not_run"); otherwise they run for the eligible files only, with a 4 GiB
free-disk start floor for the CITE predictions (M6 query adaptation). The baseline must be an amended Mode R
manifest and compare_runs.py uses the versioned tolerances file.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
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
        op_path = repo / "evidence/operational-approval.json"
        operational = json.loads(op_path.read_text()) if op_path.is_file() else {}
        prior = float(operational.get("budget_changes", {}).get("prior_reproduction_seconds", 0))
        if prior < 0 or prior >= self.ceiling_f:
            raise Stop("Invalid prior reproduction runtime")
        self.env_attempts = int(operational.get("environment_setup_attempts_remaining", self.max_attempts))
        if not 1 <= self.env_attempts <= self.max_attempts:
            raise Stop("Invalid environment attempt allowance")
        self.t0 = now() - prior
        self.f_used = prior
        self.pool_used = {}
        self.paper_used = 0.0
        self.runner = runner or self._guarded
        self.run_dir = repo / "runs" / f"F-{utc()}"
        cache = repo / ".cache-study"
        self.env = {"UV_CACHE_DIR": str(cache / "uv"), "UV_PROJECT_ENVIRONMENT": str(repo / ".venv"),
                    "HF_HOME": str(cache / "hf"), "XDG_CACHE_HOME": str(cache / "xdg"),
                    "CELLTYPIST_FOLDER": str(cache / "celltypist"), "MPLCONFIGDIR": str(cache / "mpl"),
                    "PYTHONDONTWRITEBYTECODE": "1", "PYTHONWARNINGS": "ignore"}
        self.receipt = {"driver": "scripts/reproduce.py", "created_utc": utc(), "mode": "F",
                        "fresh_execution": True, "config": cfg, "steps": [], "status": "running",
                        "external_cache": None, "prior_seconds_reserved": prior,
                        "environment_setup_attempts_remaining": self.env_attempts}
        self.python = str(repo / ".venv" / "bin" / "python")
        self.amendment = dict(cfg["amendment"]) if cfg.get("amendment") else None
        # The full-run config predates this reproduction-only key. Its approved
        # replacement amendment pins v2; preserve the original run config bytes.
        if self.amendment is not None:
            self.amendment.setdefault("tolerances", "protocol/tolerances-v2.json")
        if self.amendment:
            if self.amendment.get("id") != RM.AMENDMENT_ID:
                raise Stop(f"amendment id {self.amendment.get('id')!r} is not the approved {RM.AMENDMENT_ID!r}")
            if self.amendment.get("cite_builder") != REPLACEMENT_BUILDER:
                raise Stop("amendment.cite_builder must be the approved replacement builder")
            if not self.amendment.get("tolerances") or Path(self.amendment["tolerances"]).name == "tolerances.json":
                raise Stop("amendment.tolerances must name the versioned (v2) tolerances file, not v1")
            if "adopt" in f:
                raise Stop("Mode F is fully fresh: adoption of cached fits is not allowed")
            self.receipt["amendment"] = RM.AMENDMENT_ID

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
                              swap_growth_limit=int(4 * RG.GiB), disk_start_min=int(disk_floor_gib(name, bool(self.amendment)) * RG.GiB),
                              disk_run_min=int(1.5 * RG.GiB), storage_cap=int(g["storage_cap_gib"] * RG.GiB),
                              threads=int(g["threads"]), disk_path=self.repo,
                              cap_paths=[self.repo / p for p in CAP_DIRS], time_l=True)

    def step(self, name, kind, argv_fn, mode_f=True, out=True):
        for attempt in range(1, (self.env_attempts if name == "env" else self.max_attempts) + 1):
            h_left = self.ceiling_h - (self.now() - self.t0)
            f_left = self.ceiling_f - self.f_used if mode_f else h_left
            left = min(h_left, f_left)
            if not mode_f:
                left = min(left, float(self.cfg["budgets"]["paper_seconds"]) - self.paper_used)
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
            else:
                self.paper_used += dt_
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
        if self.amendment:
            if b.get("amendment") != RM.AMENDMENT_ID:
                raise Stop("baseline Mode R manifest is not an amended (protein-replacement) manifest")
            tp = self.repo / self.amendment["tolerances"]
            if not tp.is_file():
                raise Stop(f"versioned tolerances file missing: {tp}")
            if not (self.repo / REPLACEMENT_BUILDER).is_file():
                raise Stop(f"replacement builder missing: {REPLACEMENT_BUILDER}")
            self.receipt["tolerances"] = {"path": self.amendment["tolerances"], "sha256": sha256(tp)}
        elif b.get("amendment"):
            raise Stop("baseline manifest is amended but the config has no amendment")
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
        builder = f"{R}/{REPLACEMENT_BUILDER}" if self.amendment else f"{sc}/build_cite.py"
        cite_cmd = (lambda o: [py, builder, "r4prime", "--workspace", R, "--data", str(D), "--out", str(o)]) \
            if self.amendment else (lambda o: [py, builder, "--workspace", R, "--data", str(D), "--out", str(o)])
        ci = self.step("cite_build", "cite_build", cite_cmd)
        elig = None
        if self.amendment:
            elig = RM.parse_eligibility(ci / RM.ELIGIBILITY_FILE)
            self.receipt["eligibility"] = {"sha256": elig["sha256"], "verdicts": elig["verdicts"],
                                           "n_eligible": elig["n_eligible"]}
            self.save()
        run_cite = elig is None or elig["n_eligible"] > 0
        tc = None
        if run_cite:
            cp = {m: self.step(f"A_{m}_cite", "cite_predict", lambda o, m=m: rm + [
                "--data", str(ci), "--arm", "A", "--method", m, "--stage", "predict", "--model-dir",
                str(fits["A", m]), "--out", str(o)] + checkpoint_hash_args["A", m]) for m in METHODS}
            tc = self.run_dir / "armA_cite"
            tc.mkdir()
            for m in METHODS:
                os.symlink(cp[m], tc / m)
        else:
            self.receipt["protein_check"] = {"status": "not_run", "reason": "no eligible replacement file",
                                             "steps_not_run": [f"A_{m}_cite" for m in METHODS] + ["protein"]}
            self.save()
        scd = self.step("score", "score", lambda o: [py, f"{sc}/score_all.py", "--workspace", R, "--data", str(D),
                                                      "--matched", f"A={arms['A']}", f"B={arms['B']}", "--reps",
                                                      "1000", "--natural-unknown-scope", "natural", "--out", str(o)])
        prd = None
        if run_cite:
            prd = self.step("protein", "protein", lambda o: [py, f"{sc}/protein_check.py", "--workspace", R, "--cite",
                                                              str(ci), "--matched", f"A={tc}", "--thresholds",
                                                              str(scd / "thresholds_validation.csv"), "--out", str(o)])
        # results + Mode F manifest (fresh outputs only)
        ev = RM.find_optional_evidence(scd, prd)
        man = self.run_dir / "comparison_manifest.json"
        extra, am_kw = None, {}
        if self.amendment:
            pc = RM.protein_check_summary(elig, prd)
            self.receipt["protein_check"] = dict(self.receipt.get("protein_check", {}), status=pc["status"])
            extra = {"protein_check": pc}
            am_kw = dict(eligibility=ci / RM.ELIGIBILITY_FILE, amendment=RM.AMENDMENT_ID, protein_status=pc["status"])
        RM.write_compare_manifest(man, mode="F", data=D, cite=ci,
                                  arms={"A": [arms["A"]] + ([tc] if tc else []), "B": [arms["B"]]},
                                  score={"primary": scd}, protein=prd, fresh=True,
                                  d03_features=baseline_d03(self.baseline), **am_kw, **ev)
        res = RM.aggregate_results(scd, prd, extra=extra)
        (self.repo / RESULTS).parent.mkdir(parents=True, exist_ok=True)
        RM.write_json(self.repo / RESULTS, res)
        self.receipt["results"] = str(RESULTS)
        report = self.run_dir / "compare" / "report.json"
        report.parent.mkdir(parents=True)
        tol = str(self.repo / (self.amendment["tolerances"] if self.amendment else "protocol/tolerances.json"))
        # Comparison shares the approved F/H budgets and retry accounting.
        # Record its result even when the comparison reports a deterministic breach.
        try:
            self.step("compare", "compare", lambda o: [py, str(HERE / "compare_runs.py"),
                      "--original", str(self.baseline), "--reproduction", str(man),
                      "--tolerances", tol, "--out", str(report)], out=False)
        finally:
            steps = [x for x in self.receipt["steps"] if x["name"] == "compare"]
            if steps:
                rec = steps[-1]
                self.receipt["comparison"] = {"returncode": rec.get("returncode"),
                                              "status": rec["status"], "report": str(report)}
                self.save()
        paper = self.repo / "paper"
        prot_args = ["--protein", str(prd)] if prd else ["--protein-not-run"]
        self.step("paper_assets", "paper", lambda o: [py, str(HERE / "make_paper_assets.py"), "--score", str(scd)]
                  + prot_args + (["--eligibility", str(ci / RM.ELIGIBILITY_FILE)] if self.amendment else [])
                  + ["--comparison", str(report), "--output", str(paper)], mode_f=False, out=False)
        self.step("paper_build", "paper", lambda o: [py, str(HERE / "build_paper.py")], mode_f=False, out=False)
        if not (self.repo / PDF).is_file():
            raise Stop("paper build reported success but paper/build/main.pdf is missing")
        self.receipt["status"] = "complete"
        self.save()


REPLACEMENT_BUILDER = "companion/scripts/build_cite_totalvi.py"


def disk_floor_gib(name: str, amended: bool) -> float:
    """Start floors: fits 4 GiB; amended Arm A CITE predictions (M6 query adaptation, R5 counterpart) 4 GiB."""
    if name.endswith("_fit") or (amended and name.startswith("A_M") and name.endswith("_cite")):
        return 4.0
    return 3.0


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
    try:
        if os.environ.get("RESEARCH_REPRODUCTION_PARENT"):
            sys.modules.setdefault("reproduce", sys.modules[__name__])
            from continue_reproduction import ContinuedRepro
            cls = ContinuedRepro
        else:
            cls = Repro
        r = cls(REPO, json.loads(a.config.read_text()))
    except Stop as e:
        print(f"STOPPED: {e}", file=sys.stderr)
        return 1
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
    # Allow the nested resource guard to clean its separate process group when
    # the outer harness terminates make and this driver.
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    sys.exit(main())

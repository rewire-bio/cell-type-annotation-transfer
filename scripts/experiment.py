#!/usr/bin/env python3
"""Harness experiment entry point: Mode R cached recovery -> results.json + comparison manifest.

    python scripts/experiment.py --config configs/full.json --output OUT

Runs scripts/recover.py (hash-verified reuse of completed historical steps only; Arm B M4-M6,
CITE build/predictions, scoring and protein check recomputed under resource_guard), then writes

    OUT/results.json               aggregate scalar metrics (stable keys, no times/paths)
    OUT/comparison_manifest.json   celltransfer-compare-manifest/1, mode R
    OUT/provenance.json            cached-vs-recomputed provenance + recovery status

Historical root:   $HISTORICAL_RUNS_ROOT, default <repo>/historical (read-only).
Historical manifest: $CELLTRANSFER_HISTORICAL_MANIFEST, default config "historical_manifest".
Fails closed (non-zero, no results.json) if recovery is blocked or any output is missing.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import result_manifest as RM  # noqa: E402

REPO = HERE.parent


def load_config(p: Path) -> dict:
    c = json.loads(Path(p).read_text())
    if c.get("mode") != "full":
        raise SystemExit("config mode must be 'full'")
    return c


def last_ok(record: dict, name: str) -> Path:
    oks = [s for s in record["steps"] if s["name"] == name and s["status"] == "ok"]
    if len(oks) != 1:
        raise RM.ManifestError(f"step {name}: expected exactly one ok attempt, found {len(oks)}")
    return Path(oks[0]["out_dir"])


def build_outputs(out: Path, run_dir: Path, mode_r_cfg: dict) -> dict:
    rec = json.loads((run_dir / "recovery_manifest.json").read_text())
    if rec.get("status") != "complete":
        raise RM.ManifestError(f"recovery status {rec.get('status')!r}: {rec.get('blocker')}")
    lay = rec["historical_layout"]
    D, TA, TB = Path(lay["data"]), Path(lay["armA"]), Path(lay["armB"])
    score, protein, cite = last_ok(rec, "score"), last_ok(rec, "protein"), last_ok(rec, "cite_build")
    # Arm A: historical, hash-verified dir used as is. Arm B: cached M1-M3 + recomputed M4-M6 fit+predict.
    srcB = {m: [TB / m] for m in ("M1", "M2", "M3")}
    for m in ("M4", "M5", "M6"):
        srcB[m] = [last_ok(rec, f"B_{m}_predict"), last_ok(rec, f"B_{m}_fit")]
    armB = RM.assemble_arm(out / "compare_arms" / "B", srcB)
    ev = RM.find_optional_evidence(score, protein)
    d03 = os.environ.get("CELLTRANSFER_D03_FEATURES") or mode_r_cfg.get("d03_features")
    if d03 and not Path(d03).is_absolute():
        d03 = str(Path(os.environ.get("HISTORICAL_RUNS_ROOT", REPO / "historical")) / d03)
    cached = sorted(rec.get("cached", {}))
    prov = {"mode": "R", "cached_files_sha256_verified": len(cached),
            "historical_manifest_sha256": rec["historical_manifest_sha256"],
            "recomputed_steps": sorted({s["name"] for s in rec["steps"] if s["status"] == "ok"}),
            "cached_steps": ["data", "armA_M1-M6_fit+predict", "armB_M1-M3_fit+predict"]}
    RM.write_compare_manifest(out / "comparison_manifest.json", mode="R", data=D, cite=cite,
                              arms={"A": [TA, run_dir / "armA_cite"], "B": [armB]}, score={"primary": score}, protein=protein,
                              fresh=False, d03_features=d03 if d03 and Path(d03).is_file() else None,
                              provenance=prov, **ev)
    res = RM.aggregate_results(score, protein)
    RM.write_json(out / "results.json", res)
    RM.write_json(out / "provenance.json", {"provenance": prov, "steps": rec["steps"],
                                            "optional_evidence_present": sorted(ev)})
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    a = ap.parse_args(argv)
    cfg = load_config(a.config)
    r = cfg["mode_r"]
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    hist = Path(os.environ.get("HISTORICAL_RUNS_ROOT") or (REPO / "historical")).resolve()
    hman = os.environ.get("CELLTRANSFER_HISTORICAL_MANIFEST") or r.get("historical_manifest")
    if not hman or not Path(hman).is_file():
        print(f"BLOCKED: historical manifest not found ({hman!r}); set CELLTRANSFER_HISTORICAL_MANIFEST",
              file=sys.stderr)
        return 3
    import recover  # noqa: E402  (imported late: owned by another worker, API: main(argv))
    run_dir = out / "recovery"
    argv_r = ["--workspace", str(REPO), "--historical-root", str(hist), "--historical-manifest", str(hman),
              "--run-dir", str(run_dir), "--python", os.environ.get("CELLTRANSFER_PYTHON", sys.executable),
              "--stage-ceiling", str(r["stage_ceiling_s"]), "--mem-limit-gib", str(r["mem_limit_gib"])]
    argv_r += ["--prior-attempts", json.dumps(r.get("prior_attempts", {})), "--prior-seconds", str(r.get("prior_seconds", 0))]
    if os.environ.get("CELLTRANSFER_STOP_AFTER_MATCHED") == "1":
        argv_r += ["--stop-after-matched"]
    rc = recover.main(argv_r)
    if rc != 0:
        print(f"recovery exited {rc}; no results emitted", file=sys.stderr)
        return rc
    try:
        build_outputs(out, run_dir, r)
    except RM.ManifestError as e:
        print(f"FAILED: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

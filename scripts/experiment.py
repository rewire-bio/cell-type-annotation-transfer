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

Amended continuation (config "amendment": {"id": "2026-10-06-approved-protein-replacement", ...}):
recover.py is called with --amendment, --adopt-from <mode_r.adopt.prior_manifest>, --adopt-receipts-dir
and --prior-r4-seconds; B M4-M6 are adopted (never refit), the CITE input is the replacement builder's
output and results.json carries an explicit "protein_check" entry (status run | not_run).
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


def last_ok(record: dict, name: str, adopted: bool = False) -> Path:
    want = ("ok", "adopted") if adopted else ("ok",)
    oks = [s for s in record["steps"] if s["name"] == name and s["status"] in want]
    if len(oks) != 1:
        raise RM.ManifestError(f"step {name}: expected exactly one {'/'.join(want)} attempt, found {len(oks)}")
    return Path(oks[0]["out_dir"])


def amended_recover_args(cfg: dict) -> list[str]:
    """Validate the amended config (fail closed) and return the extra recover.py arguments."""
    import recover  # noqa: E402
    am, r = cfg["amendment"], cfg["mode_r"]
    if am.get("id") != recover.AMENDMENT_ID:
        raise RM.ManifestError(f"amendment id {am.get('id')!r} is not the approved {recover.AMENDMENT_ID!r}")
    if am.get("cite_builder", recover.REPLACEMENT_BUILDER) != recover.REPLACEMENT_BUILDER:
        raise RM.ManifestError("amendment.cite_builder differs from the approved replacement builder")
    if r.get("prior_seconds") or r.get("prior_attempts"):
        raise RM.ManifestError("mode_r.prior_seconds/prior_attempts must be removed under the amendment: they are "
                               "already inside the adopted manifest (double counting refused)")
    ad = r.get("adopt") or {}
    if not ad.get("prior_manifest"):
        raise RM.ManifestError("mode_r.adopt.prior_manifest is required (no refit of B M4-M6 is authorised)")
    r4 = r.get("prior_r4_seconds")
    if isinstance(r4, bool) or not isinstance(r4, (int, float)) or r4 < 0:
        raise RM.ManifestError("mode_r.prior_r4_seconds (measured time of R4 attempt 1, HTTP 403) is required")
    rel = lambda v: str(Path(v) if Path(v).is_absolute() else REPO / v)  # noqa: E731
    out = ["--amendment", am["id"], "--adopt-from", rel(ad["prior_manifest"]), "--prior-r4-seconds", str(float(r4))]
    if ad.get("receipts_dir"):
        out += ["--adopt-receipts-dir", rel(ad["receipts_dir"])]
    return out


def build_outputs(out: Path, run_dir: Path, mode_r_cfg: dict) -> dict:
    rec = json.loads((run_dir / "recovery_manifest.json").read_text())
    if rec.get("status") != "complete":
        raise RM.ManifestError(f"recovery status {rec.get('status')!r}: {rec.get('blocker')}")
    if rec.get("amendment"):
        return build_outputs_amended(out, run_dir, mode_r_cfg, rec)
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


def build_outputs_amended(out: Path, run_dir: Path, mode_r_cfg: dict, rec: dict) -> dict:
    if rec["amendment"].get("id") != RM.AMENDMENT_ID:
        raise RM.ManifestError("recovery manifest amendment id is not the approved one")
    lay = rec["historical_layout"]
    D, TA, TB = Path(lay["data"]), Path(lay["armA"]), Path(lay["armB"])
    adopted = sorted({s["name"] for s in rec["steps"] if s["status"] == "adopted"})
    if adopted != sorted(f"B_{m}_{k}" for m in ("M4", "M5", "M6") for k in ("fit", "predict")):
        raise RM.ManifestError(f"adopted steps {adopted} are not exactly B M4-M6 fit+predict")
    if any(s["status"] == "ok" and s["name"].startswith("B_") for s in rec["steps"]):
        raise RM.ManifestError("an Arm B fit/predict was re-executed in the amended run")
    cite, score = last_ok(rec, "cite_build"), last_ok(rec, "score")
    el = RM.parse_eligibility(cite / RM.ELIGIBILITY_FILE)
    if el["sha256"] != rec.get("eligibility", {}).get("sha256"):
        raise RM.ManifestError("eligibility.json differs from the hash recorded by recover.py")
    protein = last_ok(rec, "protein") if el["n_eligible"] else None
    pc = RM.protein_check_summary(el, protein)
    if rec.get("protein_check", {}).get("status") != pc["status"]:
        raise RM.ManifestError("recovery protein_check status disagrees with eligibility.json")
    srcB = {m: [TB / m] for m in ("M1", "M2", "M3")}
    for m in ("M4", "M5", "M6"):
        srcB[m] = [last_ok(rec, f"B_{m}_predict", adopted=True), last_ok(rec, f"B_{m}_fit", adopted=True)]
    armB = RM.assemble_arm(out / "compare_arms" / "B", srcB)
    ev = RM.find_optional_evidence(score, protein)
    d03 = os.environ.get("CELLTRANSFER_D03_FEATURES") or mode_r_cfg.get("d03_features")
    if d03 and not Path(d03).is_absolute():
        d03 = str(Path(os.environ.get("HISTORICAL_RUNS_ROOT", REPO / "historical")) / d03)
    ad = rec["adoption"]
    prov = {"mode": "R", "amendment": RM.AMENDMENT_ID, "cached_files_sha256_verified": len(rec.get("cached", {})),
            "historical_manifest_sha256": rec["historical_manifest_sha256"],
            "adopted_steps": adopted, "adopted_from_manifest_sha256": ad["prior_manifest_sha256"],
            "adopted_source": ad["prior_source"],
            "recomputed_steps": sorted({s["name"] for s in rec["steps"] if s["status"] == "ok"}),
            "cached_steps": ["data", "armA_M1-M6_fit+predict", "armB_M1-M3_fit+predict"],
            "eligibility": {"sha256": el["sha256"], "verdicts": el["verdicts"], "n_eligible": el["n_eligible"]},
            "protein_check": pc["status"]}
    armsA = [TA] + ([run_dir / "armA_cite"] if el["n_eligible"] else [])
    RM.write_compare_manifest(out / "comparison_manifest.json", mode="R", data=D, cite=cite,
                              arms={"A": armsA, "B": [armB]}, score={"primary": score}, protein=protein,
                              fresh=False, d03_features=d03 if d03 and Path(d03).is_file() else None,
                              provenance=prov, eligibility=cite / RM.ELIGIBILITY_FILE, amendment=RM.AMENDMENT_ID,
                              protein_status=pc["status"], **ev)
    res = RM.aggregate_results(score, protein, extra={"protein_check": pc})
    RM.write_json(out / "results.json", res)
    RM.write_json(out / "provenance.json", {"provenance": prov, "steps": rec["steps"],
                                            "carried": ad["carried"], "protein_check": rec.get("protein_check"),
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
    if cfg.get("amendment"):
        try:
            argv_r += amended_recover_args(cfg)
        except RM.ManifestError as e:
            print(f"BLOCKED: {e}", file=sys.stderr)
            return 3
    else:
        argv_r += ["--prior-attempts", json.dumps(r.get("prior_attempts", {})),
                   "--prior-seconds", str(r.get("prior_seconds", 0))]
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

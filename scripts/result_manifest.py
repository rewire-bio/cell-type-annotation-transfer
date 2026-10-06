#!/usr/bin/env python3
"""Aggregate results.json and portable comparison manifests (standard library only).

* ``aggregate_results(score_dir, protein_dir)`` -> dict with stable keys only (no times, no paths).
  Floats are finite or ``None`` (undefined: NaN/inf/empty). Fixed sample counts are exact ints.
* ``assemble_arm(dest, sources)`` builds one arm directory ``dest/M1..M6`` of symlinks that combine
  fit and predict outputs without duplicating prediction files (duplicate parquet = fatal).
* ``write_compare_manifest(...)`` writes a ``celltransfer-compare-manifest/1`` JSON with paths
  relative to the manifest directory (compare_runs.py resolves them against it).

Nothing here computes a scientific value; it only re-reads score_all.py / protein_check.py outputs.

Approved protein replacement (amendment 2026-10-06): ``parse_eligibility`` is the single strict reader of
the builder's ``eligibility.json`` used by recover.py, experiment.py, reproduce.py and compare_runs.py.
Integration contract with companion/scripts/build_cite_totalvi.py (owned elsewhere; see
protocol/amended-recovery-integration.md):

  eligibility.json  {"files": {"<name>": {"verdict": "eligible"|"ineligible",
                                          "first_failing_criterion": null | <criterion>,
                                          "sha256": "<input sha256 or null>", "bytes": <int or null>}, ...}}
                    (a list of {"name": ..., ...} entries is also accepted); exactly the two pinned names.
  mapping_<name>.csv           frozen symbol->Ensembl mapping table (amendment s5)
  postqc_barcodes_<name>.txt   post-QC barcode list, one barcode per line (amendment s7 T1 addition)
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
from pathlib import Path

MANIFEST_SCHEMA = "celltransfer-compare-manifest/1"
RESULTS_SCHEMA = "celltransfer-results/1"
METHODS = ("M1", "M2", "M3", "M4", "M5", "M6")
# columns that identify a row, never treated as metrics
KEY_COLS = ("arm", "method", "vs", "metric", "file", "study", "role", "stratum", "label_status")
# volatile fields that must never enter results.json (harness compares exactly on keys)
VOLATILE = ("seconds", "time", "utc", "path", "dir", "host", "created", "elapsed", "peak_memory")
COUNT_FILE = "cell_counts.csv"

AMENDMENT_ID = "2026-10-06-approved-protein-replacement"
PROTEIN_LABEL = f"descriptive; replacement inputs (amendment {AMENDMENT_ID})"
ELIGIBILITY_FILE = "eligibility.json"
VERDICTS = ("eligible", "ineligible")
# amendment s2.2 pins (binding identity: sha256 and byte count)
REPLACEMENT_FILES = {
    "totalvi_pbmc5k_protein_v3": {"file": "pbmc_5k_protein_v3.h5ad", "bytes": 18294964,
                                  "sha256": "a1bf51e070d24b39627ea4de9b3e489a4637ff795e1061e0733e26c3baec8847"},
    "totalvi_pbmc10k_protein_v3": {"file": "pbmc_10k_protein_v3.h5ad", "bytes": 24937137,
                                   "sha256": "5f08b8575febf9e04b209b94eb43f6335f1e33b0985cdcf44adf7320f6243c69"},
}


def mapping_csv_name(name: str) -> str:
    return f"mapping_{name}.csv"


def postqc_barcodes_name(name: str) -> str:
    return f"postqc_barcodes_{name}.txt"


def sha256_path(p) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


class ManifestError(RuntimeError):
    pass


def _num(s):
    """Parse a CSV cell: int for integer literals, finite float, None for undefined, else str."""
    if s is None:
        return None
    if isinstance(s, bool):
        return s
    if isinstance(s, (int, float)):
        return None if isinstance(s, float) and not math.isfinite(s) else s
    t = str(s).strip()
    if t == "" or t.lower() in ("nan", "none", "null", "inf", "-inf", "+inf", "infinity", "-infinity"):
        return None
    try:
        return int(t)
    except ValueError:
        pass
    try:
        v = float(t)
    except ValueError:
        return t
    return v if math.isfinite(v) else None


def _volatile(col: str) -> bool:
    c = col.lower()
    return any(v in c for v in VOLATILE)


def _read_csv(p: Path) -> list[dict]:
    with open(p, newline="") as fh:
        return list(csv.DictReader(fh))


def _row_key(row: dict) -> str:
    parts = [f"{k}={row[k]}" for k in KEY_COLS if k in row and str(row[k]) != ""]
    if not parts:
        raise ManifestError(f"row without key columns: {sorted(row)}")
    return "|".join(parts)


def _ci(v):
    """'[lo, hi]' / 'lo;hi' CI strings -> [lo, hi] floats (None for undefined)."""
    if not isinstance(v, str):
        return None
    t = v.strip().strip("[]()")
    for sep in (",", ";"):
        if sep in t:
            a, b = t.split(sep, 1)
            lo, hi = _num(a), _num(b)
            if all(x is None or isinstance(x, (int, float)) for x in (lo, hi)):
                return [None if x is None else float(x) for x in (lo, hi)]
    return None


def table_metrics(p: Path, as_float: bool = True) -> dict:
    """{row_key: {metric: value}}; numeric metric floats (as_float) or exact ints (counts)."""
    out: dict = {}
    for row in _read_csv(p):
        k = _row_key(row)
        if k in out:
            raise ManifestError(f"{p.name}: duplicate row key {k}")
        vals = {}
        for col, raw in row.items():
            if col in KEY_COLS or col is None or _volatile(col):
                continue
            v = _num(raw)
            if col.endswith("_ci95"):
                ci = _ci(raw)
                if ci is not None:
                    vals[col + "_lo"], vals[col + "_hi"] = ci
                elif v is None:
                    vals[col + "_lo"] = vals[col + "_hi"] = None
                continue
            if isinstance(v, str):
                continue  # labels/descriptive text are not scalar metrics
            if v is None:
                vals[col] = None
            elif as_float:
                vals[col] = float(v)
            else:
                if not isinstance(v, int):
                    raise ManifestError(f"{p.name}: count column {col} not an exact integer: {raw!r}")
                vals[col] = v
        out[k] = dict(sorted(vals.items()))
    return dict(sorted(out.items()))


def aggregate_results(score_dir: Path, protein_dir: Path | None, extra: dict | None = None) -> dict:
    """Mode-independent: Mode R and Mode F results.json must have identical keys for the harness."""
    score_dir = Path(score_dir)
    req = ["summary_test.csv", "paired_differences_vs_M4.csv", "thresholds_validation.csv", COUNT_FILE]
    missing = [f for f in req if not (score_dir / f).is_file()]
    if missing:
        raise ManifestError(f"score outputs missing in {score_dir}: {missing}")
    res = {"schema": RESULTS_SCHEMA,
           "summary_test": table_metrics(score_dir / "summary_test.csv"),
           "paired_differences_vs_M4": table_metrics(score_dir / "paired_differences_vs_M4.csv"),
           "thresholds_validation": table_metrics(score_dir / "thresholds_validation.csv"),
           "cell_counts": table_metrics(score_dir / COUNT_FILE, as_float=False)}
    info = score_dir / "score_info.json"
    if info.is_file():
        si = json.loads(info.read_text())
        res["score_info"] = {k: v for k, v in sorted(si.items())
                             if isinstance(v, (int, bool)) and not _volatile(k)}
    if protein_dir is not None:
        pa = Path(protein_dir) / "protein_agreement.csv"
        if not pa.is_file():
            raise ManifestError(f"protein_agreement.csv missing in {protein_dir}")
        res["protein_agreement"] = table_metrics(pa)
    if extra:
        res.update(extra)
    check_results(res)
    return res


def check_results(obj, path="results"):
    """Fail closed on non-finite floats or volatile keys anywhere in results."""
    if isinstance(obj, float) and not math.isfinite(obj):
        raise ManifestError(f"non-finite float at {path}")
    if isinstance(obj, dict):
        for k, v in obj.items():
            if _volatile(str(k)):
                raise ManifestError(f"volatile key {k!r} at {path}")
            check_results(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            check_results(v, f"{path}[{i}]")


def assemble_arm(dest: Path, sources: dict[str, list[Path]]) -> Path:
    """dest/<M>/ <- symlinks to every file in each source dir (fit dir, predict dir, ...).

    Prediction parquet files may come from exactly one source; a small JSON present in several
    sources (e.g. fit_info.json) is taken from the first source only if byte-identical, else fatal.
    """
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=False)
    for m, dirs in sources.items():
        md = dest / m
        md.mkdir()
        seen: dict[str, Path] = {}
        for d in dirs:
            d = Path(d).resolve()
            if not d.is_dir():
                raise ManifestError(f"{m}: source dir missing {d}")
            for f in sorted(d.iterdir()):
                if not f.is_file():
                    continue
                if f.name in seen:
                    if f.suffix == ".parquet" or f.read_bytes() != seen[f.name].read_bytes():
                        raise ManifestError(f"{m}: duplicate {f.name} in {seen[f.name].parent} and {d}")
                    continue
                seen[f.name] = f
                os.symlink(f, md / f.name)
        if not any(n.startswith("predictions_") for n in seen):
            raise ManifestError(f"{m}: no predictions_*.parquet in {dirs}")
    return dest


def _rel(p, base: Path):
    if p is None:
        return None
    return os.path.relpath(Path(p).resolve(), base.resolve())


def write_compare_manifest(path: Path, *, mode: str, data, cite, arms: dict, score: dict, protein,
                           fresh: bool, sampled_ids=None, bootstrap_weights=None, protein_classes=None,
                           d03_features=None, resources=None, provenance=None, eligibility=None,
                           amendment=None, protein_status=None) -> dict:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    base = path.parent
    if mode not in ("R", "F"):
        raise ManifestError("mode must be R or F")
    if mode == "F" and not fresh:
        raise ManifestError("Mode F manifest requires fresh_execution")
    for a, dirs in arms.items():
        hits = [d for d in dirs if (Path(d) / "M4" / "fit_info.json").is_file()]
        if len(hits) != 1:
            raise ManifestError(f"arm {a}: need exactly one M4/fit_info.json, found {len(hits)}")
    if amendment is not None:
        if amendment != AMENDMENT_ID or eligibility is None:
            raise ManifestError("amended manifest needs the approved amendment id and an eligibility.json")
        summary = protein_check_summary(parse_eligibility(eligibility), protein)
        if protein_status != summary["status"]:
            raise ManifestError(f"protein_status {protein_status!r} != {summary['status']!r} from eligibility.json")
    elif protein is None or eligibility is not None:
        raise ManifestError("protein output is required (and eligibility.json is only valid) under the amendment")
    m = {"schema": MANIFEST_SCHEMA, "mode": mode, "fresh_execution": bool(fresh),
         "data": _rel(data, base), "cite": _rel(cite, base),
         "arms": {a: [_rel(d, base) for d in v] for a, v in sorted(arms.items())},
         "score": {k: _rel(v, base) for k, v in sorted(score.items())}, "protein": _rel(protein, base)}
    if sampled_ids:
        m["sampled_ids"] = _rel(sampled_ids, base)
    if bootstrap_weights:
        m["bootstrap_weights"] = _rel(bootstrap_weights, base)
    if protein_classes:
        m["protein_classes"] = {k: _rel(v, base) for k, v in sorted(protein_classes.items())}
    if d03_features:
        # reference check only: the D03 file is never used as reproduction data
        m["d03_features"] = _rel(d03_features, base)
        m["d03_features_role"] = "reference-check-only"
    if amendment is not None:
        m["amendment"] = amendment
        m["eligibility"] = _rel(eligibility, base)
        m["eligibility_sha256"] = sha256_path(eligibility)
        m["protein_status"] = protein_status
    if resources:
        m["resources"] = resources
    if provenance:
        m["provenance"] = provenance
    path.write_text(json.dumps(m, indent=1, sort_keys=True))
    return m


def find_optional_evidence(score_dir: Path, protein_dir: Path | None) -> dict:
    """Exact-evidence outputs the scoring worker is adding; absent -> comparator reports unsupported."""
    out = {}
    bw = Path(score_dir) / "bootstrap_weights.npy"
    if bw.is_file():
        out["bootstrap_weights"] = bw
    if protein_dir is not None:
        pcs = sorted(Path(protein_dir).glob("protein_classes_*.parquet")) + \
            sorted(Path(protein_dir).glob("protein_classes_*.csv"))
        if pcs:
            out["protein_classes"] = {p.stem[len("protein_classes_"):]: p for p in pcs}
    sid = Path(score_dir) / "sampled_ids.csv"
    if sid.is_file():
        out["sampled_ids"] = sid
    return out


def parse_eligibility(path) -> dict:
    """Strict reader; raises ManifestError on any deviation from the documented contract."""
    path = Path(path)
    if not path.is_file():
        raise ManifestError(f"{ELIGIBILITY_FILE} missing: {path}")
    raw = path.read_bytes()
    try:
        doc = json.loads(raw)
    except ValueError as e:
        raise ManifestError(f"{path}: not JSON ({e})") from e
    files = doc.get("files") if isinstance(doc, dict) else None
    if isinstance(files, list):
        if any(not isinstance(e, dict) or "name" not in e for e in files):
            raise ManifestError(f"{path}: list entries need a 'name'")
        names = [e["name"] for e in files]
        if len(set(names)) != len(names):
            raise ManifestError(f"{path}: duplicate file entries")
        files = {e["name"]: {k: v for k, v in e.items() if k != "name"} for e in files}
    if not isinstance(files, dict):
        raise ManifestError(f"{path}: 'files' must be an object or list")
    if sorted(files) != sorted(REPLACEMENT_FILES):
        raise ManifestError(f"{path}: files {sorted(files)} != pinned replacement files {sorted(REPLACEMENT_FILES)}")
    out = {}
    for n, e in sorted(files.items()):
        if not isinstance(e, dict) or e.get("verdict") not in VERDICTS:
            raise ManifestError(f"{path}: {n}: verdict must be one of {VERDICTS}")
        crit = e.get("first_failing_criterion")
        if e["verdict"] == "eligible" and crit not in (None, ""):
            raise ManifestError(f"{path}: {n}: eligible file with a failing criterion {crit!r}")
        if e["verdict"] == "ineligible" and crit in (None, ""):
            raise ManifestError(f"{path}: {n}: ineligible file without first_failing_criterion")
        out[n] = dict(e, first_failing_criterion=None if e["verdict"] == "eligible" else crit)
    eligible = [n for n in sorted(out) if out[n]["verdict"] == "eligible"]
    if isinstance(doc, dict) and "n_eligible" in doc and doc["n_eligible"] != len(eligible):
        raise ManifestError(f"{path}: n_eligible {doc['n_eligible']} != {len(eligible)} eligible verdicts")
    return {"sha256": hashlib.sha256(raw).hexdigest(), "files": out, "eligible": eligible,
            "n_eligible": len(eligible), "verdicts": {n: out[n]["verdict"] for n in sorted(out)},
            "first_failing_criterion": {n: out[n]["first_failing_criterion"] for n in sorted(out)
                                        if out[n]["verdict"] != "eligible"}}


def protein_check_summary(elig: dict, protein_dir) -> dict:
    """Explicit, stable results.json entry; zero eligible is 'not_run', never an empty success."""
    n = elig["n_eligible"]
    if n == 0 and protein_dir is not None:
        raise ManifestError("protein outputs present although no replacement file is eligible")
    if n > 0 and protein_dir is None:
        raise ManifestError(f"{n} eligible replacement file(s) but no protein_check output")
    return {"status": "run" if n else "not_run", "n_eligible": n, "eligible_files": list(elig["eligible"]),
            "ineligible_first_failing_criterion": {k: str(v) for k, v in elig["first_failing_criterion"].items()},
            "reason": None if n else "no eligible replacement file (eligibility.json)", "label": PROTEIN_LABEL}


def write_json(path: Path, obj) -> None:
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, sort_keys=True, allow_nan=False))
    tmp.replace(path)

"""Replacement CITE-seq builder: two totalVI author-processed h5ad files (approved amendment).

Implements protocol/amendments/protein-replacement-reviewed.md (sha256 e5ba0c34...eae1), approved
by the user per protocol/amendments/2026-10-06-approved-protein-replacement.md. The frozen
companion/scripts/build_cite.py and protein_check.py are NOT modified; this is a separate builder.

Phases (each a subcommand; ``r4prime`` runs them in order in one process):

  plan         print the pins; no network, no writes
  acquire      E1  - one GET per file of the pinned raw URL, or verified cached bytes (--cache-dir)
  eligibility  E2-E5 - criteria 2-7 from metadata, names and counts only; writes and hashes
               eligibility.json, mapping_<name>.{json,csv}, barcodes_qc_<name>.txt.
               Imports no prediction code and produces no prediction, gate or agreement value.
  build        E6-real - eligible files only: query_<name>_F.h5ad, adt_<name>.parquet,
               released_predictions_<name>.parquet (P1/P2 via the unchanged released.py
               interface), receipt.json, coverage.json. Refuses to run unless eligibility.json
               matches its recorded sha256.
  r4prime      acquire -> eligibility -> build, stopping at the first R4' failure.

  build_cite_totalvi.py r4prime --workspace W --data DATA_RUN --out RUNS/<R4'> [--cache-dir DIR]

Exit codes: 0 success (including "not run" because no file is eligible), 2 R4' failure
(acquisition/infrastructure; the replacement stops), 3 configuration error detected before any
network request (wrong data run, missing input), 4 eligibility record missing or tampered.

No retry, no alternate host, no LFS fallback, no alias or manual gene rescue. Nothing here
relaxes a criterion. Dependencies are those pinned in pyproject.toml / uv.lock.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import shutil
import sys
import time
import urllib.request
from fractions import Fraction
from pathlib import Path

# ----------------------------------------------------------------------------- pins (amendment §2.2)
AMENDMENT_PATH = "protocol/amendments/protein-replacement-reviewed.md"
AMENDMENT_SHA256 = "e5ba0c347b66cba1c76dd249e386789c26e1916a95bc9c82a0208a696c89eae1"
APPROVAL_RECORD = "protocol/amendments/2026-10-06-approved-protein-replacement.md"
REPO = "YosefLab/totalVI_reproducibility"
COMMIT = "27d65a9c49182f39df0c4325249bc7dc8e663dd0"
URL_TEMPLATE = "https://raw.githubusercontent.com/{repo}/{commit}/data/{file}"
BYTE_CAP = 64 * 2**20
ASSAY = "10x CITE-seq (totalVI-processed)"
USER_AGENT = "celltransfer-build-cite-totalvi/1 (study input acquisition; single request)"
HTTP_TIMEOUT_S = 120

PINS = {
    "totalvi_pbmc5k_protein_v3": {
        "file": "pbmc_5k_protein_v3.h5ad",
        "sha256": "a1bf51e070d24b39627ea4de9b3e489a4637ff795e1061e0733e26c3baec8847",
        "bytes": 18294964,
        "shape": (3994, 16581),
        "proteins": ["CD3_TotalSeqB", "CD4_TotalSeqB", "CD8a_TotalSeqB", "CD11b_TotalSeqB", "CD14_TotalSeqB",
                     "CD15_TotalSeqB", "CD16_TotalSeqB", "CD19_TotalSeqB", "CD20_TotalSeqB", "CD25_TotalSeqB",
                     "CD27_TotalSeqB", "CD28_TotalSeqB", "CD34_TotalSeqB", "CD45RA_TotalSeqB", "CD45RO_TotalSeqB",
                     "CD56_TotalSeqB", "CD62L_TotalSeqB", "CD69_TotalSeqB", "CD80_TotalSeqB", "CD86_TotalSeqB",
                     "CD127_TotalSeqB", "CD137_TotalSeqB", "CD197_TotalSeqB", "CD274_TotalSeqB", "CD278_TotalSeqB",
                     "CD335_TotalSeqB", "PD-1_TotalSeqB", "HLA-DR_TotalSeqB", "TIGIT_TotalSeqB"],
        # inspection.json mapping_feasibility (looser rule; observed metadata, not realised coverage)
        "feasibility": {"G": (12957, 19331), "F_A": (1565, 2020), "F_B": (1576, 2016)},
    },
    "totalvi_pbmc10k_protein_v3": {
        "file": "pbmc_10k_protein_v3.h5ad",
        "sha256": "5f08b8575febf9e04b209b94eb43f6335f1e33b0985cdcf44adf7320f6243c69",
        "bytes": 24937137,
        "shape": (6855, 16727),
        "proteins": ["CD3_TotalSeqB", "CD4_TotalSeqB", "CD8a_TotalSeqB", "CD14_TotalSeqB", "CD15_TotalSeqB",
                     "CD16_TotalSeqB", "CD56_TotalSeqB", "CD19_TotalSeqB", "CD25_TotalSeqB", "CD45RA_TotalSeqB",
                     "CD45RO_TotalSeqB", "PD-1_TotalSeqB", "TIGIT_TotalSeqB", "CD127_TotalSeqB"],
        "feasibility": {"G": (13064, 19331), "F_A": (1603, 2020), "F_B": (1605, 2016)},
    },
}
NAMES = list(PINS)  # fixed processing order

# Mapping reference (amendment §5 / criterion 3): logical digest as in scripts/acquire_inputs.py.
CENSUS_VAR_REL = "runs/data/census_2025-11-08_var.parquet"
CENSUS_VAR_LOGICAL_SHA256 = "c6f8bc7c79fac6dc074839f47a0fca48d0f09dfaeef23b751647d80908a0c8e2"

# Eligibility floors (amendment §6). Exact rationals: no float rounding at the boundary.
COVERAGE_FLOORS = {"F_A": Fraction(3, 4), "F_B": Fraction(3, 4), "G": Fraction(3, 5)}
MAX_DROP_BELOW_FEASIBILITY = Fraction(1, 100)
MARKER_MIN_MAPPED = 5
QC_MIN_GENES = 200
QC_MAX_MT_FRAC = 0.20
QC_MIN_RETENTION = Fraction(99, 100)
GATE_CLASSES = ["CD4 T", "CD8 T", "B", "NK", "CD14 mono", "CD16 mono"]  # protein_check gate names == K names
# Antibodies each protein_check gate needs (transcribed from protein_check.gate_cells; equivalence is unit-tested)
GATE_REQUIRES = {"CD4 T": ["CD3", "CD4", "CD8"], "CD8 T": ["CD3", "CD8", "CD4"], "B": ["CD19", "CD3"],
                 "NK": ["CD56", "CD3", "CD19", "CD14"], "CD14 mono": ["CD14", "CD3", "CD19", "CD56"],
                 "CD16 mono": ["CD16", "CD14", "CD3", "CD19", "CD56"]}
CRITERIA = {1: "identity", 2: "structure", 3: "mapping_reference", 4: "coverage", 5: "marker_coverage",
            6: "gate_availability", 7: "qc_retention"}
STATUSES = ["mapped", "ambiguous_make_unique", "ambiguous_census", "unmapped", "ambiguous_collision"]
MAKE_UNIQUE_RE = re.compile(r"^(.+)-(\d+)$")
HDF5_MAGIC = b"\x89HDF\r\n\x1a\n"
LFS_PREFIX = b"version https://git-lfs"

# Output schema (E6-real). protein_check.py reads these exact released-prediction columns.
RELEASED_REQUIRED = ["soma_joinid", "P1_celltypist_target", "P1_celltypist_status", "P1_celltypist_conf",
                     "P2_sctab_target", "P2_sctab_status", "P2_sctab_conf"]
QUERY_OBS_COLUMNS = ["soma_joinid", "barcode", "study", "role", "donor_id", "stratum", "label_status", "target",
                     "assay", "total_counts_all", "total_counts_G"]


class ConfigError(Exception):
    """Wrong or missing inputs detected before any network request (exit 3)."""


class R4Failure(Exception):
    """Acquisition / infrastructure failure: ends the replacement (amendment §10; exit 2)."""


class EligibilityRecordError(Exception):
    """eligibility.json missing, unreadable or not matching its recorded sha256 (exit 4)."""


# ----------------------------------------------------------------------------- small helpers
def utc() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def canonical_json(obj) -> bytes:
    return (json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=True, default=str) + "\n").encode()


def write_atomic(path: Path, data: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    with open(part, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(part, path)
    return sha256_bytes(data)


def url_for(name: str) -> str:
    return URL_TEMPLATE.format(repo=REPO, commit=COMMIT, file=PINS[name]["file"])


def frac_record(present: int, total: int) -> dict:
    return {"present": int(present), "total": int(total), "fraction": (present / total) if total else None,
            "fraction_exact": f"{present}/{total}"}


# ----------------------------------------------------------------------------- E1 acquisition
def classify_payload(head: bytes, content_type: str | None) -> str | None:
    """Return a failure reason for HTML / LFS-pointer / non-HDF5 payloads, else None."""
    if content_type and "text/html" in content_type.lower():
        return f"HTML response (Content-Type {content_type})"
    s = head.lstrip()
    if s.startswith(LFS_PREFIX):
        return "Git LFS pointer instead of file bytes"
    if s[:15].lower().startswith((b"<!doctype", b"<html")):
        return "HTML body instead of file bytes"
    if not head.startswith(HDF5_MAGIC):
        return "payload is not HDF5 (h5ad) bytes"
    return None


def verify_identity(path: Path, name: str) -> dict:
    """Criterion 1: byte count and sha256 equal the pins. Never raises on mismatch; reports."""
    pin = PINS[name]
    n = path.stat().st_size
    with open(path, "rb") as fh:
        head = fh.read(64)
    digest = sha256_file(path)
    bad = classify_payload(head, None)
    ok = n == pin["bytes"] and digest == pin["sha256"] and bad is None
    reason = None
    if not ok:
        reason = bad or ("byte count %d != pinned %d" % (n, pin["bytes"]) if n != pin["bytes"]
                         else f"sha256 {digest} != pinned {pin['sha256']}")
    return {"pass": ok, "bytes": n, "sha256": digest, "reason": reason}


def http_get_once(url: str, dest: Path, opener=urllib.request.urlopen) -> dict:
    """Exactly one GET, streamed to dest.part with the byte cap. Raises R4Failure on transport errors.

    Payload problems (HTML, LFS pointer, wrong size/hash) do not raise: the bytes are kept as
    received (for audit) and criterion 1 then fails for that file.
    """
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT}, method="GET")
    part = dest.with_name(dest.name + ".part")
    dest.parent.mkdir(parents=True, exist_ok=True)
    info = {"url": url, "requested_utc": utc(), "requests": 1}
    try:
        with opener(req, timeout=HTTP_TIMEOUT_S) as r:
            status = getattr(r, "status", None) or r.getcode()
            info["http_status"] = status
            ctype = r.headers.get("Content-Type") if getattr(r, "headers", None) is not None else None
            info["content_type"] = ctype
            if status != 200:
                raise R4Failure(f"HTTP {status} for {url}")
            clen = r.headers.get("Content-Length") if getattr(r, "headers", None) is not None else None
            if clen is not None and int(clen) > BYTE_CAP:
                raise R4Failure(f"Content-Length {clen} exceeds cap {BYTE_CAP}")
            n = 0
            with open(part, "wb") as fh:
                while True:
                    b = r.read(1 << 20)
                    if not b:
                        break
                    n += len(b)
                    if n > BYTE_CAP:
                        raise R4Failure(f"response exceeds cap {BYTE_CAP} bytes")
                    fh.write(b)
                fh.flush()
                os.fsync(fh.fileno())
    except R4Failure:
        part.unlink(missing_ok=True)
        raise
    except Exception as e:  # network, HTTPError, timeout: infrastructure failure, no retry
        part.unlink(missing_ok=True)
        raise R4Failure(f"GET {url} failed: {type(e).__name__}: {e}") from e
    os.replace(part, dest)
    info["completed_utc"] = utc()
    info["content_type_html"] = bool(info.get("content_type") and "text/html" in info["content_type"].lower())
    return info


def copy_cached(src: Path, dest: Path, name: str) -> dict:
    """Verified cached bytes (OA-3). The cache must match both pins BEFORE copying; no GET follows."""
    pin = PINS[name]
    if not src.is_file():
        raise R4Failure(f"cached file missing: {src}")
    pre = verify_identity(src, name)
    if not pre["pass"]:
        raise R4Failure(f"cached file does not match pins: {pre['reason']}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    shutil.copyfile(src, part)
    if sha256_file(part) != pin["sha256"]:
        part.unlink(missing_ok=True)
        raise R4Failure("sha256 mismatch after copying cached file")
    os.replace(part, dest)
    return {"cache_path": str(src), "requests": 0, "copied_utc": utc()}


def acquire(out: Path, cache_dir: Path | None = None, opener=urllib.request.urlopen) -> dict:
    """E1 for both files in fixed order. On an R4Failure, the manifest is written and the error re-raised."""
    inputs = out / "inputs"
    manifest = {"schema": "celltransfer-totalvi-acquisition/1", "amendment_sha256": AMENDMENT_SHA256,
                "commit": COMMIT, "mode": "cached" if cache_dir else "get", "started_utc": utc(),
                "retries": 0, "alternate_hosts": [], "files": {}}
    try:
        for name in NAMES:
            pin = PINS[name]
            dest = inputs / pin["file"]
            rec = {"source": "cached" if cache_dir else "get", "dest": str(dest.relative_to(out))}
            manifest["files"][name] = rec
            if dest.exists():
                raise R4Failure(f"{dest} already exists: R4' writes into a fresh attempt directory only")
            if cache_dir is not None:
                rec.update(copy_cached(Path(cache_dir) / pin["file"], dest, name))
            else:
                rec.update(http_get_once(url_for(name), dest, opener=opener))
            ident = verify_identity(dest, name)
            if rec.get("content_type_html"):
                ident = {**ident, "pass": False, "reason": f"HTML response (Content-Type {rec['content_type']})"}
            rec["identity"] = ident
    except R4Failure as e:
        manifest["status"] = "failed"
        manifest["error"] = str(e)
        manifest["finished_utc"] = utc()
        write_atomic(out / "acquisition.json", canonical_json(manifest))
        raise
    manifest["status"] = "complete"
    manifest["finished_utc"] = utc()
    write_atomic(out / "acquisition.json", canonical_json(manifest))
    return manifest


# ----------------------------------------------------------------------------- mapping (amendment §5)
def logical_var_digest(df) -> str:
    """Identical to scripts/acquire_inputs.logical_var_digest (equivalence is unit-tested)."""
    cols = ["soma_joinid", "feature_id", "feature_name"]
    d = df[cols].sort_values("soma_joinid").reset_index(drop=True)
    return hashlib.sha256(d.to_csv(index=False).encode()).hexdigest()


def census_symbol_index(census_var) -> dict[str, list[str]]:
    """sym -> sorted unique versionless Ensembl IDs with feature_name == sym (exact, case-sensitive)."""
    eid = census_var.feature_id.astype(str).str.split(".").str[0]
    idx: dict[str, set] = {}
    for sym, e in zip(census_var.feature_name.astype(str), eid):
        idx.setdefault(sym, set()).add(e)
    return {k: sorted(v) for k, v in idx.items()}


def map_symbols(var_names: list[str], sym_index: dict[str, list[str]]) -> list[dict]:
    """Deterministic frozen mapping. Returns one record per var name, in file order."""
    names = [str(v) for v in var_names]
    nameset = set(names)
    make_unique = set()
    for v in names:
        m = MAKE_UNIQUE_RE.match(v)
        if m and m.group(1) in nameset:
            make_unique.update({v, m.group(1)})
    recs = []
    for i, v in enumerate(names):
        cands = sym_index.get(v, [])
        if v in make_unique:
            st, eid = "ambiguous_make_unique", None
        elif len(cands) == 1:
            st, eid = "mapped", cands[0]
        elif len(cands) > 1:
            st, eid = "ambiguous_census", None
        else:
            st, eid = "unmapped", None
        recs.append({"index": i, "var_name": v, "status": st, "eid": eid, "census_eids": ";".join(cands)})
    by_eid: dict[str, list[int]] = {}
    for r in recs:
        if r["status"] == "mapped":
            by_eid.setdefault(r["eid"], []).append(r["index"])
    for e, ii in by_eid.items():
        if len(ii) > 1:
            for i in ii:
                recs[i]["status"] = "ambiguous_collision"
    return recs


def mapped_positions(recs: list[dict]) -> dict[str, int]:
    """eid -> column index in the h5ad, for status == mapped only."""
    return {r["eid"]: r["index"] for r in recs if r["status"] == "mapped"}


def coverage(recs: list[dict], meta: dict, G_ids: list[str], name: str) -> dict:
    pos = mapped_positions(recs)
    have = set(pos)
    counts = {s: sum(r["status"] == s for r in recs) for s in STATUSES}
    sets = {"G": list(G_ids), "F_A": meta["F_A"], "F_B": meta["F_B"],
            "markers_A": sorted({g for v in meta["markers_A"].values() for g in v}),
            "markers_B": sorted({g for v in meta["markers_B"].values() for g in v})}
    cov = {k: frac_record(sum(g in have for g in v), len(v)) for k, v in sets.items()}
    per_class = {"K": {c: {"mapped": sum(g in have for g in meta["markers_A"].get(c, [])),
                           "listed": len(meta["markers_A"].get(c, []))} for c in meta["K"]},
                 "K_B": {c: {"mapped": sum(g in have for g in meta["markers_B"].get(c, [])),
                             "listed": len(meta["markers_B"].get(c, []))} for c in meta["K_B"]}}
    feas = PINS[name]["feasibility"]
    diff = {k: {"frozen_present": cov[k]["present"], "feasibility_present": feas[k][0],
                "present_minus_feasibility": cov[k]["present"] - feas[k][0],
                "total_frozen": cov[k]["total"], "total_feasibility": feas[k][1]} for k in ("G", "F_A", "F_B")}
    excluded = {s: [r["var_name"] for r in recs if r["status"] == s] for s in STATUSES if s != "mapped"}
    return {"file": name, "status_counts": counts, "coverage": cov, "per_class_marker_coverage": per_class,
            "difference_from_feasibility": diff, "excluded_var_names": excluded,
            "mapping_reference": CENSUS_VAR_REL, "rule": "amendment §5 (exact, case-sensitive; no aliases)"}


def mapping_csv(recs: list[dict], meta: dict, G_ids: list[str]) -> bytes:
    """Deterministic CSV (T1-exact in tolerances v2): fixed columns, file order, LF line endings."""
    gs, fa, fb = set(G_ids), set(meta["F_A"]), set(meta["F_B"])
    lines = ["index,var_name,status,eid,census_eids,in_G,in_F_A,in_F_B"]
    for r in recs:
        e = r["eid"] if r["status"] == "mapped" else ""
        mapped = r["status"] == "mapped"
        q = lambda s: '"' + s.replace('"', '""') + '"' if ("," in s or '"' in s) else s  # noqa: E731
        lines.append(",".join([str(r["index"]), q(r["var_name"]), r["status"], e, q(r["census_eids"]),
                               str(int(mapped and e in gs)), str(int(mapped and e in fa)),
                               str(int(mapped and e in fb))]))
    return ("\n".join(lines) + "\n").encode()


# ----------------------------------------------------------------------------- criteria (amendment §6)
def check_coverage(cov: dict, name: str) -> tuple[bool, dict]:
    feas = PINS[name]["feasibility"]
    detail, ok = {}, True
    for k in ("F_A", "F_B", "G"):
        c = cov["coverage"][k]
        f = Fraction(c["present"], c["total"]) if c["total"] else Fraction(0)
        fz = Fraction(*feas[k])
        floor_ok = f >= COVERAGE_FLOORS[k]
        drop_ok = f >= fz - MAX_DROP_BELOW_FEASIBILITY
        detail[k] = {"fraction_exact": f"{c['present']}/{c['total']}", "floor": str(COVERAGE_FLOORS[k]),
                     "feasibility_exact": f"{feas[k][0]}/{feas[k][1]}", "floor_ok": floor_ok,
                     "regression_ok": drop_ok}
        ok = ok and floor_ok and drop_ok
    return ok, detail


def check_markers(recs: list[dict], meta: dict) -> tuple[bool, dict]:
    have = set(mapped_positions(recs))
    detail, ok = {}, True
    for c in GATE_CLASSES:
        if c not in meta["K"] or c not in meta["markers_A"]:
            detail[c] = {"present_in_K": c in meta["K"], "pass": False, "reason": "gate class absent from K/markers_A"}
            ok = False
            continue
        mk = meta["markers_A"][c]
        n = sum(g in have for g in mk)
        detail[c] = {"listed": len(mk), "mapped": n, "pass": n >= MARKER_MIN_MAPPED}
        ok = ok and n >= MARKER_MIN_MAPPED
    return ok, detail


def gate_availability(columns: list[str], markers: dict, find) -> tuple[bool, dict]:
    """Criterion 6 on column NAMES only, using protein_check.MARKERS / protein_check.find."""
    used = {m: find(list(columns), pats) for m, pats in markers.items()}
    if used.get("CD19") is None and used.get("CD20") is not None:  # protein_check's CD20 substitute
        used["CD19"] = used["CD20"] + " (CD20 substitute)"
    avail = [g for g in GATE_CLASSES if all(used.get(m) is not None for m in GATE_REQUIRES[g])]
    return len(avail) == len(GATE_CLASSES), {"antibodies_found": used, "gates_available": avail}


def is_nonneg_integer(X) -> bool:
    import numpy as np
    import scipy.sparse as sp
    d = X.data if sp.issparse(X) else np.asarray(X)
    if d.size == 0:
        return True
    d = np.asarray(d, dtype=np.float64)
    return bool(np.all(np.isfinite(d)) and np.all(d >= 0) and np.all(d == np.floor(d)))


def qc_mask(X, var_names):
    """Frozen CITE QC (protocol §7; as in build_cite.py): >=200 detected genes and <20% MT counts."""
    import numpy as np
    import scipy.sparse as sp
    X = sp.csr_matrix(X, dtype=np.float64)
    ngenes = np.asarray((X > 0).sum(1)).ravel()
    mito = np.array([str(v).upper().startswith("MT-") for v in var_names], dtype=bool)
    lib = np.asarray(X.sum(1)).ravel()
    mt = np.asarray(X[:, mito].sum(1)).ravel() / np.maximum(lib, 1)
    return (ngenes >= QC_MIN_GENES) & (mt < QC_MAX_MT_FRAC)


def check_structure(data, name: str) -> tuple[bool, dict]:
    pin = PINS[name]
    d = {"shape": list(data["X"].shape), "pinned_shape": list(pin["shape"]),
         "protein_shape": list(data["protein"].shape), "protein_key": data.get("protein_key")}
    checks = {
        "rna_shape": tuple(data["X"].shape) == tuple(pin["shape"]),
        "protein_shape": tuple(data["protein"].shape) == (pin["shape"][0], len(pin["proteins"])),
        "protein_names_in_order": list(map(str, data["protein"].columns)) == pin["proteins"],
        "rna_nonnegative_integer": is_nonneg_integer(data["X"]),
        "protein_nonnegative_integer": is_nonneg_integer(data["protein"].to_numpy()),
        "unique_barcodes": len(set(map(str, data["obs_names"]))) == len(data["obs_names"]),
        "barcodes_align": list(map(str, data["protein"].index)) == list(map(str, data["obs_names"])),
        "no_IgG": not any(str(c).startswith("IgG") for c in data["protein"].columns),
        "var_names_unique": len(set(map(str, data["var_names"]))) == len(data["var_names"]),
    }
    d["checks"] = checks
    return all(checks.values()), d


def locate_protein(adata, name: str):
    """Find the ADT matrix by pinned shape AND pinned names; exactly one candidate or fail closed.

    The evidence records the ADT shape and names but not the AnnData slot, so the slot is identified
    by content, never assumed. Returns (DataFrame indexed by obs_names, key) or (None, reason).
    """
    import pandas as pd
    pin = PINS[name]
    want = pin["proteins"]
    hits = []
    for k in list(adata.obsm.keys()):
        v = adata.obsm[k]
        if isinstance(v, pd.DataFrame):
            cols = list(map(str, v.columns))
            arr = v.to_numpy()
        else:
            cols = None
            for uk in (f"{k}_names", "protein_names"):
                if uk in adata.uns and len(adata.uns[uk]) == getattr(v, "shape", (0, 0))[1]:
                    cols = [str(c) for c in adata.uns[uk]]
                    break
            arr = v
        if cols == want and getattr(arr, "shape", None) == (adata.n_obs, len(want)):
            hits.append((k, pd.DataFrame(arr, index=list(map(str, adata.obs_names)), columns=want)))
    if len(hits) != 1:
        return None, f"expected exactly one obsm entry with the pinned ADT names/shape, found {len(hits)} " \
                     f"(obsm keys {sorted(adata.obsm.keys())})"
    return hits[0][1], hits[0][0]


def load_h5ad(path: Path, name: str) -> dict:
    """Read one replacement h5ad into plain arrays. Raises ValueError on an unusable structure."""
    import anndata as ad
    import scipy.sparse as sp
    a = ad.read_h5ad(path)
    prot, key = locate_protein(a, name)
    X = a.X if sp.issparse(a.X) else sp.csr_matrix(a.X)
    data = {"X": sp.csr_matrix(X), "var_names": list(map(str, a.var_names)), "obs_names": list(map(str, a.obs_names))}
    if prot is None:
        import pandas as pd
        data["protein"] = pd.DataFrame(index=data["obs_names"])
        data["protein_key"] = None
        data["protein_error"] = key
    else:
        data["protein"] = prot
        data["protein_key"] = key
    return data


def load_reference(workspace: Path):
    import pandas as pd
    return pd.read_parquet(workspace / CENSUS_VAR_REL)


def load_data_run(data_dir: Path) -> tuple[dict, list[str]]:
    import pandas as pd
    meta = json.loads((data_dir / "features_and_classes.json").read_text())
    G = pd.read_csv(data_dir / "gene_universe_G.csv")
    return meta, G.feature_id.astype(str).tolist()


def preflight_data_run(meta: dict, G_ids: list[str]) -> None:
    """The feasibility totals were computed on the frozen data run; a different run is a config error."""
    for name in NAMES:
        feas = PINS[name]["feasibility"]
        got = {"G": len(G_ids), "F_A": len(meta["F_A"]), "F_B": len(meta["F_B"])}
        for k, n in got.items():
            if n != feas[k][1]:
                raise ConfigError(f"data run {k} has {n} features; approved feasibility total is {feas[k][1]} "
                                  "(wrong data run supplied)")
    for k in ("K", "K_B", "F_A", "F_B", "markers_A", "markers_B"):
        if k not in meta:
            raise ConfigError(f"features_and_classes.json lacks {k}")


def evaluate_file(name: str, identity: dict, ref_ok: bool, ref_detail: dict, loader, sym_index, meta, G_ids,
                  find, markers) -> tuple[dict, dict | None]:
    """Criteria 1-7 in order; stop at the first failure. Returns (verdict record, artifacts or None)."""
    res = {"file": PINS[name]["file"], "criteria": {}, "verdict": None, "first_failing_criterion": None}
    arts = None

    def fail(i, detail):
        res["criteria"][CRITERIA[i]] = {"pass": False, **detail}
        res["verdict"] = "ineligible"
        res["first_failing_criterion"] = {"number": i, "name": CRITERIA[i]}
        for j in range(i + 1, 8):
            res["criteria"][CRITERIA[j]] = {"pass": None, "not_evaluated": True}
        return res, arts

    if not identity["pass"]:
        return fail(1, identity)
    res["criteria"]["identity"] = {"pass": True, **identity}
    try:
        data = loader()
    except Exception as e:  # unreadable bytes with correct pins cannot occur, but fail closed
        return fail(2, {"error": f"{type(e).__name__}: {e}"})
    if data.get("protein_key") is None:
        return fail(2, {"error": data.get("protein_error", "ADT matrix not located")})
    ok, det = check_structure(data, name)
    if not ok:
        return fail(2, det)
    res["criteria"]["structure"] = {"pass": True, **det}
    if not ref_ok:
        return fail(3, ref_detail)
    res["criteria"]["mapping_reference"] = {"pass": True, **ref_detail}
    recs = map_symbols(data["var_names"], sym_index)
    cov = coverage(recs, meta, G_ids, name)
    arts = {"data": data, "recs": recs, "coverage": cov}
    ok, det = check_coverage(cov, name)
    if not ok:
        return fail(4, det)
    res["criteria"]["coverage"] = {"pass": True, **det}
    ok, det = check_markers(recs, meta)
    if not ok:
        return fail(5, det)
    res["criteria"]["marker_coverage"] = {"pass": True, **det}
    ok, det = gate_availability(list(data["protein"].columns), markers, find)
    if not ok:
        return fail(6, det)
    res["criteria"]["gate_availability"] = {"pass": True, **det}
    keep = qc_mask(data["X"], data["var_names"])
    n, kept = len(keep), int(keep.sum())
    lost = [b for b, k in zip(data["obs_names"], keep) if not k]
    det = {"cells_h5ad": n, "cells_qc": kept, "lost": n - kept, "lost_barcodes": lost,
           "max_lost_allowed": n - -(-QC_MIN_RETENTION.numerator * n // QC_MIN_RETENTION.denominator)}
    arts["keep"] = keep
    if Fraction(kept, n) < QC_MIN_RETENTION:
        return fail(7, det)
    res["criteria"]["qc_retention"] = {"pass": True, **det}
    res["verdict"] = "eligible"
    return res, arts


def import_protein_check(workspace: Path):
    """Import the unchanged protein_check.py for MARKERS/find (name-only use; no gating is run)."""
    import importlib.util
    p = workspace / "companion/scripts/protein_check.py"
    spec = importlib.util.spec_from_file_location("protein_check_frozen", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, sha256_file(p)


def eligibility(workspace: Path, data_dir: Path, out: Path, *, loader=None, reference=None, pc=None) -> dict:
    """E2-E5. Writes eligibility.json (+ .sha256), mapping_<name>.{json,csv}, barcodes_qc_<name>.txt.

    Uses metadata, names and counts only. No prediction code is imported or run.
    """
    acq = json.loads((out / "acquisition.json").read_text())
    if acq.get("status") != "complete":
        raise R4Failure("acquisition.json does not record a complete E1")
    meta, G_ids = load_data_run(data_dir)
    preflight_data_run(meta, G_ids)
    if pc is None:
        pc, pc_sha = import_protein_check(workspace)
    else:
        pc_sha = getattr(pc, "SHA256", None)
    ref_detail = {"path": CENSUS_VAR_REL, "expected_logical_sha256": CENSUS_VAR_LOGICAL_SHA256}
    try:
        ref = reference if reference is not None else load_reference(workspace)
        ref_detail["logical_sha256"] = logical_var_digest(ref)
        ref_ok = ref_detail["logical_sha256"] == CENSUS_VAR_LOGICAL_SHA256
    except Exception as e:
        ref, ref_ok = None, False
        ref_detail["error"] = f"{type(e).__name__}: {e}"
    sym_index = census_symbol_index(ref) if ref_ok else {}
    record = {"schema": "celltransfer-totalvi-eligibility/1", "amendment": AMENDMENT_PATH,
              "amendment_sha256": AMENDMENT_SHA256, "approval_record": APPROVAL_RECORD,
              "builder_sha256": sha256_file(Path(__file__)), "protein_check_sha256": pc_sha,
              "acquisition_sha256": sha256_file(out / "acquisition.json"), "created_utc": utc(),
              "blinding": "written before any query file, released prediction, protein class or agreement value",
              "files": {}}
    for name in NAMES:
        path = out / "inputs" / PINS[name]["file"]
        ident = acq["files"][name]["identity"]
        # re-verify on disk: the bytes evaluated must be the bytes acquired
        if ident["pass"]:
            now = verify_identity(path, name) if path.exists() else {"pass": False, "sha256": None}
            if not now["pass"] or now["sha256"] != ident["sha256"]:
                ident = {**ident, "pass": False, "reason": "input bytes missing or changed since acquisition"}
        ld = (lambda p=path, n=name: load_h5ad(p, n)) if loader is None else (lambda n=name: loader(n))
        res, arts = evaluate_file(name, ident, ref_ok, ref_detail, ld, sym_index, meta, G_ids, pc.find, pc.MARKERS)
        if arts is not None:
            res["mapping_csv_sha256"] = write_atomic(out / f"mapping_{name}.csv", mapping_csv(arts["recs"], meta, G_ids))
            res["mapping_json_sha256"] = write_atomic(out / f"mapping_{name}.json", canonical_json(arts["coverage"]))
        if res["verdict"] == "eligible":
            kept = [b for b, k in zip(arts["data"]["obs_names"], arts["keep"]) if k]
            res["barcodes_qc_sha256"] = write_atomic(out / f"barcodes_qc_{name}.txt",
                                                     ("\n".join(kept) + "\n").encode())
        record["files"][name] = res
    elig = sorted(n for n, r in record["files"].items() if r["verdict"] == "eligible")
    record["eligible_files"] = elig
    record["n_eligible"] = len(elig)
    record["outcome"] = "run" if elig else "not_run"
    record["deviation_log_lines"] = [
        f"replacement ineligible: {PINS[n]['file']}, criterion {r['first_failing_criterion']['number']} "
        f"({r['first_failing_criterion']['name']})" for n, r in record["files"].items() if r["verdict"] != "eligible"]
    blob = canonical_json(record)
    if (out / "eligibility.json").exists():
        raise R4Failure("eligibility.json already exists; it is written once per R4' attempt")
    digest = write_atomic(out / "eligibility.json", blob)
    write_atomic(out / "eligibility.json.sha256", f"{digest}  eligibility.json\n".encode())
    return record


def read_eligibility(out: Path) -> dict:
    p, s = out / "eligibility.json", out / "eligibility.json.sha256"
    if not p.is_file() or not s.is_file():
        raise EligibilityRecordError("eligibility.json or its .sha256 record is missing")
    want = s.read_text().split()[0]
    if sha256_file(p) != want:
        raise EligibilityRecordError("eligibility.json does not match its recorded sha256")
    rec = json.loads(p.read_text())
    elig = sorted(n for n, r in rec["files"].items() if r["verdict"] == "eligible")
    if elig != rec["eligible_files"] or rec["n_eligible"] != len(elig):
        raise EligibilityRecordError("eligibility.json is internally inconsistent")
    return rec


# ----------------------------------------------------------------------------- E6-real build
def to_counts(X):
    """Raw-count conversion: verified non-negative integers -> float32 CSR (as the frozen builder)."""
    import numpy as np
    import scipy.sparse as sp
    if not is_nonneg_integer(X):
        raise ValueError("matrix is not non-negative integer counts")
    return sp.csr_matrix(X, dtype=np.float32)


def g_matrix(X, recs, G_ids):
    """Columns in G order; mapped eids take their h5ad column, all other G genes are zero."""
    import numpy as np
    import scipy.sparse as sp
    pos = mapped_positions(recs)
    gi = np.array([pos.get(g, -1) for g in G_ids], dtype=np.int64)
    present = gi >= 0
    sel = X[:, np.where(present, gi, 0)]
    return sp.csr_matrix(sel.multiply(present[None, :].astype(np.float32)), dtype=np.float32), int(present.sum())


def build_file(name: str, data: dict, recs: list[dict], keep, meta: dict, G, annotate_p1, annotate_p2, out: Path,
               write_query) -> dict:
    """Write the three per-file outputs for one eligible file. Predictors are injected callables."""
    import numpy as np
    import pandas as pd
    X = to_counts(data["X"])[keep]
    cells = [b for b, k in zip(data["obs_names"], keep) if k]
    G_ids = G.feature_id.astype(str).tolist()
    XG, n_present = g_matrix(X, recs, G_ids)
    lib = np.asarray(X.sum(1)).ravel()
    obs = pd.DataFrame({"soma_joinid": np.arange(len(cells)), "barcode": np.asarray(cells, dtype=object),
                        "study": name, "role": "cite", "donor_id": name, "stratum": "natural",
                        "label_status": "none",
                        # all-missing categorical: an all-None object column cannot be written to h5ad under
                        # the pinned anndata 0.12.19; reads back as missing labels, like Census queries
                        "target": pd.Categorical([None] * len(cells)), "assay": ASSAY, "total_counts_all": lib,
                        "total_counts_G": np.asarray(XG.sum(1)).ravel()})
    p2 = annotate_p2(XG)
    p1 = annotate_p1(X, list(data["var_names"]))
    pred = pd.concat([p1.reset_index(drop=True), p2.reset_index(drop=True)], axis=1)
    pred.insert(0, "soma_joinid", obs.soma_joinid.to_numpy())
    pred.to_parquet(out / f"released_predictions_{name}.parquet")
    F = sorted(set(meta["F_A"]) | set(meta["F_B"]))
    write_query(XG, obs, G, F, out / f"query_{name}_F.h5ad")
    prot = data["protein"].loc[cells]
    A = pd.DataFrame(prot.to_numpy().astype(np.int64), columns=list(prot.columns))
    A.insert(0, "barcode", np.asarray(cells, dtype=object))
    A.to_parquet(out / f"adt_{name}.parquet")
    return {"cells_qc": len(cells), "scTab_genes_present": n_present, "antibodies": list(prot.columns),
            "protein_key": data["protein_key"]}


def validate_outputs(out: Path, rec: dict, read_query=None) -> list[str]:
    """Schema check of E6-real outputs. Returns a list of problems (empty = valid)."""
    import pandas as pd
    errs = []
    for name in rec["eligible_files"]:
        for f in (f"released_predictions_{name}.parquet", f"adt_{name}.parquet", f"query_{name}_F.h5ad"):
            if not (out / f).is_file():
                errs.append(f"missing {f}")
        if errs:
            continue
        rp = pd.read_parquet(out / f"released_predictions_{name}.parquet")
        adt = pd.read_parquet(out / f"adt_{name}.parquet")
        miss = [c for c in RELEASED_REQUIRED if c not in rp.columns]
        if miss:
            errs.append(f"{name}: released predictions lack {miss}")
        if list(adt.columns) != ["barcode"] + PINS[name]["proteins"]:
            errs.append(f"{name}: adt columns differ from the pinned names")
        bq = (out / f"barcodes_qc_{name}.txt").read_text().split("\n")[:-1]
        if adt.barcode.tolist() != bq:
            errs.append(f"{name}: adt barcodes differ from barcodes_qc")
        if len(rp) != len(bq) or rp.soma_joinid.tolist() != list(range(len(bq))):
            errs.append(f"{name}: released predictions rows do not align with barcodes_qc")
        if read_query is not None:
            obs, var_index = read_query(out / f"query_{name}_F.h5ad")
            if list(obs.columns) != QUERY_OBS_COLUMNS:
                errs.append(f"{name}: query obs columns {list(obs.columns)}")
            if obs.barcode.astype(str).tolist() != bq:
                errs.append(f"{name}: query barcodes differ from barcodes_qc")
            if set(obs.assay.astype(str)) != {ASSAY}:
                errs.append(f"{name}: assay label wrong")
    return errs


def real_predictors(workspace: Path):
    """P1/P2 through the unchanged companion released.py interface (as in build_cite.py)."""
    import pandas as pd
    sys.path.insert(0, str(workspace / "companion/src"))
    from celltransfer.released import ScTab, celltypist_annotate
    sct = ScTab(workspace / "runs/data/downloads/sctab_val_f1_macro_epoch41.ckpt",
                workspace / "evidence/probes/P00-metadata-20261005/hf-hparams.yaml",
                workspace / "companion/vendor/sctab_cellnet")
    sct_map = pd.read_csv(workspace / "evidence/label-maps/sctab_164_labels.csv").sort_values("index")
    ct_map = pd.read_csv(workspace / "evidence/label-maps/celltypist_immune_all_low_v2.csv")
    model = workspace / "runs/data/models/celltypist/Immune_All_Low.pkl"
    return (lambda X, syms: celltypist_annotate(X, syms, model, ct_map)), (lambda XG: sct.annotate(XG, sct_map))


def real_write_query(workspace: Path):
    sys.path.insert(0, str(workspace / "companion/src"))
    from celltransfer import census_data as cd

    def w(XG, obs, G, F, path):
        q = cd.to_anndata(XG, obs, G)
        q[:, F].copy().write_h5ad(path, compression="gzip")
    return w


def real_read_query(path: Path):
    import anndata as ad
    q = ad.read_h5ad(path, backed="r")
    obs, idx = q.obs.copy(), list(q.var_names)
    q.file.close()
    return obs, idx


def build(workspace: Path, data_dir: Path, out: Path, *, loader=None, predictors=None, write_query=None,
          read_query=None) -> dict:
    import pandas as pd
    rec = read_eligibility(out)  # raises unless the hashed record is intact
    receipt = {"schema": "celltransfer-totalvi-receipt/1", "amendment_sha256": AMENDMENT_SHA256,
               "eligibility_sha256": sha256_file(out / "eligibility.json"), "n_eligible": rec["n_eligible"],
               "eligible_files": rec["eligible_files"], "assay": ASSAY, "files": {}}
    if rec["n_eligible"] == 0:
        receipt["outcome"] = "not_run"
        write_atomic(out / "receipt.json", canonical_json(receipt))
        write_coverage(out, rec)
        return receipt
    meta = json.loads((data_dir / "features_and_classes.json").read_text())
    G = pd.read_csv(data_dir / "gene_universe_G.csv")
    shutil.copy(data_dir / "features_and_classes.json", out / "features_and_classes.json")
    acq = json.loads((out / "acquisition.json").read_text())
    p1, p2 = predictors if predictors is not None else real_predictors(workspace)
    wq = write_query or real_write_query(workspace)
    for name in rec["eligible_files"]:
        t0 = time.time()
        path = out / "inputs" / PINS[name]["file"]
        if sha256_file(path) != PINS[name]["sha256"]:
            raise R4Failure(f"{path} changed after eligibility")
        data = loader(name) if loader is not None else load_h5ad(path, name)
        ref_recs = mapping_from_csv(out / f"mapping_{name}.csv")
        bq = (out / f"barcodes_qc_{name}.txt").read_text().split("\n")[:-1]
        keep = qc_mask(data["X"], data["var_names"])
        if [b for b, k in zip(data["obs_names"], keep) if k] != bq:
            raise R4Failure(f"{name}: post-QC barcodes differ from the eligibility record")
        info = build_file(name, data, ref_recs, keep, meta, G, p1, p2, out, wq)
        a = acq["files"][name]
        receipt["files"][name] = {"file": PINS[name]["file"], "source": a["source"], "url": a.get("url"),
                                  "cache_path": a.get("cache_path"), "sha256": PINS[name]["sha256"],
                                  "bytes": PINS[name]["bytes"], "cells_h5ad": len(data["obs_names"]),
                                  "mapping_summary": json.loads((out / f"mapping_{name}.json").read_text())[
                                      "coverage"], **info, "seconds": round(time.time() - t0, 1)}
    errs = validate_outputs(out, rec, read_query or real_read_query)
    receipt["schema_errors"] = errs
    receipt["outcome"] = "run" if not errs else "schema_invalid"
    write_atomic(out / "receipt.json", canonical_json(receipt))
    write_coverage(out, rec)
    if errs:
        raise R4Failure("E6-real outputs are not schema-valid: " + "; ".join(errs))
    return receipt


def mapping_from_csv(path: Path) -> list[dict]:
    """Re-read the hashed mapping so E6 uses exactly the recorded mapping."""
    import csv
    with open(path, newline="") as fh:
        rows = list(csv.DictReader(fh))
    return [{"index": int(r["index"]), "var_name": r["var_name"], "status": r["status"],
             "eid": r["eid"] or None, "census_eids": r["census_eids"]} for r in rows]


def write_coverage(out: Path, rec: dict) -> None:
    """Machine-readable coverage summary across files (aggregates only; publishable per §9)."""
    cov = {"schema": "celltransfer-totalvi-coverage/1", "n_eligible": rec["n_eligible"],
           "eligible_files": rec["eligible_files"], "files": {}}
    for name in NAMES:
        p = out / f"mapping_{name}.json"
        r = rec["files"][name]
        cov["files"][name] = {"verdict": r["verdict"], "first_failing_criterion": r["first_failing_criterion"],
                              "mapping": json.loads(p.read_text()) if p.exists() else None}
    write_atomic(out / "coverage.json", canonical_json(cov))


# ----------------------------------------------------------------------------- tolerances v2 support
def expected_cite_files(cite_dir: Path) -> dict:
    """Deterministic `n_eligible` for tolerances v2: read only from the hashed eligibility.json.

    Returns {"n_eligible", "eligible_files", "eligibility_sha256"}; raises EligibilityRecordError if the
    record is missing, tampered or inconsistent (the comparison must then report a structural failure).
    """
    rec = read_eligibility(Path(cite_dir))
    return {"n_eligible": rec["n_eligible"], "eligible_files": rec["eligible_files"],
            "eligibility_sha256": sha256_file(Path(cite_dir) / "eligibility.json")}


def t1_replacement_checks(dir_o: Path, dir_f: Path) -> list[dict]:
    """Added T1 items of tolerances v2, comparing Mode R (o) and Mode F (f) CITE run directories.

    Items: input sha256 equal to pins; eligibility verdicts (and first failing criterion) identical;
    mapping_<name>.csv byte-identical; post-QC barcode list byte-identical. Returns one dict per check
    with status "pass" or "breach"; a missing/tampered record is a breach, never a skip.
    """
    out = []

    def add(item, ok, file=None, **kw):
        out.append({"tier": "T1", "item": item, "file": file, "status": "pass" if ok else "breach", **kw})

    recs = {}
    for side, d in (("original", dir_o), ("reproduction", dir_f)):
        try:
            recs[side] = read_eligibility(Path(d))
        except (EligibilityRecordError, OSError, ValueError, KeyError) as e:
            add("eligibility_record", False, side=side, error=str(e))
    if len(recs) != 2:
        return out
    ro, rf = recs["original"], recs["reproduction"]
    for side, d in (("original", dir_o), ("reproduction", dir_f)):
        acq = json.loads((Path(d) / "acquisition.json").read_text())
        for name in NAMES:
            got = acq["files"].get(name, {}).get("identity", {}).get("sha256")
            add("input_sha256_equals_pin", got == PINS[name]["sha256"], name, side=side, sha256=got)
    v = lambda r: {n: (x["verdict"], (x["first_failing_criterion"] or {}).get("number"))  # noqa: E731
                   for n, x in r["files"].items()}
    add("eligibility_verdicts", v(ro) == v(rf) and ro["n_eligible"] == rf["n_eligible"],
        original=v(ro), reproduction=v(rf))
    for name in NAMES:
        for item, fn in (("mapping_csv", f"mapping_{name}.csv"), ("post_qc_barcodes", f"barcodes_qc_{name}.txt")):
            po, pf = Path(dir_o) / fn, Path(dir_f) / fn
            if not po.exists() and not pf.exists():
                continue  # not produced in either mode (file stopped before this stage in both)
            ok = po.exists() and pf.exists() and sha256_file(po) == sha256_file(pf)
            add(item, ok, name)
    return out


# ----------------------------------------------------------------------------- CLI
def check_disk(out: Path, min_free_gib: float) -> None:
    p = out if out.exists() else out.parent
    free = shutil.disk_usage(p).free / 2**30
    if free < min_free_gib:
        raise ConfigError(f"free disk {free:.2f} GiB < {min_free_gib} GiB guard; nothing requested or written")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["plan", "acquire", "eligibility", "build", "r4prime"])
    ap.add_argument("--workspace", default=str(Path(__file__).resolve().parents[2]))
    ap.add_argument("--data", help="frozen data run (features_and_classes.json, gene_universe_G.csv)")
    ap.add_argument("--out", help="fresh R4' attempt directory, e.g. runs/<R4'>")
    ap.add_argument("--cache-dir", default=None, help="verified cached bytes instead of a GET (labelled cached)")
    ap.add_argument("--min-free-gib", type=float, default=3.0)
    a = ap.parse_args(argv)
    if a.command == "plan":
        print(json.dumps({n: {**{k: v for k, v in p.items() if k != "proteins"}, "url": url_for(n),
                              "n_proteins": len(p["proteins"])} for n, p in PINS.items()}, indent=1, default=str))
        return 0
    if not a.out:
        print("--out is required", file=sys.stderr)
        return 3
    W, OUT = Path(a.workspace).resolve(), Path(a.out).resolve()
    try:
        if a.command in ("acquire", "r4prime"):
            if not a.data:
                raise ConfigError("--data is required")
            check_disk(OUT, a.min_free_gib)
            meta, G_ids = load_data_run(Path(a.data))
            preflight_data_run(meta, G_ids)  # config errors surface before any network request
            if OUT.exists() and any(OUT.iterdir()):
                raise ConfigError(f"{OUT} is not empty; R4' needs a fresh attempt directory")
            OUT.mkdir(parents=True, exist_ok=True)
            acquire(OUT, Path(a.cache_dir) if a.cache_dir else None)
        if a.command in ("eligibility", "r4prime"):
            if not a.data:
                raise ConfigError("--data is required")
            rec = eligibility(W, Path(a.data), OUT)
            print(json.dumps({"n_eligible": rec["n_eligible"], "eligible_files": rec["eligible_files"],
                              "deviation_log_lines": rec["deviation_log_lines"]}), flush=True)
        if a.command in ("build", "r4prime"):
            if not a.data:
                raise ConfigError("--data is required")
            r = build(W, Path(a.data), OUT)
            print(json.dumps({"outcome": r["outcome"], "n_eligible": r["n_eligible"]}), flush=True)
    except ConfigError as e:
        print(f"configuration error (no request made): {e}", file=sys.stderr)
        return 3
    except EligibilityRecordError as e:
        print(f"eligibility record error: {e}", file=sys.stderr)
        return 4
    except R4Failure as e:
        print(f"R4' failure (replacement stops; attempt directory kept): {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Acquire the public, version-pinned inputs that historical/companion/scripts/build_data.py
and build_cite.py expect, with SHA-256 verification and atomic writes.

Usage:
  python scripts/acquire_inputs.py list
  python scripts/acquire_inputs.py acquire --root DIR [--cache-root DIR --allow-cache-fallback]
                                           [--only ID ...] [--dry-run] [--census-compare PATH]

Rules implemented (see protocol/input-acquisition.md):
- Normal HTTPS GET only (urllib, standard library). No cookies, no browser emulation, no
  challenge solving. A non-2xx response or an HTML challenge page is a failure, never bypassed.
- Bounded retries (default 3 attempts, exponential backoff) and a hard per-item byte cap;
  the total planned bytes must fit the study storage cap (7 GiB).
- Downloads stream to "<dest>.part" in the destination directory, are hashed, and are only
  renamed into place (os.replace) when size and SHA-256 match the pinned values.
- Optional cached third-party fallback: a read-only cache root (for example the preserved
  historical tree) is consulted ONLY when --allow-cache-fallback is given and the upstream
  retrieval failed. The copy is hash-verified and labelled "cached-third-party-fallback" in
  the retrieval manifest. The cache root is never written to.
- The Census var table is regenerated from the pinned Census build (2025-11-08) with the
  pinned cellxgene-census package; parquet bytes are not assumed deterministic, so a logical
  comparison (soma_joinid, feature_id, feature_name) is recorded instead.
- Nothing here downloads expression matrices or copies historical derived expression or
  predictions.
All writes happen under --root. Python standard library only, except the optional Census
regeneration which imports cellxgene_census/pandas lazily.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path

USER_AGENT = "cell-type-annotation-transfer-acquire/1.0 (+public reproduction; python-urllib)"
STORAGE_CAP_BYTES = 7 * 1024**3  # protocol/resume-plan-reviewed.md §3
CENSUS_VERSION = "2025-11-08"
CENSUS_PACKAGE_PIN = "cellxgene-census==1.18.0"
HF_REV = "9d49621154863948c057db0741452b18dcb78559"
HF_BASE = f"https://huggingface.co/MohamedMabrouk/scTab/resolve/{HF_REV}"


@dataclass(frozen=True)
class Item:
    id: str
    dest: str                      # path relative to --root, as build_data.py/build_cite.py expect
    kind: str                      # "url" | "repo-copy" | "census-var"
    url: str | None
    sha256: str | None
    size: int | None
    max_bytes: int
    url_provenance: str            # where the URL fact comes from
    hash_provenance: str
    licence: str                   # only what saved records support; "unknown" otherwise
    notes: str = ""
    cache_relpath: str | None = None   # path under --cache-root for the hash-verified fallback
    source_relpath: str | None = None  # for repo-copy: path inside the repository checkout
    third_party: bool = False


H = "historical"  # cache-relative prefixes mirror the preserved historical tree
ITEMS: list[Item] = [
    Item(
        id="sctab-checkpoint",
        dest="runs/data/downloads/sctab_val_f1_macro_epoch41.ckpt",
        kind="url",
        url=f"{HF_BASE}/val_f1_macro_epoch%3D41_val_f1_macro%3D0.847.ckpt",
        sha256="573b911f30f7a70d33a13d1e4e28d596827e389ac0fe55dbfe30952ece70f56c",
        size=503162157,
        max_bytes=600 * 1024**2,
        url_provenance="historical runs/data/downloads/fetch1.sh (exact URL used 2026-10-05)",
        hash_provenance="historical runs/data/downloads/fetch1.log (shasum -a 256 after download 2026-10-05T17:41Z)",
        licence="Mirror self-declares MIT (HF tag; not authoritative). Official scTab README states MIT for the "
                "code repository only; checkpoint licence from the scTab authors is not recorded.",
        notes="Third-party Hugging Face mirror of the scTab run5 checkpoint (official host pklab.med.harvard.edu "
              "serves an Incapsula JS challenge; not circumvented).",
        cache_relpath="runs/data/downloads/sctab_val_f1_macro_epoch41.ckpt",
        third_party=True,
    ),
    Item(
        id="sctab-hparams",
        dest="evidence/probes/P00-metadata-20261005/hf-hparams.yaml",
        kind="url",
        url=f"{HF_BASE}/hparams.yaml",
        sha256="e53f93c42017b20021c70ce0251d8a6bcc19a5dc6374cea1c6019a4003dfbf94",
        size=507,
        max_bytes=1024**2,
        url_provenance="INFERRED: access-and-feasibility.md names `hparams.yaml` in mirror rev 9d49621; the exact "
                       "retrieval URL was not saved",
        hash_provenance="sha256 of the preserved historical probe copy (computed 2026-10-06); not an upstream-published hash",
        licence="as sctab-checkpoint (mirror self-declared MIT; not authoritative)",
        cache_relpath="evidence/probes/P00-metadata-20261005/hf-hparams.yaml",
        third_party=True,
    ),
    Item(
        id="sctab-var",
        dest="evidence/probes/P01-census-blood-obs-20261005/sctab_var.parquet",
        kind="url",
        url=f"{HF_BASE}/merlin_cxg_2023_05_15_sf-log1p_minimal/var.parquet",
        sha256="eca915f6fb7158ac67c58736b54f78f79c455632c977828d4295deb010317579",
        size=436152,
        max_bytes=16 * 1024**2,
        url_provenance="Exact historical retrieval command recovered from original orchestration/claude-stream.jsonl; pinned mirror revision 9d49621154863948c057db0741452b18dcb78559.",
        hash_provenance="sha256 of the preserved historical probe copy (computed 2026-10-06); not an upstream-published hash",
        licence="as sctab-checkpoint (mirror self-declared MIT; not authoritative)",
        cache_relpath="evidence/probes/P01-census-blood-obs-20261005/sctab_var.parquet",
        third_party=True,
    ),
    Item(
        id="celltypist-immune-all-low",
        dest="runs/data/models/celltypist/Immune_All_Low.pkl",
        kind="url",
        url="https://celltypist.cog.sanger.ac.uk/models/Pan_Immune_CellTypist/v2/Immune_All_Low.pkl",
        sha256="290874d35dac039d4c9218c343fde4aac1077709b72a331ce7266f6828c36502",
        size=2824990,
        max_bytes=64 * 1024**2,
        url_provenance="historical probes/P00-metadata-20261005/celltypist-models.json (models.json, v2, 2022-07-16)",
        hash_provenance="historical runs/data/models/celltypist/SHA256SUMS (2026-10-05)",
        licence="unknown (access-and-feasibility.md: 'to verify'); source Dominguez Conde et al. 2022 "
                "https://doi.org/10.1126/science.abl5197",
        cache_relpath="runs/data/models/celltypist/Immune_All_Low.pkl",
    ),
    Item(
        id="celltypist-immune-all-high",
        dest="runs/data/models/celltypist/Immune_All_High.pkl",
        kind="url",
        url="https://celltypist.cog.sanger.ac.uk/models/Pan_Immune_CellTypist/v2/Immune_All_High.pkl",
        sha256="a715fec36c2c421f7c4e31cf4cb4bea883eedab7fd7b20a4b76f091c22660448",
        size=1070426,
        max_bytes=64 * 1024**2,
        url_provenance="historical probes/P00-metadata-20261005/celltypist-models.json",
        hash_provenance="historical runs/data/models/celltypist/SHA256SUMS (2026-10-05)",
        licence="unknown (access-and-feasibility.md: 'to verify')",
        notes="Not read by build_data.py; listed in the historical model folder. Optional.",
        cache_relpath="runs/data/models/celltypist/Immune_All_High.pkl",
    ),
    Item(
        id="cl-basic-obo",
        dest="runs/data/ontology/cl-basic-v2025-07-30.obo",
        kind="url",
        url="https://github.com/obophenotype/cell-ontology/releases/download/v2025-07-30/cl-basic.obo",
        sha256="ba24e2439bceb2608ae47adb9496d79675e717058259677305dd260f478ba07d",
        size=2413965,
        max_bytes=64 * 1024**2,
        url_provenance="INFERRED from the GitHub release tag v2025-07-30 named in access-and-feasibility.md; the "
                       "exact retrieval URL was not saved",
        hash_provenance="historical runs/data/ontology/cl-basic-v2025-07-30.obo.sha256 (2026-10-05)",
        licence="CC BY 4.0 (access-and-feasibility.md table; upstream licence file not re-inspected here)",
        cache_relpath="runs/data/ontology/cl-basic-v2025-07-30.obo",
    ),
    Item(
        id="census-var",
        dest=f"runs/data/census_{CENSUS_VERSION}_var.parquet",
        kind="census-var",
        url=f"s3://cellxgene-census-public-us-west-2/cell-census/{CENSUS_VERSION}/soma/ (via {CENSUS_PACKAGE_PIN})",
        sha256=None,
        size=None,
        max_bytes=64 * 1024**2,
        url_provenance="historical probes/P00-metadata-20261005/census-release.json; census_data.CENSUS_VERSION",
        hash_provenance="not byte-pinned: regenerated; logical comparison (soma_joinid, feature_id, feature_name) "
                        "against a reference copy if supplied. Historical file sha256 "
                        "5b2c4c611fe22e222acb8cff56d60e12198aeedb799318f668b93504cf1f1676 (informational)",
        licence="CELLxGENE Discover data CC BY 4.0 per access-and-feasibility.md ('to be verified in dossier')",
        notes="Historical generation command was not saved; regenerated as homo_sapiens ms['RNA'].var, all columns.",
        cache_relpath="runs/data/census_2025-11-08_var.parquet",
    ),
] + [
    Item(
        id=f"label-map-{name.split('.')[0]}",
        dest=f"evidence/label-maps/{name}",
        kind="repo-copy",
        url=None,
        sha256=sha,
        size=None,
        max_bytes=64 * 1024**2,
        url_provenance="study-authored label map committed in this repository (historical/evidence/label-maps)",
        hash_provenance="sha256 of the committed repository file (2026-10-06)",
        licence="study-authored",
        source_relpath=f"historical/evidence/label-maps/{name}",
    )
    for name, sha in [
        ("census_blood_author_labels.csv", "888b3522812e47688a9a908861ef6c263a068d62698794c8eb398381e82e151b"),
        ("sctab_164_labels.csv", "fb19d4153ce622759d578e11daf6767279fc54df79053ab549c663d6a0356006"),
        ("celltypist_immune_all_low_v2.csv", "f4b2f9a46dc6b60b2bae80a46c262f75a569f0f2207146992695b3156ed7c1ea"),
    ]
]
ITEMS_BY_ID = {i.id: i for i in ITEMS}


class AcquireError(RuntimeError):
    pass


@dataclass
class Record:
    id: str
    dest: str
    status: str                    # verified-existing | downloaded | cached-third-party-fallback | copied |
    #                                regenerated | planned | failed
    source: str | None
    sha256: str | None = None
    bytes: int | None = None
    attempts: int = 0
    errors: list[str] = field(default_factory=list)
    retrieved_utc: str | None = None
    extra: dict = field(default_factory=dict)


def utcnow() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def safe_dest(root: Path, rel: str) -> Path:
    root = root.resolve()
    p = (root / rel).resolve()
    if p != root and root not in p.parents:
        raise AcquireError(f"destination escapes root: {rel}")
    return p


def _open(url: str, timeout: float):
    if not url.startswith("https://"):
        raise AcquireError(f"only https:// URLs are retrieved: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT}, method="GET")
    return urllib.request.urlopen(req, timeout=timeout)


def download(url: str, dest: Path, expected_sha: str, expected_size: int | None, max_bytes: int,
             attempts: int = 3, timeout: float = 120.0, backoff: float = 2.0, opener=_open,
             sleep=time.sleep) -> tuple[int, list[str]]:
    """Stream url to dest atomically. Returns (attempts_used, errors). Raises AcquireError on failure."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    errors: list[str] = []
    for k in range(1, attempts + 1):
        try:
            with opener(url, timeout) as resp:
                status = getattr(resp, "status", 200)
                if not 200 <= status < 300:
                    raise AcquireError(f"HTTP {status}")
                ctype = (resp.headers.get("Content-Type") or "").lower() if resp.headers else ""
                if "text/html" in ctype:
                    raise AcquireError("HTML response (possible access challenge); not bypassed")
                clen = resp.headers.get("Content-Length") if resp.headers else None
                if clen is not None and int(clen) > max_bytes:
                    raise AcquireError(f"Content-Length {clen} exceeds cap {max_bytes}")
                h, n = hashlib.sha256(), 0
                with open(part, "wb") as out:
                    while True:
                        b = resp.read(1 << 20)
                        if not b:
                            break
                        n += len(b)
                        if n > max_bytes:
                            raise AcquireError(f"stream exceeded cap {max_bytes} bytes")
                        h.update(b)
                        out.write(b)
                    out.flush()
                    os.fsync(out.fileno())
            if expected_size is not None and n != expected_size:
                raise AcquireError(f"size {n} != expected {expected_size}")
            if h.hexdigest() != expected_sha:
                raise AcquireError(f"sha256 {h.hexdigest()} != expected {expected_sha}")
            os.replace(part, dest)
            return k, errors
        except (AcquireError, urllib.error.URLError, OSError, ValueError) as e:
            errors.append(f"attempt {k}: {type(e).__name__}: {e}")
            if part.exists():
                part.unlink()
            # integrity failures will not improve on retry; HTTP 4xx neither
            if isinstance(e, urllib.error.HTTPError) and 400 <= e.code < 500 and e.code != 429:
                break
            if isinstance(e, AcquireError) and ("sha256" in str(e) or "HTML" in str(e)):
                break
            if k < attempts:
                sleep(backoff ** k)
    raise AcquireError("; ".join(errors))


def copy_verified(src: Path, dest: Path, expected_sha: str, max_bytes: int) -> int:
    if not src.is_file():
        raise AcquireError(f"missing source {src}")
    n = src.stat().st_size
    if n > max_bytes:
        raise AcquireError(f"{src} exceeds cap {max_bytes}")
    if sha256_file(src) != expected_sha:
        raise AcquireError(f"sha256 mismatch for {src}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    shutil.copyfile(src, part)
    if sha256_file(part) != expected_sha:
        part.unlink()
        raise AcquireError(f"sha256 mismatch after copy of {src}")
    os.replace(part, dest)
    return n


def logical_var_digest(df) -> str:
    cols = ["soma_joinid", "feature_id", "feature_name"]
    d = df[cols].sort_values("soma_joinid").reset_index(drop=True)
    return hashlib.sha256(d.to_csv(index=False).encode()).hexdigest()


def regenerate_census_var(dest: Path, max_bytes: int, compare_to: Path | None = None) -> dict:
    import cellxgene_census  # noqa: lazy, pinned in pyproject (1.18.0)
    import pandas as pd

    with cellxgene_census.open_soma(census_version=CENSUS_VERSION) as census:
        var = census["census_data"]["homo_sapiens"].ms["RNA"].var.read().concat().to_pandas()
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    expected_logical = "c6f8bc7c79fac6dc074839f47a0fca48d0f09dfaeef23b751647d80908a0c8e2"
    if logical_var_digest(var) != expected_logical:
        raise AcquireError("Census feature identities differ from the pinned historical digest")
    var.to_parquet(part)
    if part.stat().st_size > max_bytes:
        part.unlink()
        raise AcquireError("census var exceeds cap")
    os.replace(part, dest)
    info = {"census_version": CENSUS_VERSION, "package": cellxgene_census.__version__, "rows": len(var),
            "columns": list(var.columns), "logical_sha256": logical_var_digest(var)}
    if compare_to is not None:
        ref = pd.read_parquet(compare_to)
        info["compare_to"] = str(compare_to)
        info["compare_logical_sha256"] = logical_var_digest(ref)
        info["logical_match"] = info["compare_logical_sha256"] == info["logical_sha256"]
        if not info["logical_match"]:
            raise AcquireError("Regenerated Census feature metadata differs from the historical reference")
    return info


def planned_bytes(items) -> int:
    return sum((i.size or i.max_bytes) for i in items)


def acquire(root: Path, items, repo: Path, cache_root: Path | None = None, allow_cache: bool = False,
            dry_run: bool = False, census_compare: Path | None = None, opener=_open, sleep=time.sleep,
            attempts: int = 3) -> list[Record]:
    if planned_bytes(items) > STORAGE_CAP_BYTES:
        raise AcquireError("planned bytes exceed the 7 GiB study storage cap")
    if cache_root is not None and allow_cache:
        rc, rr = cache_root.resolve(), root.resolve()
        if rc == rr or rr in rc.parents:
            raise AcquireError("cache root must be outside --root (it is read-only)")
    recs: list[Record] = []
    for it in items:
        dest = safe_dest(root, it.dest)
        rec = Record(id=it.id, dest=it.dest, status="planned", source=it.url or it.source_relpath)
        recs.append(rec)
        if it.sha256 and dest.is_file() and sha256_file(dest) == it.sha256:
            rec.status, rec.sha256, rec.bytes = "verified-existing", it.sha256, dest.stat().st_size
            continue
        if dry_run:
            continue
        try:
            if it.kind == "repo-copy":
                rec.bytes = copy_verified(repo / it.source_relpath, dest, it.sha256, it.max_bytes)
                rec.status, rec.sha256 = "copied", it.sha256
            elif it.kind == "census-var":
                rec.extra = regenerate_census_var(dest, it.max_bytes, census_compare)
                rec.status, rec.sha256, rec.bytes = "regenerated", sha256_file(dest), dest.stat().st_size
                if rec.extra.get("logical_match") is False:
                    rec.status = "failed"
                    rec.errors.append("logical comparison with reference var table failed")
            else:
                try:
                    rec.attempts, rec.errors = download(it.url, dest, it.sha256, it.size, it.max_bytes,
                                                        attempts=attempts, opener=opener, sleep=sleep)
                    rec.status, rec.sha256, rec.bytes = "downloaded", it.sha256, dest.stat().st_size
                except AcquireError as e:
                    rec.errors.append(str(e))
                    rec.attempts = attempts
                    if not (allow_cache and cache_root is not None and it.cache_relpath):
                        raise
                    rec.bytes = copy_verified(cache_root / it.cache_relpath, dest, it.sha256, it.max_bytes)
                    rec.status, rec.sha256 = "cached-third-party-fallback", it.sha256
                    rec.source = f"cache:{it.cache_relpath} (upstream {it.url} failed)"
            rec.retrieved_utc = utcnow()
        except Exception as e:  # recorded, never hidden
            rec.status = "failed"
            rec.errors.append(f"{type(e).__name__}: {e}")
    return recs


def write_manifest(root: Path, recs: list[Record], dry_run: bool) -> Path:
    out = safe_dest(root, "runs/data/retrieval-manifest.json" if not dry_run else "runs/data/retrieval-plan.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = {"generated_utc": utcnow(), "dry_run": dry_run, "tool": "scripts/acquire_inputs.py",
           "items": [dict(asdict(r), **{k: v for k, v in asdict(ITEMS_BY_ID[r.id]).items()
                                         if k in ("url", "url_provenance", "hash_provenance", "licence",
                                                  "third_party", "notes")}) for r in recs]}
    tmp = out.with_name(out.name + ".part")
    tmp.write_text(json.dumps(doc, indent=1))
    os.replace(tmp, out)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="print the pinned inputs as JSON; no network, no writes")
    a = sub.add_parser("acquire")
    a.add_argument("--root", required=True, type=Path, help="study prefix; all writes go here")
    a.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    a.add_argument("--cache-root", type=Path, help="read-only, hash-verified third-party fallback tree")
    a.add_argument("--allow-cache-fallback", action="store_true")
    a.add_argument("--only", nargs="*", choices=sorted(ITEMS_BY_ID))
    a.add_argument("--skip", nargs="*", default=[], choices=sorted(ITEMS_BY_ID))
    a.add_argument("--dry-run", action="store_true", help="report what would be done; writes only the plan")
    a.add_argument("--census-compare", type=Path, help="reference census var parquet for logical comparison")
    a.add_argument("--attempts", type=int, default=3, choices=range(1, 6))
    args = ap.parse_args(argv)
    if args.cmd == "list":
        print(json.dumps([asdict(i) for i in ITEMS], indent=1))
        return 0
    items = [ITEMS_BY_ID[i] for i in (args.only or ITEMS_BY_ID) if i not in args.skip]
    recs = acquire(args.root, items, args.repo, args.cache_root, args.allow_cache_fallback, args.dry_run,
                   args.census_compare, attempts=args.attempts)
    path = write_manifest(args.root, recs, args.dry_run)
    for r in recs:
        print(f"{r.status:28s} {r.id:32s} {r.dest}" + (f"  ERR {r.errors[-1]}" if r.status == "failed" else ""))
    print(f"manifest: {path}")
    return 1 if any(r.status == "failed" for r in recs) else 0


if __name__ == "__main__":
    sys.exit(main())

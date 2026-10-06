#!/usr/bin/env python3
"""Tiered Mode R vs Mode F comparison (protocol/resume-plan-reviewed.md section 7).

  compare_runs.py --original R.json --reproduction F.json --tolerances protocol/tolerances.json --out report.json

Manifests use the portable schema documented in protocol/comparison-implementation.md.
The core logic is stdlib-only; parquet/npy/h5ad inputs need pandas+pyarrow/numpy/anndata,
which are imported lazily. Exit codes: 0 every gated check passed; 1 gated breach or
structural failure (missing/duplicate rows, files, metrics); 3 no breach but at least one
required artifact is unsupported (comparison not possible, so not reproduced); 2 usage error.

Versioned tolerances (protein-replacement amendment, tolerances v2): when
T2_labels.expected_query_files.CITE is "n_eligible" (or {"from": "eligibility.json"}), the expected CITE
file count is the number of "eligible" verdicts in the original's hashed eligibility.json (0, 1 or 2) and
T1 additionally requires the items of build_cite_totalvi.t1_replacement_checks: input sha256 equal to the pins,
identical verdicts, byte-identical mapping_<name>.csv and byte-identical barcodes_qc_<name>.txt. All other tiers are
unchanged. Zero eligible in both modes is reported explicitly ("protein_check": "not run ..."), never as a
silent protein pass; exit code then reflects the remaining tiers only.
"""
from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import json
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import result_manifest as RM  # noqa: E402  (stdlib only; shared eligibility contract)

MANIFEST_SCHEMA = "celltransfer-compare-manifest/1"
REPORT_SCHEMA = "celltransfer-compare-report/1"
METHODS_M = ["M1", "M2", "M3", "M4", "M5", "M6"]
PRACTICAL = [("P1", "P1_celltypist"), ("P2", "P2_sctab")]


class StructuralError(Exception):
    """Missing/duplicate rows, files or metrics. Never skipped or intersected."""


# ------------------------------------------------------------------ numeric states
def parse_value(s):
    """CSV cell -> None (empty: pandas writes NaN and None both as ''), float or str."""
    if s is None:
        return None
    if not isinstance(s, str):
        return s
    t = s.strip()
    if t == "" or t == "None":
        return None
    try:
        return float(t)
    except ValueError:
        return t


def state(x) -> str:
    if x is None:
        return "none"
    if isinstance(x, bool):
        return "finite"
    if isinstance(x, (int, float)):
        xf = float(x)
        if math.isnan(xf):
            return "nan"
        if math.isinf(xf):
            return "+inf" if xf > 0 else "-inf"
        return "finite"
    try:  # numpy / pandas scalars
        return state(float(x))
    except (TypeError, ValueError):
        if str(x) in ("<NA>", "NaT"):
            return "none"
        raise TypeError(f"not numeric: {x!r}")


def close(a, b, abs_tol: float, rel_tol: float):
    """Return (ok, abs_diff or None, state_a, state_b) per section 7."""
    sa, sb = state(a), state(b)
    if sa == "finite" and sb == "finite":
        a, b = float(a), float(b)
        d = abs(a - b)
        return d <= abs_tol + rel_tol * max(abs(a), abs(b)), d, sa, sb
    return sa == sb, None, sa, sb


def allowed_disagreements(n: int, frac: float, minimum: int) -> int:
    return max(minimum, int(math.floor(frac * n + 1e-12)))


def parse_ci(s):
    """'[0.1, 0.2]' / '[nan, nan]' -> (lo, hi)."""
    if s is None or (isinstance(s, str) and s.strip() == ""):
        return (None, None)
    if isinstance(s, (list, tuple)):
        if len(s) != 2:
            raise StructuralError(f"CI does not have two endpoints: {s!r}")
        return tuple(s)
    t = str(s).strip()
    if not (t.startswith("[") and t.endswith("]")):
        raise StructuralError(f"unparseable CI: {s!r}")
    parts = [p.strip() for p in t[1:-1].split(",")]
    if len(parts) != 2:
        raise StructuralError(f"CI does not have two endpoints: {s!r}")
    return tuple(float(p) for p in parts)


def norm_label(x):
    if x is None:
        return None
    try:
        if isinstance(x, float) and math.isnan(x):
            return None
    except TypeError:
        pass
    if str(x) in ("<NA>", "nan", "None"):
        return None
    return str(x)


# ------------------------------------------------------------------ tables
def index_rows(rows, key_cols, where):
    idx = {}
    for r in rows:
        for k in key_cols:
            if k not in r:
                raise StructuralError(f"{where}: key column {k!r} missing")
        k = tuple(str(r[c]) for c in key_cols)
        if k in idx:
            raise StructuralError(f"{where}: duplicate row for key {k}")
        idx[k] = r
    return idx


def match_keys(o: dict, f: dict, where: str):
    mo, mf = sorted(set(o) - set(f)), sorted(set(f) - set(o))
    if mo or mf:
        raise StructuralError(f"{where}: rows missing in reproduction {mo[:20]} / extra in reproduction {mf[:20]}"
                              f" ({len(mo)} missing, {len(mf)} extra)")
    return sorted(o)


def read_csv(path) -> list[dict]:
    p = Path(path)
    if not p.is_file():
        raise StructuralError(f"missing file {p}")
    with open(p, newline="") as fh:
        rows = list(csv.DictReader(fh))
    return rows


def read_parquet_records(path) -> list[dict]:
    p = Path(path)
    if not p.is_file():
        raise StructuralError(f"missing file {p}")
    import pandas as pd  # lazy: scientific env only
    df = pd.read_parquet(p)
    out = []
    cols = list(df.columns)
    for row in df.itertuples(index=False, name=None):
        rec = {}
        for c, v in zip(cols, row):
            if v is pd.NA:
                v = None
            elif hasattr(v, "item") and not isinstance(v, (str, bytes)):
                v = v.item()
            rec[c] = v
        out.append(rec)
    return out


def read_table(path):
    return read_parquet_records(path) if str(path).endswith(".parquet") else read_csv(path)


# ------------------------------------------------------------------ manifests
def _resolve(base: Path, p):
    if p is None:
        return None
    q = Path(p)
    return q if q.is_absolute() else (base / q)


def load_manifest(path) -> dict:
    path = Path(path)
    m = json.load(open(path))
    if m.get("schema") != MANIFEST_SCHEMA:
        raise StructuralError(f"{path}: schema must be {MANIFEST_SCHEMA!r}")
    for k in ("mode", "data", "arms", "score", "protein", "cite"):
        if k not in m:
            raise StructuralError(f"{path}: manifest key {k!r} missing")
    base = path.parent
    out = dict(m)
    out["_path"] = str(path)
    for k in ("data", "cite", "protein", "sampled_ids", "bootstrap_weights", "d03_features", "eligibility"):
        out[k] = _resolve(base, m.get(k))
    if isinstance(m["score"], str):
        out["score"] = {"primary": _resolve(base, m["score"])}
    else:
        out["score"] = {k: _resolve(base, v) for k, v in m["score"].items()}
    out["arms"] = {a: [_resolve(base, d) for d in (v if isinstance(v, list) else [v])] for a, v in m["arms"].items()}
    pc = m.get("protein_classes")
    out["protein_classes"] = {k: _resolve(base, v) for k, v in pc.items()} if isinstance(pc, dict) else None
    return out


def manifest_paths(m) -> list[Path]:
    ps = [m["data"], m["cite"], m["protein"], m.get("sampled_ids"), m.get("bootstrap_weights")]
    ps += list(m["score"].values())
    for v in m["arms"].values():
        ps += v
    if m.get("protein_classes"):
        ps += list(m["protein_classes"].values())
    return [p for p in ps if p is not None]


def check_fresh(orig, repro) -> list[str]:
    """No cached/original outputs may be counted as reproduced."""
    errs = []
    if repro.get("mode") != "F":
        errs.append("reproduction manifest mode must be 'F'")
    if orig.get("mode") != "R":
        errs.append("original manifest mode must be 'R'")
    if repro.get("fresh_execution") is not True:
        errs.append("reproduction manifest must assert fresh_execution: true (outputs produced by this Mode F run)")
    oreal = [os.path.realpath(p) for p in manifest_paths(orig)]
    for p in manifest_paths(repro):
        rp = os.path.realpath(p)
        for o in oreal:
            if rp == o or rp.startswith(o.rstrip(os.sep) + os.sep) or o.startswith(rp.rstrip(os.sep) + os.sep):
                errs.append(f"reproduction path {p} resolves into/over original path {o}")
        # symlinks inside reproduction dirs pointing into original outputs
        if os.path.isdir(rp):
            for root, dirs, files in os.walk(p, followlinks=False):
                for n in dirs + files:
                    q = os.path.join(root, n)
                    if os.path.islink(q):
                        t = os.path.realpath(q)
                        if any(t == o or t.startswith(o.rstrip(os.sep) + os.sep) for o in oreal):
                            errs.append(f"reproduction symlink {q} points into original outputs ({t})")
    return errs


# ------------------------------------------------------------------ report container
class Report:
    def __init__(self):
        self.checks = []

    def add(self, tier, check, status, arm=None, method=None, file=None, gated=True, **details):
        self.checks.append({"tier": tier, "check": check, "status": status, "gated": gated,
                            "arm": arm, "method": method, "file": file, "details": details})

    def structural(self, check, err, arm=None, method=None, file=None):
        self.add("structure", check, "structural_failure", arm, method, file, gated=True, error=str(err))

    def unsupported(self, tier, check, reason, arm=None, method=None):
        self.add(tier, check, "unsupported", arm, method, gated=True, reason=reason)


def _json_safe(x):
    if isinstance(x, float):
        if math.isnan(x):
            return "NaN"
        if math.isinf(x):
            return "Infinity" if x > 0 else "-Infinity"
        return x
    if isinstance(x, dict):
        return {str(k): _json_safe(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_json_safe(v) for v in x]
    return x


# ------------------------------------------------------------------ T1
def compare_exact_rows(rep, check, o_rows, f_rows, key_cols, tier="T1", arm=None, method=None, file=None):
    """Exact equality of every non-key column (state-aware for numbers)."""
    oi = index_rows(o_rows, key_cols, f"{check} original")
    fi = index_rows(f_rows, key_cols, f"{check} reproduction")
    keys = match_keys(oi, fi, check)
    ocols = set().union(*[set(r) for r in o_rows]) if o_rows else set()
    fcols = set().union(*[set(r) for r in f_rows]) if f_rows else set()
    if ocols != fcols:
        raise StructuralError(f"{check}: column sets differ: only original {sorted(ocols - fcols)}, only reproduction {sorted(fcols - ocols)}")
    diffs = []
    for k in keys:
        for c in sorted(ocols - set(key_cols)):
            a, b = oi[k].get(c), fi[k].get(c)
            if not _exact_equal(a, b):
                diffs.append({"key": list(k), "column": c, "original": a, "reproduction": b})
    rep.add(tier, check, "pass" if not diffs else "breach", arm, method, file, rows=len(keys), differences=diffs)
    return not diffs


def _exact_equal(a, b):
    a2, b2 = parse_value(a) if isinstance(a, str) else a, parse_value(b) if isinstance(b, str) else b
    try:
        sa, sb = state(a2), state(b2)
        if sa != sb:
            return False
        return sa != "finite" or float(a2) == float(b2)
    except TypeError:
        return a2 == b2


def t1_features(rep, o, f):
    keys = ["F_A", "F_B", "K", "K_B", "markers_A", "markers_B"]
    try:
        jo = json.load(open(o["data"] / "features_and_classes.json"))
        jf = json.load(open(f["data"] / "features_and_classes.json"))
    except FileNotFoundError as e:
        rep.structural("features_and_classes.json", e)
        return None
    missing = [k for k in keys if k not in jo or k not in jf]
    if missing:
        rep.structural("features_and_classes.json", f"keys missing: {missing}")
        return None
    diff = {k: {"original": jo[k], "reproduction": jf[k]} for k in keys if jo[k] != jf[k]}
    rep.add("T1", "features_and_classes", "pass" if not diff else "breach", differences=diff)
    for k in sorted(set(jo) | set(jf)):
        if k not in keys:
            rep.add("descriptive", f"features_and_classes:{k}", "identical" if jo.get(k) == jf.get(k) else "differs", gated=False)
    for who, m, j in (("original", o, jo), ("reproduction", f, jf)):
        if m.get("d03_features"):
            try:
                d = json.load(open(m["d03_features"]))
                dd = {k: True for k in keys if d.get(k) != j[k]}
                rep.add("T1", f"features_equal_D03:{who}", "pass" if not dd else "breach", differing_keys=sorted(dd))
            except FileNotFoundError as e:
                rep.structural(f"features_equal_D03:{who}", e)
    if not o.get("d03_features") and not f.get("d03_features"):
        rep.unsupported("T1", "features_equal_D03", "no d03_features path in either manifest")
    return jo


def t1_sampled_ids(rep, o, f):
    def load(m):
        if m.get("sampled_ids"):
            rows = read_table(m["sampled_ids"])
        else:
            files = sorted(glob.glob(str(m["data"] / "query_*_F.h5ad")))
            if not files:
                raise StructuralError(f"no sampled_ids table and no query_*_F.h5ad in {m['data']}")
            import anndata as ad  # lazy
            rows = []
            for p in files:
                obs = ad.read_h5ad(p, backed="r").obs
                for s, r, st, j in zip(obs.study, obs.role, obs.stratum, obs.soma_joinid):
                    rows.append({"study": str(s), "role": str(r), "stratum": str(st), "soma_joinid": int(j)})
        return rows
    try:
        ro, rf = load(o), load(f)
    except ImportError as e:
        rep.unsupported("T1", "sampled_soma_joinid", f"no sampled_ids table and h5ad reader unavailable: {e}")
        return
    except StructuralError as e:
        rep.structural("sampled_soma_joinid", e)
        return
    for r in ro + rf:
        r["soma_joinid"] = str(int(float(r["soma_joinid"])))
    try:
        compare_exact_rows(rep, "sampled_soma_joinid", ro, rf, ["study", "role", "stratum", "soma_joinid"])
    except StructuralError as e:
        rep.add("T1", "sampled_soma_joinid", "breach", error=str(e))


def t1_cell_counts_and_info(rep, o, f, sname):
    try:
        compare_exact_rows(rep, f"cell_counts.csv[{sname}]", read_csv(o["score"][sname] / "cell_counts.csv"),
                           read_csv(f["score"][sname] / "cell_counts.csv"), ["role", "study", "stratum", "label_status"])
    except StructuralError as e:
        rep.add("T1", f"cell_counts.csv[{sname}]", "breach", error=str(e))
    try:
        io = json.load(open(o["score"][sname] / "score_info.json"))
        jf = json.load(open(f["score"][sname] / "score_info.json"))
    except FileNotFoundError as e:
        rep.structural(f"score_info.json[{sname}]", e)
        return
    for k in ("test_donors", "reps", "seed"):
        if k not in io or k not in jf:
            rep.structural(f"score_info.json[{sname}]", f"key {k} missing")
            continue
        rep.add("T1", f"score_info:{k}[{sname}]", "pass" if io[k] == jf[k] else "breach",
                original=io[k], reproduction=jf[k])
    if io.get("methods") != jf.get("methods"):
        rep.structural(f"score_info:methods[{sname}]", f"method sets differ: {io.get('methods')} vs {jf.get('methods')}")


def t1_m4_chosen_c(rep, o, f):
    def find(m, arm):
        hits = [d / "M4" / "fit_info.json" for d in m["arms"][arm] if (d / "M4" / "fit_info.json").is_file()]
        if len(hits) != 1:
            raise StructuralError(f"arm {arm}: expected exactly one M4/fit_info.json, found {len(hits)}")
        return json.load(open(hits[0]))
    for arm in sorted(o["arms"]):
        try:
            io, jf = find(o, arm), find(f, arm)
        except StructuralError as e:
            rep.structural("M4_chosen_C", e, arm, "M4")
            continue
        if "chosen_C" not in io or "chosen_C" not in jf:
            rep.structural("M4_chosen_C", "chosen_C missing", arm, "M4")
            continue
        same = float(io["chosen_C"]) == float(jf["chosen_C"])
        det = {"original": io["chosen_C"], "reproduction": jf["chosen_C"]}
        if not same:
            det["validation_macro_f1_by_C"] = {"original": io.get("validation_macro_f1_by_C"),
                                               "reproduction": jf.get("validation_macro_f1_by_C")}
        if "note" in io or "note" in jf:
            det["notes"] = [io.get("note"), jf.get("note")]
        rep.add("T1", "M4_chosen_C", "pass" if same else "breach", arm, "M4", **det)


def t1_bootstrap(rep, o, f):
    if not o.get("bootstrap_weights") or not f.get("bootstrap_weights"):
        rep.unsupported("T1", "bootstrap_weights",
                        "score_all.py does not persist the donor bootstrap weight matrix; a bootstrap_weights .npy "
                        "is required in both manifests for an exact comparison")
        return
    try:
        import numpy as np
    except ImportError as e:
        rep.unsupported("T1", "bootstrap_weights", f"numpy unavailable: {e}")
        return
    for p in (o["bootstrap_weights"], f["bootstrap_weights"]):
        if not Path(p).is_file():
            rep.structural("bootstrap_weights", f"missing file {p}")
            return
    a, b = np.load(o["bootstrap_weights"]), np.load(f["bootstrap_weights"])
    if a.shape != b.shape:
        rep.add("T1", "bootstrap_weights", "breach", shape=[list(a.shape), list(b.shape)])
        return
    neq = int((a != b).sum())
    rep.add("T1", "bootstrap_weights", "pass" if neq == 0 else "breach", shape=list(a.shape), differing_entries=neq,
            max_abs_diff=float(abs(a.astype(float) - b.astype(float)).max()) if a.size else 0.0)


def t1_adt(rep, o, f, cite_files):
    for name in cite_files:
        try:
            ro = read_parquet_records(o["cite"] / f"adt_{name}.parquet")
            rf = read_parquet_records(f["cite"] / f"adt_{name}.parquet")
            compare_exact_rows(rep, "adt_counts", ro, rf, ["barcode"], file=name)
        except ImportError as e:
            rep.unsupported("T1", "adt_counts", f"parquet reader unavailable: {e}")
            return
        except StructuralError as e:
            rep.add("T1", "adt_counts", "breach", file=name, error=str(e))


# ------------------------------------------------------------------ T2 labels/conf
def _stem(p, prefix, suffix=".parquet"):
    n = Path(p).name
    return n[len(prefix):-len(suffix)]


def list_files(d, prefix, suffix=".parquet"):
    return sorted(_stem(p, prefix, suffix) for p in glob.glob(str(Path(d) / f"{prefix}*{suffix}")))


def compare_labels(o_rows, f_rows, label_fn, conf_col, tol, key="soma_joinid"):
    """Per-file label and conf comparison keyed by soma_joinid. Returns detail dict."""
    oi = index_rows(o_rows, [key], "predictions original")
    fi = index_rows(f_rows, [key], "predictions reproduction")
    keys = match_keys(oi, fi, "predictions")
    n = len(keys)
    disagree, conf_breach, maxd = [], [], 0.0
    for k in keys:
        lo, lf = label_fn(oi[k]), label_fn(fi[k])
        if lo != lf:
            disagree.append({"id": k[0], "original": lo, "reproduction": lf})
            continue
        if conf_col is None:
            continue
        ok, d, sa, sb = close(oi[k].get(conf_col), fi[k].get(conf_col), tol["conf_abs"], tol["conf_rel"])
        if d is not None:
            maxd = max(maxd, d)
        if not ok:
            conf_breach.append({"id": k[0], "original": oi[k].get(conf_col), "reproduction": fi[k].get(conf_col),
                                "abs_diff": d, "states": [sa, sb]})
    return {"n": n, "disagreements": len(disagree), "allowed": allowed_disagreements(n, tol["max_disagree_fraction"], tol["min_disagree_allowed"]),
            "agreement": (n - len(disagree)) / n if n else None, "disagreeing_cells": disagree,
            "conf_breaches": conf_breach, "max_abs_conf_diff_agreeing": maxd}


def t2_predictions(rep, o, f, tol, d_files, cite_files):
    t2 = tol["T2_labels"]
    all_files = [("D", n) for n in d_files] + [("CITE", n) for n in cite_files]
    # practical P1/P2 from released_predictions
    for kind, name in all_files:
        base = "data" if kind == "D" else "cite"
        try:
            ro = read_parquet_records(o[base] / f"released_predictions_{name}.parquet")
            rf = read_parquet_records(f[base] / f"released_predictions_{name}.parquet")
        except ImportError as e:
            rep.unsupported("T2", "practical_predictions", f"parquet reader unavailable: {e}")
            return
        except StructuralError as e:
            rep.structural("released_predictions", e, "practical", None, name)
            continue
        for mid, pref in PRACTICAL:
            fn = lambda r, p=pref: (norm_label(r.get(f"{p}_target")), norm_label(r.get(f"{p}_status")))
            try:
                d = compare_labels(ro, rf, fn, f"{pref}_conf", t2)
            except StructuralError as e:
                rep.structural(f"{mid}_labels", e, "practical", mid, name)
                continue
            if mid == "P1":
                rep.add("T1", "P1_labels", "pass" if d["disagreements"] == 0 else "breach", "practical", mid, name,
                        n=d["n"], disagreements=d["disagreements"], disagreeing_cells=d["disagreeing_cells"])
            else:
                rep.add("T2", "labels", "pass" if d["disagreements"] <= d["allowed"] else "breach", "practical", mid, name,
                        **{k: d[k] for k in ("n", "disagreements", "allowed", "agreement", "disagreeing_cells")})
            rep.add("T2", "conf", "pass" if not d["conf_breaches"] else "breach", "practical", mid, name,
                    n_agreeing=d["n"] - d["disagreements"], conf_breaches=d["conf_breaches"],
                    max_abs_conf_diff_agreeing=d["max_abs_conf_diff_agreeing"])
    # matched methods
    for arm in sorted(o["arms"]):
        if set(o["arms"]) != set(f["arms"]):
            rep.structural("arms", f"arm sets differ {sorted(o['arms'])} vs {sorted(f['arms'])}")
            return
        for mid in METHODS_M:
            for kind, name in all_files:
                try:
                    po = _one_pred(o, arm, mid, name)
                    pf = _one_pred(f, arm, mid, name)
                except StructuralError as e:
                    rep.structural("predictions", e, arm, mid, name)
                    continue
                if po is None and pf is None:
                    if kind == "CITE" and arm != "A":
                        continue  # protocol: CITE predictions are Arm A only (R5 --matched A=...)
                    rep.structural("predictions", f"predictions_{name}.parquet missing in both modes", arm, mid, name)
                    continue
                if po is None or pf is None:
                    rep.structural("predictions", f"predictions_{name}.parquet present in only one mode", arm, mid, name)
                    continue
                try:
                    d = compare_labels(read_parquet_records(po), read_parquet_records(pf),
                                       lambda r: norm_label(r.get("pred")), "conf", t2)
                except ImportError as e:
                    rep.unsupported("T2", "matched_predictions", f"parquet reader unavailable: {e}")
                    return
                except StructuralError as e:
                    rep.structural("predictions", e, arm, mid, name)
                    continue
                if mid == "M6":
                    rep.add("diagnostic", "M6_labels_conf", "diagnostic", arm, mid, name, gated=False,
                            heuristic_agreement=tol["diagnostic"]["M6_heuristic_agreement"],
                            heuristic_note=tol["diagnostic"]["M6_heuristic_note"],
                            heuristic_met=(d["agreement"] is not None and d["agreement"] >= tol["diagnostic"]["M6_heuristic_agreement"]),
                            **{k: d[k] for k in ("n", "disagreements", "agreement", "disagreeing_cells",
                                                 "max_abs_conf_diff_agreeing", "conf_breaches")})
                    continue
                rep.add("T2", "labels", "pass" if d["disagreements"] <= d["allowed"] else "breach", arm, mid, name,
                        **{k: d[k] for k in ("n", "disagreements", "allowed", "agreement", "disagreeing_cells")})
                rep.add("T2", "conf", "pass" if not d["conf_breaches"] else "breach", arm, mid, name,
                        n_agreeing=d["n"] - d["disagreements"], conf_breaches=d["conf_breaches"],
                        max_abs_conf_diff_agreeing=d["max_abs_conf_diff_agreeing"])


def _one_pred(m, arm, mid, name):
    hits = [d / mid / f"predictions_{name}.parquet" for d in m["arms"][arm]
            if (d / mid / f"predictions_{name}.parquet").is_file()]
    if len(hits) > 1:
        raise StructuralError(f"duplicate predictions_{name}.parquet for {arm}:{mid}: {hits}")
    return hits[0] if hits else None


# ------------------------------------------------------------------ metrics
def metric_check(rep, tier, check, a, b, tol, arm, method, file=None, gated=True, extra=None):
    ok, d, sa, sb = close(a, b, tol["abs"], tol["rel"])
    det = {"original": a, "reproduction": b, "abs_diff": d, "states": [sa, sb], "tolerance": tol}
    if extra:
        det.update(extra)
    rep.add(tier, check, "pass" if ok else "breach", arm, method, file, gated=gated, **det)
    return ok


def m_summary(rep, o, f, tol, sname):
    M = tol["M_metrics"]
    try:
        so = index_rows(read_csv(o["score"][sname] / "summary_test.csv"), ["arm", "method"], "summary_test original")
        sf = index_rows(read_csv(f["score"][sname] / "summary_test.csv"), ["arm", "method"], "summary_test reproduction")
        keys = match_keys(so, sf, f"summary_test[{sname}]")
    except StructuralError as e:
        rep.structural(f"summary_test[{sname}]", e)
        return
    for k in keys:
        arm, mid = k
        ro, rf = so[k], sf[k]
        for c in ("f1_classes", "test_scorable_natural", "unknown_cells"):
            if c not in ro or c not in rf:
                rep.structural(f"summary_test:{c}[{sname}]", "column missing", arm, mid)
                continue
            rep.add("T1", f"summary_test:{c}[{sname}]", "pass" if _exact_equal(ro[c], rf[c]) else "breach", arm, mid,
                    original=ro[c], reproduction=rf[c])
        if ro.get("unknown_kind") != rf.get("unknown_kind"):
            rep.structural(f"summary_test:unknown_kind[{sname}]", f"{ro.get('unknown_kind')} vs {rf.get('unknown_kind')}", arm, mid)
        for c in M["summary_test_fields"]:
            if c.startswith("unassigned@"):
                src = "coverage@" + c.split("@", 1)[1]
                if src not in ro or src not in rf:
                    continue  # reported as missing under its source column
                a, b = parse_value(ro[src]), parse_value(rf[src])
                a = 1 - a if state(a) == "finite" else a
                b = 1 - b if state(b) == "finite" else b
            else:
                if c not in ro or c not in rf:
                    rep.structural(f"summary_test:{c}[{sname}]", "metric column missing", arm, mid)
                    continue
                a, b = parse_value(ro[c]), parse_value(rf[c])
            metric_check(rep, "M", f"summary_test:{c}[{sname}]", a, b, M["default"], arm, mid)
        if "aurc" not in ro or "aurc" not in rf:
            rep.structural(f"summary_test:aurc[{sname}]", "metric column missing", arm, mid)
        else:
            a, b = parse_value(ro["aurc"]), parse_value(rf["aurc"])
            rel = (abs(a - b) / max(abs(a), abs(b))) if state(a) == state(b) == "finite" and max(abs(a), abs(b)) > 0 else None
            metric_check(rep, "M", f"summary_test:aurc[{sname}]", a, b, M["aurc"], arm, mid, extra={"relative_size": rel})
        for c in M["summary_test_ci_fields"]:
            if c not in ro or c not in rf:
                rep.structural(f"summary_test:{c}[{sname}]", "CI column missing", arm, mid)
                continue
            try:
                lo_o, hi_o = parse_ci(ro[c])
                lo_f, hi_f = parse_ci(rf[c])
            except (StructuralError, ValueError) as e:
                rep.structural(f"summary_test:{c}[{sname}]", e, arm, mid)
                continue
            metric_check(rep, "M", f"summary_test:{c}.lo[{sname}]", lo_o, lo_f, M["default"], arm, mid)
            metric_check(rep, "M", f"summary_test:{c}.hi[{sname}]", hi_o, hi_f, M["default"], arm, mid)


def m_calibration(rep, o, f, tol, sname):
    C = tol["M_metrics"]["calibration"]
    try:
        co = index_rows(read_csv(o["score"][sname] / "calibration_test.csv"), ["arm", "method"], "calibration original")
        cf = index_rows(read_csv(f["score"][sname] / "calibration_test.csv"), ["arm", "method"], "calibration reproduction")
        keys = match_keys(co, cf, f"calibration_test[{sname}]")
    except StructuralError as e:
        rep.structural(f"calibration_test[{sname}]", e)
        return
    for k in keys:
        arm, mid = k
        gated = mid in C["methods"]
        for c in C["fields"]:
            if c not in co[k] or c not in cf[k]:
                rep.structural(f"calibration:{c}[{sname}]", "column missing", arm, mid)
                continue
            metric_check(rep, "M" if gated else "descriptive", f"calibration:{c}[{sname}]", parse_value(co[k][c]),
                         parse_value(cf[k][c]), {"abs": C["abs"], "rel": C["rel"]}, arm, mid, gated=gated)
        # reliability bins: descriptive
        try:
            bo, bf = json.loads(co[k].get("reliability") or "[]"), json.loads(cf[k].get("reliability") or "[]")
        except json.JSONDecodeError as e:
            rep.structural(f"calibration:reliability[{sname}]", e, arm, mid)
            continue
        mo = {(round(b[0], 9), round(b[1], 9)): b for b in bo}
        mf = {(round(b[0], 9), round(b[1], 9)): b for b in bf}
        diffs = {}
        for edge in sorted(set(mo) | set(mf)):
            if edge not in mo or edge not in mf:
                diffs[str(edge)] = "bin present in one mode only"
                continue
            diffs[str(edge)] = [abs(x - y) for x, y in zip(mo[edge][2:], mf[edge][2:])]
        rep.add("descriptive", f"calibration:reliability_bins[{sname}]", "reported", arm, mid, gated=False, abs_diff_by_bin=diffs)


def m_thresholds(rep, o, f, tol, sname):
    M = tol["M_metrics"]
    try:
        to = index_rows(read_csv(o["score"][sname] / "thresholds_validation.csv"), ["arm", "method"], "thresholds original")
        tf = index_rows(read_csv(f["score"][sname] / "thresholds_validation.csv"), ["arm", "method"], "thresholds reproduction")
        keys = match_keys(to, tf, f"thresholds_validation[{sname}]")
    except StructuralError as e:
        rep.structural(f"thresholds_validation[{sname}]", e)
        return
    for k in keys:
        arm, mid = k
        for c in tol["T2_thresholds"]["fields"]:
            if c not in to[k] or c not in tf[k]:
                rep.structural(f"thresholds:{c}[{sname}]", "column missing", arm, mid)
                continue
            a, b = parse_value(to[k][c]), parse_value(tf[k][c])
            sa, sb = state(a), state(b)
            d = abs(a - b) if sa == sb == "finite" else None
            rep.add("T2", f"thresholds:{c}[{sname}]", "pass" if sa == sb else "breach", arm, mid,
                    original=a, reproduction=b, states=[sa, sb], abs_delta_tau=d)
        for c in M["threshold_fields"]:
            if c not in to[k] or c not in tf[k]:
                rep.structural(f"thresholds:{c}[{sname}]", "column missing", arm, mid)
                continue
            metric_check(rep, "M", f"thresholds:{c}[{sname}]", parse_value(to[k][c]), parse_value(tf[k][c]), M["default"], arm, mid)
        for c in ("eligible_cap_validation", "validation_cells"):
            if c in to[k] and c in tf[k]:
                a, b = parse_value(to[k][c]), parse_value(tf[k][c])
                rep.add("descriptive", f"thresholds:{c}[{sname}]", "reported", arm, mid, gated=False,
                        original=a, reproduction=b, abs_diff=abs(a - b) if state(a) == state(b) == "finite" else None)


def is_headline(lo, hi, mean, thr):
    return state(lo) == state(hi) == state(mean) == "finite" and (lo > 0 or hi < 0) and abs(mean) > thr


def excludes_zero(lo, hi):
    return state(lo) == state(hi) == "finite" and (lo > 0 or hi < 0)


def m_paired(rep, o, f, tol, sname):
    M, S = tol["M_metrics"], tol["S_sign"]
    try:
        po = index_rows(read_csv(o["score"][sname] / "paired_differences_vs_M4.csv"), ["arm", "method", "vs", "metric"], "paired original")
        pf = index_rows(read_csv(f["score"][sname] / "paired_differences_vs_M4.csv"), ["arm", "method", "vs", "metric"], "paired reproduction")
        keys = match_keys(po, pf, f"paired_differences_vs_M4[{sname}]")
    except StructuralError as e:
        rep.structural(f"paired_differences_vs_M4[{sname}]", e)
        return
    for k in keys:
        arm, mid, vs, metric = k
        ro, rf = po[k], pf[k]
        vals = {}
        for c in M["paired_difference_fields"]:
            if c not in ro or c not in rf:
                rep.structural(f"paired:{c}[{sname}]", "column missing", arm, mid)
                continue
            vals[c] = (parse_value(ro[c]), parse_value(rf[c]))
            metric_check(rep, "M", f"paired:{metric}:{c}[{sname}]", *vals[c], M["default"], arm, mid, extra={"vs": vs})
        if len(vals) < 3:
            continue
        (mo, mf), (loo, lof), (hio, hif) = vals["mean_diff"], vals["ci95_lo"], vals["ci95_hi"]
        thr = S["headline_abs_mean_diff_gt"]
        if is_headline(loo, hio, mo, thr):
            same_sign = state(mf) == "finite" and (mf > 0) == (mo > 0) and mf != 0
            same_side = excludes_zero(lof, hif) and ((lof > 0) == (loo > 0))
            rep.add("S", f"sign:{metric}[{sname}]", "pass" if (same_sign and same_side) else "breach", arm, mid, vs=vs,
                    original={"mean_diff": mo, "ci95": [loo, hio]}, reproduction={"mean_diff": mf, "ci95": [lof, hif]},
                    same_sign=same_sign, reproduction_ci_excludes_zero_same_side=same_side)
        elif excludes_zero(loo, hio) != excludes_zero(lof, hif):
            near = state(mo) == state(mf) == "finite" and abs(mo) <= thr and abs(mf) <= thr
            rep.add("S", f"sign:{metric}[{sname}]", "near_zero_note" if near else "reported", arm, mid, gated=False, vs=vs,
                    note=(S["near_zero_note"] if near else "CI-exclusion status changed for a non-headline difference"),
                    original={"mean_diff": mo, "ci95": [loo, hio]}, reproduction={"mean_diff": mf, "ci95": [lof, hif]})


def descriptive_table(rep, o, f, sname, fname, key_cols, ordinal=False):
    try:
        ro, rf = read_csv(o["score"][sname] / fname), read_csv(f["score"][sname] / fname)
    except StructuralError as e:
        rep.structural(f"{fname}[{sname}]", e)
        return
    if ordinal:
        for rows in (ro, rf):
            cnt = {}
            for r in rows:
                g = tuple(r[c] for c in key_cols[:-1])
                r[key_cols[-1]] = cnt.get(g, 0)
                cnt[g] = cnt.get(g, 0) + 1
    try:
        oi, fi = index_rows(ro, key_cols, f"{fname} original"), index_rows(rf, key_cols, f"{fname} reproduction")
        keys = match_keys(oi, fi, f"{fname}[{sname}]")
    except StructuralError as e:
        rep.structural(f"{fname}[{sname}]", e)
        return
    maxd, state_changes = {}, []
    for k in keys:
        for c in oi[k]:
            if c in key_cols:
                continue
            if c not in fi[k]:
                rep.structural(f"{fname}[{sname}]", f"column {c} missing in reproduction")
                return
            a, b = parse_value(oi[k][c]), parse_value(fi[k][c])
            try:
                sa, sb = state(a), state(b)
            except TypeError:
                if a != b:
                    state_changes.append({"key": list(k), "column": c, "original": a, "reproduction": b})
                continue
            if sa == sb == "finite":
                maxd[c] = max(maxd.get(c, 0.0), abs(a - b))
            elif sa != sb:
                state_changes.append({"key": list(k), "column": c, "original": a, "reproduction": b})
    rep.add("descriptive", f"{fname}[{sname}]", "reported", gated=False, rows=len(keys), max_abs_diff=maxd,
            state_or_text_changes=state_changes, note="not gated; small n")


# ------------------------------------------------------------------ protein
def protein(rep, o, f, tol, cite_files):
    M = tol["M_metrics"]
    try:
        po = index_rows(read_csv(o["protein"] / "protein_agreement.csv"), ["file", "arm", "method"], "protein original")
        pf = index_rows(read_csv(f["protein"] / "protein_agreement.csv"), ["file", "arm", "method"], "protein reproduction")
        keys = match_keys(po, pf, "protein_agreement")
    except StructuralError as e:
        rep.structural("protein_agreement", e)
        return
    files_seen = sorted({k[0] for k in keys})
    if files_seen != sorted(cite_files):
        rep.structural("protein_agreement", f"files {files_seen} != CITE files {sorted(cite_files)}")
    for k in keys:
        name, arm, mid = k
        for c in M["protein_fields"]:
            if c not in po[k] or c not in pf[k]:
                rep.structural(f"protein:{c}", "column missing", arm, mid, name)
                continue
            metric_check(rep, "M", f"protein:{c}", parse_value(po[k][c]), parse_value(pf[k][c]), M["default"], arm, mid, name)
    try:
        go, gf = json.load(open(o["protein"] / "gates.json")), json.load(open(f["protein"] / "gates.json"))
        rep.add("descriptive", "protein:gates.json", "reported", gated=False,
                identical=go == gf, original=go if go != gf else None, reproduction=gf if go != gf else None)
    except FileNotFoundError as e:
        rep.structural("protein:gates.json", e)
    # per-cell protein classes (T2 gating)
    T = tol["T2_protein_gating"]
    if not o.get("protein_classes") or not f.get("protein_classes"):
        rep.unsupported("T2", "protein_gating_per_cell",
                        "protein_check.py does not persist per-cell protein classes (gates.json holds counts only); "
                        "protein_classes paths per CITE file are required in both manifests")
        return
    if sorted(o["protein_classes"]) != sorted(cite_files) or sorted(f["protein_classes"]) != sorted(cite_files):
        rep.structural("protein_gating_per_cell", "protein_classes must list exactly the CITE files")
        return
    for name in cite_files:
        try:
            d = compare_labels(read_table(o["protein_classes"][name]), read_table(f["protein_classes"][name]),
                               lambda r: norm_label(r.get("protein_class")), None,
                               {"max_disagree_fraction": T["max_disagree_fraction"], "min_disagree_allowed": T["min_disagree_allowed"]},
                               key="barcode")
        except ImportError as e:
            rep.unsupported("T2", "protein_gating_per_cell", f"reader unavailable: {e}")
            return
        except StructuralError as e:
            rep.structural("protein_gating_per_cell", e, file=name)
            continue
        rep.add("T2", "protein_gating_per_cell", "pass" if d["disagreements"] <= d["allowed"] else "breach", file=name,
                **{k: d[k] for k in ("n", "disagreements", "allowed", "agreement", "disagreeing_cells")})


def resources(rep, o, f, tol):
    ro, rf = o.get("resources") or {}, f.get("resources") or {}
    ratio = tol["not_toleranced"]["flag_ratio"]
    for step in sorted(set(ro) | set(rf)):
        for k in sorted(set(ro.get(step, {})) | set(rf.get(step, {}))):
            a, b = ro.get(step, {}).get(k), rf.get(step, {}).get(k)
            r = (b / a) if isinstance(a, (int, float)) and isinstance(b, (int, float)) and a > 0 else None
            flag = r is not None and (r > ratio or r < 1 / ratio)
            rep.add("not_toleranced", f"resource:{step}:{k}", "flag_over_2x" if flag else "reported", gated=False,
                    original=a, reproduction=b, ratio=r)


# ------------------------------------------------------------------ amendment: dynamic eligibility
def cite_expectation(tol):
    """('static', n) for v1; ('dynamic', None) for the v2 eligibility-driven count."""
    v = tol["T2_labels"]["expected_query_files"]["CITE"]
    if isinstance(v, bool):
        raise StructuralError(f"tolerances: invalid CITE expectation {v!r}")
    if isinstance(v, int):
        return "static", v
    if v == "n_eligible" or (isinstance(v, dict) and (v.get("rule") == "n_eligible"
                                                      or "eligibility" in str(v.get("from", "")))):
        return "dynamic", None  # protocol/tolerances-v2.json: {"rule": "n_eligible", "allowed_values": [0, 1, 2]}
    raise StructuralError(f"tolerances: unrecognised CITE expectation {v!r}")


def load_eligibility(m, who):
    p = m.get("eligibility") or (m["cite"] / RM.ELIGIBILITY_FILE)
    try:
        el = RM.parse_eligibility(p)
    except RM.ManifestError as e:
        raise StructuralError(f"{who} eligibility: {e}") from e
    if m.get("eligibility_sha256") and m["eligibility_sha256"] != el["sha256"]:
        raise StructuralError(f"{who} eligibility.json sha256 differs from the hash recorded in its manifest")
    return el


def _file_sha(p: Path):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest() if Path(p).is_file() else None


def t1_eligibility(rep, o, f, eo, ef):
    """T1 additions of the amendment (s7), computed by the builder's authoritative ``t1_replacement_checks``
    (input sha256 == pins from acquisition.json, identical verdicts + first failing criterion, byte-identical
    mapping_<name>.csv and barcodes_qc_<name>.txt). A missing/tampered record is a breach, never a skip."""
    B = RM.builder()
    try:
        items = B.t1_replacement_checks(Path(o["cite"]), Path(f["cite"]))
    except (OSError, ValueError, KeyError, TypeError) as e:
        rep.add("T1", "replacement_records", "breach", error=f"{type(e).__name__}: {e}")
        return
    for it in items:
        det = {k: v for k, v in it.items() if k not in ("tier", "item", "file", "status")}
        rep.add("T1", it["item"], it["status"], file=it.get("file"), **det)
    co, cf = eo["first_failing_criterion"], ef["first_failing_criterion"]
    rep.add("descriptive", "eligibility_first_failing_criterion", "identical" if co == cf else "differs", gated=False,
            original=co, reproduction=cf)


# ------------------------------------------------------------------ outcomes
def outcomes(rep, tol, score_names):
    labels = tol["outcomes"]
    gated = [c for c in rep.checks if c["gated"]]
    am = sorted({(c["arm"], c["method"]) for c in rep.checks if c["arm"] and c["method"]})
    out = {}
    for arm, mid in am:
        mine = [c for c in gated if (c["arm"] == arm and c["method"] == mid) or (c["arm"] is None and c["method"] is None)]
        t1 = [c for c in mine if c["tier"] == "T1" and c["status"] == "breach"]
        breaches = [c for c in mine if c["status"] in ("breach", "structural_failure")]
        unsup = [c for c in mine if c["status"] == "unsupported"]
        if t1:
            o = labels["data_level"]
        elif breaches:
            o = labels["partial"]
        elif unsup:
            o = "not assessable: required artifact unsupported"
        else:
            o = labels["reproduced"]
        out[f"{arm}:{mid}"] = {"outcome": o, "breaches": len(breaches), "unsupported": len(unsup)}
    breaches = [c for c in gated if c["status"] in ("breach", "structural_failure")]
    unsup = [c for c in gated if c["status"] == "unsupported"]
    t1 = [c for c in gated if c["tier"] == "T1" and c["status"] == "breach"]
    fresh_fail = any(c["check"] == "fresh_execution" for c in breaches)
    overall = ("not compared: reproduction outputs are not a fresh Mode F execution" if fresh_fail else
               labels["data_level"] if t1 else labels["partial"] if breaches
               else "not assessable: required artifact unsupported" if unsup else labels["reproduced"])
    m6_only = bool(breaches) and not t1 and all(c["method"] == "M6" for c in breaches)
    return out, overall, breaches, unsup, m6_only


def run(orig_path, repro_path, tol_path, out_path) -> int:
    tol_bytes = Path(tol_path).read_bytes()
    tol = json.loads(tol_bytes)
    rep = Report()
    o, f = load_manifest(orig_path), load_manifest(repro_path)
    fresh = check_fresh(o, f)
    for e in fresh:
        rep.structural("fresh_execution", e)
    if sorted(o["score"]) != sorted(f["score"]):
        rep.structural("score_sets", f"score output sets differ {sorted(o['score'])} vs {sorted(f['score'])}")
    snames = sorted(set(o["score"]) & set(f["score"])) if sorted(o["score"]) == sorted(f["score"]) else []
    t2 = tol["T2_labels"]["expected_query_files"]
    kind_cite, n_cite = cite_expectation(tol)
    eo = ef = None
    protein_note = None
    amended = [bool(m.get("amendment")) for m in (o, f)]
    if kind_cite == "dynamic":
        if amended != [True, True] or o.get("amendment") != f.get("amendment"):
            raise StructuralError("v2 (eligibility-driven) tolerances require two manifests of the same amendment")
        eo, ef = load_eligibility(o, "original"), load_eligibility(f, "reproduction")
        n_cite = eo["n_eligible"]
    elif any(amended):
        raise StructuralError("amended manifests must be compared with the versioned (v2) tolerances")
    d_files_o, d_files_f = list_files(o["data"], "released_predictions_"), list_files(f["data"], "released_predictions_")
    c_files_o, c_files_f = list_files(o["cite"], "released_predictions_"), list_files(f["cite"], "released_predictions_")
    files_ok = True
    if eo is not None:
        for who, el, got in (("original", eo, c_files_o), ("reproduction", ef, c_files_f)):
            if got != el["eligible"]:
                rep.structural("query_files", f"{who}: CITE files {got} != eligible verdicts {el['eligible']}")
                files_ok = False
    for kind, a, b, n in (("D", d_files_o, d_files_f, t2["D"]), ("CITE", c_files_o, c_files_f, n_cite)):
        if a != b:
            rep.structural("query_files", f"{kind} query file sets differ: {a} vs {b}")
            files_ok = False
        if len(a) != n:
            rep.structural("query_files", f"{kind} query files: expected {n}, original has {len(a)}")
        if len(b) != n:
            rep.structural("query_files", f"{kind} query files: expected {n}, reproduction has {len(b)}")
    adt_o, adt_f = list_files(o["cite"], "adt_"), list_files(f["cite"], "adt_")
    if adt_o != c_files_o or adt_f != c_files_f:
        rep.structural("adt_files", f"adt files {adt_o}/{adt_f} do not match CITE files {c_files_o}/{c_files_f}")
    d_files, c_files = sorted(set(d_files_o) & set(d_files_f)), sorted(set(c_files_o) & set(c_files_f))
    if not fresh:
        t1_features(rep, o, f)
        t1_sampled_ids(rep, o, f)
        for s in snames:
            t1_cell_counts_and_info(rep, o, f, s)
        t1_m4_chosen_c(rep, o, f)
        t1_bootstrap(rep, o, f)
        if eo is not None:
            t1_eligibility(rep, o, f, eo, ef)
        if files_ok:
            t1_adt(rep, o, f, c_files)
            t2_predictions(rep, o, f, tol, d_files, c_files)
        for s in snames:
            m_summary(rep, o, f, tol, s)
            m_calibration(rep, o, f, tol, s)
            m_thresholds(rep, o, f, tol, s)
            m_paired(rep, o, f, tol, s)
            descriptive_table(rep, o, f, s, "per_study_test.csv", ["arm", "method", "study"])
            descriptive_table(rep, o, f, s, "per_class_test.csv", ["arm", "method", "class"])
            descriptive_table(rep, o, f, s, "platform.csv", ["arm", "method", "platform"])
            descriptive_table(rep, o, f, s, "unknowns_test.csv", ["arm", "method", "class"])
            descriptive_table(rep, o, f, s, "risk_coverage_test.csv", ["arm", "method", "_ordinal"], ordinal=True)
        rep.add("descriptive", "nan_replicate_counts", "unsupported", gated=False,
                reason="score_all.py does not write NaN-replicate counts; not compared")
        if eo is not None and (eo["n_eligible"] == 0 or ef["n_eligible"] == 0):
            if eo["n_eligible"] == ef["n_eligible"] == 0:
                protein_note = "not run: no eligible replacement file in either mode"
                for who, m in (("original", o), ("reproduction", f)):
                    if m.get("protein") is not None or m.get("protein_status") != "not_run":
                        rep.structural("protein_check", f"{who}: zero eligible files but manifest does not record "
                                                        f"protein_status 'not_run' with no protein output")
                rep.add("protein", "protein_check", "not_run", gated=False, reason=protein_note)
            else:
                protein_note = "not compared: protein check run in only one mode (eligibility verdicts differ)"
                rep.structural("protein_check", protein_note)
        elif o.get("protein") is None or f.get("protein") is None:
            rep.structural("protein_check", "protein output missing although CITE files are eligible/expected")
        else:
            if eo is not None:
                protein_note = f"run on {eo['n_eligible']} eligible replacement file(s): {eo['eligible']}"
            protein(rep, o, f, tol, c_files)
        resources(rep, o, f, tol)
    per, overall, breaches, unsup, m6_only = outcomes(rep, tol, snames)
    report = {
        "schema": REPORT_SCHEMA,
        "tolerances": {"path": str(tol_path), "sha256": hashlib.sha256(tol_bytes).hexdigest()},
        "original_manifest": str(orig_path), "reproduction_manifest": str(repro_path),
        "result_of_record": "Mode R (original)",
        "overall": overall if protein_note is None or not protein_note.startswith("not run")
        else f"{overall}; protein check {protein_note}",
        "protein_check": protein_note,
        "eligibility": None if eo is None else {"original": eo["verdicts"], "reproduction": ef["verdicts"],
                                                "n_eligible": [eo["n_eligible"], ef["n_eligible"]]},
        "per_arm_method": per,
        "m6_only_breach": m6_only,
        "m6_only_wording": tol["outcomes"]["m6_only_wording"] if m6_only else None,
        "counts": {"checks": len(rep.checks), "gated_breaches_or_structural": len(breaches), "unsupported": len(unsup)},
        "failures": [c for c in rep.checks if c["status"] in ("breach", "structural_failure")],
        "unsupported": [c for c in rep.checks if c["status"] == "unsupported" and c["gated"]],
        "ungated_unavailable": [c for c in rep.checks if c["status"] == "unsupported" and not c["gated"]],
        "checks": rep.checks,
    }
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as fh:
        json.dump(_json_safe(report), fh, indent=1, default=str)
    print(json.dumps({"overall": report["overall"], "breaches": len(breaches), "unsupported": len(unsup),
                      "protein_check": protein_note, "report": str(out_path)}))
    return 1 if breaches else (3 if unsup else 0)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--original", required=True, help="Mode R manifest (JSON)")
    ap.add_argument("--reproduction", required=True, help="Mode F manifest (JSON)")
    ap.add_argument("--tolerances", default=str(Path(__file__).resolve().parent.parent / "protocol/tolerances.json"))
    ap.add_argument("--out", required=True, help="report.json path")
    a = ap.parse_args(argv)
    try:
        return run(a.original, a.reproduction, a.tolerances, a.out)
    except (StructuralError, FileNotFoundError, json.JSONDecodeError) as e:
        print(f"compare_runs: fatal: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

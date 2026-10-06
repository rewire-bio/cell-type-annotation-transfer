"""celltransfer: annotate a new blood/PBMC cohort with an abstaining reference classifier.

    celltransfer annotate --bundle BUNDLE_DIR --query my_cells.h5ad --out predictions.csv
    celltransfer check    --bundle BUNDLE_DIR --query my_cells.h5ad

Input contract (checked; violations stop with a clear message):
  * AnnData .h5ad with one row per cell and unique `obs_names` (cell IDs).
  * Raw UMI counts (non-negative integers) in `.X`, or in the layer given by `--layer`, or in
    `.raw.X` with `--use-raw`.
  * Gene identifiers: Ensembl gene IDs (versions are ignored) in `var_names` or in the column
    given by `--gene-id-column`; or HGNC symbols with `--gene-symbols`.
  * Library size is taken from all genes in the file, so pass the full matrix, not a gene subset.

Output: one CSV row per cell with the label, confidence, accept/unassigned decision and a
marker-support check, plus a JSON summary next to it.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp


class InputError(SystemExit):
    pass


def load_bundle(path):
    path = Path(path)
    meta = json.loads((path / "bundle.json").read_text())
    arr = np.load(path / "model.npz")
    return meta, {k: arr[k] for k in arr.files}


def read_query(args):
    import anndata as ad
    q = ad.read_h5ad(args.query)
    if q.n_obs == 0:
        raise InputError("query has no cells")
    if not q.obs_names.is_unique:
        raise InputError("cell IDs (obs_names) are not unique; run adata.obs_names_make_unique() first")
    if args.use_raw:
        if q.raw is None:
            raise InputError("--use-raw given but the file has no .raw")
        X, var = q.raw.X, q.raw.var
    elif args.layer:
        if args.layer not in q.layers:
            raise InputError(f"layer '{args.layer}' not found; available: {list(q.layers)}")
        X, var = q.layers[args.layer], q.var
    else:
        X, var = q.X, q.var
    X = sp.csr_matrix(X)
    sample = X.data[: min(len(X.data), 100000)]
    if len(sample) and (sample.min() < 0 or not np.allclose(sample, np.round(sample))):
        raise InputError("expression values are not raw non-negative integer counts; "
                         "pass raw counts via --layer counts or --use-raw")
    if args.gene_id_column:
        if args.gene_id_column not in var.columns:
            raise InputError(f"--gene-id-column '{args.gene_id_column}' not in var columns {list(var.columns)}")
        ids = var[args.gene_id_column].astype(str)
    else:
        ids = pd.Series(var.index.astype(str), index=var.index)
    ids = ids.str.split(".").str[0].to_numpy() if not args.gene_symbols else ids.to_numpy()
    return q.obs_names.to_numpy(), X.astype(np.float32), ids


def align(meta, X, ids, use_symbols):
    model_ids = meta["gene_symbols"] if use_symbols else meta["gene_ids"]
    pos = pd.Series(np.arange(len(ids)), index=ids)
    pos = pos[~pos.index.duplicated()]
    idx = pd.Series(model_ids).map(pos)
    found = idx.notna().to_numpy()
    cols = idx.fillna(0).astype(int).to_numpy()
    Xm = sp.csr_matrix(X[:, cols].multiply(found[None, :].astype(np.float32)))
    return Xm, float(found.mean()), [g for g, f in zip(model_ids, found) if not f]


def predict(meta, arr, X, lib):
    lib = lib.astype(np.float64).copy()
    lib[lib <= 0] = 1.0
    Xn = sp.csr_matrix(sp.diags(10000.0 / lib) @ X)
    Xn.data = np.log1p(Xn.data)
    Z = np.clip((Xn.toarray() - arr["mu"]) / arr["sd"], -10, 10)
    logits = Z @ arr["coef"].T + arr["intercept"]
    logits -= logits.max(1, keepdims=True)
    P = np.exp(logits)
    P /= P.sum(1, keepdims=True)
    return P, Z


def cmd_annotate(args, check_only=False):
    meta, arr = load_bundle(args.bundle)
    cells, X, ids = read_query(args)
    lib = np.asarray(X.sum(1)).ravel()
    detected = np.asarray((X > 0).sum(1)).ravel()
    Xm, overlap, missing = align(meta, X, ids, args.gene_symbols)
    report = {"cells": int(len(cells)), "model_gene_overlap": round(overlap, 4), "missing_model_genes": len(missing),
              "min_gene_overlap": args.min_gene_overlap}
    if overlap < args.min_gene_overlap:
        msg = (f"only {overlap:.1%} of the {len(meta['gene_ids'])} model genes were found "
               f"(required {args.min_gene_overlap:.0%}); check --gene-id-column/--gene-symbols. "
               f"First missing: {missing[:10]}")
        if check_only:
            print(json.dumps(report, indent=1))
        raise InputError(msg)
    if check_only:
        report["ok"] = True
        print(json.dumps(report, indent=1))
        return
    classes = np.array(meta["classes"])
    gpos = {g: i for i, g in enumerate(meta["gene_ids"])}
    marker_cols = {c: [gpos[g] for g in mk if g in gpos] for c, mk in meta["markers"].items()}
    n = len(cells)
    conf, conf2 = np.empty(n), np.empty(n)
    label, label2 = np.empty(n, dtype=object), np.empty(n, dtype=object)
    support = np.full(n, np.nan)
    for s in range(0, n, args.chunk_size):  # dense z-scores are built per chunk to bound memory
        e = min(s + args.chunk_size, n)
        P, Z = predict(meta, arr, Xm[s:e], lib[s:e])
        order = np.argsort(-P, 1)
        r = np.arange(e - s)
        conf[s:e], conf2[s:e] = P[r, order[:, 0]], P[r, order[:, 1]]
        lab = classes[order[:, 0]]
        label[s:e], label2[s:e] = lab, classes[order[:, 1]]
        for c, cols in marker_cols.items():
            m = lab == c
            if cols and m.any():
                support[s:e][m] = Z[np.ix_(m, cols)].mean(1)
    op = meta["operating_points"][args.operating_point]
    tau = op["threshold"]
    low = (lib < args.min_counts) | (detected < args.min_genes)
    accepted = (conf >= tau) & ~low
    reason = np.where(low, "low_counts_or_genes", np.where(conf < tau, "below_threshold", ""))
    out = pd.DataFrame({"cell_id": cells, "predicted_label": label, "confidence": conf.round(5),
                        "decision": np.where(accepted, "accepted", "unassigned"), "reason": reason,
                        "operating_point": args.operating_point, "threshold": tau,
                        "second_label": label2, "second_confidence": conf2.round(5),
                        "marker_support_z": np.round(support, 3),
                        "marker_flag": np.where(np.nan_to_num(support, nan=-9) < 0, "weak_markers", ""),
                        "total_counts": lib.astype(int), "genes_detected": detected.astype(int)})
    out.to_csv(args.out, index=False)
    report.update({"operating_point": args.operating_point, "threshold": tau,
                   "validation_note": op.get("note", ""),
                   "accepted_fraction": round(float(accepted.mean()), 4),
                   "accepted_label_counts": out[out.decision == "accepted"].predicted_label.value_counts().to_dict(),
                   "unassigned_by_reason": out[out.decision == "unassigned"].reason.value_counts().to_dict(),
                   "bundle": meta.get("provenance", {})})
    Path(str(args.out) + ".summary.json").write_text(json.dumps(report, indent=1, default=str))
    print(json.dumps({k: report[k] for k in ("cells", "model_gene_overlap", "accepted_fraction", "threshold")}))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="celltransfer", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("annotate", "check"):
        p = sub.add_parser(name)
        p.add_argument("--bundle", required=True)
        p.add_argument("--query", required=True)
        p.add_argument("--layer", default=None)
        p.add_argument("--use-raw", action="store_true")
        p.add_argument("--gene-id-column", default=None)
        p.add_argument("--gene-symbols", action="store_true")
        p.add_argument("--min-gene-overlap", type=float, default=0.8)
        if name == "annotate":
            p.add_argument("--out", required=True)
            p.add_argument("--operating-point", choices=["coverage90", "error5"], default="coverage90")
            p.add_argument("--min-counts", type=int, default=500)
            p.add_argument("--min-genes", type=int, default=200)
            p.add_argument("--chunk-size", type=int, default=20000)
    args = ap.parse_args(argv)
    try:
        cmd_annotate(args, check_only=(args.cmd == "check"))
    except InputError as e:
        print(f"celltransfer: input error: {e.code}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

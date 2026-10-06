"""Fit or predict one matched-track method for one arm (protocol sections 3-4).

  run_matched.py --workspace W --data DATA_RUN --arm A --method M4 --stage fit     --out RUN
  run_matched.py --workspace W --data DATA_RUN --arm A --method M4 --stage predict --out RUN

`fit` writes RUN/model.pkl (+ scanvi/ for M6); `predict` reads it and writes
RUN/predictions_<study>.parquet for every query file in DATA_RUN. Each stage is meant to be
wrapped in `/usr/bin/time -l` so runtime and peak memory are measured per process.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

REMOVED_B = ["pDC", "ASC", "MAIT"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--arm", choices=["A", "B"], required=True)
    ap.add_argument("--method", choices=["M1", "M2", "M3", "M4", "M5", "M6"], required=True)
    ap.add_argument("--stage", choices=["fit", "predict"], required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model-dir", default=None, help="predict: load model.pkl from here (default: --out)")
    ap.add_argument("--fixed-c", type=float, default=None, help="smoke tests only: skip validation C choice")
    ap.add_argument("--queries", default="", help="comma-separated study names (default: all query files)")
    args = ap.parse_args()
    W, D, OUT = Path(args.workspace), Path(args.data), Path(args.out)
    OUT.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(W / "companion/src"))
    import anndata as ad
    from sklearn.metrics import f1_score
    from celltransfer import methods as M

    meta = json.load(open(D / "features_and_classes.json"))
    K = meta["K"] if args.arm == "A" else meta["K_B"]
    genes = meta["F_A"] if args.arm == "A" else meta["F_B"]
    markers = meta["markers_A"] if args.arm == "A" else meta["markers_B"]
    t0 = time.time()
    info = {"arm": args.arm, "method": args.method, "stage": args.stage, "data": str(D), "K": K, "n_genes": len(genes)}

    if args.stage == "fit":
        ref = ad.read_h5ad(D / "reference_F.h5ad")
        ref = ref[ref.obs.target.isin(K)].copy()
        info["reference_cells"] = int(ref.n_obs)
        if args.method == "M1":
            model = M.MarkerRule(markers).fit(ref, genes)
        elif args.method == "M2":
            model = M.NearestCentroid().fit(ref, genes)
        elif args.method == "M3":
            model = M.KNN(15).fit(ref, genes)
        elif args.method == "M5":
            model = M.CellTypistRetrained().fit(ref, genes)
        elif args.method == "M6":
            model = M.ScanviTransfer().fit(ref, genes, OUT / "scanvi")
        elif args.fixed_c is not None:
            model = M.Logistic(args.fixed_c).fit(ref, genes)
            info["chosen_C"] = args.fixed_c
            info["note"] = "fixed C (smoke test only)"
        else:  # M4: choose C on validation studies only (closed-set macro-F1, known classes)
            vals = [ad.read_h5ad(p) for p in sorted(D.glob("query_*_F.h5ad"))]
            vals = [v for v in vals if v.obs.role.iloc[0] == "validation"]
            val = ad.concat(vals, merge="same")
            val = val[(val.obs.label_status == "mapped") & val.obs.target.isin(K)].copy()
            scores, models = {}, {}
            for C in (0.01, 0.1, 1.0):
                m = M.Logistic(C).fit(ref, genes)
                p = m.predict(val)
                scores[C] = float(f1_score(val.obs.target.to_numpy(), p.pred.to_numpy(), average="macro"))
                models[C] = m
            best = max(scores, key=lambda c: (scores[c], -c))
            info["validation_macro_f1_by_C"] = scores
            info["chosen_C"] = best
            model = models[best]
        M.save(model, OUT / "model.pkl")
    else:
        model = M.load(Path(args.model_dir or OUT) / "model.pkl")
        info["model_dir"] = str(Path(args.model_dir or OUT))
        want = [q for q in args.queries.split(",") if q]
        per = {}
        for p in sorted(D.glob("query_*_F.h5ad")):
            study = p.name[len("query_"):-len("_F.h5ad")]
            if want and study not in want:
                continue
            q = ad.read_h5ad(p)
            t1 = time.time()
            pred = model.predict(q)
            per[study] = round(time.time() - t1, 2)
            pred.insert(0, "soma_joinid", q.obs.soma_joinid.to_numpy())
            pred.reset_index(drop=True).to_parquet(OUT / f"predictions_{study}.parquet")
        info["seconds_predict_by_study"] = per
    info["seconds_stage"] = round(time.time() - t0, 2)
    json.dump(info, open(OUT / f"{args.stage}_info.json", "w"), indent=1)
    print(json.dumps(info))


if __name__ == "__main__":
    main()

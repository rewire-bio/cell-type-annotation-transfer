"""Export the Arm A logistic-regression (M4) model as a portable numpy bundle for the CLI.

  export_bundle.py --workspace W --data DATA_RUN --model-dir T01/M4 --score SC01 --out BUNDLE_DIR
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    for a in ("--workspace", "--data", "--model-dir", "--score", "--out"):
        ap.add_argument(a, required=True)
    args = ap.parse_args()
    W, D, OUT = Path(args.workspace), Path(args.data), Path(args.out)
    OUT.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(W / "companion/src"))
    from celltransfer import methods as M
    m = M.load(Path(args.model_dir) / "model.pkl")
    meta = json.load(open(D / "features_and_classes.json"))
    G = pd.read_csv(D / "gene_universe_G.csv").set_index("feature_id")
    thr = pd.read_csv(Path(args.score) / "thresholds_validation.csv")
    t = thr[(thr.arm == "A") & (thr.method == "M4")].iloc[0]
    fit = json.load(open(Path(args.model_dir) / "fit_info.json"))
    np.savez_compressed(OUT / "model.npz", coef=m.clf.coef_.astype(np.float32), intercept=m.clf.intercept_.astype(np.float32),
                        mu=m.mu.astype(np.float32), sd=m.sd.astype(np.float32))
    genes = list(m.genes)
    bundle = {
        "format": "celltransfer-bundle/1",
        "classes": list(m.classes), "gene_ids": genes,
        "gene_symbols": [str(G.loc[g, "feature_name"]) for g in genes],
        "markers": {c: v for c, v in meta["markers_A"].items() if c in m.classes},
        "operating_points": {
            "coverage90": {"threshold": float(t.tau_cov), "note": "accepts 90% of validation-study cells (kidney cancer cohort blood, clonal haematopoiesis); test-study coverage and error differ"},
            "error5": {"threshold": float(t.tau_err) if pd.notna(t.tau_err) else 1.01, "note": "lowest threshold with <=5% accepted error on validation studies"}},
        "provenance": {"model": "multinomial logistic regression (scikit-learn lbfgs), Arm A matched reference",
                       "chosen_C": fit.get("chosen_C"), "reference_cells": fit.get("reference_cells"),
                       "reference_studies": "Hao 2021, OneK1K, Perez 2022, van der Wijst 2021, COMBAT 2022, CVID atlas (CELLxGENE Census 2025-11-08; CC BY 4.0)",
                       "cell_ontology": "cl-basic v2025-07-30", "normalisation": "log1p counts per 10,000 (library size over all genes), z-score with reference mean/SD, clip +/-10",
                       "data_run": D.name, "score_run": Path(args.score).name},
    }
    (OUT / "bundle.json").write_text(json.dumps(bundle, indent=1))
    with open(OUT / "SHA256SUMS", "w") as fh:
        for f in ("bundle.json", "model.npz"):
            fh.write(f"{hashlib.sha256((OUT / f).read_bytes()).hexdigest()}  {f}\n")
    print(json.dumps({"classes": len(m.classes), "genes": len(genes), **bundle["operating_points"]}, indent=1))


if __name__ == "__main__":
    main()

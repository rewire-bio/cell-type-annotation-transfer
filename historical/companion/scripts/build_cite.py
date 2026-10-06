"""Build unlabelled CITE-seq queries for the orthogonal protein check (protocol section 7).

  build_cite.py --workspace W --data DATA_RUN --out RUN

Downloads each 10x filtered_feature_bc_matrix.h5 from the public CDN, records SHA-256,
applies QC (>=200 genes, <20% mitochondrial counts), writes query_<name>_F.h5ad (raw counts
on the matched-track feature set), adt_<name>.parquet (raw antibody counts) and
released_predictions_<name>.parquet, then deletes the downloaded .h5 to save disk.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp

FILES = {
    "pbmc10k_protein_v3": "https://cf.10xgenomics.com/samples/cell-exp/3.0.0/pbmc_10k_protein_v3/pbmc_10k_protein_v3_filtered_feature_bc_matrix.h5",
    "pbmc5k_protein_v3_nextgem": "https://cf.10xgenomics.com/samples/cell-exp/3.0.2/5k_pbmc_protein_v3_nextgem/5k_pbmc_protein_v3_nextgem_filtered_feature_bc_matrix.h5",
    "pbmc10k_TotalSeqB_3p": "https://cf.10xgenomics.com/samples/cell-exp/6.0.0/10k_PBMCs_TotalSeq_B_3p/10k_PBMCs_TotalSeq_B_3p_filtered_feature_bc_matrix.h5",
    "pbmc_vdj_v1_5p_TotalSeqC": "https://cf.10xgenomics.com/samples/cell-vdj/3.1.0/vdj_v1_hs_pbmc3/vdj_v1_hs_pbmc3_filtered_feature_bc_matrix.h5",
}


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    W, D, OUT = Path(args.workspace), Path(args.data), Path(args.out)
    OUT.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(W / "companion/src"))
    import scanpy as sc
    from celltransfer import census_data as cd
    from celltransfer.released import ScTab, celltypist_annotate

    shutil.copy(D / "features_and_classes.json", OUT / "features_and_classes.json")
    meta = json.load(open(D / "features_and_classes.json"))
    F = sorted(set(meta["F_A"]) | set(meta["F_B"]))
    G = pd.read_csv(D / "gene_universe_G.csv")
    sct = ScTab(W / "runs/data/downloads/sctab_val_f1_macro_epoch41.ckpt",
                W / "evidence/probes/P00-metadata-20261005/hf-hparams.yaml", W / "companion/vendor/sctab_cellnet")
    sct_map = pd.read_csv(W / "evidence/label-maps/sctab_164_labels.csv").sort_values("index")
    ct_map = pd.read_csv(W / "evidence/label-maps/celltypist_immune_all_low_v2.csv")
    receipt = {}
    for name, url in FILES.items():
        if args.only and name not in args.only.split(","):
            continue
        cd.guard(OUT, 0.4)
        h5 = OUT / f"{name}.h5"
        t0 = time.time()
        urllib.request.urlretrieve(url, h5)
        digest, size = sha256(h5), h5.stat().st_size
        a = sc.read_10x_h5(h5, gex_only=False)
        a.var_names_make_unique()
        gex = a[:, (a.var.feature_types == "Gene Expression").to_numpy()].copy()
        adt = a[:, (a.var.feature_types == "Antibody Capture").to_numpy()].copy()
        X = sp.csr_matrix(gex.X, dtype=np.float32)
        ngenes = np.asarray((X > 0).sum(1)).ravel()
        mito = gex.var_names.str.upper().str.startswith("MT-").to_numpy()
        lib = np.asarray(X.sum(1)).ravel()
        mt_frac = np.asarray(X[:, mito].sum(1)).ravel() / np.maximum(lib, 1)
        keep = (ngenes >= 200) & (mt_frac < 0.20)
        X, lib = X[keep], lib[keep]
        cells = gex.obs_names[keep]
        ens = gex.var.gene_ids.astype(str).str.split(".").str[0].to_numpy()
        pos = pd.Series(np.arange(len(ens)), index=ens)
        pos = pos[~pos.index.duplicated()]
        # scTab gene order (zero for absent genes)
        gi = G.feature_id.map(pos)
        present = gi.notna().to_numpy()
        XG = sp.csr_matrix(X[:, np.where(present, gi.fillna(0).astype(int), 0)].multiply(present[None, :].astype(np.float32)))
        p2 = sct.annotate(XG, sct_map)
        p1 = celltypist_annotate(X, gex.var_names.tolist(), W / "runs/data/models/celltypist/Immune_All_Low.pkl", ct_map)
        obs = pd.DataFrame({"soma_joinid": np.arange(len(cells)), "barcode": np.asarray(cells), "study": name,
                            "role": "cite", "donor_id": name, "stratum": "natural", "label_status": "none",
                            "target": None, "assay": "10x CITE-seq", "total_counts_all": lib,
                            "total_counts_G": np.asarray(XG.sum(1)).ravel()})
        pred = pd.concat([p1, p2], axis=1)
        pred.insert(0, "soma_joinid", obs.soma_joinid.to_numpy())
        pred.to_parquet(OUT / f"released_predictions_{name}.parquet")
        q = cd.to_anndata(XG, obs, G)
        q[:, F].copy().write_h5ad(OUT / f"query_{name}_F.h5ad", compression="gzip")
        A = pd.DataFrame(adt.X[keep].toarray() if sp.issparse(adt.X) else adt.X[keep], columns=list(adt.var_names))
        A.insert(0, "barcode", np.asarray(cells))
        A.to_parquet(OUT / f"adt_{name}.parquet")
        h5.unlink()
        receipt[name] = {"url": url, "sha256": digest, "bytes": size, "cells_raw": int(a.n_obs),
                         "cells_qc": int(keep.sum()), "antibodies": list(adt.var_names),
                         "scTab_genes_present": int(present.sum()), "seconds": round(time.time() - t0, 1)}
        print(name, receipt[name]["cells_qc"], "cells;", len(adt.var_names), "antibodies", flush=True)
    json.dump(receipt, open(OUT / "receipt.json", "w"), indent=1)


if __name__ == "__main__":
    main()

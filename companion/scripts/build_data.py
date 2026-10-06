"""Build the frozen-protocol data: reference (matched track) and validation/test/platform
queries with released-model (practical track) predictions computed on the fly.

Usage: build_data.py --workspace W --out RUN_DIR [--smoke] [--resume]
Writes only inside RUN_DIR. Stored matrices hold raw counts for the union of the Arm A and
Arm B matched-track feature sets; released models see the full gene set in memory only.
With --resume, studies whose checkpoint (RUN_DIR/checkpoints/<name>.json, written after the
study's outputs) exists are loaded instead of pulled, and the sampling RNG is restored to the
state saved after that study, so the samples are identical to an uninterrupted run.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp

warnings.filterwarnings("ignore", category=FutureWarning)

REFERENCE = {"Hao2021": "ed5d841d-6346-47d4-ab2f-7119ad7e3a35", "OneK1K": "3faad104-2ab8-4434-816d-474d8d2641db",
             "Perez2022": "218acb0f-9f2f-4f76-b90b-15a4b7c7f629", "vanderWijst2021": "01ad3cd7-3929-4654-84c0-6db05bd5fd59",
             "COMBAT2022": "ebc2e1ff-c8f9-466a-acf4-9d291afaf8b3", "CVID": "3c75a463-6a87-4132-83a8-c3002624394d"}
VALIDATION = {"KidneyBlood": "5af90777-6760-4003-9dba-8f945fec6fdf", "ClonalHaem": "19e46756-9100-4e01-8b0e-23b557558a4c"}
TEST = {"HIHA": "e522d2cd-7927-4e59-a4ed-064009569279", "RA": "d18736c3-6292-4379-919a-d6d973204c87",
        "Glaucoma": "30c2a6fd-d547-460f-a5e7-44c62a2af7ad", "JDM": "a199ca73-035d-44e2-9893-4c493151db21"}
PLATFORM_COLLECTION = "398e34a9-8736-4b27-a9a7-31a47a67f446"
REMOVED_B = ["pDC", "ASC", "MAIT"]


def log(msg):
    print(f"[{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}] {msg}", flush=True)


def select_features(adata_G, study_col, classes, n_hvg=2000, n_markers=10):
    import scanpy as sc
    a = adata_G[adata_G.obs.target.isin(classes)].copy()
    h = sc.pp.highly_variable_genes(a, n_top_genes=n_hvg, flavor="seurat_v3", batch_key=study_col, inplace=False)
    hvg = set(a.var_names[h.highly_variable.to_numpy()])
    lib = a.obs.total_counts_all.to_numpy().astype(np.float32)
    Xn = sp.diags(10000.0 / lib) @ a.X
    Xn.data = np.log1p(Xn.data)
    b = sc.AnnData(X=sp.csr_matrix(Xn), obs=a.obs[["target"]].copy(), var=a.var.copy())
    sc.tl.rank_genes_groups(b, "target", method="t-test", n_genes=200)
    markers = {}
    for cls in classes:
        df = sc.get.rank_genes_groups_df(b, group=cls)
        df = df[df.logfoldchanges > 1].head(n_markers)
        markers[cls] = df.names.tolist()
    feats = hvg | {g for v in markers.values() for g in v}
    return sorted(feats), markers, sorted(hvg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--smoke", action="store_true", help="2 donors per study, tiny caps, ref+1 test study")
    ap.add_argument("--resume", action="store_true", help="reuse completed per-study checkpoints in --out")
    args = ap.parse_args()
    W = Path(args.workspace)
    OUT = Path(args.out)
    OUT.mkdir(parents=True, exist_ok=True)
    CK = OUT / "checkpoints"
    if not args.resume:
        assert not any(p.suffix in (".h5ad", ".parquet", ".json") for p in OUT.iterdir()), "run directory not empty"
    CK.mkdir(exist_ok=True)
    sys.path.insert(0, str(W / "companion/src"))
    import anndata as ad
    import cellxgene_census
    from celltransfer import census_data as cd
    from celltransfer.released import ScTab, celltypist_annotate

    t0 = time.time()
    rng = np.random.default_rng(cd.SEED)
    author_map = pd.read_csv(W / "evidence/label-maps/census_blood_author_labels.csv")
    census_var = pd.read_parquet(W / "runs/data/census_2025-11-08_var.parquet")
    sctab_var = pd.read_parquet(W / "evidence/probes/P01-census-blood-obs-20261005/sctab_var.parquet")
    G = cd.gene_universe(census_var, sctab_var)
    G.to_csv(OUT / "gene_universe_G.csv", index=False)
    present = G.census_joinid.to_numpy() >= 0
    log(f"G: {len(G)} genes, {present.sum()} in Census, {(~present).sum()} zero-filled")
    all_var = census_var.soma_joinid.to_numpy()
    # column positions of G genes inside the all-gene pull (all_var is 0..n-1 ordered)
    G_pos = G.census_joinid.to_numpy()

    smoke = args.smoke
    ref_kw = dict(n_donors=2, per_class=20) if smoke else {}
    q_kw = dict(n_donors=2, natural=100, topup=5) if smoke else {}
    ref_studies = dict(list(REFERENCE.items())[:2]) if smoke else REFERENCE
    receipt = {"census_version": cd.CENSUS_VERSION, "seed": cd.SEED, "smoke": smoke, "studies": {}}

    def load_checkpoint(name):
        """Return the saved receipt entry and restore the RNG, or None if the study is not done."""
        p = CK / f"{name}.json"
        if not (args.resume and p.exists()):
            return None
        ck = json.load(open(p))
        rng.bit_generator.state = ck["rng_state_after"]
        log(f"resume {name}: loaded checkpoint")
        return ck["receipt"]

    def save_checkpoint(name, entry):
        tmp = CK / f"{name}.json.tmp"
        json.dump({"receipt": entry, "rng_state_after": rng.bit_generator.state}, open(tmp, "w"))
        tmp.rename(CK / f"{name}.json")

    def write_h5ad(a, path):
        tmp = path.with_suffix(".tmp.h5ad")
        a.write_h5ad(tmp, compression="gzip")
        tmp.rename(path)

    def pull_all_genes(census, obs):
        X = cd.fetch_counts(census, obs.soma_joinid.to_numpy(), all_var)
        obs = obs.copy()
        obs["total_counts_all"] = np.asarray(X.sum(1)).ravel()
        XG = sp.csr_matrix(X[:, np.where(present, G_pos, 0)].multiply(present[None, :].astype(np.float32)))
        obs["total_counts_G"] = np.asarray(XG.sum(1)).ravel()
        return X, XG, obs

    with cellxgene_census.open_soma(census_version=cd.CENSUS_VERSION) as census:
        # ---------------- reference ----------------
        ref_parts = []
        for name, did in ref_studies.items():
            part = CK / f"reference_{name}_G.h5ad"
            entry = load_checkpoint(name)
            if entry is not None:
                ref_parts.append(ad.read_h5ad(part))
                receipt["studies"][name] = entry
                continue
            cd.guard(OUT)
            df = cd.attach_labels(cd.read_obs(census, did), author_map)
            s = cd.sample_reference(df, rng, **ref_kw)
            s["study"] = name
            _, XG, s = pull_all_genes(census, s)
            ref_parts.append(cd.to_anndata(XG, s, G))
            receipt["studies"][name] = {"role": "reference", "dataset_id": did, "obs_rows": len(df),
                                        "donors": sorted(s.donor_id.unique().tolist()), "cells": len(s)}
            cd.guard(OUT)
            write_h5ad(ref_parts[-1], part)
            save_checkpoint(name, receipt["studies"][name])
            log(f"reference {name}: {len(s)} cells, {s.donor_id.nunique()} donors")
        ref = ad.concat(ref_parts, merge="same")
        ref.var = ref_parts[0].var
        counts = ref.obs.groupby("target").agg(cells=("study", "size"), studies=("study", "nunique"))
        K = sorted(counts[(counts.cells >= (5 if smoke else 100)) & (counts.studies >= 2)].index.tolist())
        K_B = [k for k in K if k not in REMOVED_B]
        log(f"K ({len(K)}): {K}")
        F_A, markers_A, hvg_A = select_features(ref, "study", K)
        refB = ref[~ref.obs.target.isin(REMOVED_B)].copy()
        F_B, markers_B, hvg_B = select_features(refB, "study", K_B)
        F = sorted(set(F_A) | set(F_B))
        json.dump({"K": K, "K_B": K_B, "F_A": F_A, "F_B": F_B, "markers_A": markers_A, "markers_B": markers_B,
                   "hvg_A": hvg_A, "hvg_B": hvg_B, "reference_class_counts": counts.reset_index().to_dict("records")},
                  open(OUT / "features_and_classes.json", "w"), indent=1)
        log(f"F_A {len(F_A)}, F_B {len(F_B)}, union {len(F)}")
        if not (OUT / "reference_F.h5ad").exists():
            cd.guard(OUT)
            write_h5ad(ref[:, F].copy(), OUT / "reference_F.h5ad")
        del ref, refB, ref_parts

        # ---------------- queries ----------------
        sct = ScTab(W / "runs/data/downloads/sctab_val_f1_macro_epoch41.ckpt",
                    W / "evidence/probes/P00-metadata-20261005/hf-hparams.yaml",
                    W / "companion/vendor/sctab_cellnet")
        sct_map = pd.read_csv(W / "evidence/label-maps/sctab_164_labels.csv").sort_values("index")
        ct_map = pd.read_csv(W / "evidence/label-maps/celltypist_immune_all_low_v2.csv")
        ct_model = W / "runs/data/models/celltypist/Immune_All_Low.pkl"

        queries = [("validation", n, d) for n, d in VALIDATION.items()] + [("test", n, d) for n, d in TEST.items()]
        if smoke:
            queries = [("test", "HIHA", TEST["HIHA"])]
        else:
            ds = census["census_info"]["datasets"].read().concat().to_pandas()
            plat = ds[ds.collection_id == PLATFORM_COLLECTION]
            obs_assay = {}
            for did in sorted(plat.dataset_id):
                a = census["census_data"]["homo_sapiens"].obs.read(
                    value_filter=f"dataset_id == '{did}'", column_names=["assay"]).concat().to_pandas()
                obs_assay[did] = a.assay.astype(str).iloc[0] if len(a) else None
            first = {}
            for did in sorted(obs_assay):
                if obs_assay[did] is not None and obs_assay[did] not in first:
                    first[obs_assay[did]] = did
            for assay, did in sorted(first.items()):
                queries.append(("platform", "Platform_" + "".join(ch for ch in assay if ch.isalnum()), did))
        for role, name, did in queries:
            entry = load_checkpoint(name)
            if entry is not None:
                receipt["studies"][name] = entry
                continue
            cd.guard(OUT)
            tq = time.time()
            df = cd.attach_labels(cd.read_obs(census, did), author_map)
            s = cd.sample_platform(df, rng, n=100 if smoke else 1000) if role == "platform" else cd.sample_query(df, rng, **q_kw)
            s["study"], s["role"] = name, role
            X, XG, s = pull_all_genes(census, s)
            t_pull = time.time() - tq
            t1 = time.time()
            p2 = sct.annotate(XG, sct_map)
            t_sct = time.time() - t1
            t1 = time.time()
            p1 = celltypist_annotate(X, census_var.feature_name.tolist(), ct_model, ct_map)
            t_ct = time.time() - t1
            pred = pd.concat([p1, p2], axis=1)
            pred.insert(0, "soma_joinid", s.soma_joinid.to_numpy())
            cd.guard(OUT)
            pred.to_parquet(OUT / f"released_predictions_{name}.parquet")
            a = cd.to_anndata(XG, s, G)
            write_h5ad(a[:, F].copy(), OUT / f"query_{name}_F.h5ad")
            receipt["studies"][name] = {"role": role, "dataset_id": did, "obs_rows": len(df), "cells": len(s),
                                        "donors": sorted(s.donor_id.unique().tolist()),
                                        "assays": sorted(s.assay.unique().tolist()),
                                        "seconds_pull": round(t_pull, 1), "seconds_sctab": round(t_sct, 1),
                                        "seconds_celltypist": round(t_ct, 1)}
            save_checkpoint(name, receipt["studies"][name])
            log(f"{role} {name}: {len(s)} cells, {s.donor_id.nunique()} donors; pull {t_pull:.0f}s scTab {t_sct:.0f}s CellTypist {t_ct:.0f}s")
            del X, XG, a
    receipt["seconds_total"] = round(time.time() - t0, 1)
    json.dump(receipt, open(OUT / "receipt.json", "w"), indent=1)
    log("done")


if __name__ == "__main__":
    main()

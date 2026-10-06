"""Practical-track wrappers: released scTab run5 checkpoint and CellTypist Immune_All_Low.

Both return a per-cell frame with the raw top label, its probability (the confidence used
for thresholding), the mapped status/target/lineage, and target-level probabilities
(released label probabilities summed per target class; mass on coarser/outside labels goes
to the column "other").
"""
from __future__ import annotations

import sys
from collections import OrderedDict
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp

from .ontology import TARGETS

TARGET_NAMES = list(TARGETS)


def aggregate(probs: np.ndarray, label_map: pd.DataFrame) -> np.ndarray:
    """probs: cells x labels (label order = label_map rows). Returns cells x (targets + other)."""
    A = np.zeros((len(label_map), len(TARGET_NAMES) + 1), dtype=np.float32)
    for i, (st, tg) in enumerate(zip(label_map.status, label_map.target)):
        A[i, TARGET_NAMES.index(tg) if st == "mapped" else len(TARGET_NAMES)] = 1.0
    return probs @ A


def _frame(top_idx, top_p, label_map, agg, prefix):
    lm = label_map.reset_index(drop=True)
    out = pd.DataFrame({
        f"{prefix}_label": lm.label.to_numpy()[top_idx],
        f"{prefix}_conf": top_p.astype(np.float32),
        f"{prefix}_status": lm.status.to_numpy()[top_idx],
        f"{prefix}_target": lm.target.to_numpy()[top_idx],
        f"{prefix}_lineage": lm.lineage.to_numpy()[top_idx],
    })
    for j, name in enumerate(TARGET_NAMES + ["other"]):
        out[f"{prefix}_p::{name}"] = agg[:, j]
    return out


class ScTab:
    def __init__(self, ckpt: str | Path, hparams: str | Path, vendor_dir: str | Path, threads: int = 4):
        import torch
        import yaml
        sys.path.insert(0, str(vendor_dir))
        from cellnet.tabnet.tab_network import TabNet
        torch.set_num_threads(threads)
        ck = torch.load(str(ckpt), map_location="cpu")
        w = OrderedDict((k.replace("classifier.", ""), v) for k, v in ck["state_dict"].items() if "classifier." in k)
        hp = yaml.full_load(open(hparams).read())
        self.net = TabNet(input_dim=hp["gene_dim"], output_dim=hp["type_dim"], n_d=hp["n_d"], n_a=hp["n_a"],
                          n_steps=hp["n_steps"], gamma=hp["gamma"], n_independent=hp["n_independent"],
                          n_shared=hp["n_shared"], epsilon=hp["epsilon"],
                          virtual_batch_size=hp["virtual_batch_size"], momentum=hp["momentum"],
                          mask_type=hp["mask_type"])
        self.net.load_state_dict(w)
        self.net.eval()
        self.torch = torch

    def predict_proba(self, X_counts_G: sp.csr_matrix, batch: int = 2048) -> np.ndarray:
        """X_counts_G: raw counts in scTab gene order (19,331 columns)."""
        torch = self.torch
        out = []
        with torch.no_grad():
            for s in range(0, X_counts_G.shape[0], batch):
                x = torch.from_numpy(X_counts_G[s:s + batch].toarray().astype(np.float32))
                counts = x.sum(1, keepdim=True)
                counts += counts == 0.0
                logits, _ = self.net(torch.log1p(10000.0 / counts * x))
                out.append(torch.softmax(logits, 1).numpy())
        return np.vstack(out)

    def annotate(self, X_counts_G, label_map: pd.DataFrame) -> pd.DataFrame:
        p = self.predict_proba(X_counts_G)
        return _frame(p.argmax(1), p.max(1), label_map, aggregate(p, label_map), "P2_sctab")


def celltypist_annotate(X_counts_all: sp.csr_matrix, gene_symbols: list[str], model_path: str | Path,
                        label_map: pd.DataFrame) -> pd.DataFrame:
    """CellTypist on log1p CP10k computed over all supplied genes; no majority voting."""
    import anndata as ad
    import celltypist
    X = sp.csr_matrix(X_counts_all, dtype=np.float32)
    lib = np.asarray(X.sum(1)).ravel()
    lib[lib == 0] = 1.0
    Xn = sp.diags(10000.0 / lib) @ X
    Xn.data = np.log1p(Xn.data)
    sym = pd.Index(gene_symbols)
    keep = ~sym.duplicated()
    a = ad.AnnData(X=sp.csr_matrix(Xn[:, np.where(keep)[0]]), var=pd.DataFrame(index=sym[keep].astype(str)))
    model = celltypist.models.Model.load(str(model_path))
    res = celltypist.annotate(a, model=model, majority_voting=False)
    pm = res.probability_matrix
    lm = label_map.set_index("label").loc[list(pm.columns)].reset_index()
    p = pm.to_numpy(dtype=np.float32)
    return _frame(p.argmax(1), p.max(1), lm, aggregate(p, lm), "P1_celltypist")

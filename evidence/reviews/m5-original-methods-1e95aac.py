"""Matched-track annotators M1-M6 (protocol section 3).

Every annotator is fitted on reference AnnData holding raw counts for the stored feature
set, with `obs.target` labels and `obs.total_counts_all` (library size over all genes).
`predict` returns a DataFrame indexed like the query with columns `pred`, `conf` and, when
the method produces class probabilities, `p::<class>`.
"""
from __future__ import annotations

import pickle
import warnings

import numpy as np
import pandas as pd
import scipy.sparse as sp

warnings.filterwarnings("ignore", category=FutureWarning)


def lognorm(X, lib) -> sp.csr_matrix:
    """log1p of counts per 10,000, using library sizes computed over all genes."""
    X = sp.csr_matrix(X, dtype=np.float32)
    lib = np.asarray(lib, dtype=np.float64).copy()
    lib[lib <= 0] = 1.0
    Xn = sp.csr_matrix(sp.diags(10000.0 / lib) @ X, dtype=np.float32)
    Xn.data = np.log1p(Xn.data)
    return Xn


class _Scaled:
    """Shared preprocessing: log-normalise, z-score with reference statistics (clip ±10)."""

    def _prep_fit(self, adata, genes):
        self.genes = list(genes)
        X = lognorm(adata[:, self.genes].X, adata.obs.total_counts_all).toarray()
        self.mu = X.mean(0)
        self.sd = X.std(0)
        self.sd[self.sd == 0] = 1.0
        return np.clip((X - self.mu) / self.sd, -10, 10)

    def _prep(self, adata):
        X = lognorm(adata[:, self.genes].X, adata.obs.total_counts_all).toarray()
        return np.clip((X - self.mu) / self.sd, -10, 10)


class MarkerRule(_Scaled):
    name = "M1_marker"

    def __init__(self, markers: dict[str, list[str]]):
        self.markers = {k: v for k, v in markers.items() if v}

    def fit(self, adata, genes):
        self.classes = sorted(self.markers)
        mk = sorted({g for v in self.markers.values() for g in v})
        self._prep_fit(adata, mk)
        return self

    def predict(self, adata):
        Z = self._prep(adata)
        idx = {g: i for i, g in enumerate(self.genes)}
        S = np.column_stack([Z[:, [idx[g] for g in self.markers[c]]].mean(1) for c in self.classes])
        o = np.argsort(-S, 1)
        top, second = S[np.arange(len(S)), o[:, 0]], S[np.arange(len(S)), o[:, 1]]
        return pd.DataFrame({"pred": np.array(self.classes)[o[:, 0]], "conf": top - second}, index=adata.obs_names)


class _PCA(_Scaled):
    def _fit_pca(self, adata, genes, n=50):
        from sklearn.decomposition import PCA
        Z = self._prep_fit(adata, genes)
        self.pca = PCA(n_components=n, random_state=0, svd_solver="randomized").fit(Z)
        return self.pca.transform(Z)

    def _pc(self, adata):
        return self.pca.transform(self._prep(adata))


class NearestCentroid(_PCA):
    name = "M2_centroid"

    def fit(self, adata, genes):
        P = self._fit_pca(adata, genes)
        y = adata.obs.target.to_numpy()
        self.classes = sorted(set(y))
        C = np.vstack([P[y == c].mean(0) for c in self.classes])
        self.C = C / np.linalg.norm(C, axis=1, keepdims=True)
        return self

    def predict(self, adata):
        P = self._pc(adata)
        P = P / np.maximum(np.linalg.norm(P, axis=1, keepdims=True), 1e-12)
        S = P @ self.C.T
        o = np.argsort(-S, 1)
        r = np.arange(len(S))
        return pd.DataFrame({"pred": np.array(self.classes)[o[:, 0]], "conf": S[r, o[:, 0]] - S[r, o[:, 1]]},
                            index=adata.obs_names)


class KNN(_PCA):
    name = "M3_knn"

    def __init__(self, k: int = 15):
        self.k = k

    def fit(self, adata, genes):
        from sklearn.neighbors import NearestNeighbors
        P = self._fit_pca(adata, genes)
        self.y = adata.obs.target.to_numpy()
        self.classes = sorted(set(self.y))
        self.nn = NearestNeighbors(n_neighbors=self.k, metric="cosine", algorithm="brute", n_jobs=4).fit(P)
        return self

    def predict(self, adata):
        _, ind = self.nn.kneighbors(self._pc(adata))
        votes = self.y[ind]
        V = np.column_stack([(votes == c).mean(1) for c in self.classes])
        best = V.argmax(1)
        out = pd.DataFrame({"pred": np.array(self.classes)[best], "conf": V.max(1)}, index=adata.obs_names)
        for j, c in enumerate(self.classes):
            out[f"p::{c}"] = V[:, j]
        return out


class Logistic(_Scaled):
    name = "M4_logistic"

    def __init__(self, C: float = 1.0):
        self.C = C

    def fit(self, adata, genes):
        from sklearn.linear_model import LogisticRegression
        Z = self._prep_fit(adata, genes)
        self.clf = LogisticRegression(C=self.C, max_iter=1000, solver="lbfgs", n_jobs=4, random_state=0)
        self.clf.fit(Z, adata.obs.target.to_numpy())
        self.classes = list(self.clf.classes_)
        return self

    def predict(self, adata):
        P = self.clf.predict_proba(self._prep(adata))
        out = pd.DataFrame({"pred": np.array(self.classes)[P.argmax(1)], "conf": P.max(1)}, index=adata.obs_names)
        for j, c in enumerate(self.classes):
            out[f"p::{c}"] = P[:, j]
        return out


class CellTypistRetrained:
    name = "M5_celltypist"

    def fit(self, adata, genes):
        import celltypist
        self.genes = list(genes)
        X = lognorm(adata[:, self.genes].X, adata.obs.total_counts_all)
        self.model = celltypist.train(X, labels=adata.obs.target.to_numpy(), genes=np.array(self.genes),
                                      check_expression=False, use_SGD=False, feature_selection=False, n_jobs=4)
        self.classes = list(self.model.cell_types)
        return self

    def predict(self, adata):
        import anndata as ad
        import celltypist
        X = lognorm(adata[:, self.genes].X, adata.obs.total_counts_all)
        q = ad.AnnData(X=X, obs=pd.DataFrame(index=adata.obs_names), var=pd.DataFrame(index=self.genes))
        res = celltypist.annotate(q, model=self.model, majority_voting=False)
        P = res.probability_matrix[self.classes].to_numpy()
        out = pd.DataFrame({"pred": np.array(self.classes)[P.argmax(1)], "conf": P.max(1)}, index=adata.obs_names)
        for j, c in enumerate(self.classes):
            out[f"p::{c}"] = P[:, j]
        return out


class ScanviTransfer:
    """scANVI reference model; per-query unlabelled scArches adaptation at predict time."""
    name = "M6_scanvi"

    def __init__(self, ref_epochs=100, scanvi_epochs=20, query_epochs=50):
        self.ref_epochs, self.scanvi_epochs, self.query_epochs = ref_epochs, scanvi_epochs, query_epochs

    def _ad(self, adata, labelled):
        import anndata as ad
        a = ad.AnnData(X=sp.csr_matrix(adata[:, self.genes].X, dtype=np.float32),
                       obs=pd.DataFrame(index=adata.obs_names), var=pd.DataFrame(index=self.genes))
        a.obs["batch"] = (adata.obs.study.astype(str) + "|" + adata.obs.donor_id.astype(str)).to_numpy()
        a.obs["label"] = adata.obs.target.astype(str).to_numpy() if labelled else "Unknown"
        return a

    def fit(self, adata, genes, workdir):
        import scvi
        import torch
        torch.set_num_threads(4)
        scvi.settings.seed = 0
        scvi.settings.num_threads = 4
        self.genes = list(genes)
        a = self._ad(adata, True)
        scvi.model.SCVI.setup_anndata(a, batch_key="batch", labels_key="label")
        vae = scvi.model.SCVI(a, n_latent=30, n_layers=2)
        vae.train(max_epochs=self.ref_epochs, accelerator="cpu", enable_progress_bar=False)
        lvae = scvi.model.SCANVI.from_scvi_model(vae, unlabeled_category="Unknown")
        lvae.train(max_epochs=self.scanvi_epochs, n_samples_per_label=100, accelerator="cpu",
                   enable_progress_bar=False)
        self.dir = str(workdir)
        lvae.save(self.dir, overwrite=True, save_anndata=True)
        self.classes = sorted(set(a.obs.label))
        return self

    def predict(self, adata):
        import scvi
        import torch
        torch.set_num_threads(4)
        scvi.settings.seed = 0
        q = self._ad(adata, False)
        scvi.model.SCANVI.prepare_query_anndata(q, self.dir)
        m = scvi.model.SCANVI.load_query_data(q, self.dir)
        m.train(max_epochs=self.query_epochs, plan_kwargs={"weight_decay": 0.0}, accelerator="cpu",
                enable_progress_bar=False)
        P = m.predict(soft=True)
        P = P[[c for c in P.columns if c != "Unknown"]]
        P = P.div(P.sum(1), axis=0)
        cls = list(P.columns)
        V = P.to_numpy()
        out = pd.DataFrame({"pred": np.array(cls)[V.argmax(1)], "conf": V.max(1)}, index=adata.obs_names)
        for j, c in enumerate(cls):
            out[f"p::{c}"] = V[:, j]
        return out


def save(obj, path):
    with open(path, "wb") as fh:
        pickle.dump(obj, fh)


def load(path):
    with open(path, "rb") as fh:
        return pickle.load(fh)

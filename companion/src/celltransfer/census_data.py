"""Bounded, provenance-recorded pulls from CELLxGENE Census (protocol section 2)."""
from __future__ import annotations

import shutil
from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd
import scipy.sparse as sp

CENSUS_VERSION = "2025-11-08"
SEED = 20261005
BASE_FILTER = "is_primary_data == True and disease == 'normal' and tissue_general == 'blood'"
OBS_COLS = ["soma_joinid", "dataset_id", "donor_id", "assay", "cell_type", "cell_type_ontology_term_id",
            "suspension_type", "sex", "development_stage"]
RARE = ["ASC", "pDC", "cDC", "MAIT", "gamma-delta T", "CD16 mono", "HSPC", "ILC", "platelet/MK", "erythroid"]


def free_gib(path: str | Path = ".") -> float:
    return shutil.disk_usage(path).free / 2**30


def guard(path: str | Path = ".", floor: float = 0.4, wait_s: int = 7200) -> None:
    """Block (polling every 30 s) until at least `floor` GiB is free; stop after `wait_s`."""
    import time
    waited = 0
    while free_gib(path) < floor:
        if waited == 0:
            print(f"disk guard: {free_gib(path):.2f} GiB free < {floor} GiB; waiting", flush=True)
        if waited >= wait_s:
            raise SystemExit(f"disk guard: still below {floor} GiB after {wait_s} s; stopping before writing")
        time.sleep(30)
        waited += 30


def read_obs(census, dataset_id: str) -> pd.DataFrame:
    obs = census["census_data"]["homo_sapiens"].obs
    vf = f"{BASE_FILTER} and dataset_id == '{dataset_id}'"
    df = obs.read(value_filter=vf, column_names=OBS_COLS).concat().to_pandas()
    for c in OBS_COLS[1:]:
        df[c] = df[c].astype(str)
    return df


def attach_labels(df: pd.DataFrame, label_map: pd.DataFrame) -> pd.DataFrame:
    m = label_map.set_index("cell_type_ontology_term_id")
    df = df.copy()
    df["label_status"] = df.cell_type_ontology_term_id.map(m.status).fillna("unknown")
    df["target"] = df.cell_type_ontology_term_id.map(m.target).where(df.label_status == "mapped")
    return df


def eligible_donors(df: pd.DataFrame, min_cells: int, mapped_only: bool) -> list[str]:
    d = df[df.label_status == "mapped"] if mapped_only else df
    vc = d.donor_id.value_counts()
    return sorted(vc[vc >= min_cells].index.tolist())


def pick_donors(donors: list[str], k: int, rng: np.random.Generator) -> list[str]:
    if len(donors) <= k:
        return donors
    return sorted(rng.choice(donors, size=k, replace=False).tolist())


def sample_reference(df: pd.DataFrame, rng: np.random.Generator, n_donors=12, per_class=150) -> pd.DataFrame:
    donors = pick_donors(eligible_donors(df, 300, mapped_only=True), n_donors, rng)
    d = df[(df.donor_id.isin(donors)) & (df.label_status == "mapped")]
    parts = []
    for (_, _), g in d.groupby(["donor_id", "target"], sort=True):
        take = g if len(g) <= per_class else g.iloc[np.sort(rng.choice(len(g), per_class, replace=False))]
        parts.append(take)
    out = pd.concat(parts)
    out["stratum"] = "reference"
    return out


def sample_query(df: pd.DataFrame, rng: np.random.Generator, n_donors=12, natural=600, topup=40) -> pd.DataFrame:
    donors = pick_donors(eligible_donors(df, 300, mapped_only=False), n_donors, rng)
    parts = []
    for donor in donors:
        g = df[df.donor_id == donor]
        nat = g if len(g) <= natural else g.iloc[np.sort(rng.choice(len(g), natural, replace=False))]
        nat = nat.assign(stratum="natural")
        parts.append(nat)
        rest = g[~g.soma_joinid.isin(nat.soma_joinid) & (g.label_status == "mapped")]
        for cls in RARE:
            r = rest[rest.target == cls]
            if len(r):
                take = r if len(r) <= topup else r.iloc[np.sort(rng.choice(len(r), topup, replace=False))]
                parts.append(take.assign(stratum="rare_topup"))
    return pd.concat(parts)


def sample_platform(df: pd.DataFrame, rng: np.random.Generator, n=1000) -> pd.DataFrame:
    s = df if len(df) <= n else df.iloc[np.sort(rng.choice(len(df), n, replace=False))]
    return s.assign(stratum="natural")


def fetch_counts(census, joinids: np.ndarray, var_joinids: np.ndarray) -> sp.csr_matrix:
    """Raw counts for the given cells x genes, rows in the order of `joinids`."""
    import cellxgene_census
    order = np.argsort(joinids)
    sorted_ids = joinids[order]
    a = cellxgene_census.get_anndata(census, organism="Homo sapiens", obs_coords=sorted_ids,
                                     var_coords=np.sort(var_joinids), column_names={"obs": ["soma_joinid"], "var": ["soma_joinid"]})
    # get_anndata returns rows/cols ordered by soma_joinid
    assert np.array_equal(a.obs.soma_joinid.to_numpy(), sorted_ids)
    X = sp.csr_matrix(a.X, dtype=np.float32)
    col_order = np.searchsorted(a.var.soma_joinid.to_numpy(), var_joinids)
    X = X[:, col_order]
    inv = np.empty_like(order)
    inv[order] = np.arange(len(order))
    return X[inv]


def gene_universe(census_var: pd.DataFrame, sctab_var: pd.DataFrame) -> pd.DataFrame:
    """scTab gene order with Census var joinids (-1 where absent)."""
    cv = census_var.assign(eid=census_var.feature_id.str.split(".").str[0]).drop_duplicates("eid").set_index("eid")
    g = sctab_var[["feature_id", "feature_name"]].copy()
    g["census_joinid"] = g.feature_id.map(cv.soma_joinid).fillna(-1).astype(int)
    g["census_name"] = g.feature_id.map(cv.feature_name)
    return g.reset_index(drop=True)


def to_anndata(X: sp.csr_matrix, obs: pd.DataFrame, genes: pd.DataFrame) -> ad.AnnData:
    obs = obs.copy()
    obs.index = pd.Index(obs.soma_joinid.astype(str).to_numpy(), name=None)
    var = genes.set_index("feature_id")
    return ad.AnnData(X=X, obs=obs, var=var)

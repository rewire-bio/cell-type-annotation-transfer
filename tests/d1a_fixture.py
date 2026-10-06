"""Build a synthetic scoring fixture (run with the pinned study venv python).

  d1a_fixture.py OUTDIR

Design (expected values asserted in test_scoring_numerical.py):
  K = [CD4 T, B, pDC, ASC, MAIT]; K_B = [CD4 T, B]  (REMOVED_B = pDC, ASC, MAIT)
  validation study V: 20 CD4 T + 20 B, all correct, conf linspace(0.5, 1.0)
  test study T, 4 donors:
    48 natural known (CD4 T/B), correct, conf 0.9
    10 natural neutrophil  (outside K)  conf 0.99  -> accepted
     7 topup   erythroid   (outside K)  conf 0.01  -> rejected
     6 natural pDC/ASC/MAIT (in K, removed in B) conf 0.99
     3 topup   pDC/ASC/MAIT                         conf 0.01
  Arm A / practical primary natural unknowns: 10 cells, false-accept@OPcov = 1.0
  all-strata secondary: 17 cells, false-accept = 10/17
  Arm B simulated unknowns, all strata: 9 cells, false-accept = 6/9
"""
import json
import sys
from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd

LIN = {"CD4 T": "T", "B": "B lineage", "pDC": "dendritic", "ASC": "B lineage", "MAIT": "T",
       "neutrophil": "granulocyte", "erythroid": "MK/erythroid"}


def main(out: Path):
    D = out / "data"
    D.mkdir(parents=True)
    json.dump({"K": ["CD4 T", "B", "pDC", "ASC", "MAIT"], "K_B": ["CD4 T", "B"]}, open(D / "features_and_classes.json", "w"))
    rows = []
    jid = 0

    def add(study, role, donor, stratum, target, pred, conf):
        nonlocal jid
        rows.append(dict(soma_joinid=jid, study=study, role=role, donor_id=donor, stratum=stratum,
                         label_status="mapped", target=target, assay="10x", pred=pred, conf=conf))
        jid += 1

    for i, c in enumerate(np.linspace(0.5, 1.0, 40)):
        t = "CD4 T" if i % 2 else "B"
        add("V", "validation", f"v{i % 3}", "natural", t, t, float(c))
    for i in range(48):
        t = "CD4 T" if i % 2 else "B"
        add("T", "test", f"d{i % 4}", "natural", t, t, 0.9)
    for i in range(10):
        add("T", "test", f"d{i % 4}", "natural", "neutrophil", "CD4 T", 0.99)
    for i in range(7):
        add("T", "test", f"d{i % 4}", "topup", "erythroid", "CD4 T", 0.01)
    for i, t in enumerate(["pDC", "ASC", "MAIT"] * 2):
        add("T", "test", f"d{i % 4}", "natural", t, "CD4 T", 0.99)
    for i, t in enumerate(["pDC", "ASC", "MAIT"]):
        add("T", "test", f"d{i % 4}", "topup", t, "CD4 T", 0.01)
    df = pd.DataFrame(rows)
    for study, g in df.groupby("study"):
        obs = g[["soma_joinid", "study", "role", "donor_id", "stratum", "label_status", "target", "assay"]].copy()
        obs.index = pd.Index(obs.soma_joinid.astype(str).to_numpy(), name="cell")
        for c in ("study", "role", "donor_id", "stratum", "label_status", "target", "assay"):
            obs[c] = obs[c].astype("category")
        ad.AnnData(X=np.zeros((len(obs), 1), np.float32), obs=obs).write_h5ad(D / f"query_{study}_F.h5ad")
        pr = g[["soma_joinid", "pred", "conf"]].reset_index(drop=True)
        for arm in ("A", "B"):
            md = out / f"arm{arm}" / "M4"
            md.mkdir(parents=True, exist_ok=True)
            pr.to_parquet(md / f"predictions_{study}.parquet")
        rel = pd.DataFrame({"soma_joinid": g.soma_joinid.to_numpy()})
        for pref in ("P1_celltypist", "P2_sctab"):
            rel[f"{pref}_target"] = g.pred.to_numpy()
            rel[f"{pref}_status"] = "mapped"
            rel[f"{pref}_lineage"] = g.pred.map(LIN).to_numpy()
            rel[f"{pref}_conf"] = g.conf.to_numpy()
        rel.to_parquet(D / f"released_predictions_{study}.parquet")


if __name__ == "__main__":
    main(Path(sys.argv[1]))

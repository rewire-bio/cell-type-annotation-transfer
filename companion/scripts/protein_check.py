"""Orthogonal protein check (protocol section 7).

  protein_check.py --workspace W --cite CITE_RUN --matched A=RUN_A --thresholds SCORE_RUN/thresholds_validation.csv --out RUN

Protein classes come from ADT only: per-cell CLR, then a 2-component Gaussian mixture per
antibody (positive = posterior of the higher-mean component > 0.5). A cell matching exactly
one gate gets that class; others are unresolved. Agreement is computed for RNA predictions
accepted at each method's validation OP-cov threshold.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

MARKERS = {"CD3": [r"^CD3(_|$|-)", r"^CD3E"], "CD4": [r"^CD4(_|$|-|\.)"], "CD8": [r"^CD8A?(_|$|-|\.)", r"^CD8a"],
           "CD14": [r"^CD14(_|$|-|\.)"], "CD16": [r"^CD16(_|$|-|\.)"], "CD19": [r"^CD19(_|$|-|\.)"],
           "CD20": [r"^CD20(_|$|-|\.)"], "CD56": [r"^CD56(_|$|-|\.)"]}


def find(cols, pats):
    hits = [c for c in cols if any(re.search(p, c, re.I) for p in pats)]
    return hits[0] if hits else None


def gate_cells(adt: pd.DataFrame, seed: int = 0):
    from sklearn.mixture import GaussianMixture
    ab = adt.drop(columns=["barcode"])
    L = np.log1p(ab.to_numpy(dtype=float))
    clr = L - L.mean(1, keepdims=True)
    clr = pd.DataFrame(clr, columns=ab.columns)
    pos, used = {}, {}
    for m, pats in MARKERS.items():
        c = find(list(ab.columns), pats)
        if c is None:
            continue
        x = clr[c].to_numpy().reshape(-1, 1)
        gm = GaussianMixture(2, random_state=seed).fit(x)
        hi = int(np.argmax(gm.means_.ravel()))
        pos[m] = gm.predict_proba(x)[:, hi] > 0.5
        used[m] = c
    if "CD19" not in pos and "CD20" in pos:
        pos["CD19"] = pos["CD20"]
        used["CD19"] = used["CD20"] + " (CD20 substitute)"
    n = len(adt)
    P = lambda m: pos.get(m)
    gates = {}
    def g(name, plus, minus):
        if any(P(m) is None for m in plus + minus):
            return
        v = np.ones(n, bool)
        for m in plus:
            v &= P(m)
        for m in minus:
            v &= ~P(m)
        gates[name] = v
    g("CD4 T", ["CD3", "CD4"], ["CD8"])
    g("CD8 T", ["CD3", "CD8"], ["CD4"])
    g("B", ["CD19"], ["CD3"])
    g("NK", ["CD56"], ["CD3", "CD19", "CD14"])
    g("CD14 mono", ["CD14"], ["CD3", "CD19", "CD56"])
    g("CD16 mono", ["CD16"], ["CD14", "CD3", "CD19", "CD56"])
    G = pd.DataFrame(gates)
    nhit = G.sum(1).to_numpy()
    cls = np.where(nhit == 1, G.idxmax(1).to_numpy(), None)
    return cls, used, list(gates)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--cite", required=True)
    ap.add_argument("--matched", nargs="+", required=True)
    ap.add_argument("--thresholds", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    C, OUT = Path(args.cite), Path(args.out)
    OUT.mkdir(parents=True, exist_ok=True)
    thr = pd.read_csv(args.thresholds)
    rows, gate_info = [], {}
    for adtf in sorted(C.glob("adt_*.parquet")):
        name = adtf.name[4:-8]
        adt = pd.read_parquet(adtf)
        cls, used, gates = gate_cells(adt)
        pd.DataFrame({"barcode": adt.barcode.to_numpy(), "protein_class": cls}).to_parquet(OUT / f"protein_classes_{name}.parquet", index=False)
        gate_info[name] = {"antibodies_used": used, "gates_available": gates, "cells": len(adt),
                           "resolved": int(pd.notna(cls).sum()),
                           "protein_class_counts": pd.Series(cls).value_counts().to_dict()}
        preds = {}
        rel = pd.read_parquet(C / f"released_predictions_{name}.parquet")
        preds["practical:P1"] = (rel.P1_celltypist_target.to_numpy(), rel.P1_celltypist_status.to_numpy(), rel.P1_celltypist_conf.to_numpy())
        preds["practical:P2"] = (rel.P2_sctab_target.to_numpy(), rel.P2_sctab_status.to_numpy(), rel.P2_sctab_conf.to_numpy())
        for spec in args.matched:
            arm, run = spec.split("=", 1)
            for mdir in sorted(Path(run).glob("M*")):
                f = mdir / f"predictions_{name}.parquet"
                if f.exists():
                    p = pd.read_parquet(f)
                    preds[f"{arm}:{mdir.name}"] = (p.pred.to_numpy(), np.array(["mapped"] * len(p)), p.conf.to_numpy())
        resolved = pd.notna(cls)
        for key, (pt, st, conf) in preds.items():
            arm, mid = key.split(":")
            t = thr[(thr.arm == arm) & (thr.method == mid)]
            tau = float(t.tau_cov.iloc[0]) if len(t) else np.nan
            acc = np.isin(st, ["mapped", "outside"]) & (conf >= tau)
            in_gate = resolved & acc
            agree = in_gate & (pt == cls)
            # restrict to RNA predictions within the six gateable classes for a fair denominator
            gateable = np.isin(pt, gates)
            rows.append({"file": name, "arm": arm, "method": mid, "tau_cov": tau,
                         "protein_resolved_cells": int(resolved.sum()),
                         "accepted_among_resolved": float(acc[resolved].mean()) if resolved.any() else np.nan,
                         "agreement_accepted": float(agree.sum() / in_gate.sum()) if in_gate.sum() else np.nan,
                         "agreement_accepted_gateable_preds": float((agree & gateable).sum() / (in_gate & gateable).sum()) if (in_gate & gateable).sum() else np.nan,
                         "n_accepted_resolved": int(in_gate.sum())})
    pd.DataFrame(rows).to_csv(OUT / "protein_agreement.csv", index=False)
    json.dump(gate_info, open(OUT / "gates.json", "w"), indent=1, default=str)
    print(pd.DataFrame(rows).to_string())


if __name__ == "__main__":
    main()

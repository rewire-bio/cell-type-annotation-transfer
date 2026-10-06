"""Score every method under the frozen protocol and write result tables.

  score_all.py --workspace W --data DATA_RUN --matched A=RUN_A B=RUN_B --out RUN [--reps 1000]

RUN_A / RUN_B hold one sub-directory per method (M1..M6) with predictions_<study>.parquet.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REMOVED_B = ["pDC", "ASC", "MAIT"]
NATURAL_SCOPE = "natural"
OBS_COLS = ["soma_joinid", "study", "role", "donor_id", "stratum", "label_status", "target", "assay"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--matched", nargs="+", required=True, help="ARM=RUN_DIR")
    ap.add_argument("--out", required=True)
    ap.add_argument("--reps", type=int, default=1000)
    ap.add_argument("--natural-unknown-scope", choices=["natural", "all"], default="natural",
                    help="D-1a default 'natural' (primary); 'all' reproduces the historical all-strata behaviour")
    args = ap.parse_args()
    global NATURAL_SCOPE
    NATURAL_SCOPE = args.natural_unknown_scope
    W, D, OUT = Path(args.workspace), Path(args.data), Path(args.out)
    OUT.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(W / "companion/src"))
    import anndata as ad
    from celltransfer import evaluate as E
    from celltransfer.ontology import LINEAGE

    meta = json.load(open(D / "features_and_classes.json"))
    obs = pd.concat([ad.read_h5ad(p, backed="r").obs[OBS_COLS].copy() for p in sorted(D.glob("query_*_F.h5ad"))])
    obs["soma_joinid"] = obs.soma_joinid.astype(np.int64)
    obs = obs.reset_index(drop=True)
    for c in ["study", "role", "donor_id", "stratum", "label_status", "assay"]:
        obs[c] = obs[c].astype(str)
    obs["target"] = obs.target.astype(object).where(obs.label_status == "mapped")
    key = obs.study + "|" + obs.soma_joinid.astype(str)

    tables: dict[tuple[str, str], pd.DataFrame] = {}
    # matched methods
    for spec in args.matched:
        arm, run = spec.split("=", 1)
        for mdir in sorted(Path(run).glob("M*")):
            parts = []
            for p in sorted(mdir.glob("predictions_*.parquet")):
                study = p.name[len("predictions_"):-len(".parquet")]
                d = pd.read_parquet(p).assign(study=study)
                parts.append(d)
            if not parts:
                continue
            d = pd.concat(parts)
            d.index = d.study + "|" + d.soma_joinid.astype(str)
            d = d.reindex(key.to_numpy())
            t = obs.copy()
            t["pred_target"] = d.pred.to_numpy()
            t["pred_status"] = np.where(pd.isna(d.pred.to_numpy()), "missing", "mapped")
            t["pred_lineage"] = pd.Series(d.pred.to_numpy()).map(LINEAGE).to_numpy()
            t["conf"] = d.conf.to_numpy()
            for c in d.columns:
                if c.startswith("p::"):
                    t[c] = d[c].to_numpy()
            tables[(arm, mdir.name.split("_")[0] if "_" in mdir.name else mdir.name)] = t
    # released models (practical track; scored against Arm A classes)
    rel = pd.concat([pd.read_parquet(p).assign(study=p.name[len("released_predictions_"):-len(".parquet")])
                     for p in sorted(D.glob("released_predictions_*.parquet"))])
    rel.index = rel.study + "|" + rel.soma_joinid.astype(str)
    rel = rel.reindex(key.to_numpy())
    for pref, mid in (("P1_celltypist", "P1"), ("P2_sctab", "P2")):
        t = obs.copy()
        t["pred_target"] = rel[f"{pref}_target"].to_numpy()
        t["pred_status"] = rel[f"{pref}_status"].to_numpy()
        t["pred_lineage"] = rel[f"{pref}_lineage"].to_numpy()
        t["conf"] = rel[f"{pref}_conf"].to_numpy()
        for c in rel.columns:
            if c.startswith(f"{pref}_p::"):
                t["p::" + c.split("::", 1)[1]] = rel[c].to_numpy()
        tables[("practical", mid)] = t

    secondary_rows = []
    rows, thr, perclass, calib, rc_rows, platform_rows, unknown_rows = [], [], [], [], [], [], []
    test_mask = (obs.role == "test").to_numpy()
    test_obs = obs[test_mask].reset_index(drop=True)
    Wb = E.donor_bootstrap_weights(test_obs, args.reps, 20261005)
    np.save(OUT / "bootstrap_weights.npy", Wb, allow_pickle=False)
    test_obs[["study", "donor_id", "soma_joinid"]].to_csv(OUT / "bootstrap_ids.csv", index=False)
    boot = {}
    for (arm, mid), t in sorted(tables.items()):
        K = meta["K_B"] if arm == "B" else meta["K"]
        val = t[(t.role == "validation").to_numpy() & E.scorable(t, K)]
        tau_cov, cap = E.threshold_coverage(val)
        tau_err = E.threshold_error(val)
        thr.append({"arm": arm, "method": mid, "tau_cov": tau_cov, "eligible_cap_validation": cap,
                    "tau_err": tau_err, "validation_cells": len(val),
                    "validation_coverage_at_tau_cov": E.coverage_error(val, tau_cov)["coverage"],
                    "validation_error_at_tau_cov": E.coverage_error(val, tau_cov)["accepted_error"]})
        tt = t[test_mask].reset_index(drop=True)
        sc = E.scorable(tt, K)
        nat = (tt.stratum == "natural").to_numpy()
        tn = tt[sc & nat]
        classes_f1 = [c for c in K if (tn.target == c).sum() >= 20]
        res = {"arm": arm, "method": mid, "test_scorable_natural": int(len(tn)), "f1_classes": len(classes_f1),
               "macro_f1_closed": E.macro_f1(tn, classes_f1),
               "coarser_fraction": float((tn.pred_status == "coarser").mean()),
               "outside_fraction": float((tn.pred_status == "outside").mean())}
        for op, tau in (("cov", tau_cov), ("err", tau_err)):
            for k, v in E.coverage_error(tn, tau).items():
                res[f"{k}@OP{op}"] = v
        res["aurc"], res["max_coverage"] = E.aurc(tn)
        res.update(E.risk_at(tn))
        # lineage-level accuracy (practical track reporting): accepted-or-coarser lineage agreement
        res["lineage_agreement_closed"] = float((tn.pred_lineage.to_numpy() == tn.target.map(LINEAGE).to_numpy()).mean())
        # unknowns
        if arm == "B":
            unk = tt[(tt.label_status == "mapped").to_numpy() & tt.target.isin(REMOVED_B).to_numpy()]
            kind = "simulated"
        else:
            # D-1a (protocol/amendments/2026-10-06-approved-resumption.md; protocol.md s6 "natural stratum
            # only"): primary natural unknowns for Arm A / practical are restricted to the natural stratum.
            unk_all = tt[(tt.label_status == "mapped").to_numpy() & ~tt.target.isin(K).to_numpy()]
            unk = unk_all[(unk_all.stratum == "natural").to_numpy()] if NATURAL_SCOPE == "natural" else unk_all
            kind = "natural" if NATURAL_SCOPE == "natural" else "natural-allstrata"
            secondary_rows.append({"arm": arm, "method": mid, "analysis": "secondary-sensitivity-all-strata",
                                   "unknown_cells": int(len(unk_all)),
                                   "unknown_false_accept@OPcov": E.acceptance(unk_all, tau_cov),
                                   "unknown_false_accept@OPerr": E.acceptance(unk_all, tau_err),
                                   "unknown_auroc": E.auroc_known_unknown(tn.conf.to_numpy(), unk_all.conf.to_numpy())})
        res[f"unknown_kind"] = kind
        res["unknown_cells"] = int(len(unk))
        res["unknown_false_accept@OPcov"] = E.acceptance(unk, tau_cov)
        res["unknown_false_accept@OPerr"] = E.acceptance(unk, tau_err)
        res["unknown_auroc"] = E.auroc_known_unknown(tn.conf.to_numpy(), unk.conf.to_numpy())
        for cls in sorted(unk.target.unique()):
            u = unk[unk.target == cls]
            pred_top = u.pred_target.astype(str).value_counts(normalize=True).head(3).round(3).to_dict()
            unknown_rows.append({"arm": arm, "method": mid, "kind": kind, "class": cls, "cells": len(u),
                                 "false_accept@OPcov": E.acceptance(u, tau_cov),
                                 "false_accept@OPerr": E.acceptance(u, tau_err), "top_predictions": json.dumps(pred_top)})
        cal = E.calibration(tn, K)
        calib.append({"arm": arm, "method": mid, "brier": cal["brier"], "ece": cal["ece"],
                      "reliability": json.dumps(cal.get("reliability", []))})
        pc = E.per_class(tn, tt[sc], K, tau_cov)
        pc.insert(0, "method", mid)
        pc.insert(0, "arm", arm)
        perclass.append(pc)
        rc = E.risk_coverage(tn)
        if len(rc):
            sel = rc.iloc[np.unique(np.linspace(0, len(rc) - 1, 200).astype(int))]
            rc_rows.append(sel.assign(arm=arm, method=mid))
        # per study
        for s in sorted(tn.study.unique()):
            ts = tn[tn.study == s]
            d = {"arm": arm, "method": mid, "study": s, "cells": len(ts),
                 "macro_f1_closed": E.macro_f1(ts, [c for c in classes_f1 if (ts.target == c).sum() >= 1])}
            for op, tau in (("cov", tau_cov), ("err", tau_err)):
                for k, v in E.coverage_error(ts, tau).items():
                    d[f"{k}@OP{op}"] = v
            rows.append(d)
        # platform
        tp = t[(t.role == "platform").to_numpy() & E.scorable(t, K)]
        for s in sorted(tp.study.unique()):
            ps = tp[tp.study == s]
            d = {"arm": arm, "method": mid, "platform": s, "assay": ps.assay.iloc[0], "cells": len(ps)}
            d.update(E.coverage_error(ps, tau_cov))
            d["closed_set_accuracy"] = float(E.is_correct(ps).mean())
            platform_rows.append(d)
        # bootstrap (aligned to test_obs rows)
        m_sc = sc & nat
        m_unk = np.zeros(len(tt), bool)
        m_unk[unk.index.to_numpy()] = True
        b = {k: [] for k in ["coverage@OPcov", "accepted_error@OPcov", "coverage@OPerr", "accepted_error@OPerr",
                             "macro_f1_closed", "unknown_false_accept@OPcov", "cross_lineage_rate@OPcov"]}
        for r in range(args.reps):
            w = Wb[r]
            ce = E.coverage_error(tn, tau_cov, w[m_sc])
            ce2 = E.coverage_error(tn, tau_err, w[m_sc])
            b["coverage@OPcov"].append(ce["coverage"])
            b["accepted_error@OPcov"].append(ce["accepted_error"])
            b["cross_lineage_rate@OPcov"].append(ce["cross_lineage_rate"])
            b["coverage@OPerr"].append(ce2["coverage"])
            b["accepted_error@OPerr"].append(ce2["accepted_error"])
            b["macro_f1_closed"].append(E.macro_f1(tn, classes_f1, w[m_sc]))
            b["unknown_false_accept@OPcov"].append(E.acceptance(unk, tau_cov, w[m_unk]) if len(unk) else np.nan)
        boot[(arm, mid)] = {k: np.array(v, dtype=float) for k, v in b.items()}
        res.update({f"{k}_ci95": [float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5))]
                    for k, v in boot[(arm, mid)].items()})
        res["main"] = True
        rows.append(res)

    pd.DataFrame([{ "arm": arm, "method": mid, "metric": metric, "nan_replicates": int(np.isnan(values).sum()) } for (arm, mid), metrics in boot.items() for metric, values in metrics.items()]).to_csv(OUT / "bootstrap_nan_counts.csv", index=False)

    # paired differences versus M4 within arm (matched) and versus Arm A M4 (practical)
    diffs = []
    for (arm, mid), b in boot.items():
        ref = ("A" if arm == "practical" else arm, "M4")
        if (arm, mid) == ref or ref not in boot:
            continue
        for k in b:
            d = b[k] - boot[ref][k]
            diffs.append({"arm": arm, "method": mid, "vs": f"{ref[0]}:M4", "metric": k,
                          "mean_diff": float(np.nanmean(d)), "ci95_lo": float(np.nanpercentile(d, 2.5)),
                          "ci95_hi": float(np.nanpercentile(d, 97.5))})
    allrows = pd.DataFrame(rows)
    allrows[allrows.get("main", False) == True].drop(columns=["main"]).to_csv(OUT / "summary_test.csv", index=False)
    allrows[allrows.get("main", False) != True].drop(columns=["main"], errors="ignore").to_csv(OUT / "per_study_test.csv", index=False)
    pd.DataFrame(thr).to_csv(OUT / "thresholds_validation.csv", index=False)
    pd.concat(perclass).to_csv(OUT / "per_class_test.csv", index=False)
    pd.DataFrame(calib).to_csv(OUT / "calibration_test.csv", index=False)
    pd.concat(rc_rows).to_csv(OUT / "risk_coverage_test.csv", index=False)
    pd.DataFrame(platform_rows).to_csv(OUT / "platform.csv", index=False)
    pd.DataFrame(unknown_rows).to_csv(OUT / "unknowns_test.csv", index=False)
    # Secondary, pre-specified sensitivity analysis (all strata incl. rare top-up cells); point estimates only.
    pd.DataFrame(secondary_rows).to_csv(OUT / "unknowns_allstrata_secondary.csv", index=False)
    json.dump({"natural_unknown_scope": NATURAL_SCOPE, "decision": "D-1a",
               "amendment": "protocol/amendments/2026-10-06-approved-resumption.md"},
              open(OUT / "scoring_scope.json", "w"), indent=1)
    pd.DataFrame(diffs).to_csv(OUT / "paired_differences_vs_M4.csv", index=False)
    counts = obs.groupby(["role", "study", "stratum", "label_status"]).size().rename("cells").reset_index()
    counts.to_csv(OUT / "cell_counts.csv", index=False)
    json.dump({"reps": args.reps, "seed": 20261005, "methods": sorted(f"{a}:{m}" for a, m in tables),
               "test_donors": int(test_obs.groupby("study").donor_id.nunique().sum())},
              open(OUT / "score_info.json", "w"), indent=1)
    print("done", len(tables), "method tables")


if __name__ == "__main__":
    main()

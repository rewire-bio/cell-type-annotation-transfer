"""Scoring under the frozen protocol (sections 5-6).

A *unified prediction table* has one row per query cell with columns:
  pred_target  target class or None
  pred_status  'mapped' | 'coarser' | 'outside'  (matched methods are always 'mapped')
  pred_lineage lineage group or None
  conf         confidence used for thresholding
  p::<class>   optional probabilities (for calibration); released models include p::other
and the cell metadata columns: study, role, donor_id, stratum, label_status, target.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .ontology import LINEAGE

COVERAGE_TARGET = 0.90
ERROR_TARGET = 0.05


def eligible(t: pd.DataFrame) -> np.ndarray:
    """Predictions that can be accepted at the target level (coarser never can)."""
    return t.pred_status.isin(["mapped", "outside"]).to_numpy()


def is_correct(t: pd.DataFrame) -> np.ndarray:
    return ((t.pred_status == "mapped") & (t.pred_target == t.target)).to_numpy()


def scorable(t: pd.DataFrame, K: list[str]) -> np.ndarray:
    return ((t.label_status == "mapped") & t.target.isin(K)).to_numpy()


# ---------------------------------------------------------------- thresholds (validation)
def threshold_coverage(v: pd.DataFrame, target=COVERAGE_TARGET) -> tuple[float, float]:
    """Return (tau, achievable_cap). Accepted = eligible & conf >= tau."""
    el = eligible(v)
    n = len(v)
    cap = el.mean() if n else 0.0
    conf = np.sort(v.conf.to_numpy()[el])[::-1]
    need = int(np.ceil(target * n))
    if need > len(conf) or len(conf) == 0:
        return -np.inf, float(cap)
    return float(conf[need - 1]), float(cap)


def threshold_error(v: pd.DataFrame, target=ERROR_TARGET) -> float | None:
    """Lowest threshold whose accepted error on validation is <= target (None if none)."""
    el = eligible(v)
    conf = v.conf.to_numpy()[el]
    corr = is_correct(v)[el]
    order = np.argsort(-conf, kind="stable")
    conf, corr = conf[order], corr[order]
    cum_err = np.cumsum(~corr) / np.arange(1, len(corr) + 1)
    # thresholds are distinct confidence values; evaluate at the last index of each tie block
    last = np.r_[conf[1:] != conf[:-1], True]
    ok = np.where(last & (cum_err <= target))[0]
    if len(ok) == 0:
        return None
    return float(conf[ok.max()])


# ---------------------------------------------------------------- weighted metrics
def _w(t, w):
    return np.ones(len(t)) if w is None else w


def coverage_error(t: pd.DataFrame, tau: float | None, w=None) -> dict:
    w = _w(t, w)
    if tau is None:
        return {"coverage": np.nan, "accepted_error": np.nan, "cross_lineage_share": np.nan,
                "cross_lineage_rate": np.nan}
    acc = eligible(t) & (t.conf.to_numpy() >= tau)
    cor = is_correct(t)
    wrong = acc & ~cor
    true_lin = t.target.map(LINEAGE).to_numpy()
    cross = wrong & (t.pred_lineage.to_numpy() != true_lin)
    W_acc = (w * acc).sum()
    W_wrong = (w * wrong).sum()
    return {"coverage": (w * acc).sum() / w.sum(),
            "accepted_error": W_wrong / W_acc if W_acc else np.nan,
            "cross_lineage_share": (w * cross).sum() / W_wrong if W_wrong else np.nan,
            "cross_lineage_rate": (w * cross).sum() / W_acc if W_acc else np.nan}


def macro_f1(t: pd.DataFrame, classes: list[str], w=None) -> float:
    from sklearn.metrics import f1_score
    y = t.target.to_numpy().astype(str)
    p = np.where(t.pred_status == "mapped", t.pred_target.astype(str), "__none__")
    return float(f1_score(y, p, labels=classes, average="macro", sample_weight=w, zero_division=0))


def acceptance(t: pd.DataFrame, tau: float | None, w=None) -> float:
    if tau is None:
        return np.nan
    w = _w(t, w)
    acc = eligible(t) & (t.conf.to_numpy() >= tau)
    return (w * acc).sum() / w.sum() if len(t) else np.nan


def auroc_known_unknown(known_conf, unknown_conf) -> float:
    from sklearn.metrics import roc_auc_score
    if len(known_conf) == 0 or len(unknown_conf) == 0:
        return np.nan
    y = np.r_[np.ones(len(known_conf)), np.zeros(len(unknown_conf))]
    s = np.r_[known_conf, unknown_conf]
    s = np.where(np.isfinite(s), s, -1e9)
    return float(roc_auc_score(y, s))


def risk_coverage(t: pd.DataFrame) -> pd.DataFrame:
    """Risk-coverage points over all scorable cells (non-eligible predictions never accepted)."""
    el = eligible(t)
    conf = t.conf.to_numpy()[el]
    corr = is_correct(t)[el]
    order = np.argsort(-conf, kind="stable")
    corr = corr[order]
    n = len(t)
    k = np.arange(1, len(corr) + 1)
    return pd.DataFrame({"coverage": k / n, "risk": np.cumsum(~corr) / k})


def aurc(t: pd.DataFrame) -> tuple[float, float]:
    rc = risk_coverage(t)
    if rc.empty:
        return np.nan, 0.0
    return float(rc.risk.mean() * rc.coverage.iloc[-1]), float(rc.coverage.iloc[-1])


def risk_at(t: pd.DataFrame, levels=(0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0)) -> dict:
    rc = risk_coverage(t)
    out = {}
    for c in levels:
        r = rc[rc.coverage >= c - 1e-12]
        out[f"risk@{c:.2f}"] = float(r.risk.iloc[0]) if len(r) else np.nan
    return out


def calibration(t: pd.DataFrame, classes: list[str], bins: int = 15) -> dict:
    cols = [c for c in t.columns if c.startswith("p::")]
    if not cols:
        return {"brier": np.nan, "ece": np.nan}
    P = t[cols].to_numpy(dtype=np.float64)
    names = [c[3:] for c in cols]
    s = P.sum(1, keepdims=True)
    s[s == 0] = 1.0
    P = P / s
    Y = np.zeros_like(P)
    idx = {n: j for j, n in enumerate(names)}
    for i, y in enumerate(t.target.to_numpy()):
        Y[i, idx[y] if y in idx else idx.get("other", 0)] = 1.0
    brier = float(((P - Y) ** 2).sum(1).mean())
    conf = t.conf.to_numpy()
    corr = is_correct(t)
    edges = np.linspace(0, 1, bins + 1)
    ece = 0.0
    rows = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi) if lo > 0 else (conf >= lo) & (conf <= hi)
        if m.sum():
            ece += m.mean() * abs(corr[m].mean() - conf[m].mean())
            rows.append((lo, hi, int(m.sum()), float(conf[m].mean()), float(corr[m].mean())))
    return {"brier": brier, "ece": float(ece), "reliability": rows}


def per_class(t_nat: pd.DataFrame, t_all: pd.DataFrame, classes: list[str], tau) -> pd.DataFrame:
    rows = []
    for c in classes:
        a = t_all[t_all.target == c]
        n_nat = (t_nat.target == c).sum()
        pred_c = (t_nat.pred_status == "mapped") & (t_nat.pred_target == c)
        prec = ((t_nat.target == c) & pred_c).sum() / pred_c.sum() if pred_c.sum() else np.nan
        rec = is_correct(a).mean() if len(a) else np.nan
        acc_rec = (is_correct(a) & eligible(a) & (a.conf.to_numpy() >= (tau if tau is not None else np.inf))).mean() if len(a) else np.nan
        rows.append({"class": c, "n_natural": int(n_nat), "n_all_strata": int(len(a)),
                     "precision_natural": prec, "recall_closed_set": rec, "recall_accepted_OPcov": acc_rec})
    return pd.DataFrame(rows)


def donor_bootstrap_weights(t: pd.DataFrame, reps: int, seed: int) -> np.ndarray:
    """reps x cells matrix of donor multiplicities, resampling donors within each study."""
    rng = np.random.default_rng(seed)
    key = (t.study.astype(str) + "|" + t.donor_id.astype(str)).to_numpy()
    W = np.zeros((reps, len(t)), dtype=np.float32)
    groups = {s: np.unique(key[t.study.to_numpy() == s]) for s in t.study.unique()}
    pos = {k: np.where(key == k)[0] for k in np.unique(key)}
    for r in range(reps):
        for s, donors in groups.items():
            draw = rng.choice(donors, size=len(donors), replace=True)
            u, c = np.unique(draw, return_counts=True)
            for d, n in zip(u, c):
                W[r, pos[d]] += n
    return W

"""Receipt-backed charts from a score run (static PNG + SVG, light surface, CSV twins).

  make_charts.py --score SC01 --runs T01 T02 [--protein PC01] [--timing timing.csv] --out RUN
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

SURFACE, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
S1, S2, S3 = "#2a78d6", "#eb6834", "#1baf7a"   # categorical slots 1-3 (validated all-pairs)
GREY = "#c3c2b7"
NAMES = {"M1": "Marker rule", "M2": "Nearest centroid", "M3": "PCA + kNN", "M4": "Logistic regression",
         "M5": "CellTypist (retrained)", "M6": "scANVI", "P1": "CellTypist Immune_All_Low (released)",
         "P2": "scTab run5 (released)"}
FOOT = "Source: rewire.it annotation-transfer benchmark, run {run}; 4 held-out studies, donor bootstrap 95% intervals."


def style(ax):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(AXIS)
        ax.spines[s].set_linewidth(0.8)
    ax.tick_params(colors=INK2, labelsize=9)
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def save(fig, out, name, foot):
    fig.text(0.01, 0.005, foot, fontsize=7.5, color=MUTED, ha="left", va="bottom")
    fig.patch.set_facecolor(SURFACE)
    for ext in ("png", "svg"):
        fig.savefig(out / f"{name}.{ext}", dpi=200, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)


def label(arm, m):
    return NAMES[m] + ("" if arm in ("A", "practical") else " (Arm B)")


def chart_operating_point(s, out, run):
    d = s[s.arm.isin(["A", "practical"])].copy()
    d["name"] = [label(a, m) for a, m in zip(d.arm, d.method)]
    d = d.sort_values("accepted_error@OPcov", ascending=False)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), sharey=True)
    for ax, col, title in ((axes[0], "accepted_error@OPcov", "Error among accepted cells"),
                           (axes[1], "coverage@OPcov", "Share of cells accepted (coverage)")):
        style(ax)
        y = np.arange(len(d))
        lo = np.array([v[0] for v in d[f"{col}_ci95"]])
        hi = np.array([v[1] for v in d[f"{col}_ci95"]])
        val = d[col].to_numpy()
        col_c = [S2 if a == "practical" else S1 for a in d.arm]
        ax.hlines(y, lo, hi, color=col_c, linewidth=2)
        ax.scatter(val, y, s=40, color=col_c, edgecolor=SURFACE, linewidth=2, zorder=3)
        ax.set_yticks(y, d.name, color=INK)
        ax.set_title(title, fontsize=10, color=INK, loc="left")
        ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    axes[1].axvline(0.9, color=AXIS, linewidth=1)
    handles = [plt.Line2D([], [], marker="o", color=S1, linestyle="", label="Matched track (same reference)"),
               plt.Line2D([], [], marker="o", color=S2, linestyle="", label="Practical track (released model)")]
    fig.legend(handles=handles, loc="upper center", ncol=2, frameon=False, fontsize=9, bbox_to_anchor=(0.55, 1.04))
    fig.suptitle("Threshold set on validation studies to accept 90% of cells; scored on held-out studies",
                 fontsize=10.5, color=INK, x=0.01, ha="left", y=1.1)
    save(fig, out, "01-operating-point-error-coverage", FOOT.format(run=run))
    d[["arm", "method", "name", "accepted_error@OPcov", "accepted_error@OPcov_ci95", "coverage@OPcov",
       "coverage@OPcov_ci95"]].to_csv(out / "01-operating-point-error-coverage.csv", index=False)


def chart_risk_coverage(rc, out, run, highlight=("M4", "M6", "P2")):
    d = rc[rc.arm.isin(["A", "practical"])]
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    style(ax)
    colours = dict(zip(highlight, (S1, S3, S2)))
    for (arm, m), g in d.groupby(["arm", "method"]):
        if m in colours:
            continue
        ax.plot(g.coverage, g.risk, color=GREY, linewidth=1.2)
    for m in highlight:
        g = d[d.method == m]
        if len(g):
            ax.plot(g.coverage, g.risk, color=colours[m], linewidth=2, label=label(g.arm.iloc[0], m))
            ax.annotate(NAMES[m], (g.coverage.iloc[-1], g.risk.iloc[-1]), xytext=(4, 0), textcoords="offset points",
                        fontsize=8.5, color=INK2, va="center")
    ax.plot([], [], color=GREY, linewidth=1.2, label="Other methods")
    ax.set_xlabel("Coverage (share of scorable cells accepted)", color=INK2)
    ax.set_ylabel("Error among accepted cells", color=INK2)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    ax.set_title("Risk-coverage on held-out studies (cells sorted by each method's confidence)",
                 fontsize=10.5, color=INK, loc="left")
    save(fig, out, "02-risk-coverage", "Source: rewire.it annotation-transfer benchmark, run " + run +
         "; natural-composition cells, 4 held-out studies. Released-model curves stop where only coarser labels remain.")
    d.to_csv(out / "02-risk-coverage.csv", index=False)


def chart_unknowns(u, out, run):
    d = u[(u.arm == "B") & (u.kind == "simulated")].copy()
    if d.empty:
        return
    classes = sorted(d["class"].unique())
    fig, axes = plt.subplots(1, len(classes), figsize=(3.4 * len(classes), 3.8), sharex=True, sharey=True)
    axes = np.atleast_1d(axes)
    order = [m for m in ("M1", "M2", "M3", "M4", "M5", "M6") if m in set(d.method)]
    for ax, c in zip(axes, classes):
        style(ax)
        g = d[d["class"] == c].set_index("method").reindex(order)
        y = np.arange(len(order))
        ax.barh(y, g["false_accept@OPcov"], height=0.55, color=S1)
        ax.set_yticks(y, [NAMES[m] for m in order], color=INK)
        ax.set_title(f"{c} removed (n={int(g.cells.max())})", fontsize=9.5, color=INK, loc="left")
        ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
        ax.set_xlim(0, 1)
    fig.suptitle("Unknown cells wrongly given a known label at the 90%-coverage threshold",
                 fontsize=10.5, color=INK, x=0.01, ha="left", y=1.03)
    save(fig, out, "03-unknown-false-acceptance", "Source: rewire.it benchmark, run " + run +
         "; Arm B reference with every pDC, ASC and MAIT cell removed; test cells of those types.")
    d.to_csv(out / "03-unknown-false-acceptance.csv", index=False)


def chart_perclass(pc, out, run):
    d = pc[pc.arm.isin(["A", "practical"])].copy()
    d["name"] = [label(a, m) for a, m in zip(d.arm, d.method)]
    M = d.pivot_table(index="name", columns="class", values="recall_closed_set")
    M = M.loc[:, sorted(M.columns, key=lambda c: -d[d["class"] == c].n_natural.max())]
    fig, ax = plt.subplots(figsize=(10, 4.4))
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("blue", ["#f0efec", "#9ec5f4", "#3987e5", "#1c5cab", "#0d366b"])
    im = ax.imshow(M.to_numpy(), cmap=cmap, vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(M.shape[1]), M.columns, rotation=40, ha="right", fontsize=8.5, color=INK)
    ax.set_yticks(range(M.shape[0]), M.index, fontsize=8.5, color=INK)
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            v = M.iat[i, j]
            if np.isfinite(v):
                ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=6.5, color="white" if v > 0.6 else INK)
    for s in ax.spines.values():
        s.set_visible(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.025)
    cb.ax.tick_params(labelsize=8, colors=INK2)
    cb.outline.set_visible(False)
    ax.set_title("Per-class recall without abstention (columns ordered from common to rare)", fontsize=10.5,
                 color=INK, loc="left")
    save(fig, out, "04-per-class-recall", "Source: rewire.it benchmark, run " + run +
         "; natural plus rare top-up cells from 4 held-out studies.")
    M.to_csv(out / "04-per-class-recall.csv")


def chart_resources(t, out, run):
    if t is None or t.empty:
        return
    t = t.sort_values("wall_s")
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), sharey=True)
    for ax, col, title in ((axes[0], "wall_s", "Wall-clock time, fit + predict (s)"),
                           (axes[1], "peak_gb", "Peak memory of the larger stage (GB)")):
        style(ax)
        y = np.arange(len(t))
        ax.barh(y, t[col], height=0.55, color=[S2 if m.startswith("P") else S1 for m in t.method])
        ax.set_yticks(y, [NAMES[m] for m in t.method], color=INK)
        ax.set_title(title, fontsize=10, color=INK, loc="left")
        for yi, v in zip(y, t[col]):
            ax.text(v, yi, f" {v:,.0f}" if col == "wall_s" else f" {v:.1f}", va="center", fontsize=8, color=INK2)
    save(fig, out, "05-runtime-memory", "Source: /usr/bin/time -l receipts, run " + run +
         "; Apple M4, 4 threads, CPU only; one timed run per stage.")
    t.to_csv(out / "05-runtime-memory.csv", index=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--score", required=True)
    ap.add_argument("--timing", default=None)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    S, OUT = Path(args.score), Path(args.out)
    OUT.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": ["Helvetica Neue", "Arial", "DejaVu Sans"], "svg.fonttype": "none"})
    s = pd.read_csv(S / "summary_test.csv")
    for c in [c for c in s.columns if c.endswith("_ci95")]:
        s[c] = s[c].apply(lambda v: json.loads(v) if isinstance(v, str) else v)
    run = S.name
    chart_operating_point(s, OUT, run)
    chart_risk_coverage(pd.read_csv(S / "risk_coverage_test.csv"), OUT, run)
    chart_unknowns(pd.read_csv(S / "unknowns_test.csv"), OUT, run)
    chart_perclass(pd.read_csv(S / "per_class_test.csv"), OUT, run)
    chart_resources(pd.read_csv(args.timing) if args.timing else None, OUT, run)
    print("charts written to", OUT)


if __name__ == "__main__":
    main()

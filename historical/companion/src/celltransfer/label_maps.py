"""Frozen maps from released-model output labels to the target level.

Each released label maps to (status, target, lineage):
  mapped   -> a single target class (fine-level prediction)
  coarser  -> above the target level; unresolved at the target level, lineage may be known
  outside  -> a cell type outside the target set; an accepted outside prediction is a
              fine-level error
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from .ontology import LINEAGE, ancestors, lineage_of, map_term, parse_obo

# CellTypist Immune_All_Low v2 (98 labels). Frozen by hand from label names and the
# CellTypist encyclopedia descriptions; see evidence/protocol.md section 4.
_CT = {
    "CD4 T": ["Tcm/Naive helper T cells", "Tem/Effector helper T cells", "Tem/Effector helper T cells PD1+",
              "Regulatory T cells", "Treg(diff)", "Type 1 helper T cells", "Type 17 helper T cells",
              "Follicular helper T cells", "Memory CD4+ cytotoxic T cells"],
    "CD8 T": ["Tcm/Naive cytotoxic T cells", "Tem/Temra cytotoxic T cells", "Tem/Trm cytotoxic T cells",
              "Trm cytotoxic T cells"],
    "MAIT": ["MAIT cells"],
    "gamma-delta T": ["gamma-delta T cells", "CRTAM+ gamma-delta T cells", "Cycling gamma-delta T cells"],
    "NK": ["CD16+ NK cells", "CD16- NK cells", "NK cells", "Transitional NK", "Cycling NK cells"],
    "B": ["B cells", "Naive B cells", "Memory B cells", "Age-associated B cells", "Transitional B cells",
          "Follicular B cells", "Germinal center B cells", "Proliferative germinal center B cells", "Cycling B cells"],
    "ASC": ["Plasma cells", "Plasmablasts"],
    "CD14 mono": ["Classical monocytes"],
    "CD16 mono": ["Non-classical monocytes"],
    "cDC": ["DC1", "DC2", "DC3", "Migratory DCs"],
    "pDC": ["pDC"],
    "platelet/MK": ["Megakaryocytes/platelets"],
    "HSPC": ["HSC/MPP", "CMP", "GMP", "MEMP", "ELP", "Megakaryocyte-erythroid-mast cell progenitor",
             "Neutrophil-myeloid progenitor"],
    "erythroid": ["Erythrocytes", "Early erythroid", "Mid erythroid", "Late erythroid"],
    "ILC": ["ILC", "ILC1", "ILC2", "ILC3", "ILC precursor"],
    "neutrophil": ["Neutrophils"],
}
_CT_COARSER = {"Monocytes": "monocyte", "Cycling monocytes": "monocyte", "DC": "dendritic",
               "Cycling DCs": "dendritic", "Cycling T cells": "T", "Granulocytes": "granulocyte",
               "MNP": None, "Mono-mac": None}
# Everything else in Immune_All_Low is "outside"; lineage where unambiguous.
_CT_OUTSIDE_LINEAGE = {"NKT cells": "T", "T(agonist)": "T", "CD8a/a": "T", "CD8a/b(entry)": "T",
                       "Double-negative thymocytes": "T", "Double-positive thymocytes": "T", "ETP": "progenitor",
                       "Early lymphoid/T lymphoid": "progenitor", "pDC precursor": "dendritic",
                       "DC precursor": "dendritic", "Transitional DC": "dendritic", "Monocyte precursor": "monocyte",
                       "Early MK": "MK/erythroid", "Megakaryocyte precursor": "MK/erythroid",
                       "Pre-pro-B cells": "B lineage", "Pro-B cells": "B lineage", "Large pre-B cells": "B lineage",
                       "Small pre-B cells": "B lineage", "Myelocytes": "granulocyte", "Promyelocytes": "granulocyte"}


def celltypist_map(labels: list[str]) -> pd.DataFrame:
    inv = {lab: t for t, labs in _CT.items() for lab in labs}
    rows = []
    for lab in labels:
        if lab in inv:
            rows.append((lab, "mapped", inv[lab], LINEAGE[inv[lab]]))
        elif lab in _CT_COARSER:
            rows.append((lab, "coarser", None, _CT_COARSER[lab]))
        else:
            rows.append((lab, "outside", None, _CT_OUTSIDE_LINEAGE.get(lab)))
    return pd.DataFrame(rows, columns=["label", "status", "target", "lineage"])


def _name_index(obo: str | Path) -> dict[str, str]:
    terms = parse_obo(obo)
    idx = {t.name: i for i, t in terms.items() if not t.obsolete}
    text = Path(obo).read_text(encoding="utf-8")
    for block in text.split("\n\n"):
        if not block.startswith("[Term]"):
            continue
        m = re.search(r"^id: (CL:\d+)", block, re.M)
        if m:
            for s in re.findall(r'^synonym: "([^"]+)" EXACT', block, re.M):
                idx.setdefault(s, m.group(1))
    return idx


def ontology_label_map(labels: list[str], obo: str | Path) -> pd.DataFrame:
    """Map Cell Ontology label names (e.g. scTab outputs) by exact name, then EXACT synonym."""
    terms = parse_obo(obo)
    idx = _name_index(obo)
    rows = []
    for lab in labels:
        cid = idx.get(lab)
        if cid is None:
            rows.append((lab, None, "outside", None, None))
            continue
        status, target = map_term(terms, cid)
        if status == "mapped":
            rows.append((lab, cid, "mapped", target, LINEAGE[target]))
        elif status == "coarser":
            rows.append((lab, cid, "coarser", None, lineage_of(terms, cid)))
        else:
            rows.append((lab, cid, "outside", None, lineage_of(terms, cid)))
    return pd.DataFrame(rows, columns=["label", "cl_id", "status", "target", "lineage"])

"""Cell Ontology handling: parse a pinned cl-basic.obo and map terms to a fixed target level.

The target level is a fixed list of Cell Ontology classes. A source term maps to a target
class when the target is an is_a ancestor (or the term itself). A term that maps to more
than one target is "ambiguous"; a term above every target (for example "T cell") is
"coarser"; a term under none of them is "outside". Only "mapped" terms are used for
training or fine-level scoring.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

# Fixed target level (frozen in evidence/protocol.md). Order defines class indices.
TARGETS: dict[str, list[str]] = {
    "CD4 T": ["CL:0000624"],            # CD4-positive, alpha-beta T cell
    "CD8 T": ["CL:0000625"],            # CD8-positive, alpha-beta T cell
    "MAIT": ["CL:0000940"],             # mucosal invariant T cell
    "gamma-delta T": ["CL:0000798"],    # gamma-delta T cell
    "NK": ["CL:0000623"],               # natural killer cell
    "B": ["CL:0000236"],                # B cell
    "ASC": ["CL:0000946"],              # antibody secreting cell (plasmablast, plasma cell)
    "CD14 mono": ["CL:0001054"],        # CD14-positive monocyte
    "CD16 mono": ["CL:0002396"],        # CD14-low, CD16-positive monocyte
    "cDC": ["CL:0000990"],              # conventional dendritic cell
    "pDC": ["CL:0000784"],              # plasmacytoid dendritic cell
    "platelet/MK": ["CL:0000233", "CL:0000556"],  # platelet, megakaryocyte
    "HSPC": ["CL:0008001"],             # hematopoietic precursor cell
    "erythroid": ["CL:0000232", "CL:0000764"],    # erythrocyte, erythroid lineage cell
    "ILC": ["CL:0001065"],              # innate lymphoid cell
    "neutrophil": ["CL:0000775"],       # neutrophil
}

# Frozen manual overrides (documented in evidence/protocol.md). In cl-basic v2025-07-30,
# "classical monocyte" and "non-classical monocyte" are siblings of the CD14/CD16 classes
# rather than descendants, and "CD141-positive myeloid dendritic cell" has an is_a link to
# "plasmacytoid dendritic cell". Plasmablasts are both "mature B cell" and "antibody
# secreting cell"; they are scored as ASC.
OVERRIDES: dict[str, str] = {
    "CL:0000860": "CD14 mono",   # classical monocyte
    "CL:0000875": "CD16 mono",   # non-classical monocyte
    "CL:0002394": "cDC",         # CD141-positive myeloid dendritic cell (cDC1)
}
PRECEDENCE: list[tuple[str, str]] = [("ASC", "B")]  # (wins, loses) when both are ancestors

# Fixed lineage groups for the hierarchy-aware error definition.
LINEAGE: dict[str, str] = {
    "CD4 T": "T", "CD8 T": "T", "MAIT": "T", "gamma-delta T": "T",
    "NK": "NK/ILC", "ILC": "NK/ILC",
    "B": "B lineage", "ASC": "B lineage",
    "CD14 mono": "monocyte", "CD16 mono": "monocyte",
    "cDC": "dendritic", "pDC": "dendritic",
    "platelet/MK": "MK/erythroid", "erythroid": "MK/erythroid",
    "HSPC": "progenitor",
    "neutrophil": "granulocyte",
}

# Lineage anchors used only for predictions that are coarser than, or outside, the target
# level (practical-track released labels). First matching anchor wins, in this order.
LINEAGE_ANCHORS: list[tuple[str, str]] = [
    ("CL:0000084", "T"), ("CL:0001065", "NK/ILC"), ("CL:0000945", "B lineage"),
    ("CL:0000576", "monocyte"), ("CL:0000451", "dendritic"), ("CL:0000233", "MK/erythroid"),
    ("CL:0000556", "MK/erythroid"), ("CL:0000764", "MK/erythroid"), ("CL:0000232", "MK/erythroid"),
    ("CL:0008001", "progenitor"), ("CL:0000094", "granulocyte"),
]


def lineage_of(terms: dict[str, "Term"], tid: str) -> str | None:
    anc = ancestors(terms, tid)
    for anchor, lin in LINEAGE_ANCHORS:
        if anchor in anc:
            return lin
    return None


@dataclass
class Term:
    id: str
    name: str
    parents: list[str]
    obsolete: bool = False


def parse_obo(path: str | Path) -> dict[str, Term]:
    terms: dict[str, Term] = {}
    cur: dict | None = None
    in_term = False

    def flush():
        if cur and cur.get("id", "").startswith("CL:"):
            terms[cur["id"]] = Term(cur["id"], cur.get("name", ""), cur.get("is_a", []), cur.get("obsolete", False))

    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line.startswith("["):
                flush()
                in_term = line == "[Term]"
                cur = {"is_a": []} if in_term else None
                continue
            if not in_term or cur is None or ": " not in line:
                continue
            key, val = line.split(": ", 1)
            if key == "id":
                cur["id"] = val.strip()
            elif key == "name":
                cur["name"] = val.strip()
            elif key == "is_a":
                cur["is_a"].append(val.split("!")[0].strip().split(" ")[0])
            elif key == "is_obsolete" and val.strip() == "true":
                cur["obsolete"] = True
    flush()
    return terms


def ancestors(terms: dict[str, Term], tid: str) -> set[str]:
    seen: set[str] = set()
    stack = [tid]
    while stack:
        t = stack.pop()
        if t in seen:
            continue
        seen.add(t)
        if t in terms:
            stack.extend(terms[t].parents)
    return seen


def map_term(terms: dict[str, Term], tid: str) -> tuple[str, str | None]:
    """Return (status, target) where status is mapped/ambiguous/coarser/outside/unknown."""
    if tid not in terms:
        return "unknown", None
    if tid in OVERRIDES:
        return "mapped", OVERRIDES[tid]
    anc = ancestors(terms, tid)
    hits = [name for name, ids in TARGETS.items() if any(i in anc for i in ids)]
    # keep the deepest targets: drop a hit whose term is an ancestor of another hit's term
    deep = []
    for h in hits:
        others = [i for o in hits if o != h for i in TARGETS[o]]
        if not any(set(TARGETS[h]) & ancestors(terms, i) for i in others):
            deep.append(h)
    hits = deep
    for win, lose in PRECEDENCE:
        if win in hits and lose in hits:
            hits.remove(lose)
    if len(hits) == 1:
        return "mapped", hits[0]
    if len(hits) > 1:
        return "ambiguous", "|".join(hits)
    # coarser: some descendant of the term maps to a target class (e.g. "T cell",
    # "naive T cell", "regulatory T cell"), so the term does not fix the target class.
    for other in terms:
        if other != tid and tid in ancestors(terms, other):
            o_anc = ancestors(terms, other)
            if other in OVERRIDES or any(i in o_anc for ids in TARGETS.values() for i in ids):
                return "coarser", None
    return "outside", None


def mapping_table(obo: str | Path, term_ids: list[str]) -> list[dict]:
    terms = parse_obo(obo)
    out = []
    for tid in sorted(set(term_ids)):
        status, target = map_term(terms, tid)
        out.append({"cell_type_ontology_term_id": tid,
                    "name": terms[tid].name if tid in terms else "",
                    "status": status, "target": target,
                    "lineage": LINEAGE.get(target) if status == "mapped" else None})
    return out


if __name__ == "__main__":
    import sys
    obo, ids_json = sys.argv[1], sys.argv[2]
    print(json.dumps(mapping_table(obo, json.load(open(ids_json))), indent=1))

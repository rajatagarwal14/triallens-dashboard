"""
Disease-progression ontology (v2, OPTIONAL).

Loads the JSON entries under `backend/data/ontology/` that `import_dossier.py`
writes from Claude Science `indication-dossier` runs, and exposes the one
question the cohort engine needs to ask:

    are these two conditions in the same disease family?

Why that matters: the v1 basket rule counts any condition that isn't the primary
indication as "foreign", so a trial recruiting Myelofibrosis + Polycythemia Vera
+ Essential Thrombocythemia is labelled a basket. Clinically it is not — those
are stages/siblings on one myeloproliferative continuum. A true basket mixes
unrelated families (myeloid + solid tumour).

With no ontology files present this module is inert (`loaded()` is False) and the
caller keeps the v1 behaviour exactly. Nothing here reaches the network.
"""
from __future__ import annotations

import functools
import json
import pathlib

_DIR = pathlib.Path(__file__).resolve().parent.parent / "data" / "ontology"


@functools.lru_cache(maxsize=1)
def _index() -> dict:
    """{alias_or_name(lower) -> node}, plus parent links. Cached per process."""
    nodes: dict[str, dict] = {}
    alias_to_name: dict[str, str] = {}
    if _DIR.is_dir():
        for p in sorted(_DIR.glob("*.json")):
            try:
                e = json.loads(p.read_text())
            except json.JSONDecodeError:
                continue
            name = (e.get("indication") or "").strip()
            if not name:
                continue
            nodes[name.lower()] = e
            alias_to_name[name.lower()] = name.lower()
            for a in (e.get("aliases") or []):
                if a and a.strip():
                    alias_to_name[a.strip().lower()] = name.lower()
    return {"nodes": nodes, "alias": alias_to_name}


def loaded() -> bool:
    return bool(_index()["nodes"])


def resolve(term: str) -> str | None:
    """Map a free-text condition string to a canonical node name.

    Exact alias hit first, then substring containment so CT.gov strings like
    'Post-PV Myelofibrosis' still resolve to the 'Myelofibrosis' node.
    """
    if not term:
        return None
    t = term.strip().lower()
    idx = _index()["alias"]
    if t in idx:
        return idx[t]
    for alias, canonical in idx.items():
        if len(alias) >= 4 and alias in t:
            return canonical
    return None


def family_root(term: str) -> str | None:
    """Walk `parent` links to the top of the chain. Returns a canonical name."""
    name = resolve(term)
    if not name:
        return None
    nodes = _index()["nodes"]
    seen: set[str] = set()
    while name and name not in seen:
        seen.add(name)
        parent = (nodes.get(name) or {}).get("parent")
        if not parent:
            return name
        nxt = resolve(parent) or parent.strip().lower()
        if nxt == name:
            return name
        name = nxt
    return name


def same_family(a: str, b: str) -> bool:
    """True only when both terms resolve AND share a family root."""
    ra, rb = family_root(a), family_root(b)
    return bool(ra and rb and ra == rb)


def reset_cache() -> None:
    _index.cache_clear()

"""Curation store for extracted drivers — Neo4j edition.

Delegates to the shared dual-mode store (`graphrag_neo4j.store`), same
governance as before: extracted drivers land in a *staging* state; a
human approves or rejects them before the analyst may cite them.
State lives in `data/graph_approval.json` (the shared single source of
truth); in Neo4j mode the property is also written to the database.

Public API unchanged: load_approval / save_approval / is_citable /
set_approval.
"""
from __future__ import annotations

from graphrag_neo4j.store import APPROVAL_PATHS, get_store as _get_shared

APPROVAL_PATH = APPROVAL_PATHS["cost"]


def _store():
    return _get_shared("cost", prefer_neo4j=False)


def load_approval() -> dict[str, bool]:
    return _store().load_approval()


def save_approval(state: dict[str, bool]) -> None:
    _store().save_approval(state)


def set_approval(entity_id: str, approved: bool) -> None:
    _store().set_approval(entity_id, approved)


def is_citable(driver_id: str, node: dict) -> bool:
    return _store().is_citable(driver_id, node)


def get_store():
    """The active (Neo4j-backed or local) store for the cost domain (prefers Neo4j)."""
    return _get_shared("cost")

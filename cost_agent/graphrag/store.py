"""Curation store for extracted drivers — Neo4j edition.

Thin facade over the shared dual-mode store (`graphrag_neo4j.store`),
same governance as before: extracted drivers land in a *staging* state;
a human approves or rejects them before the analyst may cite them.
State lives in `data/graph_approval.json`; in Neo4j mode the property
is also written to the database.

Public API unchanged: load_approval / save_approval / is_citable /
set_approval / get_store.
"""
from __future__ import annotations

from graphrag_neo4j.store import DomainStore

_STORE = DomainStore("cost")

APPROVAL_PATH = _STORE.approval_path


def load_approval() -> dict[str, bool]:
    return _STORE.load_approval()


def save_approval(state: dict[str, bool]) -> None:
    _STORE.save_approval(state)


def set_approval(entity_id: str, approved: bool) -> None:
    _STORE.set_approval(entity_id, approved)


def is_citable(driver_id: str, node: dict) -> bool:
    return _STORE.is_citable(driver_id, node)


def get_store():
    """The active (Neo4j-backed or local) store for the cost domain."""
    return _STORE.get_store()

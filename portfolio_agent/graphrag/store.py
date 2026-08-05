"""Curation store for portfolio-journey lineage drivers — Neo4j edition.

Thin facade over the shared dual-mode store (`graphrag_neo4j.store`):
Neo4j when a server is reachable, in-memory networkx otherwise. Approval
state lives in `data/portfolio_graph_approval.json`.

Public API unchanged: load_approval / save_approval / is_citable /
set_approval / get_store.
"""
from __future__ import annotations

from graphrag_neo4j.store import DomainStore

_STORE = DomainStore("portfolio")

APPROVAL_PATH = _STORE.approval_path


def load_approval() -> dict[str, bool]:
    return _STORE.load_approval()


def save_approval(state: dict[str, bool]) -> None:
    _STORE.save_approval(state)


def set_approval(entity_id: str, approved: bool) -> None:
    _STORE.set_approval(entity_id, approved)


def is_citable(signal_id: str, node: dict) -> bool:
    return _STORE.is_citable(signal_id, node)


def get_store():
    """The active (Neo4j-backed or local) store for the portfolio domain."""
    return _STORE.get_store()

"""Curation store for portfolio-journey lineage drivers — Neo4j edition.

Same shape and governance as cost_agent/graphrag/store.py, now backed
by the shared dual-mode store (`graphrag_neo4j.store`): Neo4j when a
server is reachable, in-memory networkx otherwise. Approval state lives
in `data/portfolio_graph_approval.json`.

Public API unchanged: load_approval / save_approval / is_citable /
set_approval.
"""
from __future__ import annotations

from graphrag_neo4j.store import APPROVAL_PATHS, get_store as _get_shared

APPROVAL_PATH = APPROVAL_PATHS["portfolio"]


def _store():
    return _get_shared("portfolio", prefer_neo4j=False)


def load_approval() -> dict[str, bool]:
    return _store().load_approval()


def save_approval(state: dict[str, bool]) -> None:
    _store().save_approval(state)


def set_approval(entity_id: str, approved: bool) -> None:
    _store().set_approval(entity_id, approved)


def is_citable(signal_id: str, node: dict) -> bool:
    return _store().is_citable(signal_id, node)


def get_store():
    """The active (Neo4j-backed or local) store for the portfolio domain (prefers Neo4j)."""
    return _get_shared("portfolio")

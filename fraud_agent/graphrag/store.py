"""Curation store for fraud-intelligence graph entities — Neo4j edition.

Delegates to the shared dual-mode store (`graphrag_neo4j.store`):

  - Neo4j mode:   the synthetic graph lives in a real database; every
                  read is genuine Cypher; curation toggles are written
                  both to the JSON approval file and to node properties
                  in Neo4j.
  - Fallback mode: the same query API is served from an in-memory
                  networkx graph with identical semantics (offline
                  reproducible evals, same as the mock-LLM philosophy).

The public API is unchanged, so the investigator's tools and the
GraphRAG tab keep working exactly as before:
    load_approval / save_approval / is_citable / set_approval
"""
from __future__ import annotations

from graphrag_neo4j.store import APPROVAL_PATHS, get_store as _get_shared

APPROVAL_PATH = APPROVAL_PATHS["fraud"]


def _store():
    return _get_shared("fraud", prefer_neo4j=False)


def load_approval() -> dict[str, bool]:
    return _store().load_approval()


def save_approval(state: dict[str, bool]) -> None:
    _store().save_approval(state)


def set_approval(entity_id: str, approved: bool) -> None:
    _store().set_approval(entity_id, approved)


def is_citable(entity_id: str, node: dict | None = None) -> bool:
    return _store().is_citable(entity_id, node)


def get_store():
    """The active (Neo4j-backed or local) store for the fraud domain (prefers Neo4j)."""
    return _get_shared("fraud")

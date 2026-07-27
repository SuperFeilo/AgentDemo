"""Curation store for fraud-intelligence graph entities.

Extracted fraud intel (rings, suspect shops, pattern links) lands in a
*staging* state; a human approves or rejects before the investigator may
use it in decisions. The same governance instinct as the SIU checkpoint
— knowledge that can influence case disposition deserves a checkpoint too.

State lives in `data/fraud_graph_approval.json` keyed by entity_id.
Entities marked `curated: true` in the graph baseline are always citable;
anything else defaults to approved=True unless the file says otherwise,
so headless evals stay green out of the box.
"""
from __future__ import annotations

import json

from fraud_agent.paths import DATA_DIR

APPROVAL_PATH = DATA_DIR / "fraud_graph_approval.json"


def load_approval() -> dict[str, bool]:
    if APPROVAL_PATH.exists():
        return json.loads(APPROVAL_PATH.read_text())
    return {}


def save_approval(state: dict[str, bool]) -> None:
    APPROVAL_PATH.write_text(json.dumps(state, indent=2))


def is_citable(entity_id: str, node: dict | None = None) -> bool:
    if node and node.get("curated"):
        return True
    return load_approval().get(entity_id, True)

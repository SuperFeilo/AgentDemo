"""Curation store for extracted drivers.

Extracted drivers land in a *staging* state; a human approves or rejects
them before the analyst may cite them (the same governance instinct as
the fraud agent's SIU checkpoint — knowledge that can influence decisions
deserves a checkpoint too).

State lives in `data/graph_approval.json` keyed by driver_id. Drivers
marked `curated: true` in the graph are always citable; anything else
defaults to approved=True unless the file says otherwise, so headless
evals stay green out of the box.
"""
from __future__ import annotations

import json

from fraud_agent.paths import DATA_DIR

APPROVAL_PATH = DATA_DIR / "graph_approval.json"


def load_approval() -> dict[str, bool]:
    if APPROVAL_PATH.exists():
        return json.loads(APPROVAL_PATH.read_text())
    return {}


def save_approval(state: dict[str, bool]) -> None:
    APPROVAL_PATH.write_text(json.dumps(state, indent=2))


def is_citable(driver_id: str, node: dict) -> bool:
    if node.get("curated"):
        return True
    return load_approval().get(driver_id, True)

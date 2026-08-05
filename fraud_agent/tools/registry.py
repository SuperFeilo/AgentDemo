"""ANATOMY COMPONENT: TOOL CALLS (1/2 — the registry)

Tools are the agent's only way to touch the world. Each tool is a plain
Python function plus a schema (name, description, arguments) — exactly
what an LLM function-calling API would receive. The brain chooses a
tool by name; the harness executes it through `call_tool`, which is the
single choke point where errors are caught and counted.

Every tool also declares three pieces of operational metadata:

  origin       — where its data comes from: persistent_db,
                 knowledge_graph, model_brain, or side_effect. Powers
                 the dossier's data-lineage view.
  autonomy     — "auto" (harness executes immediately, read-only) or
                 "gated" (harness pauses for a human checkpoint first —
                 the AUTONOMY GATE, generalized from the SIU escalation).
  cost_units   — the price-sheet cost of one call (analog of API token
                 pricing). The harness meters it against the goal's
                 cost budget (COST & OPERATIONAL CONTROL).
"""
from __future__ import annotations

from typing import Callable

_REGISTRY: dict[str, dict] = {}


def tool(name: str, description: str, args: dict[str, str], *,
         origin: str = "persistent_db", autonomy: str = "auto",
         cost_units: int = 1):
    """Decorator: register a function as an agent tool with a schema."""
    def wrap(fn: Callable):
        _REGISTRY[name] = {
            "name": name, "description": description, "args": args,
            "origin": origin, "autonomy": autonomy,
            "cost_units": cost_units, "fn": fn,
        }
        return fn
    return wrap


def tool_meta(name: str) -> dict:
    return _REGISTRY[name]


def call_tool(name: str, **kwargs):
    """The one and only way tools are executed."""
    if name not in _REGISTRY:
        raise KeyError(f"Unknown tool: {name}")
    return _REGISTRY[name]["fn"](**kwargs)

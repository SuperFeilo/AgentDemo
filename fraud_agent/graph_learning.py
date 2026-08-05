"""ANATOMY COMPONENT: GRAPH-WEIGHT LEARNING — shared core (cost + portfolio)

Both the cost analyst and the portfolio journey analyst learn the same
way: their knowledge lives in graph edge weights (driver -> metric,
signal -> outcome), and when next-quarter actuals arrive they score each
edge — did the world move the way this edge claims?

  - validates=true  -> edge predicted reality: small reinforcement
  - validates=false -> edge contradicted reality: decay the weight

Proposals are written out and applied to the domain graph ONLY after
human approval — knowledge that influences decisions gets a checkpoint,
always. `cost_agent/learning.py` and `portfolio_agent/learning.py` are
thin wrappers around this core (was duplicated 2x).
"""
from __future__ import annotations

import json

from fraud_agent.paths import DATA_DIR  # noqa: F401  (documents the home)


def analyze_graph(outcomes_path, graph_path, relation: str,
                  target_key: str, reinforce: float, cap: float,
                  decay: float, floor: float) -> dict:
    """Score every `relation` edge against the outcome actuals."""
    outcomes = {o["driver_id"]: o
                for o in json.loads(outcomes_path.read_text())}
    graph = json.loads(graph_path.read_text())
    proposals = []
    for edge in graph["edges"]:
        if edge["relation"] != relation:
            continue
        outcome = outcomes.get(edge["a"])
        if not outcome:
            continue
        current = edge["weight"]
        if outcome["validates"]:
            proposed = min(cap, round(current + reinforce, 2))
            rationale = f"validated: {outcome['note']}"
        else:
            proposed = max(floor, round(current * decay, 2))
            rationale = f"CONTRADICTED: {outcome['note']}"
        if proposed != current:
            proposals.append({
                "driver_id": edge["a"], target_key: edge["b"],
                "region": edge.get("region"), "coverage": edge.get("coverage"),
                "current_weight": current, "proposed_weight": proposed,
                "rationale": rationale})
    return {"proposals": proposals, "graph_path": str(graph_path)}


def apply_graph_proposals(report: dict, graph_path, proposals_path,
                          target_key: str) -> dict:
    """Apply approved proposals to the graph + persist the proposal log."""
    graph = json.loads(graph_path.read_text())
    by_key = {(p["driver_id"], p[target_key], p["region"], p["coverage"]): p
              for p in report["proposals"]}
    changed = 0
    for edge in graph["edges"]:
        key = (edge["a"], edge["b"], edge.get("region"),
               edge.get("coverage"))
        if key in by_key:
            edge["weight"] = by_key[key]["proposed_weight"]
            changed += 1
    graph_path.write_text(json.dumps(graph, indent=2))
    proposals_path.write_text(json.dumps(report["proposals"], indent=2))
    return {"changed": changed}

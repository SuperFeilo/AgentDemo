"""ANATOMY COMPONENT: CONTINUOUS LEARNING LOOP (cost analyst)

The analyst's knowledge lives in graph edge weights (driver -> metric).
When next-quarter actuals arrive (data/outcomes_nextq.json), we can
score each driver: did the world move the way this edge claims?

  - validates=true  -> driver predicted reality: small reinforcement
  - validates=false -> driver contradicted reality: decay the weight

Proposals are written to data/cost_weight_proposals.json and applied to
data/cost_entities.json only after human approval — knowledge that
influences decisions gets a checkpoint, always.

Usage:
    python -m cost_agent.learning            # analyse + propose
    python -m cost_agent.learning --apply    # apply to the graph
"""
from __future__ import annotations

import json
import sys

from fraud_agent.paths import DATA_DIR

OUTCOMES_PATH = DATA_DIR / "outcomes_nextq.json"
GRAPH_PATH = DATA_DIR / "cost_entities.json"
PROPOSALS_PATH = DATA_DIR / "cost_weight_proposals.json"

REINFORCE = 0.05   # weight bump for validated drivers (cap 0.75)
DECAY = 0.7        # multiplier for contradicted drivers (floor 0.10)


def analyze() -> dict:
    outcomes = {o["driver_id"]: o
                for o in json.loads(OUTCOMES_PATH.read_text())}
    graph = json.loads(GRAPH_PATH.read_text())
    proposals = []
    for edge in graph["edges"]:
        if edge["relation"] != "IMPACTS":
            continue
        driver = edge["a"]
        outcome = outcomes.get(driver)
        if not outcome:
            continue
        current = edge["weight"]
        if outcome["validates"]:
            proposed = min(0.75, round(current + REINFORCE, 2))
            rationale = f"validated: {outcome['note']}"
        else:
            proposed = max(0.10, round(current * DECAY, 2))
            rationale = f"CONTRADICTED: {outcome['note']}"
        if proposed != current:
            proposals.append({"driver_id": driver, "metric": edge["b"],
                              "region": edge["region"],
                              "coverage": edge["coverage"],
                              "current_weight": current,
                              "proposed_weight": proposed,
                              "rationale": rationale})
    return {"proposals": proposals, "graph_path": str(GRAPH_PATH)}


def apply_proposals(report: dict) -> dict:
    graph = json.loads(GRAPH_PATH.read_text())
    by_key = {(p["driver_id"], p["metric"], p["region"], p["coverage"]): p
              for p in report["proposals"]}
    changed = 0
    for edge in graph["edges"]:
        key = (edge["a"], edge["b"], edge["region"], edge["coverage"])
        if key in by_key:
            edge["weight"] = by_key[key]["proposed_weight"]
            changed += 1
    GRAPH_PATH.write_text(json.dumps(graph, indent=2))
    PROPOSALS_PATH.write_text(json.dumps(report["proposals"], indent=2))
    return {"changed": changed}


if __name__ == "__main__":
    rep = analyze()
    print("\nDriver validation vs next-quarter actuals\n" + "=" * 56)
    for p in rep["proposals"]:
        print(f"  {p['driver_id']:20s} -> {p['metric']:10s} "
              f"weight {p['current_weight']} -> {p['proposed_weight']}  "
              f"{p['rationale']}")
    if "--apply" in sys.argv:
        print(f"\n{apply_proposals(rep)['changed']} edge(s) updated")
    else:
        print("\n(dry run — pass --apply, or approve in the UI, to write)")

"""ANATOMY COMPONENT: CONTINUOUS LEARNING LOOP (portfolio agent)

The journey analyst's lives in graph edge weights (signal -> outcome).
When next-quarter outcomes arrive
(`data/portfolio_outcomes_nextq.json`), we score each signal: did the
world move the way this edge claims?

  - validates=true  -> signal predicted reality: small reinforcement
  - validates=false -> signal contradicted reality: decay the weight

Proposals are written to `data/portfolio_weight_proposals.json` and
applied to `data/portfolio_entities.json` only after human approval —
knowledge that influences decisions gets a checkpoint, always. Same
governance instinct as the cost analyst.

Usage:
    python -m portfolio_agent.learning            # analyse + propose
    python -m portfolio_agent.learning --apply   # apply to the graph
"""
from __future__ import annotations

import json
import sys

from fraud_agent.paths import DATA_DIR

OUTCOMES_PATH = DATA_DIR / "portfolio_outcomes_nextq.json"
GRAPH_PATH = DATA_DIR / "portfolio_entities.json"
PROPOSALS_PATH = DATA_DIR / "portfolio_weight_proposals.json"

REINFORCE = 0.05
DECAY = 0.7


def analyze() -> dict:
    outcomes = {o["driver_id"]: o for o in
                json.loads(OUTCOMES_PATH.read_text())}
    graph = json.loads(GRAPH_PATH.read_text())
    proposals = []
    for edge in graph["edges"]:
        if edge["relation"] != "PREDISPOSES":
            continue
        driver = edge["a"]
        outcome = outcomes.get(driver)
        if not outcome:
            continue
        current = edge["weight"]
        if outcome["validates"]:
            proposed = min(0.80, round(current + REINFORCE, 2))
            rationale = f"validated: {outcome['note']}"
        else:
            proposed = max(0.15, round(current * DECAY, 2))
            rationale = f"CONTRADICTED: {outcome['note']}"
        if proposed != current:
            proposals.append({
                "driver_id": driver, "outcome": edge["b"],
                "region": edge.get("region"), "coverage": edge.get("coverage"),
                "current_weight": current, "proposed_weight": proposed,
                "rationale": rationale,
            })
    return {"proposals": proposals, "graph_path": str(GRAPH_PATH)}


def apply_proposals(report: dict) -> dict:
    graph = json.loads(GRAPH_PATH.read_text())
    by_key = {(p["driver_id"], p["outcome"], p["region"], p["coverage"]): p
              for p in report["proposals"]}
    changed = 0
    for edge in graph["edges"]:
        key = (edge["a"], edge["b"], edge.get("region"),
               edge.get("coverage"))
        if key in by_key:
            edge["weight"] = by_key[key]["proposed_weight"]
            changed += 1
    GRAPH_PATH.write_text(json.dumps(graph, indent=2))
    PROPOSALS_PATH.write_text(json.dumps(report["proposals"], indent=2))
    return {"changed": changed}


if __name__ == "__main__":
    rep = analyze()
    print("\nSignal validation vs next-quarter outcomes\n" + "=" * 60)
    for p in rep["proposals"]:
        print(f"  {p['driver_id']:30s} -> {p['outcome']:22s} "
              f"weight {p['current_weight']} -> {p['proposed_weight']}  "
              f"{p['rationale']}")
    if "--apply" in sys.argv:
        print(f"\n{apply_proposals(rep)['changed']} edge(s) updated")
    else:
        print("\n(dry run — pass --apply, or approve in the UI, to write)")
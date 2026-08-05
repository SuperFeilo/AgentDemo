"""ANATOMY COMPONENT: CONTINUOUS LEARNING LOOP (cost analyst)

The analyst's knowledge lives in graph edge weights (driver -> metric).
When next-quarter actuals arrive (data/outcomes_nextq.json), we score
each driver: did the world move the way this edge claims?

  - validates=true  -> driver predicted reality: small reinforcement
  - validates=false -> driver contradicted reality: decay the weight

Proposals are written to data/cost_weight_proposals.json and applied to
data/cost_entities.json only after human approval — knowledge that
influences decisions gets a checkpoint, always.

Thin wrapper around the shared core in `fraud_agent/graph_learning.py`
(identical logic to the portfolio agent, different relation/caps/files).

Usage:
    python -m cost_agent.learning            # analyse + propose
    python -m cost_agent.learning --apply    # apply to the graph
"""
from __future__ import annotations

import sys

from fraud_agent.graph_learning import analyze_graph, apply_graph_proposals
from fraud_agent.paths import DATA_DIR

OUTCOMES_PATH = DATA_DIR / "outcomes_nextq.json"
GRAPH_PATH = DATA_DIR / "cost_entities.json"
PROPOSALS_PATH = DATA_DIR / "cost_weight_proposals.json"

REINFORCE = 0.05   # weight bump for validated drivers (cap 0.75)
DECAY = 0.7        # multiplier for contradicted drivers (floor 0.10)


def analyze() -> dict:
    return analyze_graph(OUTCOMES_PATH, GRAPH_PATH,
                         relation="IMPACTS", target_key="metric",
                         reinforce=REINFORCE, cap=0.75,
                         decay=DECAY, floor=0.10)


def apply_proposals(report: dict) -> dict:
    return apply_graph_proposals(report, GRAPH_PATH, PROPOSALS_PATH,
                                 target_key="metric")


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

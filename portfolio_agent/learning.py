"""ANATOMY COMPONENT: CONTINUOUS LEARNING LOOP (portfolio agent)

The journey analyst's knowledge lives in graph edge weights (signal ->
outcome). When next-quarter outcomes arrive
(`data/portfolio_outcomes_nextq.json`), we score each signal: did the
world move the way this edge claims?

  - validates=true  -> signal predicted reality: small reinforcement
  - validates=false -> signal contradicted reality: decay the weight

Proposals are written to `data/portfolio_weight_proposals.json` and
applied to `data/portfolio_entities.json` only after human approval —
knowledge that influences decisions gets a checkpoint, always. Same
governance instinct as the cost analyst.

Thin wrapper around the shared core in `fraud_agent/graph_learning.py`.

Usage:
    python -m portfolio_agent.learning            # analyse + propose
    python -m portfolio_agent.learning --apply   # apply to the graph
"""
from __future__ import annotations

import sys

from fraud_agent.graph_learning import analyze_graph, apply_graph_proposals
from fraud_agent.paths import DATA_DIR

OUTCOMES_PATH = DATA_DIR / "portfolio_outcomes_nextq.json"
GRAPH_PATH = DATA_DIR / "portfolio_entities.json"
PROPOSALS_PATH = DATA_DIR / "portfolio_weight_proposals.json"

REINFORCE = 0.05
DECAY = 0.7


def analyze() -> dict:
    return analyze_graph(OUTCOMES_PATH, GRAPH_PATH,
                         relation="PREDISPOSES", target_key="outcome",
                         reinforce=REINFORCE, cap=0.80,
                         decay=DECAY, floor=0.15)


def apply_proposals(report: dict) -> dict:
    return apply_graph_proposals(report, GRAPH_PATH, PROPOSALS_PATH,
                                 target_key="outcome")


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

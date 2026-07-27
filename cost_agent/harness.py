"""Wiring: the Cost Trend Analyst on the shared harness.

Compare with FraudHarness — identical three lines of wiring, different
trio plugged in. That is the whole point of the harness abstraction.
"""
from __future__ import annotations

from fraud_agent.harness import Harness


class CostHarness(Harness):
    def __init__(self) -> None:
        import cost_agent.tools.cost_tools  # noqa: F401 — registers tools
        from cost_agent.brain.cost_brain import CostAnalystBrain
        from cost_agent.loop import cost_loop
        from cost_agent.planner import build_cost_plan

        plan = build_cost_plan()
        super().__init__(plan, CostAnalystBrain(plan), cost_loop)

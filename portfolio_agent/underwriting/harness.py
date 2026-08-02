"""Wiring: Underwriting Quality Agent on the shared harness."""
from __future__ import annotations

import portfolio_agent.underwriting.tools  # noqa: F401 — registers tools
from fraud_agent.harness import Harness


class UnderwritingHarness(Harness):
    def __init__(self) -> None:
        from portfolio_agent.underwriting.brain import UnderwritingBrain
        from portfolio_agent.underwriting.loop import underwriting_loop
        from portfolio_agent.underwriting.planner import build_underwriting_plan

        plan = build_underwriting_plan()
        super().__init__(plan, UnderwritingBrain(plan), underwriting_loop,
                         agent_name="underwriting")
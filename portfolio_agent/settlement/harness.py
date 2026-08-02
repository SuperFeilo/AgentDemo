"""Wiring: Settlement Quality Agent on the shared harness."""
from __future__ import annotations

import portfolio_agent.settlement.tools  # noqa: F401 — registers tools
from fraud_agent.harness import Harness


class SettlementHarness(Harness):
    def __init__(self) -> None:
        from portfolio_agent.settlement.brain import SettlementBrain
        from portfolio_agent.settlement.loop import settlement_loop
        from portfolio_agent.settlement.planner import build_settlement_plan

        plan = build_settlement_plan()
        super().__init__(plan, SettlementBrain(plan), settlement_loop,
                         agent_name="settlement")
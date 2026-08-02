"""Wiring: Portfolio Journey Analyst (Assembly / Reflection)."""
from __future__ import annotations

import portfolio_agent.submissions.tools   # noqa: F401 — register tools
import portfolio_agent.underwriting.tools # noqa: F401
import portfolio_agent.settlement.tools    # noqa: F401
import portfolio_agent.assembly.tools      # noqa: F401
from fraud_agent.harness import Harness


class PortfolioHarness(Harness):
    def __init__(self) -> None:
        from portfolio_agent.assembly.brain import ReflectionBrain
        from portfolio_agent.assembly.loop import portfolio_loop
        from portfolio_agent.assembly.planner import build_portfolio_plan

        plan = build_portfolio_plan()
        super().__init__(plan, ReflectionBrain(plan), portfolio_loop,
                         agent_name="portfolio")
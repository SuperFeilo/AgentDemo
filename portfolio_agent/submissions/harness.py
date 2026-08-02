"""Wiring: Submissions Quality Agent on the shared harness."""
from __future__ import annotations

from pathlib import Path

from fraud_agent.harness import Harness

# suppress unused-import — registers tools at import time
import portfolio_agent.submissions.tools  # noqa: F401


class SubmissionsHarness(Harness):
    def __init__(self) -> None:
        from portfolio_agent.submissions.brain import SubmissionsBrain
        from portfolio_agent.submissions.loop import submissions_loop
        from portfolio_agent.submissions.planner import build_submissions_plan

        plan = build_submissions_plan()
        super().__init__(plan, SubmissionsBrain(plan), submissions_loop,
                         agent_name="submissions")
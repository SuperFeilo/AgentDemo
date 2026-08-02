"""ANATOMY COMPONENT: PLAN (agent #3a — Submissions Quality Agent)

Same planner contract as the other agents: read the goal file, load the
named skill playbooks, emit ordered steps. The plan for one submission:
catalog -> load -> summarize_completeness -> note_scan -> history_broker
-> reflect -> compose.
"""
from __future__ import annotations

from pathlib import Path

from fraud_agent.planner import PlanStep
from portfolio_agent._common import build_port_plan

SKILLS_DIR = Path(__file__).resolve().parent.parent.parent / "skills_portfolio"


def build_submissions_plan() -> "Plan":  # noqa: F821 (str typehint)
    steps = [
        PlanStep("consult_catalog", "Consult semantic layer before querying "
                 "(skill: submission_quality).",
                 skill="submission_quality", tool="submission_catalog"),
        PlanStep("load_submission", "Load the submission record itself "
                 "(skill: submission_quality).",
                 skill="submission_quality", tool="submission_lookup"),
        PlanStep("summarize_completeness", "Get the broker's completeness "
                 "and conversion profile from the warehouse "
                 "(skill: submission_quality).",
                 skill="submission_quality", tool="submission_summary"),
        PlanStep("note_scan", "MOCK-LLM scan of UW notes attached to the "
                 "submission for hedging phrasing (skill: submission_quality).",
                 skill="submission_quality", tool="submission_note_scan"),
        PlanStep("history_broker", "SQL over the warehouse for prior binds "
                 "and overrides in this broker/class segment "
                 "(skill: submission_quality).",
                 skill="submission_quality", tool="submission_history_sql"),
        PlanStep("reflect", "Self-check: re-derive completeness rate and "
                 "override density before composing (skill: verification).",
                 skill="verification"),
        PlanStep("compose", "Compose the quality verdict under the citation "
                 "policy (skill: citation_policy).",
                 skill="citation_policy"),
    ]
    return build_port_plan("submissions", steps, SKILLS_DIR)
"""ANATOMY COMPONENT: PLAN (agent #3b — Underwriting Quality Agent)"""
from __future__ import annotations

from pathlib import Path

from fraud_agent.planner import PlanStep
from portfolio_agent._common import build_port_plan

SKILLS_DIR = Path(__file__).resolve().parent.parent.parent / "skills_portfolio"


def build_underwriting_plan() -> "Plan":
    steps = [
        PlanStep("consult_catalog", "Consult semantic layer before querying "
                 "(skill: underwriting_quality).",
                 skill="underwriting_quality", tool="uw_catalog"),
        PlanStep("load_submission", "Load the submission record so we know "
                 "the broker/class segment for the pricing-adequacy SQL "
                 "(skill: underwriting_quality).",
                 skill="underwriting_quality", tool="uw_submission_lookup"),
        PlanStep("uw_note_lookup", "Load UW notes for the submission "
                 "(skill: underwriting_quality).",
                 skill="underwriting_quality", tool="uw_note_lookup"),
        PlanStep("risk_score_consistency", "Pull risk score + override and "
                 "check magnitude (skill: underwriting_quality).",
                 skill="underwriting_quality", tool="risk_score_lookup"),
        PlanStep("inspection_vs_bind", "Pull inspection + bind records to "
                 "compute whether flagged issues were waived at bind "
                 "(skill: underwriting_quality).",
                 skill="underwriting_quality", tool="inspection_lookup"),
        PlanStep("bind_lookup", "Pull bind record + premium for pricing "
                 "adequacy (skill: underwriting_quality).",
                 skill="underwriting_quality", tool="bind_lookup"),
        PlanStep("pricing_adequacy", "Guarded SQL: estimate premium vs "
                 "expected loss for this class/override segment "
                 "(skill: underwriting_quality).",
                 skill="underwriting_quality", tool="pricing_adequacy_sql"),
        PlanStep("reflect", "Self-check: re-derive override magnitude and "
                 "pricing adequacy claim before composing "
                 "(skill: verification).",
                 skill="verification"),
        PlanStep("compose", "Compose the UW-quality verdict under the "
                 "citation policy(skill: citation_policy).",
                 skill="citation_policy"),
    ]
    return build_port_plan("underwriting", steps, SKILLS_DIR)
"""ANATOMY COMPONENT: PLAN (agent #3c — Loss Settlement Quality Agent)"""
from __future__ import annotations

from pathlib import Path

from fraud_agent.planner import PlanStep
from portfolio_agent._common import build_port_plan

SKILLS_DIR = Path(__file__).resolve().parent.parent.parent / "skills_portfolio"


def build_settlement_plan() -> "Plan":
    steps = [
        PlanStep("consult_catalog", "Consult semantic layer before querying "
                 "(skill: settlement_quality).",
                 skill="settlement_quality", tool="settlement_catalog"),
        PlanStep("load_policy", "Load the policy/bind record for the review "
                 "(skill: settlement_quality).",
                 skill="settlement_quality", tool="policy_lookup"),
        PlanStep("claim_lookup", "Pull claims + claim-stage reserves "
                 "(skill: settlement_quality).",
                 skill="settlement_quality", tool="claim_lookup"),
        PlanStep("settlement_lookup", "Pull settlements with leakage and "
                 "cycle time (skill: settlement_quality).",
                 skill="settlement_quality", tool="settlement_lookup"),
        PlanStep("reserve_adequacy", "Guarded SQL: aggregate reserve-vs-"
                 "settlement ratios by class to flag low-reserved bucket "
                 "(skill: settlement_quality).",
                 skill="settlement_quality", tool="reserve_adequacy_sql"),
        PlanStep("reflect", "Self-check: re-derive leakage from the raw "
                 "settlement rows before composing (skill: verification).",
                 skill="verification"),
        PlanStep("compose", "Compose the settlement-quality verdict under "
                 "the citation policy (skill: citation_policy).",
                 skill="citation_policy"),
    ]
    return build_port_plan("settlement", steps, SKILLS_DIR)
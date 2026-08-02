"""ANATOMY COMPONENT: PLAN (agent #3d — Assembly / Reflection Analyst)"""
from __future__ import annotations

from pathlib import Path

from fraud_agent.planner import PlanStep
from portfolio_agent._common import build_port_plan

SKILLS_DIR = Path(__file__).resolve().parent.parent.parent / "skills_portfolio"


def build_portfolio_plan() -> "Plan":
    steps = [
        PlanStep("consult_catalog", "Inspect available signals, stages and "
                 "outcomes in the lineage catalog (skill: lineage_analysis).",
                 skill="lineage_analysis", tool="stage_flow"),
        PlanStep("run_submissions", "Run the Submissions Quality Agent over "
                 "the segment submissions (skill: lineage_analysis).",
                 skill="lineage_analysis"),
        PlanStep("run_underwriting", "Run the Underwriting Quality Agent over "
                 "the bound policies in segment (skill: lineage_analysis).",
                 skill="lineage_analysis"),
        PlanStep("run_settlement", "Run the Loss Settlement Quality Agent "
                 "over the settled claims in segment (skill: "
                 "lineage_analysis).",
                 skill="lineage_analysis"),
        PlanStep("stage_flow", "Pull the funnel between stages from the "
                 "warehouse + lineage graph for the segment "
                 "(skill: lineage_analysis).",
                 skill="lineage_analysis", tool="stage_flow"),
        PlanStep("predisposing_signals", "Traverse PREDISPOSES edges for "
                 "the segment; rank candidate signals by weight "
                 "(skill: lineage_analysis).",
                 skill="lineage_analysis", tool="predisposing_signals"),
        PlanStep("reflect", "Self-check: re-derive funnel rates and the "
                 "top signal's weight; re-screen citation candidates "
                 "(skill: verification).",
                 skill="verification"),
        PlanStep("compose", "Compose the margin thesis + verdict under the "
                 "citation policy (skill: citation_policy).",
                 skill="citation_policy"),
    ]
    return build_port_plan("assembly", steps, SKILLS_DIR)
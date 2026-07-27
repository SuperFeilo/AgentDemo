"""ANATOMY COMPONENT: PLAN (agent #2 — Cost Trend Analyst)

Same planner contract as the fraud agent: read the goal file, load the
named skill playbooks, emit ordered steps. The steps themselves differ:
an analyst's plan is quantify -> decompose -> hypothesize -> evidence ->
compose.
"""
from __future__ import annotations

from pathlib import Path

from fraud_agent.planner import Plan, PlanStep, load_goal, load_skills

ROOT = Path(__file__).resolve().parent.parent
COST_GOAL_PATH = ROOT / "config" / "cost_goal.yaml"
COST_SKILLS_DIR = ROOT / "skills_cost"


def build_cost_plan() -> Plan:
    goal = load_goal(COST_GOAL_PATH)
    skills = load_skills(goal["skills_to_load"], skills_dir=COST_SKILLS_DIR)
    steps = [
        PlanStep("consult_catalog", "Consult the semantic layer before querying "
                 "(skill: trend_reading).", skill="trend_reading",
                 tool="metric_catalog"),
        PlanStep("read_trend", "Quantify the trend: cumulative change, recent "
                 "change, peak (skill: trend_reading).", skill="trend_reading",
                 tool="metric_trend"),
        PlanStep("decompose", "Split a national trend into regional "
                 "contributions (skill: decomposition).", skill="decomposition",
                 tool="sql_query"),
        PlanStep("find_drivers", "Traverse the driver knowledge graph for "
                 "candidate explanations (skill: driver_analysis).",
                 skill="driver_analysis", tool="driver_tree"),
        PlanStep("gather_evidence", "Pull citable evidence for each candidate "
                 "driver (skill: driver_analysis).", skill="driver_analysis",
                 tool="driver_event"),
        PlanStep("reflect", "Self-check: re-derive the headline numbers and "
                 "re-screen every citation before composing (skill: "
                 "verification).", skill="verification"),
        PlanStep("compose", "Compose the explanation under the citation policy "
                 "and issue a verdict (skill: citation_policy).",
                 skill="citation_policy"),
    ]
    return Plan(goal_statement=goal["statement"].strip(),
                constraints=goal["constraints"], skills=skills, steps=steps)

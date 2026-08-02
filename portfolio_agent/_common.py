"""Shared helpers for the three portfolio stage agents.

Each stage agent uses the cost_agent-style loop contract but has unique
interpret/reflect/compose logic. To keep that logic readable and
parallel with cost_brain.py — rather than hide it behind over-clever
abstractions — each agent keeps its own loop.py and brain.py. This
module just collects the tiny shared utilities both reuse: the verdict
mapper and the assembled-plan loaders.
"""
from __future__ import annotations

from fraud_agent.planner import Plan, PlanStep, load_goal, load_skills

ROOT_STAGE_GOALS = {
    "submissions":   "config/portfolio_submissions_goal.yaml",
    "underwriting":  "config/portfolio_underwriting_goal.yaml",
    "settlement":    "config/portfolio_settlement_goal.yaml",
    "assembly":      "config/portfolio_assembly_goal.yaml",
}


def build_port_plan(stage: str, steps: list[PlanStep],
                    skills_dir) -> Plan:
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    goal_path = root / ROOT_STAGE_GOALS[stage]
    goal = load_goal(goal_path)
    skills = load_skills(goal["skills_to_load"], skills_dir=skills_dir)
    return Plan(goal_statement=goal["statement"].strip(),
                constraints=goal["constraints"], skills=skills, steps=steps)


def verdict_thresholds(constraints: dict, high_key: str,
                       mid_key: str) -> tuple[int, int]:
    return constraints[high_key], constraints[mid_key]


def map_score_to_verdict(score: int, high: int, mid: int,
                         high_label: str, mid_label: str,
                         low_label: str) -> str:
    if score >= high:
        return high_label
    if score >= mid:
        return mid_label
    return low_label
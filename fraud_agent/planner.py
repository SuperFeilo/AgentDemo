"""ANATOMY COMPONENT: PLAN

The planner turns the GOAL into an ordered list of investigation steps.
It reads `config/goal.yaml`, loads the skill playbooks named there, and
emits a Plan the loop can execute. Steps are declarative: the brain
decides how to score each step's result, and may skip a step whose
preconditions are not met (e.g. notes analysis needs >= 2 notes).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import yaml

from fraud_agent.paths import GOAL_PATH, SKILLS_DIR


@dataclass
class PlanStep:
    name: str
    purpose: str
    skill: str | None = None   # which playbook governs this step
    tool: str | None = None    # which tool this step invokes


@dataclass
class Plan:
    goal_statement: str
    constraints: dict
    skills: dict[str, str] = field(default_factory=dict)  # name -> markdown
    steps: list[PlanStep] = field(default_factory=list)


def load_goal(path=None) -> dict:
    return yaml.safe_load((path or GOAL_PATH).read_text())["goal"]


def load_skills(names: list[str], skills_dir=None) -> dict[str, str]:
    skills = {}
    base = skills_dir or SKILLS_DIR
    for name in names:
        path = base / f"{name}.md"
        skills[name] = path.read_text(encoding="utf-8")
    return skills


def build_plan() -> Plan:
    goal = load_goal()
    skills = load_skills(goal["skills_to_load"])
    steps = [
        PlanStep("load_claim", "Load the claim record so we know what we are "
                 "investigating.", tool="claims_db_lookup"),
        PlanStep("velocity_check", "Look for claim-frequency abuse (skill: "
                 "velocity_check).", skill="velocity_check", tool="claims_history"),
        PlanStep("policy_timing", "Check whether coverage was bought just before "
                 "the loss (skill: policy_timing).", skill="policy_timing",
                 tool="policy_check"),
        PlanStep("network_analysis", "Traverse the knowledge graph for fraud-ring "
                 "links (skill: network_analysis).", skill="network_analysis",
                 tool="fraud_ring_network"),
        PlanStep("notes_analysis", "Read adjuster notes with the language-model "
                 "brain for inconsistencies (skill: notes_analysis).",
                 skill="notes_analysis", tool="notes_inconsistency_detector"),
        PlanStep("reflect", "Self-check: re-verify score arithmetic and "
                 "threshold logic before deciding (skill: verification).",
                 skill="verification"),
        PlanStep("decide", "Score all evidence and decide APPROVE / REVIEW / "
                 "ESCALATE (skill: escalation_policy).", skill="escalation_policy"),
        PlanStep("escalate", "If risk is high, file an SIU case — human approval "
                 "required (skill: escalation_policy).", skill="escalation_policy",
                 tool="siu_escalate"),
    ]
    return Plan(goal_statement=goal["statement"].strip(),
                constraints=goal["constraints"], skills=skills, steps=steps)

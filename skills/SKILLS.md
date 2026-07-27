# SKILLS.md — Fraud Investigation Skill Index

> **ANATOMY COMPONENT: SKILLS**
> Skills are versioned, human-readable playbooks. The planner loads the
> skills named in `config/goal.yaml` and uses them to build the
> investigation plan. The rule-based brain consults them when choosing
> the next action. Changing a skill file changes agent behaviour —
> no code edits required.

| Skill | File | Purpose | Tools it governs |
|---|---|---|---|
| Velocity Check | `velocity_check.md` | Detect claim-frequency abuse | `claims_history` |
| Policy Timing | `policy_timing.md` | Detect coverage bought just before the loss | `policy_check` |
| Network Analysis | `network_analysis.md` | Detect fraud rings via the knowledge graph | `fraud_ring_network` |
| Notes Analysis | `notes_analysis.md` | Detect inconsistencies in adjuster notes | `notes_inconsistency_detector` |
| Escalation Policy | `escalation_policy.md` | Decide approve / review / escalate | `siu_escalate` |

## Loading contract
Each skill file must contain:
1. **When to use** — trigger conditions.
2. **Tool** — which registered tool to call and with what arguments.
3. **Scoring** — how to convert observations into risk points.

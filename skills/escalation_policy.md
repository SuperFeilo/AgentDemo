# Skill: Escalation Policy

## When to use
Once — at the end of the investigation, after all evidence skills have
fired and the risk score is final.

## Tool
`siu_escalate(claim_id, risk_score, rationale)` — files a case with the
Special Investigations Unit. **Requires human approval**: the lifecycle
manager pauses the run until a human approves or rejects.

## Scoring → Decision
| Final risk score | Decision |
|---|---|
| 0 – 39 | `APPROVE` — pay the claim |
| 40 – 69 | `REVIEW` — route to a human adjuster |
| 70 – 100 | `ESCALATE` — SIU referral, human approval required |

Thresholds come from `config/goal.yaml` (goal.constraints); do not
hardcode them.

## Notes
- The rationale must list every signal that contributed points.
- An escalation rejected by the human reviewer ends the run as
  `REVIEW`, not `APPROVE` — caution is cheap, fraud is not.

# Skill: Policy Timing

## When to use
Always, alongside the velocity check. A policy purchased days before an
expensive loss is one of the oldest fraud patterns in the book
("buying coverage for a loss that already happened").

## Tool
`policy_check(policy_id, incident_date)` → policy inception date and the
number of days the policy had been in force at the time of loss.

## Scoring
| Days in force at loss | Risk points |
|---|---|
| 0 – 14 | +40 |
| 15 – 45 | +20 |
| more than 45 | 0 |

## Notes
- Pair this with claim amount: a short-tenure policy plus a large theft
  claim deserves explicit mention in the rationale.

# Skill: submission_quality  (agent #3a — Submissions Quality Agent)

> Score the submission-quality dimension of one commercial submission (or
> aggregated segment). Verdict: `STRONG SUBMISSION` / `ACCEPTABLE` /
> `WEAK SUBMISSION`.

## When to act
Apply this skill whenever the plan reaches the `submission_summary`,
`note_scan`, or `history_scan` steps.

## Workflow
1. **Consult the catalog first** — never invent a field. Use
   `submission_catalog` to learn the available submission attributes.
2. **Load the submission** with `submission_lookup`.
3. **Summarize completeness** — exposure detail + loss history. Use
   `submission_summary` (over the warehouse) for the baseline rate.
4. **Scan notes** — call `submission_note_scan` and count hedging phrases.
5. **History scan** — use `submission_history_sql` (guarded read-only
   SELECT) to compute prior bind/conversion behaviour for the broker.

## Scoring (0-100 weight, then map to verdict)

| Signal | Points (allocate) | Trigger |
|---|---|---|
| Exposure detail complete AND loss history present | +40 | both flags on |
| Exposure detail incomplete | -30 | `exposure_detail_complete = 0` |
| Loss history absent | -10 | `loss_history_flag = 0` |
| Broker's bind conversion within portfolio band | +15 | broker's conv rate within ±5pts of 68% |
| Broker known weak pattern (e.g. BRO-W) | -15 | broker in weak-broker set |
| Class-code has override concentration ≥ 40% | -10 | class 5437 + override density |

Map final score (`>= 70` STRONG, `40-69` ACCEPTABLE, `< 40` WEAK).
The threshold map lives in planner's goal constraints.

## What to cite
- The warehouse-derived figure for completeness % for the broker (a number).
- The class-level override rate from the warehouse.
- The submission's individual flags.
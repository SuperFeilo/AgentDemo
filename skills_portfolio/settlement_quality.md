# Skill: settlement_quality  (agent #3c — Loss Settlement Quality Agent)

> Evaluate settlement quality on claims attached to a bind/policy.
> Verdict: `CLEAN SETTLEMENT` / `ACCEPTABLE` / `LEAKAGE DETECTED`.

## When to act
Steps: `reserve_adequacy`, `settlement_speed`, `leakage_scan`,
`settlement_lineage_follow`.

## Workflow
1. Load policy with `policy_lookup`.
2. Pull claims (`claim_lookup`); if no claims attached, the verdict is
   `CLEAN SETTLEMENT` by absence — note this in the rationale.
3. Pull settlements (`settlement_lookup`).
4. Compute reserve adequacy: `settlement_vs_reserve_ratio`. Ratio above
   1.4 flags inadequate reserve (`reserve_adequacy_sql`).
5. Compute speed: days_to_settle above 180 is slow (`settlement_speed`).
6. Leakage scan: fraction of cases with leakage_amount > 5% of settlement.

## Scoring (0-100 → verdict)

| Signal | Points | Trigger |
|---|---|---|
| Reserve ratio within [0.85, 1.3] | +30 | reserve adequate |
| Reserve ratio above 1.4 (inadequate) | -30 | low reserves |
| Days-to-settle ≤ 180 | +15 | within target cycle |
| Days-to-settle > 180 | -10 | slow path |
| Leakage_pct (sum leakage/settle) above 10% | -25 | leakage detected |
| FNOL lag > 14 days | -10 | late_fnol marker |

Map `>=70` CLEAN, `40-69` ACCEPTABLE, `<40` LEAKAGE DETECTED.
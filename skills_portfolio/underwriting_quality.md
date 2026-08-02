# Skill: underwriting_quality  (agent #3b — Underwriting Quality Agent)

> Evaluate UW judgment on a submission / bound risk. Verdict:
> `WELL-UNDERWRITTEN` / `ACCEPTABLE` / `MISPRICED`.

## When to act
Apply this skill on every reach of the UW pipeline. Steps:
`uw_note_consistency`, `risk_score_consistency`, `inspection_vs_bind`,
`pricing_adequacy`, `uw_lineage_follow`.

## Workflow
1. Load UW notes (`uw_note_lookup`).
2. Load risk score + override (`risk_score_lookup`).
3. Compute consistency between the notes' theme and the override decision —
   hedging notes on overridden risks score badly.
4. Pull inspection record (`inspection_lookup`); compute whether the
   inspection-flag signal was waived at bind.
5. Pull bind + premium (`bind_lookup`); evaluate pricing adequacy vs.
   model expectation with `pricing_adequacy_sql` (guarded).
6. Follow the lineage edge from `risk_scoring` to `bind` for context.

## Scoring (0-100 → verdict)

| Signal | Points | Trigger |
|---|---|---|
| Notes align with score (clear, specific, unhedged) | +25 | no hedging note + sensible score |
| Hedging note on a risk with downward override | -25 | hedging_flag=1 & override=1 |
| Override produces score below model by >5pts | -25 | override & delta>5 |
| Inspection flagged at bind was waived | -25 | inspection_flagged_at_bind=1 |
| Premium within ±5% of model premium | +15 | pricing_adequacy in band |

Map `>=70` WELL, `40-69` ACCEPTABLE, `<40` MISPRICED.
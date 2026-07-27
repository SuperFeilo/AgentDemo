# Skill: Velocity Check

## When to use
Always, for every claim, immediately after the claim record is loaded.
Repeat filers are the single cheapest fraud signal to compute.

## Tool
`claims_history(claimant_id)` → list of prior claims with filed dates and amounts.

## Scoring
Count prior claims filed within 90 days of the current claim's filed date.

| Priors in 90d | Risk points |
|---|---|
| 0 | 0 |
| 1 | +15 |
| 2 | +30 |
| 3 or more | +55 |

## Notes
- Claims older than 90 days are background, not signal.
- If 3+ priors are found, quote the pattern explicitly in the rationale
  (e.g. "4th auto claim in 4 months").

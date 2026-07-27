# Skill: Notes Analysis

## When to use
When the claim carries two or more adjuster-note entries. Staged and
exaggerated claims are usually betrayed by the claimant's own words:
the story drifts between tellings.

## Tool
`notes_inconsistency_detector(claim_id)` — a *model-based brain* that
reads free-text adjuster notes and returns typed inconsistencies:
`date_contradiction`, `location_contradiction`, `injury_contradiction`,
`hedging_language`.

## Scoring
| Finding | Risk points |
|---|---|
| Each contradiction (any type) | +15 (cap +45) |
| Heavy hedging (>= 3 hedging phrases) | +10 |

## Notes
- Quote the conflicting sentences in the rationale — contradictions
  must be verifiable by a human in seconds.
- Hedging alone is weak evidence; it only matters alongside other signals.

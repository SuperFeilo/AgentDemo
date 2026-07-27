# Skill: Network Analysis

## When to use
After the velocity check. Fraud rings share infrastructure: phones,
addresses, repair shops, tow operators. One hop across a shared
attribute can link a clean-looking claimant to a known fraudster.

## Tool
`fraud_ring_network(claimant_id)` → subgraph of the claimant's 2-hop
neighbourhood in the knowledge graph, plus any links to entities
flagged `known_fraud`.

## Scoring
| Finding | Risk points |
|---|---|
| Shared attribute with a `known_fraud` entity | +50 |
| Shared attribute with other claimants (unflagged) | +20 |
| No shared attributes | 0 |

## Notes
- Always cite the shared attribute (e.g. "shares phone PH-900 with
  CL-201, a known fraud entity").
- Render the subgraph when this skill fires — humans reason about rings
  visually.

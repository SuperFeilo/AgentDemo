# Skill: Driver Analysis

## When to use
Once the trend is quantified and (if needed) decomposed. Now: *why*?

## Tools
- `driver_tree(metric, region, coverage)` — traverses the driver
  knowledge graph: which driver nodes IMPACT this metric, scoped to the
  segment, with edge weights, direction, lag, and confidence.
- `driver_event(driver_id)` — the quantitative evidence behind one
  driver (index changes, rates, event magnitudes) with a source label.

## Citation rules
| Condition | Action |
|---|---|
| edge weight >= 0.40 AND driver direction matches trend direction | cite it |
| edge weight < 0.40 | ignore — background noise |
| direction contradicts the trend | do NOT cite, even if the driver is real |

## Confidence
Combine cited drivers' edge weights with noisy-OR:
`confidence = 100 * (1 - Π(1 - weight))`. Compare against the goal's
thresholds (>= 70 EXPLAINED, >= 40 PARTIALLY EXPLAINED).

## Notes
- A driver without matching-direction evidence is a hypothesis, not an
  explanation. Hypotheses may be *mentioned*, clearly labeled as such.

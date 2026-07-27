# Skill: Trend Reading

## When to use
Always, first. Explaining a trend you have not measured is storytelling,
not analysis.

## Tools
- `metric_catalog()` — the semantic layer: which metrics exist, how they
  are defined, which segments are available. Consult it before querying
  so you never invent a metric or a join.
- `metric_trend(metric, region, coverage)` — quarterly series from the
  warehouse plus cumulative and recent-4-quarter change.

## Reading rules
| Signal | Interpretation |
|---|---|
| cumulative change ≥ +5% | rising trend — needs explanation |
| cumulative change ≤ -5% | falling trend — needs explanation |
| between -5% and +5% | flat — say so; do not invent a story |
| spike in one quarter then reversion | episodic event — look for event-type drivers |

## Notes
- Always quote the headline numbers in your final answer: cumulative
  change, peak quarter, and the most recent quarter's direction.

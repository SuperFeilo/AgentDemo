# Skill: Citation Policy

## When to use
At the end, while composing the final explanation — and as a final
self-check before returning.

## Rules
1. **Numbers come from the warehouse.** Every percentage you state must
   appear in a `metric_trend` or `sql_query` result. No invented figures.
2. **Drivers come from the graph.** Every driver you cite must appear in
   a `driver_tree` result and pass the citation rules in
   `driver_analysis.md`, backed by a `driver_event` evidence record.
3. **Cite the source label** from the evidence (e.g. "OEM parts index",
   "medical CPI") so a human can verify in seconds.
4. **Say UNEXPLAINED when the graph has no matching drivers.** An honest
   "we don't know yet" beats a plausible-sounding fabrication — that is
   the difference between an analyst and a storyteller.

## Verdict
| Confidence | Verdict |
|---|---|
| >= 70 | `EXPLAINED` |
| 40 – 69 | `PARTIALLY EXPLAINED` |
| < 40 | `UNEXPLAINED` |

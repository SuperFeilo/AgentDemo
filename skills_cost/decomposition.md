# Skill: Decomposition

## When to use
After trend reading, when the question targets a broad segment
(e.g. national). A national trend is an average of regional stories —
one outlier region often explains most of it.

## Tool
`sql_query(sql)` — guarded, read-only SQL against the warehouse for
ad-hoc cuts the structured tools don't cover. Standard decomposition
pattern: average of the first two quarters vs. the last two quarters,
grouped by region.

## Reading rules
| Finding | Interpretation |
|---|---|
| one region's change >> others | concentrated driver — narrow the search to that region |
| all regions move together | broad/national driver (inflation, regulation) |
| regions diverge in sign | mix of local drivers — explain each separately |

## Notes
- The guardrail is part of the tool: SELECT/WITH only, one statement,
  no DDL/DML keywords. If the guard rejects your SQL, rewrite — do not
  retry the same string.

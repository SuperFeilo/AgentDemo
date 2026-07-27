# SKILLS.md — Cost Trend Analyst Skill Index

> **ANATOMY COMPONENT: SKILLS (agent #2)**
> Same pattern as the fraud agent's skills, different craft: these
> playbooks teach the analyst brain how to read trends, decompose them,
> find drivers in the knowledge graph, and cite them honestly.

| Skill | File | Purpose | Tools it governs |
|---|---|---|---|
| Trend Reading | `trend_reading.md` | Quantify the trend before explaining it | `metric_catalog`, `metric_trend` |
| Decomposition | `decomposition.md` | Break a national trend into regional contributions | `sql_query` |
| Driver Analysis | `driver_analysis.md` | Find candidate explanations in the driver graph | `driver_tree`, `driver_event` |
| Citation Policy | `citation_policy.md` | Rules for honest, verifiable explanation | (all) |

## The analyst's creed
1. Numbers first, story second — never explain a trend you haven't measured.
2. Every driver claim needs a graph path *and* evidence.
3. "Unexplained" is an acceptable, honest answer.

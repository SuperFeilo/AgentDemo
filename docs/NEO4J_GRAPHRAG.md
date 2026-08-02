# Neo4j GraphRAG — dual-mode demo

The GraphRAG layer answers **root-cause analysis**, **deep planning** and
**investigative assignments** by retrieving from a *graph*, not documents.
It runs in two modes with identical query semantics:

| Mode | What runs | When |
|---|---|---|
| **Neo4j** | the official `neo4j` driver + genuine Cypher from `graphrag_neo4j/queries.py` | a server is reachable at `NEO4J_URI` |
| **Fallback** | the same query API computed in networkx (`queries.local`) | no server reachable — demo and evals stay reproducible offline |

This mirrors the project's mock-LLM philosophy: the real thing when
available, a deterministic stand-in with a clearly marked seam otherwise.

## Quick start (offline)

```powershell
cd C:\Users\mingm\FraudAgent
.\.venv\Scripts\Activate.ps1
python scripts\generate_neo4j_demo_data.py   # seeded synthetic graphs (committed already)
python scripts\demo_neo4j_graphrag.py        # headless end-to-end demo
python scripts\test_neo4j_graphrag.py        # ground-truth tests
streamlit run app/main.py                    # 🧬 GraphRAG tab
```

## Pointing it at a real Neo4j

Anything Neo4j 5+ works (Desktop, a local server, or AuraDB). The driver
is already in `requirements.txt`.

```powershell
$env:NEO4J_URI="bolt://localhost:7687"; $env:NEO4J_USER="neo4j"
$env:NEO4J_PASSWORD="your-password"
python scripts\demo_neo4j_graphrag.py        # mode: neo4j
python scripts\test_neo4j_graphrag.py        # same suite, live Cypher
```

Credentials can also live in `config/neo4j.yaml` (env vars win).
On first use the store bulk-loads the synthetic payload with
`UNWIND … MERGE` (a few seconds at this volume).

> No Docker on this machine? Neo4j Desktop is a one-click install, or use
> a free AuraDB instance. The Cypher library uses only core Cypher (no
> APOC), so it runs anywhere.

## The synthetic data (seeded, planted ground truth)

`graphrag_neo4j/synthetic.py` generates three graphs as a pure function
of `seed` — reproducible evals, same numbers every run:

| Domain | Volume | Planted structure |
|---|---|---|
| **fraud** | ~200 claimants, 8 rings, 6 scam patterns, 14 shops, 6 clinics, 11 attorneys, 7 shell companies, 23 memos | rings share phones/addresses/shops (e.g. RING-SOUTH-1 → QuickFix Auto → shell company); **distractors**: innocent shared households, clean claimants with zero fraud paths |
| **cost** | 3 metrics, 14 drivers, 5 causal events, 25 memos | `Event -CAUSES-> Driver -IMPACTS-> Metric -FEEDS_INTO-> Metric`; hurricane (South) vs polar vortex (Midwest) planted so the episodic trigger is unambiguous |
| **portfolio** | 7 stages, 19 signals, 5 outcomes, 5 events, 90 instance nodes (submission→bind→claim→settlement), 25 memos | per-segment leverage ground truth: BRO-W → `reserve_adequacy` (claim), class 5437 → `risk_score_override` (risk_scoring) |

Ground truth lives in `data/neo4j_ground_truth.json`; `scripts/test_neo4j_graphrag.py`
asserts the demo answers match it.

## The query library (`graphrag_neo4j/queries.py`)

Every query has a Cypher template **and** a networkx implementation with
identical semantics — `store.run(name, **params)` returns the same dict
in both modes, and `store.cypher_for(name, params)` shows the exact
Cypher that (would) run.

- **Fraud**: `ego_neighborhood`, `shared_attributes`, `paths_to_fraud`
  (shortestPath to known fraud), `cluster_score` (common-neighbor ring
  detection without APOC), `root_cause_claimant` (claimant → ring →
  pattern → facilitators → exposure), `ring_members`, `intel_catalog`.
- **Cost**: `driver_tree`, `root_cause` (event triggers + causal chains),
  `root_cause_structural` (DAG-head drivers), `driver_event`.
- **Portfolio**: `lineage_flow`, `leverage` (weight × exposure ranking),
  `journey_trace` (submission → settlement with exhibited signals).

Curation is enforced *inside* the queries: `WHERE n.id IN $approved OR
n.curated = true`, where `$approved` comes from the shared approval
files (`data/*_graph_approval.json`) — the same files the agent tools
read, so one curation decision governs both layers.

## The investigator (`graphrag_neo4j/investigator.py`)

`investigate(domain, assignment, params)` decomposes an assignment into
a plan of library queries, executes them, and composes a cited report:

```
steps: [{query, params, cypher, result}]
findings, verdict, citations  — every quantitative claim carries its
                                 source document
```

Built-in assignments (also in the 🧬 GraphRAG tab):
- `fraud_root_cause` — why is CL-201 risky? → RING-SOUTH-1, $687k, cited SIU-01/AUD-001
- `fraud_plan_investigation` — a new claimant shares attributes with a ring: ordered plan, each step backed by a query
- `cost_root_cause` — why did South auto-pd frequency spike? → hurricane event → cat_weather (winter_weather excluded as the planted distractor)
- `portfolio_leverage` — BRO-W / 5437 margin lever (matches the assembly agent's ground truth)
- `portfolio_journey` — CLM-015 full journey with signals

The intent→plan mapping is the **real-LLM seam**: replace the dispatch
with an LLM that returns `{"plan": [{query, params}], "synthesis": …}`
against the same library.

## Files

```
graphrag_neo4j/
  synthetic.py     seeded generators + ground truth (data/neo4j_*.json)
  queries.py       Cypher library + networkx fallbacks + QUERY_META
  store.py         Neo4jGraphStore | LocalGraphStore (get_store)
  investigator.py  assignment planner + report composition
config/neo4j.yaml  connection + seed settings
scripts/generate_neo4j_demo_data.py   regenerate the datasets
scripts/demo_neo4j_graphrag.py        headless end-to-end demo
scripts/test_neo4j_graphrag.py        ground-truth tests (both modes)
```

Each agent's `graphrag/store.py` still exposes the original API
(`load_approval` / `save_approval` / `is_citable`) — now backed by the
shared dual-mode store, so the agent tools, evals, and the GraphRAG tab
stay in sync.

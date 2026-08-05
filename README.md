# 🧠 Agent Anatomy Explorer — three agents, one skeleton

A **teaching project** for learning how AI agents are put together. Every
component of "agent anatomy" is a real, readable piece of code, and a
Streamlit UI lets you watch them cooperate — in **three different
agents**:

- 🕵️ **Fraud Investigator** — decides APPROVE / REVIEW / ESCALATE on
  (synthetic) insurance claims; pauses for human approval before filing
  an SIU case.
- 📈 **Cost Trend Analyst** — answers analytic research questions
  ("why is Northeast BI severity rising?") using a SQLite warehouse for
  numbers and a driver knowledge graph for honest, cited explanations.
- 🎯 **Portfolio Journey Analyst** — the multi-agent case study. Traces
  the **commercial-lines lifecycle end-to-end** (submission →
  underwriting → risk-scoring → site-inspection → bind → claim →
  settlement) across a **7-table SQLite warehouse**, runs three
  stage-quality sub-agents (submissions, underwriting, settlement) and
  an **assembly / reflection analyst** that traverses a stage-flow
  lineage graph to identify the high-leverage **profit-margin lever**
  in a market segment.

All three share one skeleton: goal → plan → skills → loop → tools →
harness → lifecycle → knowledge graph → eval. Brains are
**deterministic** (rule-based + mock-LLM heuristics) — no API keys,
fully reproducible evals. Clearly marked seams show where a real LLM
would plug in (`fraud_agent/brain/notes_llm.py`,
`cost_agent/graphrag/extractor.py`,
`portfolio_agent/graphrag/extractor.py`).

## Quick start

```powershell
cd C:\Users\mingm\FraudAgent
.\.venv\Scripts\Activate.ps1
streamlit run app/main.py          # 🏠 Home → pick an agent → its 5-page workspace
```

The app opens on a **Home** page: three agent cards (each with its
implementation style), the styles overview, and a how-to-run guide.
Picking an agent takes you into its workspace — the same five pages for
every agent (**Anatomy · Live Run · Eval Lab · GraphRAG · Learning**),
with real URLs per page. The sidebar pins the ▶️ Run controls (Start /
Step / Autoplay / autonomy / bug / human checkpoint), the 🎬 guided
demos, and the spend ledger.

Headless evals (no UI):

```powershell
python -m fraud_agent.eval.runner        # fraud: precision/recall/F1
python -m cost_agent.eval.runner         # analyst: citations/numeric/provenance
python -m portfolio_agent.eval.runner        # portfolio sub-agents: verdict+recall
python -m portfolio_agent.eval.assembly_runner  # portfolio assembly: thesis+provenance
python -m fraud_agent.learning           # outcome analysis (dry run; --apply writes)
python -m cost_agent.learning            # driver validation (dry run; --apply writes)
python -m portfolio_agent.learning       # portfolio signal validation (dry run; --apply writes)
python scripts\test_graphrag.py          # GraphRAG: extraction + curation impact
python scripts\test_packs.py          # the release gate: 27 deterministic checks
python scripts\demo_reset.py --yes    # clean demo slate (backup → restore → regen)
python scripts\generate_neo4j_demo_data.py  # (re)generate the Neo4j GraphRAG datasets
python scripts\demo_neo4j_graphrag.py       # Neo4j GraphRAG: extraction → curation → 5 assignments
python scripts\test_neo4j_graphrag.py       # Neo4j GraphRAG: ground-truth tests (both modes)
python scripts\test_llm.py                  # live DeepSeek smoke test (needs DEEPSEEK_API_KEY)
```

## The anatomy map

| Component | Where | What it does |
|---|---|---|
| **Goal** | `config/goal.yaml` | Objective, success criteria, budgets, thresholds. |
| **Plan** | `fraud_agent/planner.py` | Goal + skills → ordered investigation steps. |
| **Skills** | `skills/SKILLS.md`, `skills/*.md` | Playbooks: when to act, which tool, how to score. |
| **Loop** | `fraud_agent/loop.py` | Observe→think→act generator; yields events, receives results via `.send()`. |
| **Brains** | `fraud_agent/brain/rule_based.py`, `brain/notes_llm.py` | What to do next + how to score evidence; mock-LLM notes reader. |
| **Tool calls** | `fraud_agent/tools/registry.py`, `tools/claims_tools.py` | Schemas + implementations; single execution choke point. |
| **Graph knowledge** | `fraud_agent/knowledge/graph.py`, `data/entities.json` (rings); `data/cost_entities.json` (driver tree + semantic layer) | Relationships as queryable data. |
| **GraphRAG write path** | `data/memos.json` → `cost_agent/graphrag/` (extractor, curation store) | Mock-LLM extraction of driver candidates from source documents; human approval checkpoint; provenance on every citation. |
| **Neo4j GraphRAG** | `graphrag_neo4j/` (store, queries, synthetic, investigator) + `config/neo4j.yaml` | Dual-mode graph retrieval for **root-cause analysis, deep planning, investigative assignments**: real Cypher against a live Neo4j (or an in-memory fallback with identical semantics), seeded synthetic graphs (~200 claimants / 8 fraud rings / causal event layer / portfolio journey instances) with planted ground truth + distractors, and a query library where every read enforces human curation. See `docs/NEO4J_GRAPHRAG.md`. |
| **Case blackboard** | `fraud_agent/blackboard.py` | Typed working memory (case/evidence/hypotheses/decision); every write journaled with its data origin. |
| **Determination dossier** | `fraud_agent/dossier.py` | One auditable artifact per run — case → skills → thoughts → data by origin → decision → cost. JSON/MD export. |
| **Autonomy gate** | tool registry (`autonomy=`) + `fraud_agent/harness.py` | Gated tools pause for human approval; per-run autonomy slider (full/gated/step). |
| **Cost control** | harness metering + `max_cost_units` in goal yamls | Real latency timing + declared per-tool cost units; budget aborts runs. |
| **Reflection** | `skills*/verification.md` + `reflect` plan step | Ng's pattern: the agent re-derives its own numbers/scores before deciding; self-corrects. |
| **Learning loop** | `*/learning.py` + `data/outcomes*` | Decisions scored vs real outcomes → weight proposals → human approval → eval delta. See `docs/CONTINUOUS_LEARNING.md`. |
| **Harness** | `fraud_agent/harness.py` | Executes tools, enforces budgets, records the trace. |
| **Lifecycle** | `fraud_agent/lifecycle.py` | Run state machine + registry; human-checkpoint pause/resume. |
| **Eval** | `fraud_agent/eval/` | Labeled dataset, batch runner, precision/recall/F1. |
| **Portfolio agent** | `portfolio_agent/` | Third agent for end-to-end journey analytics: `warehouse.py` (7 linked fact tables), `submissions/` / `underwriting/` / `settlement/` stage sub-agents, `assembly/` orchestrator-reflection analyst, GraphRAG (`graphrag/`), learning loop, own eval (`portfolio_agent/eval/`). Identical seam as the cost analyst's but with stage-flow lineage (`PREDISPOSES` edges) instead of driver→metric (`IMPACTS`). |

## Implementation styles — three schools, one skeleton

All three agents share the same 12-component anatomy, but each one
demonstrates a **different implementation style** — three points on the
determinism ↔ agency spectrum — so you can see the contrast and the
tradeoffs in one project:

| Agent | Style | Practitioner lineage | Tradeoff |
|---|---|---|---|
| 🕵️ Fraud | **Deterministic workflow + reflection + human gate** | Ng's Reflection + Planning; Anthropic *workflows*; Karpathy's autonomy slider (step/gated/full — implemented); Howard/Answer.AI's deterministic tool allow-lists | predictable, auditable, cheap — but can't adapt to novel schemes |
| 📈 Cost | **Autonomous research loop + verification** | Ng's Tool Use; Anthropic *agents* + evaluator-optimizer; Chase's plan-and-execute + verification loop; Zaremba/Karpathy verifiability (citations scored vs warehouse truth) | flexible, open-ended — but costs more and needs guardrails to stay honest |
| 🎯 Portfolio | **Orchestrator–workers multi-agent** | Ng's Multi-agent collaboration; Anthropic orchestrator-workers; Chase's "a node can be a full agent run"; Zaremba's delegation | parallelism + specialization — but coordination overhead, hardest to trace/eval |

Each agent's **Anatomy map** renders with a different topology (chain /
cycle / fan-out) and labels its style; the **Home page** shows the
three styles side-by-side on the determinism axis (the Anatomy page is
agent-scoped only). Grounding:
Andrew Ng, "Agentic Design Patterns" (DeepLearning.AI, 2024); Anthropic,
"Building Effective Agents" (2024); Harrison Chase / LangChain,
plan-and-execute (2024), "The Anatomy of an Agent Harness" (2026),
"The Art of Loop Engineering" (2026), "3 Years of Graph Engineering"
(2026); Karpathy, "Verifiability" and "2025 LLM Year in Review" (2025);
Answer.AI, "The unauthorized tool call problem" (2026). For the full
comparison — every component mapped to the research that published it,
the two ideas this project takes beyond the frontier, and a roadmap of
the frontier concepts it omits (each with its code seam) — see
[`docs/FRONTIER_COMPARISON.md`](docs/FRONTIER_COMPARISON.md), rendered
live as the 🗺️ **Frontier map** page in the app.

## How a run flows

1. **Plan** — the planner loads `goal.yaml` and the skill playbooks, and
   builds the plan (fraud: load claim → velocity → policy timing → network
   → notes → reflect → decide → escalate-if-needed).
2. **Loop** — for each step the brain *thinks* (emits its reasoning),
   requests a **tool call**, and the **harness** executes it, meters its
   cost/latency, and sends the result back. Findings are posted to the
   **blackboard** with their data origin.
3. **Autonomy gate** — gated tools (like `siu_escalate`) **pause** the
   run (lifecycle PAUSED) until a human approves — unless the run's
   autonomy slider is set to full.
4. **Reflect** — before deciding, the agent re-derives its own numbers
   and self-corrects if needed (Ng's reflection pattern).
5. **Eval & learn** — the harness drains the loop headlessly over the
   labeled dataset; later, real outcomes are compared against decisions
   and the learning loop proposes weight updates for human approval.

## Try this

- **Guided demos (sidebar)**: pick a scenario in the 🎬 **Guided demo**
  panel and press **Load & run** — controls pre-set, the run starts, and
  a hint banner points your eyes at the right component boxes.
- **Watch it think**: the 🧠 Anatomy map in Live Run **pulses** with the
  trace — each event lights the components that produced it (Harness +
  Lifecycle on a gate pause, Graph on a graph read, the worker boxes on
  a `run_*` step). Boxes map 1:1 to files; open any of them from the
  Anatomy page.
- **Implementation styles**: the Home page shows the three agents on
  the determinism ↔ agency spectrum (chain / cycle / fan-out topologies)
  with the practitioner lineage for each style; each workspace is
  agent-scoped only.
- **📊 Eval Lab 🚦 Release gate**: run the deterministic regression
  (27 checks) and the 🐛 bug sweep — every planted reasoning bug is
  injected and caught by reflection.
- **Live Run (fraud)**: run `C-1011` with autonomy **gated** — approve the
  SIU gate, then open the 📄 Dossier and see data grouped by origin
  (persistent DB vs graph vs model-brain vs human). Re-run with
  autonomy **full**: no checkpoint, straight to ESCALATED.
- **Reflection**: toggle 🐛 bug and rerun `C-1005` — the reflect step
  catches the phantom points and self-corrects (watch the red card).
- **🎓 Learning tab (fraud)**: analyze outcomes — the loop discovers that
  `shared_attribute` fires only on legit claims and proposes halving its
  weight. Approve, then re-run the eval: still green, less noisy.
- **🎓 Learning tab (analyst)**: validate drivers against next-quarter
  actuals — supply_chain is contradicted and decays; validated drivers
  are reinforced. Weights update live in the knowledge graph.
- **Live Run (analyst)**: run Q3 ("why did South frequency spike?") and
  watch the agent classify an *episodic* trend, then cite the hurricane
  with provenance docs.
- **🧬 GraphRAG tab (analyst)**: extract drivers from the 8 source memos,
  then **reject** `adas_complexity`, save curation, and re-run Q1 — the
  verdict degrades to PARTIALLY EXPLAINED. Knowledge state *is* agent
  performance.
- **🕸️ Neo4j GraphRAG (all agents)**: the GraphRAG tab now runs on a
  seeded synthetic graph at demo scale. Watch the **investigative
  assignments**: root-cause CL-201 → the South Texas staged-accident ring
  (QuickFix Auto nexus, ~$687k exposure, cited to SIU-01/AUD-001);
  plan an investigation for a new claimant; explain South frequency via
  the hurricane causal chain (winter storm correctly excluded as the
  planted distractor); rank the BRO-W margin lever. Every query shows
  the exact Cypher it runs — and genuinely executes it against Neo4j if
  `NEO4J_URI` is set (fallback mode otherwise). Reject `RING-WEST-1` in
  the curation panel and watch retrieval shrink.
- **Skills**: edit a playbook in `skills/` and watch behaviour change;
  scoring weights live in `config/fraud_weights.yaml` as data.
- **Eval Lab**: sweep the fraud flag threshold to trade precision for
  recall; compare with the analyst's four-axis eval (citation
  precision/recall, numeric accuracy, faithfulness, provenance).
- **Add a claim**: append to `data/claims.json` + a label in
  `fraud_agent/eval/dataset.py` and see if the agent catches it.
- **Live Run (portfolio)**: run segment `BRO-W / ALL / ALL` and watch
  the assembly agent drive the three stage sub-agents (28 submissions,
  15 UW reviews, 3 settlements) in one trace, then compose a margin
  thesis naming `reserve_adequacy` (claim stage) as the high-leverage
  lever with confidence ~84.
- **Live Run (portfolio)**: run segment `ALL / 5437 / ALL` — the agent
  picks `risk_score_override` (risk-scoring stage) as the lever at
  confidence ~99. Different segment, different lever, same skeleton.
- **▶️ Live Run — left panel (case blackboard)**: the agent's working
  memory fills live, synced with the run — 📋 case, 🔎 evidence, 🧩
  hypotheses, ⚖️ decision as sticky notes tagged by data origin
  (persisted vs graph vs model vs human), the numbered step rail, and
  the verdict when it lands. `risk_score_override`'s FLOWS_TO +
  PREDISPOSES edges carry weight/direction/lag exactly like the cost
  agent's driver→metric graph, but across a *journey*.
- **🧬 GraphRAG tab (portfolio)**: extract signal candidates from the
  8 UW committee memos; reject `settlement_slowness`, save curation,
  re-run the BRO-W segment eval — one PREDISPOSES edge leaves the
  citable set and confidence shifts.
- **🎓 Learning tab (portfolio)**: validate the 8 PREDISPOSES signals
  vs `data/portfolio_outcomes_nextq.json`. `broker_pattern` is
  contradicted (BRO-W's loss ratio was actually fine — the override on
  5437 was the cause, not the broker) and decays; `settlement_slowness`
  is contradicted too (a planted distractor). Eight others are
  reinforced. Approve → assembly eval still matches ground truth but
  confidence redistributes between the surviving signals.
- **Eval Lab (portfolio)**: a third seven-axis verdict — stage sub-agent
  accuracy + citation recall, assembly verdict accuracy + **margin-thesis
  stage match** + provenance coverage.
- **Multi-agent composition**: compare the assembly agent's loop
  (`portfolio_agent/assembly/loop.py`) with a single-stage loop. The
  `run_*` steps drive the three sub-harnesses via `run_auto` — the
  first time in the project the *harness is itself used as a tool*.

## Data

All data is synthetic. The fraud and cost agents ship ~14 claims, a
quarterly metric warehouse with planted trends (parts inflation,
Northeast litigation, a 2024Q3 hurricane, a polar-vortex distractor),
two knowledge graphs (fraud entities; cost driver tree + semantic
layer), and 8 source memos that "ground" the cost-graph with
provenance. The portfolio agent adds a third warehouse: **7 linked
fact tables** (~117 submissions / 69 binds / 18 claims / 18 settlements)
with planted patterns that span stage boundaries — incomplete BRO-W
exposure intake, 5437 risk-score overrides hand-in-hand with waived
inspection flags, late FNOL on 5437, low reserves driving settlement
leakage — plus a stage-flow lineage graph
(`data/portfolio_entities.json`, FLOWS_TO + PREDISPOSES edges) and 8
UW-committee memos that ground the signals with provenance. The Neo4j
GraphRAG layer adds seeded demo-scale graphs (`data/neo4j_*.json`:
~200 claimants / 8 fraud rings / 6 scam patterns / 23 SIU-NICB-audit
memos; a cost causal event layer; a portfolio instance journey layer)
with planted ground truth and distractors — regenerable with
`python scripts\generate_neo4j_demo_data.py`.

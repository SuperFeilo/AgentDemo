# 🧠 Agent Anatomy Explorer — two agents, one skeleton

A **teaching project** for learning how AI agents are put together. Every
component of "agent anatomy" is a real, readable piece of code, and a
Streamlit UI lets you watch them cooperate — in **two different agents**:

- 🕵️ **Fraud Investigator** — decides APPROVE / REVIEW / ESCALATE on
  (synthetic) insurance claims; pauses for human approval before filing
  an SIU case.
- 📈 **Cost Trend Analyst** — answers analytic research questions
  ("why is Northeast BI severity rising?") using a SQLite warehouse for
  numbers and a driver knowledge graph for honest, cited explanations.

Both share one skeleton: goal → plan → skills → loop → tools → harness →
lifecycle → knowledge graph → eval. Brains are **deterministic**
(rule-based + mock-LLM heuristics) — no API keys, fully reproducible
evals. Clearly marked seams show where a real LLM would plug in
(`fraud_agent/brain/notes_llm.py`, `cost_agent/graphrag/extractor.py`).

## Quick start

```powershell
cd C:\Users\mingm\FraudAgent
.\.venv\Scripts\Activate.ps1
streamlit run app/main.py          # pick the agent in the sidebar
```

Headless evals (no UI):

```powershell
python -m fraud_agent.eval.runner        # fraud: precision/recall/F1
python -m cost_agent.eval.runner         # analyst: citations/numeric/provenance
python -m fraud_agent.learning           # outcome analysis (dry run; --apply writes)
python -m cost_agent.learning            # driver validation (dry run; --apply writes)
python scripts\test_graphrag.py          # GraphRAG: extraction + curation impact
python scripts\test_packs.py             # all pack features: 22 checks
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
| **Case blackboard** | `fraud_agent/blackboard.py` | Typed working memory (case/evidence/hypotheses/decision); every write journaled with its data origin. |
| **Determination dossier** | `fraud_agent/dossier.py` | One auditable artifact per run — case → skills → thoughts → data by origin → decision → cost. JSON/MD export. |
| **Autonomy gate** | tool registry (`autonomy=`) + `fraud_agent/harness.py` | Gated tools pause for human approval; per-run autonomy slider (full/gated/step). |
| **Cost control** | harness metering + `max_cost_units` in goal yamls | Real latency timing + declared per-tool cost units; budget aborts runs. |
| **Reflection** | `skills*/verification.md` + `reflect` plan step | Ng's pattern: the agent re-derives its own numbers/scores before deciding; self-corrects. |
| **Learning loop** | `*/learning.py` + `data/outcomes*` | Decisions scored vs real outcomes → weight proposals → human approval → eval delta. See `docs/CONTINUOUS_LEARNING.md`. |
| **Harness** | `fraud_agent/harness.py` | Executes tools, enforces budgets, records the trace. |
| **Lifecycle** | `fraud_agent/lifecycle.py` | Run state machine + registry; human-checkpoint pause/resume. |
| **Eval** | `fraud_agent/eval/` | Labeled dataset, batch runner, precision/recall/F1. |

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
- **Skills**: edit a playbook in `skills/` and watch behaviour change;
  scoring weights live in `config/fraud_weights.yaml` as data.
- **Eval Lab**: sweep the fraud flag threshold to trade precision for
  recall; compare with the analyst's four-axis eval (citation
  precision/recall, numeric accuracy, faithfulness, provenance).
- **Add a claim**: append to `data/claims.json` + a label in
  `fraud_agent/eval/dataset.py` and see if the agent catches it.

## Data

All data is synthetic: 14 claims covering classic fraud patterns
(velocity, rings, fresh policies, contradictory notes), a quarterly
metric warehouse with planted trends (parts inflation, Northeast
litigation, a 2024Q3 hurricane, a polar-vortex distractor), two
knowledge graphs (fraud entities; cost driver tree + semantic layer),
and 8 source memos that "ground" the driver graph with provenance.

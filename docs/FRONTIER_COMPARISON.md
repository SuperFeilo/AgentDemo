# Frontier Research Comparison — how this project maps onto the published AI-agent canon

A position paper for the Agent Anatomy Explorer: what the project
implements, which published agent-workflow research it instantiates,
where it *goes beyond* the frontier work, and a roadmap of the frontier
concepts it deliberately leaves out — with the exact seam each one
would plug into.

Companion artifact: the same content is rendered interactively in the
app (🗺️ **Frontier map**, Home → Getting started).

---

## 1 · TL;DR

This project is an unusually complete, pedagogically honest
implementation of the 2024–2026 practitioner canon — **Anthropic's
workflow/agent patterns, Ng's agentic design patterns, and the
LangChain harness/loop engineering school** — with the policy moved
into *deterministic, auditable code* instead of an opaque model call.

Two things in the project are **ahead of** the published frontier work
it cites:

1. **Curation-enforced retrieval** — human rejection of a knowledge
   node is enforced *inside* every graph query (`WHERE n.id IN
   $approved`), so knowledge state provably changes agent performance.
   Microsoft GraphRAG (the closest published system) has no governance
   layer like this.
2. **Weights-as-data learning with human gates** — behavior updates
   (weights, graph edges) are data files, proposed by an outcome
   analysis, gated by a human, and verified by before/after eval. This
   is approval-directed update at a level most published agents do not
   ship.

Its main frontier gap is **policy-level learning**: nothing in the
project tunes the model itself (no RL, no skill synthesis, no
multi-round self-improvement), and the multi-agent worker orchestration
is sequential rather than parallel.

---

## 2 · The anatomy map vs. the research canon

The project's shared 12-component skeleton (goal → plan → skills →
loop → brains → tools → harness → lifecycle → graph knowledge →
blackboard → dossier → eval/learning) is, component by component, a
concrete instantiation of published work:

| Project component | Where | Frontier research it instantiates | Verdict |
|---|---|---|---|
| **Goal** (`config/*.yaml`) | success criteria, budgets, thresholds as data | CoALA (Sumers et al., 2023) — goal as part of the decision procedure; Anthropic "stopping conditions" | Faithful, sharper (constraints are enforced by the harness, not suggested) |
| **Plan** (`*/planner.py`) | goal + skills → ordered steps | Ng's *Planning* pattern (2024); LangChain plan-and-execute (Chase, 2024); Anthropic "planning steps" | Faithful; static per domain with conditional step-skipping |
| **Skills** (`skills*/*.md`) | markdown playbooks: when to act, which tool, how to score | CoALA *procedural memory*; Voyager (Wang et al., 2023) skill library | Partially — static playbooks, no skill *synthesis* (gap §5.2) |
| **Loop** (`*/loop.py`) | observe→think→act generator; yields events, receives results via `.send()` | ReAct (Yao et al., ICLR 2023); Anthropic *agents* ("LLMs using tools based on environmental feedback in a loop"); LangChain *The Art of Loop Engineering* (Runkle, 2026): discover→plan→execute | Faithful to ReAct; the generator/send design is a *pedagogical improvement* for interactive stepping |
| **Brains** (`*/brain/`) | rule-based policy + mock-LLM seams | DeepSeek-R1 / OpenAI Agents / Zaremba tool-use RL — LLM-as-policy | **Deliberate divergence**: deterministic policy for reproducible evals; seams marked where a real LLM plugs in (gap §5.1) |
| **Tools** (`*/tools/registry.py`) | schemas + impls, single execution choke point; `autonomy=` per tool | Anthropic ACI / tool design appendix (2024); MCP (Anthropic, 2024); Howard / Answer.AI deterministic tool allow-lists (2026) | Faithful; the `autonomy=` flag on the registry is a governance feature the canon does not standardize |
| **Harness** (`*/harness.py`) | executes tools, enforces budgets, meters cost/latency, records traces, drives lifecycle | LangChain *The Anatomy of an Agent Harness* (Trivedy, 2026): "Agent = Model + Harness"; orchestration loop, tool layer, memory timescales | **Near 1:1** with the published harness definition; the README's 12-component skeleton is essentially Trivedy's harness decomposition |
| **Lifecycle** (`*/lifecycle.py`) | state machine + registry; checkpoint pause/resume | LangGraph interrupts/checkpointing; Anthropic "pause for human feedback at checkpoints" | Faithful |
| **Graph knowledge** (`knowledge/graph.py`, `data/*_entities.json`, `graphrag_neo4j/`) | entities, driver trees, causal chains, stage lineage as queryable data | Microsoft GraphRAG (Edge et al., arXiv:2404.16130); causal-chain/root-cause retrieval | **Divergence with an upgrade**: domain-authored synthetic graphs + deterministic traversal instead of LLM-built entity graphs + community summaries; adds curation enforced *inside queries* (§4.1) |
| **Blackboard** (`blackboard.py`) | typed working memory, every write journaled with data origin | CoALA *working memory*; Anthropic context engineering (2025); MemGPT (Packer et al., 2023) | Faithful and *stricter*: typed + origin-tagged + append-only, which CoALA's unconstrained stores are not |
| **Dossier** (`dossier.py`) | one auditable artifact per run (JSON/MD) | CoALA *episodic memory*; LangChain loop engineering *observability* | Faithful |
| **Reflection** (`reflect` plan step + `verification.md` skills) | re-derives its own numbers/scores before deciding | Ng's *Reflection* pattern (2024); Self-Refine (Madaan et al., 2023); Karpathy *Verifiability* (2025) | Faithful but single-pass, deterministic verifier — not multi-round LLM critique (gap §5.3) |
| **Eval** (`*/eval/`) | labeled datasets, batch runner, precision/recall/F1, regression suite | Karpathy "Software 2.0 easily automates what you can verify"; AgentBench-style task suites | Faithful; domain-deterministic rather than frontier-benchmark or LLM-as-judge (gap §5.6) |
| **Learning loop** (`*/learning.py`) | outcomes → proposals → human approval → weights-as-data → eval delta | Approval-directed updates; Zaremba verifiability + delegation; offline RL/DPO-family weight updates | Same *skeleton* as frontier learning loops, but heuristic weight nudges, not gradient/RL updates (gap §5.1) |

---

## 3 · The three implementation styles vs. pattern taxonomies

Each agent demonstrates a different published pattern family, on the
determinism ↔ agency spectrum:

| Agent | Topology | Anthropic (2024) | Ng (2024) | LangChain (2024–2026) | Research it *is* |
|---|---|---|---|---|---|
| 🕵️ **Fraud** | linear chain | *Workflow*: prompt chaining + evaluator-optimizer + gates | Reflection + Planning | plan-and-execute; deterministic node scale | A deterministic *workflow* with a verifier step and a human gate — the "predictable, auditable" end of the spectrum |
| 📈 **Cost** | cycle | *Agent*: autonomous loop with tool use, ground-truth at each step | Tool Use | ReAct loop + evaluator-optimizer; loop engineering "task loop + verification loop" | Textbook ReAct agent (Yao et al. 2023) incl. the inner *iterate-until-exhausted* evidence loop |
| 🎯 **Portfolio** | fan-out → synthesize | *Workflow*: orchestrator-workers | Multi-agent collaboration | "a node can be a full agent run"; Zaremba delegation | Orchestrator-workers (Anthropic) + AutoGen-style (Wu et al., 2023) multi-agent — hedged per the MAST failure taxonomy (Cemri et al., arXiv:2503.13657) |

The portfolio agent is also a live demonstration of why multi-agent
systems are hard: the Berkeley **MAST** taxonomy (Cemri et al., 2025)
catalogs 14 failure modes in 3 families — *system design, inter-agent
misalignment, task verification*. The project's design choices are
exactly the mitigations that paper would prescribe:

- workers are **deterministic sub-harnesses** (removes model-level
  misalignment between agents),
- the assembly loop **aggregates verdicts and marks them as
  `model_brain` origin** on the blackboard (makes the sub-agent result
  a *cited fact*, not a raw opinion),
- a **reflect + provenance-coverage eval axis** verifies the assembly
  task.

And it keeps the honest tradeoff the literature reports: coordination
overhead and the hardest-to-trace/eval trace — which is precisely why
Anthropic and MAST both say "prefer a single agent unless parallel
specialization demonstrably wins."

---

## 4 · Where the project goes *beyond* the cited research

### 4.1 Curation-enforced retrieval

GraphRAG (Microsoft) retrieves from an LLM-built graph but has no
governance: rejected knowledge still *exists* in the index. Here,
rejection is a first-class operation:

- `data/*_graph_approval.json` is shared by agent tools **and** the
  Neo4j query library;
- every read enforces `WHERE n.id IN $approved OR n.curated = true`
  — *rejected nodes are invisible to retrieval*, not just
  de-prioritized;
- the 🧬 GraphRAG tab demonstrates the causal link: reject
  `adas_complexity`, re-run Q1, the verdict degrades to PARTIALLY
  EXPLAINED. **Knowledge state is agent performance** — a property
  frontier GraphRAG papers describe but do not operationalize.

### 4.2 Weights-as-data learning with a human gate

The continuous learning loop (`docs/CONTINUOUS_LEARNING.md`) makes the
agent's *beliefs* data:

- scoring weights live in `config/fraud_weights.yaml`; graph edge
  weights live in `data/*_entities.json`;
- `*/learning.py` scores past decisions against real outcomes and
  proposes changes; nothing applies without human approval;
- before/after eval shows the delta; the evidence ledger is
  append-only.

This is approval-directed weight updating — simple, auditable, and
explicitly safer than autonomous self-modification for a system that
decides about people (claims denied, cases escalated). Frontier RL-based
updates (DPO, tool-use RL) do the same math with gradients; this project
shows the *governance skeleton* without the training machinery.

### 4.3 Pedagogy: the generator loop

The loop is a Python **generator**: it yields every thought/tool
call/observation and receives results back via `.send()`. That one
design choice is what makes the whole app possible — step, autoplay,
human-gate injection, live anatomy-map pulsing, and full run
serialization are all the *same* code path as headless eval. Published
harness descriptions (Trivedy 2026; Runkle 2026) describe this
interactivity as a property to have; here it is the loop's native shape.

### 4.4 Dual-mode Neo4j

Real Cypher against a live Neo4j *or* an identical networkx fallback —
one query library, both modes, same semantics. This mirrors the
project's mock-LLM philosophy and keeps evals reproducible offline.
No published GraphRAG work ships a drop-in deterministic fallback of
its query semantics.

### 4.5 The autonomy slider as a UI control

Karpathy's autonomy slider (full / gated / step) is a real control
that changes harness behavior per run — including the human-gate
checkpoints that pause the lifecycle. Frontier descriptions of
autonomy are typically policy-level; here it is an operational dial.

---

## 5 · Gap analysis — frontier concepts the project omits, and the roadmap

Each row: what the frontier does → where the project would accept it →
the existing seam to extend. Ordered roughly by leverage for a
*teaching* project.

### 5.1 LLM-as-policy / RL-tuned policies

- **Frontier:** DeepSeek-R1, OpenAI "Agents", Zaremba et al. tool-use
  RL train the *policy itself*; verifiability scores turn into
  gradient updates.
- **Here:** the brain is deterministic rule-based; the LLM writes
  narrative commentary and extracts graph intel only.
- **Roadmap:** swap the brains behind `brain/notes_llm.py` /
  `cost_agent/graphrag/extractor.py` (the marked seams) — but keep the
  *harness* and *reflection* unchanged. The clean demo of "policy is
  replaceable" is the project's core thesis already.

### 5.2 Skill synthesis (Voyager-style)

- **Frontier:** Voyager (Wang et al., 2023) stores *composed* skills
  and grows a library via automatic curriculum.
- **Here:** skills are static markdown; the learning loop only nudges
  weights.
- **Roadmap:** the learning loop's proposal stage could *draft a new
  `skills/*.md` playbook* (e.g. a newly-validated driver's playbook)
  for human approval — the outcome→proposal→human→apply pipeline
  already exists in `*/learning.py`.

### 5.3 Multi-round reflection / episodic memory (Reflexion, Self-Refine)

- **Frontier:** Reflexion (Shinn et al., NeurIPS 2023) stores verbal
  feedback in episodic memory and *re-attempts*; Self-Refine loops
  generate→critique→refine.
- **Here:** `reflect` is a single-pass deterministic verifier.
- **Roadmap:** add an episodic store keyed by claim/question id in
  `data/traces/`, and let the `reflect` step replay the previous
  episode's corrections when the same subject re-runs — the traces
  already contain everything needed.

### 5.4 Parallel orchestrator–workers

- **Frontier:** Anthropic's orchestrator-workers fan out in parallel;
  sectioning for independent subtasks.
- **Here:** `brain.run_sub_agent` drives sub-harnesses sequentially
  (`run_auto` in a loop).
- **Roadmap:** run the three stage sub-agents in threads (they already
  touch disjoint warehouses) and aggregate in the same
  `run_*` → observation step. A "workers completed in N seconds vs
  serial" caption would teach the latency tradeoff literally.

### 5.5 Routing / model cascades

- **Frontier:** Anthropic's routing workflow (small model for easy
  cases, big model for hard ones).
- **Here:** one policy for every case.
- **Roadmap:** a route on `note_count`/`fraud_links` depth choosing
  between mock-LLM vs real LLM (`llm_client.available()`) would
  demonstrate the cost/latency tradeoff with the existing spend
  ledger.

### 5.6 Frontier benchmarks & LLM-as-judge eval

- **Frontier:** SWE-bench, GAIA, AgentBench; evaluator-LLM scoring.
- **Here:** deterministic domain evals (deliberate — "no judge, no
  opinions").
- **Roadmap:** keep the deterministic evals as the release gate, and
  add an optional LLM-as-judge pass (DeepSeek via `llm_client`) whose
  agreement vs the deterministic gate is reported — the project's own
  "verifiability" argument made measurable.

### 5.7 Context-window paging (MemGPT)

- **Frontier:** MemGPT pages memory across a context budget.
- **Here:** the blackboard grows without bound.
- **Roadmap:** make the blackboard's `max_entries` real and add a
  paging/compaction policy (evict oldest `evidence`, summarize into
  `hypotheses`) — a natural lesson in context engineering (Anthropic,
  2025).

### 5.8 Sandboxed tool execution

- **Frontier:** agents run tools in sandboxes (browser/code exec) with
  strict permissions.
- **Here:** `call_tool` executes in-process.
- **Roadmap:** the registry's single choke point
  (`tools/registry.py:call_tool`) is the perfect seam for a
  permission/sandbox layer — including the Answer.AI "unauthorized
  tool call" defense-in-depth discussion.

### 5.9 Durable checkpoint persistence

- **Frontier:** LangGraph persists graph state so runs resume across
  processes.
- **Here:** runs live in the in-memory `RunRegistry`; traces are
  written to disk but the run itself is not resumable.
- **Roadmap:** serialize a paused `Run` (events + blackboard + plan
  index) to `data/traces/` and resume on load — the dossier already
  contains the full event stream.

---

## 6 · Sources (verified July/Aug 2026)

| Reference | Type | Link |
|---|---|---|
| Anthropic, "Building Effective Agents" (Dec 2024) | engineering post | https://www.anthropic.com/research/building-effective-agents |
| Anthropic, Model Context Protocol (Nov 2024) | protocol | https://www.anthropic.com/news/model-context-protocol |
| Andrew Ng, "Agentic Design Patterns" (DeepLearning.AI, 2024) | course | https://www.deeplearning.ai/the-batch/agentic-design-patterns-the-key-to-ai-agents/ |
| Harrison Chase, plan-and-execute agents (2024) | blog | https://blog.langchain.dev/plan-and-execute-agents/ |
| Vivek Trivedy (LangChain), "The Anatomy of an Agent Harness" (Mar 2026) | blog | https://www.langchain.com/blog/the-anatomy-of-an-agent-harness |
| Sydney Runkle (LangChain), "The Art of Loop Engineering" (Jun 2026) | blog | https://www.langchain.com/blog/the-art-of-loop-engineering |
| Yao et al., "ReAct" (ICLR 2023) | paper | https://arxiv.org/abs/2210.03629 |
| Shinn et al., "Reflexion" (NeurIPS 2023) | paper | https://arxiv.org/abs/2303.11366 |
| Madaan et al., "Self-Refine" (2023) | paper | https://arxiv.org/abs/2303.17651 |
| Sumers et al., "Cognitive Architectures for Language Agents" (CoALA, 2023) | paper | https://arxiv.org/abs/2309.02427 |
| Wang et al., "Voyager" (2023) | paper | https://arxiv.org/abs/2305.16291 |
| Park et al., "Generative Agents" (2023) | paper | https://arxiv.org/abs/2304.03442 |
| Wu et al., "AutoGen" (2023) | paper | https://arxiv.org/abs/2308.08155 |
| Packer et al., "MemGPT" (2023) | paper | https://arxiv.org/abs/2310.08560 |
| Edge et al. (Microsoft), "From Local to Global: A Graph RAG Approach to Query-Focused Summarization" (2024) | paper | https://arxiv.org/abs/2404.16130 |
| Cemri et al. (Berkeley), "Why Do Multi-Agent LLM Systems Fail?" (MAST taxonomy, 2025) | paper | https://arxiv.org/abs/2503.13657 |
| Karpathy, "Verifiability" & "2025 LLM Year in Review" (2025) | essay | https://karpathy.github.io/2025/12/13/2025-year-in-review/ |
| Zaremba et al., "Teaching Large Language Models to Reason with Reinforcement Learning" (OpenAI, 2025) | paper | https://arxiv.org/abs/2503.13365 |
| OpenAI, "Agents" — teaching via human approval (2025) | paper | https://openai.com/index/teaching-models-to-plan-and-reason-with-openai-agents/ |
| Howard / Answer.AI, "The unauthorized tool call problem" (2026) | essay | https://www.answer.ai/posts/2026-01-27-the-unauthorized-tool-call.html |

Note: the README's "Implementation styles" and the Home page cite the
same lineage (Ng, Anthropic, Chase, Karpathy, Zaremba, Answer.AI) — this
document expands those citations into a full comparison and is the
canonical source for the 🗺️ **Frontier map** page.

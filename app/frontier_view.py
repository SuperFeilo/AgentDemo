"""🗺️ Frontier map — this project vs. published agent-workflow research.

Reads the same content as docs/FRONTIER_COMPARISON.md (that doc is the
canonical source; the tables below mirror it for rendering). Renders
five tabs: Anatomy map vs the canon · The three styles · Beyond the
frontier · Gap roadmap · Sources.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app import ui
from app.anatomy_map import STYLES

# ── §2 · the anatomy map vs. the research canon ───────────────────────
ANATOMY_ROWS = [
    ("🎯 Goal", "config/*.yaml", "CoALA (Sumers et al. 2023); Anthropic stopping conditions",
     "Faithful — budgets/thresholds enforced by the harness"),
    ("📝 Plan", "*/planner.py", "Ng Planning (2024); LangChain plan-and-execute (2024)",
     "Faithful — static per domain + conditional step-skipping"),
    ("📚 Skills", "skills*/*.md", "CoALA procedural memory; Voyager skill library (2023)",
     "Partial — static playbooks, no skill synthesis (gap §5.2)"),
    ("🔁 Loop", "*/loop.py", "ReAct (Yao et al. 2023); Anthropic agents; Runkle loop engineering (2026)",
     "Faithful — generator/.send() design is a pedagogy upgrade"),
    ("🧠 Brains", "*/brain/", "LLM-as-policy: DeepSeek-R1, Zaremba tool-use RL (2025)",
     "Deliberate divergence — deterministic policy, marked LLM seams"),
    ("🧰 Tools", "tools/registry.py", "Anthropic ACI appendix (2024); MCP (2024); Answer.AI allow-lists (2026)",
     "Faithful — per-tool autonomy= flag not standardized in the canon"),
    ("🛟 Harness", "*/harness.py", "Trivedy, 'The Anatomy of an Agent Harness' (LangChain, 2026)",
     "Near 1:1 with the published harness definition"),
    ("⏱️ Lifecycle", "lifecycle.py", "LangGraph interrupts; Anthropic human checkpoints",
     "Faithful"),
    ("🕸️ Graph", "graphrag_neo4j/, data/*_entities.json",
     "Microsoft GraphRAG (Edge et al. arXiv:2404.16130); causal chains",
     "Divergence + upgrade — curation enforced inside queries (§4.1)"),
    ("🗂️ Blackboard", "blackboard.py", "CoALA working memory; Anthropic context engineering (2025)",
     "Faithful and stricter — typed, origin-tagged, append-only"),
    ("📄 Dossier", "dossier.py", "CoALA episodic memory; loop-engineering observability (2026)",
     "Faithful"),
    ("🧭 Reflection", "reflect step + verification.md", "Ng Reflection (2024); Self-Refine (2023); Karpathy Verifiability (2025)",
     "Faithful — single-pass deterministic verifier (gap §5.3)"),
    ("📊 Eval", "*/eval/", "Karpathy verifiability; AgentBench-style suites",
     "Faithful — domain-deterministic, no LLM-as-judge (gap §5.6)"),
    ("🎓 Learning", "*/learning.py", "Approval-directed updates; DPO/tool-use RL family",
     "Same skeleton as frontier loops — heuristic nudges, not gradients (§5.1)"),
]

# ── §3 · the three styles vs. pattern taxonomies ──────────────────────
STYLE_ROWS = [
    ("🕵️ Fraud", "linear chain", "Workflow: prompt chaining + evaluator-optimizer + gates",
     "Reflection + Planning", "plan-and-execute; deterministic node scale",
     "Anthropic workflow — predictable, auditable end of the spectrum"),
    ("📈 Cost", "cycle (ReAct)", "Agent: autonomous tool-use loop, ground truth each step",
     "Tool Use", "ReAct loop + evaluator-optimizer; task loop + verification loop",
     "Textbook ReAct (Yao et al. 2023) incl. iterate-until-exhausted evidence"),
    ("🎯 Portfolio", "fan-out → synthesize", "Workflow: orchestrator–workers",
     "Multi-agent collaboration", "'a node can be a full agent run'; Zaremba delegation",
     "Orchestrator-workers + AutoGen; hedged per MAST (Cemri et al. 2025)"),
]

# ── §4 · beyond the frontier ──────────────────────────────────────────
BEYOND_ROWS = [
    ("Curation-enforced retrieval",
     "Rejected knowledge nodes are excluded inside every graph query "
     "(`WHERE n.id IN $approved`); the GraphRAG tab shows rejection "
     "changing the verdict. GraphRAG itself has no such governance."),
    ("Weights-as-data learning with a human gate",
     "Beliefs live in YAML/JSON; outcomes → proposals → human approval → "
     "eval delta. Approval-directed updating, fully auditable."),
    ("The generator loop",
     "Yield/send makes step, autoplay, human gates, live anatomy pulsing "
     "and headless eval the same code path — interactivity as the loop's "
     "native shape."),
    ("Dual-mode Neo4j",
     "One query library: real Cypher on a live server or an identical "
     "networkx fallback — reproducible offline evals."),
    ("Autonomy slider as a UI control",
     "Karpathy's full/gated/step autonomy is an operational dial that "
     "changes harness gating per run."),
]

# ── §5 · gap analysis roadmap ─────────────────────────────────────────
GAP_ROWS = [
    ("LLM-as-policy / RL", "DeepSeek-R1, OpenAI Agents, Zaremba tool-use RL train the policy",
     "Deterministic rule-based brains; LLM writes commentary / extracts graphs",
     "brain/notes_llm.py · graphrag/extractor.py (the marked seams)"),
    ("Skill synthesis", "Voyager composes and grows a skill library",
     "Static markdown playbooks; learning loop only nudges weights",
     "*/learning.py proposal stage drafts new skills/*.md for human approval"),
    ("Multi-round reflection", "Reflexion stores verbal feedback in episodic memory and re-attempts",
     "Single-pass deterministic verifier (reflect step)",
     "Episodic store over data/traces/; replay prior corrections on re-run"),
    ("Parallel workers", "Anthropic orchestrator-workers fan out in parallel",
     "Sub-harnesses driven sequentially via run_auto",
     "portfolio_agent/assembly/brain.py run_sub_agent → thread the 3 stages"),
    ("Routing / cascades", "Anthropic routing: small model for easy, big for hard",
     "One policy for every case",
     "Route on note_count / fraud_links depth; llm_client.available()"),
    ("Frontier benchmarks", "SWE-bench, GAIA, AgentBench; LLM-as-judge scoring",
     "Deterministic domain evals (deliberate)",
     "Optional LLM-as-judge pass via llm_client vs the deterministic gate"),
    ("Context paging", "MemGPT pages memory across a context budget",
     "Blackboard grows without bound",
     "blackboard.py max_entries + eviction/compaction policy"),
    ("Sandboxed tools", "Tools run in sandboxes with strict permissions",
     "call_tool executes in-process",
     "tools/registry.py call_tool → permission/sandbox layer"),
    ("Durable checkpoints", "LangGraph persists state; runs resume across processes",
     "In-memory RunRegistry; traces written but runs not resumable",
     "Serialize paused Run to data/traces/ and resume on load"),
]

# ── §6 · sources ──────────────────────────────────────────────────────
SOURCES = [
    ("Anthropic — Building Effective Agents", "engineering post, Dec 2024",
     "https://www.anthropic.com/research/building-effective-agents"),
    ("Anthropic — Model Context Protocol", "protocol, Nov 2024",
     "https://www.anthropic.com/news/model-context-protocol"),
    ("Andrew Ng — Agentic Design Patterns", "DeepLearning.AI course, 2024",
     "https://www.deeplearning.ai/the-batch/agentic-design-patterns-the-key-to-ai-agents/"),
    ("Chase — plan-and-execute agents", "LangChain blog, 2024",
     "https://blog.langchain.dev/plan-and-execute-agents/"),
    ("Trivedy — The Anatomy of an Agent Harness", "LangChain blog, Mar 2026",
     "https://www.langchain.com/blog/the-anatomy-of-an-agent-harness"),
    ("Runkle — The Art of Loop Engineering", "LangChain blog, Jun 2026",
     "https://www.langchain.com/blog/the-art-of-loop-engineering"),
    ("Yao et al. — ReAct", "ICLR 2023", "https://arxiv.org/abs/2210.03629"),
    ("Shinn et al. — Reflexion", "NeurIPS 2023", "https://arxiv.org/abs/2303.11366"),
    ("Madaan et al. — Self-Refine", "2023", "https://arxiv.org/abs/2303.17651"),
    ("Sumers et al. — CoALA", "2023", "https://arxiv.org/abs/2309.02427"),
    ("Wang et al. — Voyager", "2023", "https://arxiv.org/abs/2305.16291"),
    ("Park et al. — Generative Agents", "2023", "https://arxiv.org/abs/2304.03442"),
    ("Wu et al. — AutoGen", "2023", "https://arxiv.org/abs/2308.08155"),
    ("Packer et al. — MemGPT", "2023", "https://arxiv.org/abs/2310.08560"),
    ("Edge et al. — Graph RAG (Microsoft)", "2024", "https://arxiv.org/abs/2404.16130"),
    ("Cemri et al. — Why Do Multi-Agent LLM Systems Fail? (MAST)", "2025",
     "https://arxiv.org/abs/2503.13657"),
    ("Karpathy — Verifiability; 2025 LLM Year in Review", "2025",
     "https://karpathy.github.io/2025/12/13/2025-year-in-review/"),
    ("Zaremba et al. — Teaching LLMs to Reason with RL", "OpenAI, 2025",
     "https://arxiv.org/abs/2503.13365"),
    ("OpenAI — Agents: teaching via human approval", "2025",
     "https://openai.com/index/teaching-models-to-plan-and-reason-with-openai-agents/"),
    ("Howard / Answer.AI — The unauthorized tool call problem", "2026",
     "https://www.answer.ai/posts/2026-01-27-the-unauthorized-tool-call.html"),
]


def frontier_page() -> None:
    st.set_page_config(page_title="Frontier map · Agent Anatomy Explorer",
                       page_icon="🗺️")
    st.markdown(
        '<div class="pagehead"><div class="phicon">🗺️</div>'
        '<div><div class="phtitle">Frontier map</div>'
        '<div><span class="stylebadge" style="background:'
        'rgba(59,130,246,.16);color:#93c5fd;">research comparison</span>'
        '<span class="archbadge">this project vs the agent canon</span>'
        '<span class="pagemuted">docs/FRONTIER_COMPARISON.md is canonical</span>'
        '</div></div></div>',
        unsafe_allow_html=True)
    st.markdown(
        '<div class="pagemuted">Every component of this project instantiates '
        "published agent-workflow research — and two of its ideas go beyond "
        "the frontier: <b>curation-enforced retrieval</b> and "
        "<b>weights-as-data learning with human gates</b>. The tabs map the "
        "project onto the canon, show where it diverges, and give a roadmap "
        "for the frontier concepts it deliberately omits.</div>",
        unsafe_allow_html=True)

    tab_anatomy, tab_styles, tab_beyond, tab_gaps, tab_sources = st.tabs(
        ["🧩 Anatomy vs the canon", "🔄 Three styles", "🚀 Beyond the frontier",
         "🗺️ Gap roadmap", "📚 Sources"])

    with tab_anatomy:
        ui.section("The 12-component skeleton, mapped to the research it instantiates")
        st.dataframe(pd.DataFrame(
            ANATOMY_ROWS,
            columns=["Component", "Where (real code)", "Research it instantiates",
                     "Verdict"]),
            hide_index=True, use_container_width=True)
        st.caption("Full prose version, including the exact citations, lives "
                   "in §2 of docs/FRONTIER_COMPARISON.md.")

    with tab_styles:
        ui.section("Three implementation styles, three published pattern families")
        cols = st.columns(3)
        for col, row in zip(cols, STYLE_ROWS):
            with col:
                st.markdown(f"**{row[0]}** — *{row[1]}*")
                st.markdown(f"**Anthropic:** {row[2]}")
                st.markdown(f"**Ng:** {row[3]}")
                st.markdown(f"**LangChain:** {row[4]}")
                st.markdown(f"**Verdict:** {row[5]}")
        ui.section("Why the portfolio style is the honest tradeoff")
        st.markdown(
            "Berkeley's **MAST taxonomy** (Cemri et al., arXiv:2503.13657) "
            "catalogs 14 multi-agent failure modes in 3 families — *system "
            "design, inter-agent misalignment, task verification*. This "
            "project ships the mitigations that paper would prescribe: "
            "deterministic workers (no model-level misalignment), "
            "aggregated verdicts posted with `model_brain` origin (sub-agent "
            "results become cited facts, not opinions), and a reflect + "
            "provenance-coverage eval axis for the assembly task. And it "
            "keeps the reported cost: coordination overhead and the "
            "hardest-to-trace eval — the reason Anthropic and MAST both say "
            "'prefer a single agent unless parallel specialization wins.'")
        st.caption("Grounding table: the styles' practitioner lineage is in "
                   "the README 'Implementation styles' section; §3 of "
                   "docs/FRONTIER_COMPARISON.md expands it.")

    with tab_beyond:
        ui.section("Where this project goes beyond the cited research")
        for title, desc in BEYOND_ROWS:
            st.markdown(f"**{title}** — {desc}")
        st.caption("§4 of docs/FRONTIER_COMPARISON.md has the full arguments, "
                   "with file-level pointers.")

    with tab_gaps:
        ui.section("Frontier concepts the project omits — and the seam for each")
        st.dataframe(pd.DataFrame(
            GAP_ROWS,
            columns=["Frontier concept", "What the frontier does",
                     "Here (current)", "Seam to extend"]),
            hide_index=True, use_container_width=True)
        st.caption("Ordered by teaching leverage; §5 of "
                   "docs/FRONTIER_COMPARISON.md expands each row into a "
                   "concrete roadmap step.")

    with tab_sources:
        ui.section("Sources (verified)")
        st.markdown("\n".join(
            f"- **{name}** — {kind}: [{url}]({url})" for name, kind, url in SOURCES))
        st.caption("Only URLs verified at the time of writing appear here; "
                   "the README's 'Implementation styles' cites the same "
                   "lineage at a glance.")

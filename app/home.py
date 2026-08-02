"""🏠 Home — pick an agent, understand the three styles.

The selection surface: hero, three agent cards (each switches into that
agent's Live Run), the implementation-styles overview (moved here from
the Anatomy page), and a how-to-run quickstart. Nothing agent-specific
lives on this page; the workspaces contain only their own agent.
"""
from __future__ import annotations

import streamlit as st

from app.anatomy_map import STYLES
from app import ui
from app.nav import get_pages

PITCH = {
    "fraud": ("A gated fraud investigation on synthetic claims — "
              "velocity, policy timing, fraud rings, adjuster notes — "
              "with a human checkpoint before any escalation."),
    "cost": ("An autonomous research analyst that answers 'why is the "
             "trend moving?' with cited, verifiable drivers from a "
             "SQLite warehouse + knowledge graph."),
    "portfolio": ("A multi-agent system: one assembly agent drives three "
                  "stage experts across the commercial-lines journey to "
                  "a margin thesis."),
}
WATCH = {
    "fraud": ("watch · the autonomy gate pause the run · the reflect step "
              "catch an injected bug · the dossier group data by origin"),
    "cost": ("watch · the think→act→observe ring spin · guarded SQL · "
             "citations scored against warehouse truth"),
    "portfolio": ("watch · the orchestrator fan out to three workers · "
                  "harness-as-tool · stage verdicts fill in"),
}


def home_page() -> None:
    st.set_page_config(page_title="Agent Anatomy Explorer",
                       page_icon="🧠")
    pages = get_pages()

    st.markdown(
        '<div class="hero"><h1>Agent Anatomy Explorer</h1>'
        '<div class="sub">Three insurance agents, one skeleton — '
        "step inside an agentic AI system and watch every component "
        "work. Real code, deterministic mock-LLMs, convincing synthetic "
        "data.</div></div>",
        unsafe_allow_html=True)

    ui.section("Pick an agent — three implementation styles, one skeleton")
    cols = st.columns(3)
    for col, agent in zip(cols, ("fraud", "cost", "portfolio")):
        meta = ui.AGENTS[agent]
        style = STYLES[agent]
        with col:
            st.markdown(
                f'<div class="agentcard"><div class="acicon">{meta["icon"]}'
                f'</div><div class="acname">{meta["name"]}</div>'
                f'<div><span class="stylebadge" style="background:'
                f'rgba(139,92,246,.16);color:#d8b4fe;">{meta["style"]}'
                f'</span><span class="archbadge">{meta["arch"]}</span></div>'
                f'<div class="acpitch">{PITCH[agent]}</div>'
                f'<div class="acwatch">{WATCH[agent]}</div></div>',
                unsafe_allow_html=True)
            if st.button(f"Enter {meta['name'].split()[0]}'s workspace",
                         use_container_width=True, key=f"home_{agent}"):
                st.switch_page(pages[agent]["live"])

    ui.section("The styles at a glance — where the tradeoffs live")
    st.caption("Every agent runs the same 12 components; each sits at a "
               "different point on the determinism ↔ agency spectrum "
               "(Anthropic 'workflows vs agents'; Chase's deterministic-"
               "to-agentic node scale). The tradeoffs are visible live: "
               "gated pauses for fraud, guarded SQL + verification for "
               "cost, fan-out for portfolio.")
    cols = st.columns(3)
    for col, agent in zip(cols, ("fraud", "cost", "portfolio")):
        s = STYLES[agent]
        with col:
            st.markdown(f"**{ui.AGENTS[agent]['name'].split()[0]}** — "
                        f"*{s['name']}*")
            st.progress(s["axis"], text="")
            st.caption("deterministic ⟵━━━━━━━╋━━━━━━━━━⟶ agentic")
            st.markdown(f"**✓ Where it wins** — {s['wins']}")
            st.markdown(f"**✗ What it costs** — {s['costs']}")

    ui.section("How to run")
    st.markdown(
        "1. **Enter an agent's workspace** (the cards above) — every "
        "agent has the same five pages: Anatomy, Live Run, Eval Lab, "
        "GraphRAG, Learning.\n"
        "2. **🎬 Guided demo** — in the sidebar, pick a scenario and "
        "press *Load & run*: controls pre-set, the run starts, a hint "
        "banner points your eyes at the right boxes.\n"
        "3. **Watch it think** — the system overview lights up as the "
        "trace flows; the blackboard fills on the left; the execution "
        "feed runs beside it. Advance with **⏭️ Step** in the sidebar's "
        "▶️ Run controls.\n"
        "4. **Read the code** — every component box opens the real "
        "source; the Anatomy page is the file map.\n"
        "5. **Verify & learn** — Eval Lab scores against ground truth; "
        "Learning proposes weight changes for human approval.")

    st.markdown(
        '<div class="footnote">Practitioner grounding: Ng\'s agentic '
        "design patterns (DeepLearning.AI, 2024) · Anthropic 'Building "
        "Effective Agents' (2024) · Harrison Chase / LangChain "
        "(plan-and-execute 2024; harness, loop & graph engineering "
        "2026) · Karpathy (verifiability 2025; autonomy slider) · "
        "Zaremba (verifiable reliability) · Howard / Answer.AI "
        "(deterministic guardrails). See README → Implementation "
        "styles.</div>",
        unsafe_allow_html=True)

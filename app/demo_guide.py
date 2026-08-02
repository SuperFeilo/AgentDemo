"""Guided demos — the waku-agent "things to try" table, in the UI.

Each scenario says what it shows, where to watch it, and what to expect.
"Load & run" pre-sets the Live Run controls and starts the run; the hint
banner then points your eyes at the right component boxes.

Scenario texts are grounded in the README's "Try this" list and the
practitioner styles documented in app/anatomy_map.py.
"""
from __future__ import annotations

import streamlit as st

# ── scenario catalogue (subject objects are resolved in main.py) ─────
GUIDES: dict[str, list[dict]] = {
    "fraud": [
        {"id": "f1", "title": "Autonomy gate — the human pause",
         "subject": "C-1011", "autonomy": "gated", "bug": False,
         "shows": "Karpathy's autonomy slider in action: the gated "
                  "siu_escalate tool pauses the run mid-loop.",
         "watch": "The 🛟 Harness + ⏱️ Lifecycle boxes pulse and the run "
                  "enters PAUSED. Approve → the dossier shows data grouped "
                  "by origin (persisted vs graph vs model vs human).",
         "expect": "ESCALATE (after you approve), lifecycle ESCALATED."},
        {"id": "f2", "title": "Reflection catches a bug",
         "subject": "C-1005", "autonomy": "full", "bug": True,
         "shows": "Ng's reflection pattern: the notes brain over-scores, "
                  "and the reflect step re-derives the numbers itself.",
         "watch": "The 🧠 Brain box pulses twice — the second time with a "
                  "red ⚠ SELF-CORRECTED card on the trace.",
         "expect": "corrected=True; final risk restored to the true signal "
                  "sum (55)."},
        {"id": "f3", "title": "Velocity + notes hedging",
         "subject": "C-1012", "autonomy": "full", "bug": False,
         "shows": "Two signals compounding: claim frequency (velocity) and "
                  "adjuster-notes hedging (mock-LLM).",
         "watch": "velocity_check and notes_analysis observations each "
                  "push the risk gauge; the Graph box stays dark.",
         "expect": "REVIEW at elevated risk from 2 signal groups."},
        {"id": "f4", "title": "Fraud-ring network traversal",
         "subject": "C-1006", "autonomy": "full", "bug": False,
         "shows": "Graph knowledge as a tool: the fraud_ring_network tool "
                  "walks the entity graph for known-fraud links.",
         "watch": "The 🕸️ Graph box lights in the component strip; the "
                  "fraud-ring subgraph chart appears under the overview.",
         "expect": "Known-fraud link(s) → risk jumps; verdict REVIEW/ESCALATE."},
        {"id": "f5", "title": "Fresh-policy timing flag",
         "subject": "C-1008", "autonomy": "full", "bug": False,
         "shows": "A single clean signal: policy in force only days before "
                  "the loss — 'insurance shopping' behavior.",
         "watch": "policy_timing observation; how the plan is the same but "
                  "the evidence differs per claim (deterministic style).",
         "expect": "REVIEW driven by policy timing alone."},
    ],
    "cost": [
        {"id": "c1", "title": "Why is Northeast BI severity rising?",
         "subject": "Q2", "autonomy": "full", "bug": False,
         "shows": "The research loop: decompose the question, find honest "
                  "drivers in the graph, verify each against the warehouse.",
         "watch": "The 🔁 Loop ring spins: catalog → trend → drivers → "
                  "gather evidence; the 📊 Eval box is the verification "
                  "ring (citations scored vs ground truth).",
         "expect": "EXPLAINED: parts inflation + Northeast litigation with "
                  "cited provenance."},
        {"id": "c2", "title": "The hurricane spike (episodic trend)",
         "subject": "Q3", "autonomy": "full", "bug": False,
         "shows": "Classifying a trend as episodic and citing the event "
                  "with provenance documents.",
         "watch": "driver_event returns the 2024Q3 hurricane with source "
                  "memos; the trend chart shows the spike shape.",
         "expect": "EXPLAINED via the hurricane causal chain."},
        {"id": "c3", "title": "The planted distractor",
         "subject": "Q5", "autonomy": "full", "bug": False,
         "shows": "Honesty under pressure: a plausible-but-wrong driver "
                  "(polar vortex) must be excluded.",
         "watch": "How the evidence step evaluates and rejects the "
                  "distractor driver; the verdict reflects what's actually "
                  "supported.",
         "expect": "Distractor excluded or verdict PARTIALLY EXPLAINED."},
    ],
    "portfolio": [
        {"id": "p1", "title": "Assembly drives three stage sub-agents",
         "subject": {"id": "A2", "segment": {"broker": "BRO-W",
                                             "class_code": "ALL",
                                             "region": "ALL"}},
         "autonomy": "full", "bug": False,
         "shows": "Orchestrator–workers (Anthropic) + harness-as-tool "
                  "(Chase): one assembly loop, three stage experts.",
         "watch": "The 🎛️ Assembly box fans out to 📥📋💸 worker boxes, "
                  "each firing its own plan/harness; then the funnel chart "
                  "and margin thesis.",
         "expect": "PROFIT EDGE IDENTIFIED — reserve_adequacy (claim stage) "
                  "as the lever, confidence ≈ 84."},
        {"id": "p2", "title": "Different segment, different lever",
         "subject": {"id": "A1", "segment": {"broker": "ALL",
                                             "class_code": "5437",
                                             "region": "ALL"}},
         "autonomy": "full", "bug": False,
         "shows": "Same skeleton, different conclusion: the lineage graph "
                  "points to the risk-scoring stage instead.",
         "watch": "predisposing_signals observation + the stage-verdict "
                  "table; confidence lands near 99.",
         "expect": "risk_score_override as the high-leverage lever."},
    ],
}


def render_guide(agent: str) -> None:
    """Sidebar panel: pick a scenario → 'Load & run' starts it."""
    st.sidebar.markdown("---")
    st.sidebar.markdown("🎬 **Guided demo**")
    guides = GUIDES[agent]
    labels = [g["title"] for g in guides]
    sel = st.sidebar.selectbox("Scenario", labels,
                               key=f"guide_sel_{agent}")
    g = next(x for x in guides if x["title"] == sel)
    st.sidebar.caption(f"**Shows:** {g['shows']}")
    st.sidebar.caption(f"**Watch:** {g['watch']}")
    st.sidebar.caption(f"**Expect:** {g['expect']}")
    if st.sidebar.button("▶️ Load & run scenario", type="primary",
                         use_container_width=True,
                         key=f"guide_load_{agent}"):
        st.session_state["guide_action"] = {"agent": agent, "guide": g}
        st.rerun()


def guide_hint(agent: str, guide: dict | None) -> str | None:
    """One-line hint banner for the Live Run tab."""
    if not guide:
        return None
    return f"🎬 **{guide['title']}** — watch: {guide['watch']}"

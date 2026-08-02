"""Shared UI kit — the design system every agent page uses.

One grammar across all five pages and all three agents: agent headers,
section headers, style badges, the floating sidebar run-controls deck,
the guided-demo panel and the spend ledger. Dark theme (see
.streamlit/config.toml); every custom component lives on the palette
defined here and in app/components.py.
"""
from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from fraud_agent.paths import DATA_DIR

# ── agent metadata (single source of truth for labels/colors) ────────
AGENTS = {
    "fraud": {
        "label": "🕵️ Fraud Investigator", "name": "Fraud Investigator",
        "icon": "🕵️", "color": "#60a5fa",
        "style": "Deterministic workflow", "arch": "linear chain",
        "tagline": "APPROVE · REVIEW · ESCALATE — a gated fraud investigation",
    },
    "cost": {
        "label": "📈 Cost Trend Analyst", "name": "Cost Trend Analyst",
        "icon": "📈", "color": "#fbbf24",
        "style": "Autonomous research loop", "arch": "think → act → observe",
        "tagline": "Why is the trend moving? A cited, verifiable explanation",
    },
    "portfolio": {
        "label": "🎯 Portfolio Journey Analyst", "name": "Portfolio Journey Analyst",
        "icon": "🎯", "color": "#c084fc",
        "style": "Orchestrator–workers", "arch": "fan-out → synthesize",
        "tagline": "One assembly agent driving three stage experts to a margin thesis",
    },
}

# ── chrome CSS — Streamlit + app-level polish (dark) ─────────────────
CHROME_CSS = """
<style>
[data-testid="stMainBlockContainer"] {padding-top: 1.2rem; padding-bottom: 4rem;}
[data-testid="stSidebar"] {border-right: 1px solid #22314f;}
[data-testid="stSidebar"] h3 {font-size: .9rem; letter-spacing: .04em;}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {color:#8ea0bd;}
h1, h2, h3 {letter-spacing: -0.02em;}
.stButton > button {border-radius: 10px; font-weight: 600;}
[data-testid="stMetricValue"] {font-weight: 700;}
[data-testid="stExpander"] {border-color: #22314f !important; background: rgba(20,29,51,.35);}
[data-testid="stDataFrame"] {border-radius: 8px; overflow: hidden;}
/* page header */
.pagehead {display:flex; align-items:center; gap:14px; margin: 6px 0 2px;}
.pagehead .phicon {font-size: 2.2rem; line-height:1;}
.pagehead .phtitle {font-size: 1.9rem; font-weight: 800; letter-spacing: -0.03em;
                    color: #e6ebf4; margin:0;}
.stylebadge {display:inline-block; font-size:.7rem; font-weight:700;
             letter-spacing:.05em; text-transform:uppercase;
             border-radius: 12px; padding: 2px 10px; margin-right:6px;}
.archbadge {display:inline-block; font-size:.7rem; font-weight:600;
            border-radius: 12px; padding: 2px 10px; margin-right:6px;
            background:#22314f; color:#a5b4cf;}
.sectiontitle {font-size:1.15rem; font-weight:700; color:#e6ebf4;
               margin: 1.4rem 0 .4rem; letter-spacing:-.01em;}
.pagemuted {color:#8ea0bd; font-size:.85rem;}
/* home */
.hero {margin: 1.2rem 0 .2rem;}
.hero h1 {font-size: 2.6rem; font-weight: 800; letter-spacing: -0.035em;
          background: linear-gradient(100deg,#60a5fa 0%,#a78bfa 45%,#fbbf24 100%);
          -webkit-background-clip: text; -webkit-text-fill-color: transparent;
          line-height:1.1;}
.hero .sub {color:#8ea0bd; font-size:1.05rem; margin-top:.4rem;}
.agentcard {border:1px solid #22314f; border-radius:14px; padding: 1.1rem 1.2rem;
            background: linear-gradient(160deg, rgba(20,29,51,.9), rgba(11,17,32,.7));
            height: 100%; display:flex; flex-direction:column;}
.agentcard:hover {border-color: #3d4d6f; transform: translateY(-2px);
                  transition: all .18s ease;}
.agentcard .acicon {font-size:1.9rem;}
.agentcard .acname {font-size:1.12rem; font-weight:700; color:#e6ebf4; margin-top:.3rem;}
.agentcard .acpitch {font-size:.85rem; color:#a5b4cf; margin-top:.35rem; flex:1;}
.agentcard .acwatch {font-size:.78rem; color:#8ea0bd; margin-top:.5rem;}
.agentcard .acbtn {margin-top: .9rem;}
.footnote {color:#64748b; font-size:.75rem;}
</style>
"""


def agent_header(agent: str, page: str) -> None:
    """Big agent title + style badges (every agent page starts with this)."""
    meta = AGENTS[agent]
    st.set_page_config(page_title=f"{meta['name']} · {page}",
                       page_icon=meta["icon"])
    st.markdown(
        f'<div class="pagehead"><div class="phicon">{meta["icon"]}</div>'
        f'<div><div class="phtitle">{meta["name"]}</div>'
        f'<div><span class="stylebadge" style="background:'
        f'rgba(139,92,246,.16);color:#d8b4fe;">{meta["style"]}</span>'
        f'<span class="archbadge">{meta["arch"]}</span>'
        f'<span class="pagemuted">{meta["tagline"]}</span></div></div></div>',
        unsafe_allow_html=True)


def section(title: str) -> None:
    st.markdown(f'<div class="sectiontitle">{title}</div>',
                unsafe_allow_html=True)


def load_claims() -> dict:
    return {c["claim_id"]: c
            for c in json.loads((DATA_DIR / "claims.json").read_text())}


PATTERN_HINTS = {
    "C-1001": "clean", "C-1002": "clean", "C-1003": "clean", "C-1004": "clean",
    "C-1005": "velocity", "C-1006": "fraud ring", "C-1007": "shaky notes",
    "C-1008": "fresh policy", "C-1009": "clean", "C-1010": "clean",
    "C-1011": "ring + notes", "C-1012": "velocity + notes",
    "C-1013": "clean", "C-1014": "clean",
}


@st.cache_resource
def get_harness(agent: str):
    if agent == "fraud":
        from fraud_agent.harness import FraudHarness
        return FraudHarness()
    if agent == "portfolio":
        from portfolio_agent.assembly.harness import PortfolioHarness
        return PortfolioHarness()
    from cost_agent.harness import CostHarness
    return CostHarness()


@st.cache_data
def get_questions() -> list[dict]:
    from cost_agent.eval.dataset import QUESTIONS
    return QUESTIONS


@st.cache_data
def get_segments() -> list[dict]:
    from portfolio_agent.eval.dataset import ASSEMBLY_DATASET
    return ASSEMBLY_DATASET


def default_subject(agent: str):
    if agent == "fraud":
        return list(load_claims())[0]
    if agent == "portfolio":
        return get_segments()[0]
    return get_questions()[0]


# ── sidebar: floating run controls + guided demo + ledger ────────────
def advance_run(agent: str, value: bool | None = None) -> bool:
    """The ONE place a live run's driver is advanced.

    All touch points (⏭️ Step, ✅ Approve, 🚫 Reject, Autoplay) go
    through here so the shared driver generator can never be resumed
    twice in one script run — Streamlit serializes runs, but stale
    widget state can otherwise fire two advances in a single run, and
    resuming an already-running generator raises
    "ValueError: generator already executing". The `_advancing` flag
    makes that impossible; if it somehow still occurs (crash mid-
    advance), we re-request a run instead of dying.

    Returns True if an event was produced, False if the run is done.
    """
    live = st.session_state.get("live")
    if not live or live.get("agent") != agent:
        return False
    if live.get("done"):
        return False
    if live.get("_advancing"):
        st.rerun()  # another path is mid-advance this run — retry cleanly
    live["_advancing"] = True
    try:
        ev = (live["driver"].send(bool(value)) if value is not None
              else next(live["driver"]))
    except StopIteration:
        live["done"] = True
        return False
    except ValueError as exc:
        if "already executing" in str(exc):
            st.rerun()
        raise
    finally:
        live["_advancing"] = False
    live["events"].append(ev)
    live["awaiting"] = ev["type"] == "checkpoint"
    if ev["type"] == "checkpoint":
        live["autoplay"] = False
    return True


def render_sidebar_controls(agent: str) -> None:
    """The pinned ▶️ Run controls deck — always visible, never scrolled."""
    harness = get_harness(agent)
    _ga = st.session_state.get("guide_action")
    if _ga and _ga["agent"] == agent:
        st.session_state["sb_autonomy"] = _ga["guide"]["autonomy"]
        st.session_state["sb_bug"] = bool(_ga["guide"].get("bug"))
        st.session_state["sb_autoplay"] = False

    with st.sidebar.container(border=True):
        st.markdown("**▶️ Run controls** — pinned here, always visible")
        autonomy = st.select_slider(
            "Autonomy", options=["step", "gated", "full"], value="gated",
            key="sb_autonomy",
            help="Karpathy's autonomy slider: step = advance manually; "
                 "gated = pause on side-effecting tools; full = never pause.")
        bug = st.toggle("🐛 bug", value=False, key="sb_bug",
                        help="Inject a reasoning bug so the reflection "
                             "step can catch it (demo).")
        autoplay = st.toggle("Autoplay", value=False, key="sb_autoplay",
                             disabled=(autonomy == "step"))
        st.session_state["autonomy"] = autonomy
        st.session_state["bug"] = bug
        st.session_state["autoplay"] = autoplay

        _live = st.session_state.get("live")
        _active = bool(_live and _live.get("agent") == agent)
        _subj = st.session_state.get(f"subject_{agent}") or \
            default_subject(agent)
        b1, b2 = st.columns(2)
        if b1.button("▶️ Start run", type="primary",
                     use_container_width=True, key="sb_start"):
            harness.brain.bug_injection = bug
            run = harness.start_run(
                _subj, autonomy_level=("full" if autonomy == "full"
                                       else "gated"))
            st.session_state.live = {"agent": agent, "run": run,
                                     "driver": harness.drive(run),
                                     "events": [], "done": False,
                                     "awaiting": False, "autoplay": autoplay}
            st.rerun()
        _step_ok = _active and not _live["done"] and not _live["awaiting"] \
            and not _live.get("autoplay")
        if b2.button("⏭️ Step", use_container_width=True, key="sb_step",
                     disabled=not _step_ok):
            advance_run(agent)
            st.rerun()
        if _active and _live["awaiting"] and _live["events"] and \
                _live["events"][-1]["type"] == "checkpoint":
            st.warning("⏸️ Human checkpoint — the run is paused.")
            a1, a2 = st.columns(2)
            if a1.button("✅ Approve", use_container_width=True,
                         key="sb_approve"):
                advance_run(agent, True)
                st.rerun()
            if a2.button("🚫 Reject", use_container_width=True,
                         key="sb_reject"):
                advance_run(agent, False)
                st.rerun()

    st.sidebar.markdown("**Same skeleton, three crafts.**")
    st.sidebar.caption(
        "Goal, plan, skills, loop, tools, harness, lifecycle, graph "
        "knowledge and eval — reused. Only the playbooks, tools and "
        "brains differ.")

    from app.demo_guide import render_guide
    render_guide(agent)  # 🎬 guided demos — pick a scenario, load & run

    with st.sidebar.expander("💸 Spend ledger (always-on tracing)"):
        from fraud_agent.tracing import ledger_summary
        _ledger = ledger_summary()
        if _ledger:
            _rows = pd.DataFrame([
                {"agent": a, "runs": s["runs"], "cost_units": s["cost_units"],
                 "latency_ms": s["latency_ms"]}
                for a, s in sorted(_ledger.items())])
            st.dataframe(_rows, hide_index=True, use_container_width=True)
            st.caption("Append-only `data/traces/*.jsonl` — the spend "
                       "ledger that a demo reset never wipes.")
        else:
            st.caption("No runs recorded yet — run anything to start the "
                       "ledger (`data/traces/`).")


def run_state_chip(state: str) -> str:
    colors = {"RUNNING": ("#4ade80", "rgba(34,197,94,.16)"),
              "PAUSED": ("#fbbf24", "rgba(245,158,11,.16)"),
              "COMPLETED": ("#7dd3fc", "rgba(56,189,248,.14)"),
              "ESCALATED": ("#f87171", "rgba(239,68,68,.16)"),
              "FAILED": ("#f87171", "rgba(239,68,68,.16)")}
    fg, bg = colors.get(state, ("#a5b4cf", "#22314f"))
    return (f'<span class="stylebadge" style="background:{bg};color:{fg};">'
            f'{state}</span>')

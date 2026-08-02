"""Shared run cockpit — the post-run display used by Live Run AND the
Eval Lab drill-in, so a drilled case looks exactly like a live run:
status → system overview → evidence → blackboard | component+feed →
dossier + raw trace. Same event list everywhere; synced by construction.
"""
from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from app.anatomy_map import render_strip
from app.components import (funnel_figure, gauge_figure, graph_figure,
                            render_event_html, trend_figure)
from app import ui


def _evidence_row(agent: str, events: list[dict], run) -> None:
    """Compact, always-visible evidence: gauge + the latest chart."""
    cols = st.columns([1, 2])
    with cols[0]:
        if agent == "fraud":
            score = max([e.get("score", 0) for e in events
                         if e["type"] == "observation"] + [run.risk_score])
            st.plotly_chart(gauge_figure(score), use_container_width=True)
        elif agent == "portfolio":
            decisions = [e for e in events if e["type"] == "decision"]
            conf = decisions[-1]["confidence"] if decisions else 0
            st.plotly_chart(gauge_figure(conf, title="Margin-confidence",
                                         good="high"),
                            use_container_width=True)
        else:
            decisions = [e for e in events if e["type"] == "decision"]
            conf = decisions[-1]["confidence"] if decisions else 0
            st.plotly_chart(gauge_figure(conf, title="Confidence",
                                         good="high"),
                            use_container_width=True)
    with cols[1]:
        if agent == "fraud":
            nets = [e for e in events
                    if e["type"] == "observation"
                    and e["step"] == "network_analysis"]
            if nets:
                raw = nets[-1]["raw"]
                hot = set()
                cid = run.subject if isinstance(run.subject, str) else None
                claims = ui.load_claims()
                if cid and cid in claims:
                    hot = {claims[cid]["claimant_id"]} | {
                        l["entity"] for l in raw["fraud_links"]} | {
                        l["via"] for l in raw["fraud_links"]}
                st.plotly_chart(
                    graph_figure(raw["nodes"], raw["edges"], hot),
                    use_container_width=True)
            else:
                st.caption("No graph evidence yet — the network step "
                           "lights the 🕸️ Graph box when it runs.")
        elif agent == "portfolio":
            funnels = [e for e in events
                       if e["type"] == "observation"
                       and e["step"] == "stage_flow"]
            if funnels:
                raw = funnels[-1]["raw"]
                funnel = raw["funnel"] if isinstance(raw, dict) else raw
                stages = [f["stage"] for f in funnel]
                counts = [f["count"] for f in funnel]
                rets = [f["retention"] for f in funnel]
                seg = raw["segment"] if isinstance(raw, dict) else {}
                label = (f"Funnel: {seg.get('broker', '?')}/"
                         f"{seg.get('class_code', '?')}/"
                         f"{seg.get('region', '?')}")
                st.plotly_chart(funnel_figure(stages, counts, rets, label),
                                use_container_width=True)
            else:
                st.caption("No funnel yet — stage_flow fills it when the "
                           "lineage graph is queried.")
        else:
            trends = [e for e in events
                      if e["type"] == "observation"
                      and e["step"] == "read_trend"]
            if trends:
                raw = trends[-1]["raw"]
                st.plotly_chart(
                    trend_figure(raw["quarters"], raw["values"],
                                 f"{raw['metric']} · {raw['region']} · "
                                 f"{raw['coverage']}"),
                    use_container_width=True)
            else:
                st.caption("No trend chart yet — read_trend fills it when "
                           "the warehouse is queried.")


def render_run_cockpit(agent: str, live: dict, harness,
                       feed_footer=None, toggle_suffix: str = "live") -> None:
    """The post-run display: overview, evidence, blackboard, feed,
    dossier, raw trace. `feed_footer` renders under the feed (e.g. the
    live page's checkpoint notice)."""
    run = live["run"]
    events = live["events"]

    st.markdown(f"**Lifecycle state:** "
                f"{ui.run_state_chip(run.state.value)} "
                f"run `{run.run_id}`  ·  "
                f"autonomy `{run.autonomy_level}`",
                unsafe_allow_html=True)
    budget = harness.plan.constraints.get("max_cost_units")
    st.metric("Cost meter", f"{run.cost_units} units",
              help=f"Budget from goal.yaml: {budget} units — the harness "
                   "aborts the run if it is exceeded.")

    ui.section("🏗️ System overview")
    from app.system_view import render_system_view
    st.markdown(render_system_view(agent, events, run.state.value),
                unsafe_allow_html=True)
    st.caption(f"Drawn from the run's architecture — "
               f"{ui.AGENTS[agent]['arch']} — lighting up as the trace "
               "flows. Below: the case blackboard (left) and the "
               "component layer + execution feed (right), all synced "
               "from the same event list.")

    st.markdown("**📊 Evidence**")
    _evidence_row(agent, events, run)

    left, right = st.columns([2, 3])
    with left:
        from app.blackboard_view import render_live_board
        render_live_board(agent, events)

    with right:
        st.markdown("**Component layer ↔ execution** — stacked & synced")
        st.markdown(render_strip(agent, events, run.state.value),
                    unsafe_allow_html=True)
        chronological = st.toggle(
            "Chronological order (oldest first)", value=False,
            key=f"feed_order_{agent}_{toggle_suffix}",
            help="Newest-first keeps the latest card pinned at the top "
                 "so it never scrolls out of view during Autoplay.")
        _evs = events
        _cards = [render_event_html(ev) for ev in
                  (_evs if chronological else reversed(_evs))]
        if _cards:
            _latest_i = len(_evs) - 1 if chronological else 0
            _cards[_latest_i] = (f'<div class="feed-latest">'
                                 f'{_cards[_latest_i]}</div>')
        st.markdown(f'<div class="feedpanel">{"".join(_cards)}</div>',
                    unsafe_allow_html=True)
        if feed_footer:
            feed_footer()

    if events:
        from fraud_agent.dossier import compile_dossier, render_markdown
        d = compile_dossier(run)
        with st.expander("📄 Determination Dossier — one auditable "
                         "artifact for this run", expanded=False):
            c1, c2 = st.columns([3, 2])
            with c1:
                st.markdown("**Data accessed, grouped by origin** "
                            "(persisted vs graph vs model vs human)")
                for origin, items in d["lineage"].items():
                    st.markdown(f"`{origin}`")
                    for item in items:
                        st.markdown(f"- {item}")
            with c2:
                st.markdown("**Cost & latency per tool call**")
                if d["cost"]["per_call"]:
                    st.dataframe(pd.DataFrame(d["cost"]["per_call"]),
                                 hide_index=True, use_container_width=True)
                st.markdown(f"**Total:** {d['cost']['total_units']} units")
                if d["human_interactions"]:
                    st.markdown("**Human interactions**")
                    for h in d["human_interactions"]:
                        st.markdown(f"- ⏸️ {h['prompt']}")
            j1, j2 = st.columns(2)
            j1.download_button("⬇️ Dossier (JSON)",
                               json.dumps(d, indent=2, default=str),
                               file_name=f"dossier_{run.run_id}.json",
                               mime="application/json")
            j2.download_button("⬇️ Dossier (Markdown)",
                               render_markdown(d),
                               file_name=f"dossier_{run.run_id}.md",
                               mime="text/markdown")

        with st.expander("📜 Raw trace (JSONL) — the loop, on tape"):
            _jsonl = "\n".join(json.dumps(e, default=str) for e in run.trace)
            st.caption("Every event, in order — plan → thoughts → tool "
                       "calls (with origin · cost · latency) → blackboard "
                       "writes → decision. The dossier is compiled from "
                       "exactly this tape.")
            st.code(_jsonl, language="json")
            st.download_button("⬇️ Download trace (JSONL)", _jsonl,
                               file_name=f"trace_{run.run_id}.jsonl",
                               mime="application/jsonl")

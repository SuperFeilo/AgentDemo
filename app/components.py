"""UI building blocks: event cards, risk gauge, knowledge-graph figures.

Every event produced by the harness gets a distinct visual card so the
user can literally *see* the loop iterating: blue thoughts, purple tool
calls, green observations, amber checkpoints.
"""
from __future__ import annotations

import json

import networkx as nx
import plotly.graph_objects as go
import streamlit as st

CSS = """
<style>
.card {border-radius:8px; padding:10px 14px; margin:8px 0; color:#1a1a2e;
       border-left:5px solid; font-size:0.92rem;}
.card .tag {font-size:0.72rem; font-weight:700; letter-spacing:0.08em;
            text-transform:uppercase; opacity:0.65;}
.thought    {background:#e8f1ff; border-color:#3b82f6;}
.toolcall   {background:#f1eaff; border-color:#8b5cf6;}
.observation{background:#e9f9ef; border-color:#22c55e;}
.checkpoint {background:#fff3df; border-color:#f59e0b;}
.skipped    {background:#f1f1f4; border-color:#9ca3af;}
.toolerror  {background:#fdeaea; border-color:#ef4444;}
.aborted    {background:#fdeaea; border-color:#b91c1c;}
.plancard   {background:#eef2f7; border-color:#64748b;}
.bbwrite    {background:#f8fafc; border-color:#94a3b8; font-size:0.82rem;
             padding:6px 12px;}
.originchip {display:inline-block; font-size:0.68rem; font-weight:700;
             padding:1px 7px; border-radius:9px; margin-left:6px;
             background:#e2e8f0; color:#475569;}
.meta       {font-size:0.72rem; opacity:0.6; margin-left:8px;}
.corrected  {background:#fdeaea; border-color:#ef4444;}
.verdict    {border-radius:10px; padding:16px; text-align:center;
             font-weight:700; font-size:1.15rem;}
.approve {background:#dcfce7; color:#166534;}
.review  {background:#fef3c7; color:#92400e;}
.escalate{background:#fee2e2; color:#991b1b;}
.signal {margin:2px 0 2px 14px; font-size:0.88rem;}
</style>
"""

DECISION_STYLE = {"APPROVE": "approve", "REVIEW": "review", "ESCALATE": "escalate",
                  "EXPLAINED": "approve", "PARTIALLY EXPLAINED": "review",
                  "UNEXPLAINED": "escalate"}
NODE_COLORS = {"claimant": "#3b82f6", "phone": "#a855f7",
               "address": "#22c55e", "repair_shop": "#f59e0b",
               "metric": "#0ea5e9", "driver": "#f97316"}


def _card(css_class: str, tag: str, body: str) -> None:
    st.markdown(f'<div class="card {css_class}"><div class="tag">{tag}</div>'
                f'{body}</div>', unsafe_allow_html=True)


def render_event(ev: dict, key_prefix: str = "") -> None:
    """Render one harness event as a card."""
    t = ev["type"]
    if t == "plan":
        steps = "".join(
            f"<div class='signal'>{i}. <b>{s['name']}</b>"
            + (f" &nbsp;<code>{s['tool']}</code>" if s.get("tool") else "")
            + (f" &nbsp;<em>(skill: {s['skill']})</em>" if s.get("skill") else "")
            + "</div>"
            for i, s in enumerate(ev["steps"], 1))
        _card("plancard", "Plan ready", f"<b>Goal:</b> {ev['goal']}<br>{steps}")
    elif t == "thought":
        _card("thought", f"Thought · {ev['step']}", ev["text"])
    elif t == "tool_call":
        meta = ""
        if "origin" in ev:
            meta = (f"<span class='meta'>origin: {ev['origin']} · "
                    f"{ev.get('cost_units', '?')}u"
                    + (f" · {ev['latency_ms']}ms" if "latency_ms" in ev else "")
                    + "</span>")
        _card("toolcall", f"Tool call · {ev['tool']}" + meta,
              f"<code>{json.dumps(ev['args'])}</code>")
    elif t == "blackboard_write":
        _card("bbwrite", f"Blackboard · {ev['section']}.{ev['key']}"
              f"<span class='originchip'>{ev['origin']}</span>",
              ev["summary"])
    elif t == "observation":
        sig = "".join(f"<div class='signal'>▸ {s}</div>"
                      for s in ev.get("signals", []))
        badge = ""
        if "risk_points" in ev:  # fraud runs carry risk scoring
            pts = ev.get("risk_points", 0)
            badge = (f" &nbsp;<b style='color:#b91c1c'>+{pts} risk "
                     f"(total {ev['score']})</b>") if pts else \
                    f" &nbsp;<span style='opacity:.6'>+0 risk (total " \
                    f"{ev.get('score', 0)})</span>"
        css = "observation"
        if "corrected" in ev:  # reflection step outcome
            if ev["corrected"]:
                badge += " &nbsp;<b style='color:#b91c1c'>⚠ SELF-CORRECTED</b>"
                css = "corrected"
            else:
                badge += " &nbsp;<span style='opacity:.6'>✓ verified</span>"
        _card(css, f"Observation · {ev['step']}", ev["summary"] + badge + sig)
    elif t == "step_skipped":
        _card("skipped", f"Step skipped · {ev['step']}", ev["reason"])
    elif t == "checkpoint":
        _card("checkpoint", "Human checkpoint — run paused", ev["prompt"])
    elif t == "tool_error":
        _card("toolerror", f"Tool error · {ev['step']}", ev["error"])
    elif t == "aborted":
        _card("aborted", "Run aborted by harness", ev["reason"])
    elif t == "decision" and "explanation" in ev:
        # analyst verdict: explanation + citations
        render_verdict(ev["decision"], ev["confidence"],
                       score_label="confidence")
        cites = "".join(
            f"<div class='signal'>▸ <b>{c['name']}</b> (weight {c['weight']}) — "
            f"{c['evidence']} <em>[source: {c['source']}"
            + (f" · docs: {', '.join(c['docs'])}]</em></div>" if c.get("docs")
               else "]</em></div>")
            for c in ev["citations"]) or "<div class='signal'>▸ none — no " \
            "matching drivers in the knowledge graph</div>"
        _card("plancard", "Explanation",
              ev["explanation"].replace("\n", "<br>") + "<hr>" + cites)
    elif t == "decision":
        render_verdict(ev["decision"], ev["risk_score"])
    elif t == "decision_override":
        _card("checkpoint", f"Decision updated → {ev['decision']}", ev["reason"])
    elif t == "run_finished":
        if "risk_score" in ev:
            label, score = "risk score", ev["risk_score"]
        else:
            label, score = "confidence", ev.get("confidence", 0)
        _card("plancard", "Run finished",
              f"Final decision: <b>{ev['decision']}</b> · "
              f"{label} <b>{score}</b>")


def render_verdict(decision: str, score: int, score_label: str = "risk") -> None:
    css = DECISION_STYLE.get(decision, "review")
    st.markdown(f'<div class="verdict {css}">{decision} · '
                f'{score_label} {score}</div>', unsafe_allow_html=True)


def gauge_figure(score: int, title: str = "Fraud risk",
                 good: str = "low") -> go.Figure:
    """Gauge where low-is-good (fraud risk) or high-is-good (confidence)."""
    if good == "low":
        color = "#16a34a" if score < 40 else ("#d97706" if score < 70 else "#dc2626")
        steps = [{"range": [0, 40], "color": "#dcfce7"},
                 {"range": [40, 70], "color": "#fef3c7"},
                 {"range": [70, 100], "color": "#fee2e2"}]
    else:
        color = "#dc2626" if score < 40 else ("#d97706" if score < 70 else "#16a34a")
        steps = [{"range": [0, 40], "color": "#fee2e2"},
                 {"range": [40, 70], "color": "#fef3c7"},
                 {"range": [70, 100], "color": "#dcfce7"}]
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=score,
        title={"text": title},
        gauge={"axis": {"range": [0, 100]}, "bar": {"color": color},
               "steps": steps,
               "threshold": {"line": {"color": "#991b1b", "width": 3},
                             "thickness": 0.8, "value": 70}}))
    fig.update_layout(height=210, margin=dict(l=20, r=20, t=40, b=10))
    return fig


def trend_figure(quarters: list[str], values: list[float],
                 title: str) -> go.Figure:
    """Line chart for a metric_trend observation (cost analyst)."""
    fig = go.Figure(go.Scatter(x=quarters, y=values, mode="lines+markers",
                               line=dict(color="#0ea5e9", width=2),
                               marker=dict(size=6)))
    fig.update_layout(title=title, height=260,
                      margin=dict(l=20, r=20, t=40, b=20),
                      xaxis_title=None, yaxis_title=None)
    return fig


def graph_figure(nodes: list[dict], edges: list[dict],
                 highlight: set[str] | None = None) -> go.Figure:
    g = nx.Graph()
    for n in nodes:
        g.add_node(n["id"], **{k: v for k, v in n.items() if k != "id"})
    for e in edges:
        g.add_edge(e["a"], e["b"])
    pos = nx.spring_layout(g, seed=7, k=0.9)

    edge_x, edge_y = [], []
    for a, b in g.edges:
        edge_x += [pos[a][0], pos[b][0], None]
        edge_y += [pos[a][1], pos[b][1], None]
    traces = [go.Scatter(x=edge_x, y=edge_y, mode="lines", hoverinfo="none",
                         line=dict(width=1, color="#cbd5e1"))]

    highlight = highlight or set()
    for ntype, color in NODE_COLORS.items():
        ids = [n for n in g.nodes if g.nodes[n].get("type") == ntype]
        if not ids:
            continue
        traces.append(go.Scatter(
            x=[pos[i][0] for i in ids], y=[pos[i][1] for i in ids],
            mode="markers+text", name=ntype,
            text=[i + (" ⚠" if g.nodes[i].get("known_fraud") else "") for i in ids],
            textposition="top center", textfont=dict(size=10),
            marker=dict(
                size=[26 if i in highlight else 16 for i in ids],
                color=["#dc2626" if g.nodes[i].get("known_fraud") else color
                       for i in ids],
                line=dict(width=[3 if i in highlight else 1 for i in ids],
                          color="#111827"))))
    fig = go.Figure(traces)
    fig.update_layout(showlegend=True, height=430, hovermode="closest",
                      margin=dict(l=10, r=10, t=10, b=10),
                      xaxis=dict(visible=False), yaxis=dict(visible=False),
                      legend=dict(orientation="h", y=-0.05))
    return fig

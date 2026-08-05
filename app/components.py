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
.card {border-radius:8px; padding:10px 14px; margin:8px 0; color:#e6ebf4;
       border-left:5px solid; font-size:0.92rem;
       background:rgba(148,163,184,.06);}
.card .tag {font-size:0.72rem; font-weight:700; letter-spacing:0.08em;
            text-transform:uppercase; opacity:0.75;}
.thought    {background:rgba(59,130,246,.14); border-color:#3b82f6;}
.toolcall   {background:rgba(139,92,246,.14); border-color:#a78bfa;}
.observation{background:rgba(34,197,94,.12); border-color:#22c55e;}
.checkpoint {background:rgba(245,158,11,.14); border-color:#f59e0b;}
.skipped    {background:rgba(148,163,184,.08); border-color:#64748b;}
.toolerror  {background:rgba(239,68,68,.14); border-color:#ef4444;}
.aborted    {background:rgba(239,68,68,.2); border-color:#dc2626;}
.plancard   {background:rgba(100,116,139,.12); border-color:#64748b;}
.bbwrite    {background:rgba(148,163,184,.07); border-color:#94a3b8;
             font-size:0.82rem; padding:6px 12px;}
.originchip {display:inline-block; font-size:0.68rem; font-weight:700;
             padding:1px 7px; border-radius:9px; margin-left:6px;
             background:#22314f; color:#a5b4cf;}
.meta       {font-size:0.72rem; opacity:0.6; margin-left:8px;}
.corrected  {background:rgba(239,68,68,.16); border-color:#ef4444;}
.verdict    {border-radius:10px; padding:16px; text-align:center;
             font-weight:700; font-size:1.15rem;}
.approve {background:rgba(34,197,94,.16); color:#4ade80;}
.review  {background:rgba(245,158,11,.16); color:#fbbf24;}
.escalate{background:rgba(239,68,68,.18); color:#f87171;}
.signal {margin:2px 0 2px 14px; font-size:0.88rem;}
.stepcard {border-radius:8px; padding:7px 12px; margin:6px 0;
           background:rgba(148,163,184,.06); border:1px solid #22314f;
           border-left:4px solid #64748b; font-size:0.88rem;}
.stepcard.current {background:rgba(59,130,246,.12); border-color:#3b82f6;
                   border-left-color:#3b82f6; box-shadow:0 0 0 1px #3b82f6;}
.stepcard.skipped {opacity:.5;}
.stepno {display:inline-block; min-width:22px; text-align:center;
         font-weight:800; background:#3b82f6; color:#fff;
         border-radius:11px; padding:0 6px; margin-right:6px;
         font-size:0.78rem;}
.stepno.skippedno {background:#64748b;}
.stepmeta {font-size:0.72rem; opacity:.65; margin-left:8px;}
.trigger {display:inline-block; font-size:0.72rem; font-weight:600;
          padding:1px 8px; border-radius:9px; margin:2px 4px 2px 0;
          background:rgba(239,68,68,.16); color:#fca5a5;
          border:1px solid rgba(239,68,68,.4);}
.postchip {display:inline-block; font-size:0.72rem; padding:1px 8px;
           border-radius:9px; margin:2px 4px 2px 0; background:#22314f;
           color:#c7d2e8;}
.boardtag {font-size:0.68rem; font-weight:700; letter-spacing:.08em;
           text-transform:uppercase; opacity:.55; margin-right:6px;}
.sticky {border-radius:8px; padding:8px 12px; margin:6px 4px;
         border-top:3px solid #94a3b8; font-size:0.82rem;
         background:rgba(20,29,51,.9); color:#e6ebf4;}
.sticky .sttitle {font-weight:700; font-size:0.72rem;
                  letter-spacing:.06em; text-transform:uppercase;
                  opacity:.7; margin-bottom:4px;}
.st-cat-case      {border-top-color:#3b82f6;}
.st-cat-evidence  {border-top-color:#22c55e;}
.st-cat-hypotheses{border-top-color:#f59e0b;}
.st-cat-decision  {border-top-color:#a78bfa;}
.feedpanel {max-height:400px; overflow-y:auto; border:1px solid #22314f;
            border-radius:8px; padding:8px 12px;
            background:rgba(9,14,26,.6);}
.feed-latest {outline:2px solid #8b5cf6; border-radius:8px;
              animation:feedpulse 1.2s ease-out 2;}
@keyframes feedpulse {
  0% {box-shadow:0 0 0 0 rgba(139,92,246,.55);}
  70% {box-shadow:0 0 0 8px rgba(139,92,246,0);}
  100% {box-shadow:0 0 0 0 rgba(139,92,246,0);}
}
</style>
"""

DECISION_STYLE = {"APPROVE": "approve", "REVIEW": "review", "ESCALATE": "escalate",
                   "EXPLAINED": "approve", "PARTIALLY EXPLAINED": "review",
                   "UNEXPLAINED": "escalate",
                   "STRONG SUBMISSION": "approve", "ACCEPTABLE": "review",
                   "WEAK SUBMISSION": "escalate",
                   "WELL-UNDERWRITTEN": "approve", "MISPRICED": "escalate",
                   "CLEAN SETTLEMENT": "approve", "LEAKAGE DETECTED": "escalate",
                   "PROFIT EDGE IDENTIFIED": "approve", "MARGINAL": "review",
                   "NO EDGE": "escalate"}
NODE_COLORS = {
    # fraud entities
    "claimant": "#60a5fa", "phone": "#a855f7", "address": "#34d399",
    "repair_shop": "#fbbf24", "clinic": "#fb7185", "attorney": "#f472b6",
    "shell_company": "#94a3b8", "fraud_ring": "#ef4444",
    "scam_type": "#f97316", "suspect_shop": "#fb923c",
    # cost entities
    "metric": "#38bdf8", "driver": "#fb923c", "event": "#facc15",
    # portfolio entities
    "stage": "#38bdf8", "signal": "#c084fc", "outcome": "#34d399",
    "submission": "#7dd3fc", "bind": "#93c5fd", "claim": "#f472b6",
    "settlement": "#f87171",
    # shared
    "source_doc": "#64748b",
}
TYPE_LABELS = {
    "claimant": "claimant", "phone": "phone", "address": "address",
    "repair_shop": "repair shop", "clinic": "clinic", "attorney": "attorney",
    "shell_company": "shell co.", "fraud_ring": "fraud ring",
    "scam_type": "scam pattern", "suspect_shop": "suspect shop",
    "metric": "metric", "driver": "driver", "event": "event",
    "stage": "stage", "signal": "signal", "outcome": "outcome",
    "submission": "submission", "bind": "bind", "claim": "claim",
    "settlement": "settlement", "source_doc": "source memo",
    "node": "entity",
}
INTEL_TYPES = {"fraud_ring", "scam_type", "suspect_shop", "driver",
               "signal", "event"}
SOURCE_COLORS = {"data": "#38bdf8", "notes": "#fbbf24",
                 "newsfeed": "#34d399", "human": "#c084fc",
                 "learned": "#fb923c"}


def _node_hover(i: str, d: dict) -> str:
    bits = [d.get("type", "")]
    if d.get("known_fraud"):
        bits.append("🚨 known fraud")
    for k in ("confidence", "weight"):
        if d.get(k) is not None:
            bits.append(f"{k}={d[k]:g}" if isinstance(d[k], float) else f"{k}={d[k]}")
    if d.get("exposure") is not None:
        bits.append(f"exposure=${d['exposure']:,}")
    if d.get("strength_word"):
        bits.append(d["strength_word"])
    if d.get("name"):
        bits.insert(0, d["name"])
    return i + " — " + " · ".join(bits)


def knowledge_map_figure(g, rejected=None, highlight=None,
                         subset_ids=None, limit=None,
                         color_mode: str = "type",
                         source_map: dict | None = None) -> go.Figure:
    """The knowledge graph, drawn as knowledge: color = entity type (or
    provenance source), size = knowledge importance, ghost = human-
    rejected (no longer citable). Labels on intel entities only, so the
    map reads as a story, not a hairball."""
    rejected = rejected or set()
    highlight = highlight or set()
    ids = list(g.nodes)
    if subset_ids is not None:
        ids = [i for i in ids if i in subset_ids]
    intel = [i for i in ids if g.nodes[i].get("type") in INTEL_TYPES
             or g.nodes[i].get("type") == "source_doc"]
    rest = [i for i in ids if i not in intel]
    rest.sort(key=lambda i: g.degree(i), reverse=True)
    if limit:
        ids = (intel + rest)[:limit]
    sg = g.subgraph(ids)
    n = sg.number_of_nodes()
    pos = nx.spring_layout(sg, seed=7, k=(0.9 if n <= 120 else 0.55))

    edge_x, edge_y = [], []
    for a, b in sg.edges:
        edge_x += [pos[a][0], pos[b][0], None]
        edge_y += [pos[a][1], pos[b][1], None]
    traces = [go.Scatter(x=edge_x, y=edge_y, mode="lines", hoverinfo="none",
                         line=dict(width=1, color="#2a3a5c"))]

    group_key = (lambda i: (source_map or {}).get(i, "data")) \
        if color_mode == "source" else \
        (lambda i: sg.nodes[i].get("type", "node"))
    groups: dict[str, list[str]] = {}
    for i in sg.nodes:
        groups.setdefault(group_key(i), []).append(i)
    for gname, ids_t in sorted(groups.items()):
        if not ids_t:
            continue
        color = (SOURCE_COLORS.get(gname, "#64748b")
                 if color_mode == "source"
                 else NODE_COLORS.get(gname, "#64748b"))
        name = (f"source · {gname}" if color_mode == "source"
                else TYPE_LABELS.get(gname, gname))
        x, y, size, lw, lc, op, text, hover = [], [], [], [], [], [], [], []
        for i in ids_t:
            d = sg.nodes[i]
            x.append(pos[i][0]); y.append(pos[i][1])
            size.append(26 if i in highlight
                        else (20 if d.get("type") in INTEL_TYPES
                              or d.get("type") == "source_doc" else 12))
            lw.append(2.5 if i in highlight else 1)
            lc.append("#8b5cf6" if i in highlight else "#0b1120")
            op.append(0.18 if i in rejected else 1.0)
            show = (d.get("type") in INTEL_TYPES
                    or d.get("type") == "source_doc"
                    or d.get("known_fraud") or i in highlight)
            text.append(i if show else "")
            hover.append(_node_hover(i, d))
        traces.append(go.Scatter(
            x=x, y=y, mode="markers+text", name=name,
            text=text, textposition="top center",
            textfont=dict(size=9, color="#e6ebf4"),
            customdata=hover, hovertemplate="%{customdata}<extra></extra>",
            marker=dict(size=size, color=color, opacity=op,
                        line=dict(width=lw, color=lc))))
    fig = go.Figure(traces)
    fig.update_layout(showlegend=True, height=540, hovermode="closest",
                      margin=dict(l=10, r=10, t=10, b=10),
                      xaxis=dict(visible=False), yaxis=dict(visible=False),
                      legend=dict(orientation="h", y=-0.08), **_DARK)
    return fig


def ranked_bar_figure(items: list[dict], score_key: str,
                      label_key: str = "name",
                      winner_id: str | None = None,
                      top: int = 8) -> go.Figure:
    """Horizontal ranked bars; the winner (if any) highlighted."""
    items = sorted(items, key=lambda x: -x.get(score_key, 0))[:top]
    labels = [str(i.get(label_key, i.get("id", "?")))[:42] for i in items]
    scores = [i.get(score_key, 0) for i in items]
    colors = ["#a78bfa" if i.get("id") == winner_id else "#3d4d6f"
              for i in items]
    fig = go.Figure(go.Bar(x=scores, y=labels, orientation="h",
                           marker=dict(color=colors),
                           text=[f"{s:.2f}" for s in scores],
                           textposition="outside"))
    fig.update_layout(height=60 + 34 * len(items),
                      margin=dict(l=10, r=30, t=10, b=10),
                      xaxis_title=None, yaxis=dict(autorange="reversed"),
                      **_DARK)
    return fig


def _card_html(css_class: str, tag: str, body: str) -> str:
    return (f'<div class="card {css_class}"><div class="tag">{tag}</div>'
            f'{body}</div>')


def render_event_html(ev: dict) -> str:
    """HTML for one harness event card (used by the feed pane)."""
    t = ev["type"]
    if t == "plan":
        steps = "".join(
            f"<div class='signal'>{i}. <b>{s['name']}</b>"
            + (f" &nbsp;<code>{s['tool']}</code>" if s.get("tool") else "")
            + (f" &nbsp;<em>(skill: {s['skill']})</em>" if s.get("skill") else "")
            + "</div>"
            for i, s in enumerate(ev["steps"], 1))
        return _card_html("plancard", "Plan ready",
                          f"<b>Goal:</b> {ev['goal']}<br>{steps}")
    if t == "thought":
        return _card_html("thought", f"Thought · {ev['step']}", ev["text"])
    if t == "tool_call":
        meta = ""
        if "origin" in ev:
            meta = (f"<span class='meta'>origin: {ev['origin']} · "
                    f"{ev.get('cost_units', '?')}u"
                    + (f" · {ev['latency_ms']}ms" if "latency_ms" in ev else "")
                    + "</span>")
        return _card_html("toolcall", f"Tool call · {ev['tool']}" + meta,
                          f"<code>{json.dumps(ev['args'])}</code>")
    if t == "blackboard_write":
        return _card_html("bbwrite", f"Blackboard · {ev['section']}.{ev['key']}"
                          f"<span class='originchip'>{ev['origin']}</span>",
                          ev["summary"])
    if t == "observation":
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
        return _card_html(css, f"Observation · {ev['step']}",
                          ev["summary"] + badge + sig)
    if t == "step_skipped":
        return _card_html("skipped", f"Step skipped · {ev['step']}", ev["reason"])
    if t == "checkpoint":
        return _card_html("checkpoint", "Human checkpoint — run paused",
                          ev["prompt"])
    if t == "tool_error":
        return _card_html("toolerror", f"Tool error · {ev['step']}", ev["error"])
    if t == "aborted":
        return _card_html("aborted", "Run aborted by harness", ev["reason"])
    if t == "decision" and "explanation" in ev:
        # analyst verdict: explanation + citations
        cites = "".join(
            f"<div class='signal'>▸ <b>{c['name']}</b> (weight {c['weight']}) — "
            f"{c['evidence']} <em>[source: {c['source']}"
            + (f" · docs: {', '.join(c['docs'])}]</em></div>" if c.get("docs")
               else "]</em></div>")
            for c in ev["citations"]) or "<div class='signal'>▸ none — no " \
            "matching drivers in the knowledge graph</div>"
        return (verdict_html(ev["decision"], ev["confidence"],
                             score_label="confidence") +
                _card_html("plancard", "Explanation",
                           ev["explanation"].replace("\n", "<br>") + "<hr>" +
                           cites))
    if t == "decision":
        return verdict_html(ev["decision"], ev["risk_score"])
    if t == "decision_override":
        return _card_html("checkpoint", f"Decision updated → {ev['decision']}",
                          ev["reason"])
    if t == "run_finished":
        if "risk_score" in ev:
            label, score = "risk score", ev["risk_score"]
        else:
            label, score = "confidence", ev.get("confidence", 0)
        return _card_html("plancard", "Run finished",
                          f"Final decision: <b>{ev['decision']}</b> · "
                          f"{label} <b>{score}</b>")
    return ""


def verdict_html(decision: str, score: int, score_label: str = "risk") -> str:
    css = DECISION_STYLE.get(decision, "review")
    return (f'<div class="verdict {css}">{decision} · '
            f'{score_label} {score}</div>')


def render_verdict(decision: str, score: int, score_label: str = "risk") -> None:
    st.markdown(verdict_html(decision, score, score_label),
                unsafe_allow_html=True)


_DARK = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
             font=dict(color="#c7d2e8"), title_font_color="#e6ebf4")


def gauge_figure(score: int, title: str = "Fraud risk",
                 good: str = "low") -> go.Figure:
    """Gauge where low-is-good (fraud risk) or high-is-good (confidence)."""
    if good == "low":
        color = "#4ade80" if score < 40 else ("#fbbf24" if score < 70 else "#f87171")
        steps = [{"range": [0, 40], "color": "rgba(34,197,94,.22)"},
                 {"range": [40, 70], "color": "rgba(245,158,11,.22)"},
                 {"range": [70, 100], "color": "rgba(239,68,68,.26)"}]
    else:
        color = "#f87171" if score < 40 else ("#fbbf24" if score < 70 else "#4ade80")
        steps = [{"range": [0, 40], "color": "rgba(239,68,68,.26)"},
                 {"range": [40, 70], "color": "rgba(245,158,11,.22)"},
                 {"range": [70, 100], "color": "rgba(34,197,94,.22)"}]
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=score,
        title={"text": title},
        gauge={"axis": {"range": [0, 100]}, "bar": {"color": color},
               "steps": steps,
               "threshold": {"line": {"color": "#f87171", "width": 3},
                             "thickness": 0.8, "value": 70}}))
    fig.update_layout(height=210, margin=dict(l=20, r=20, t=40, b=10),
                      **_DARK)
    return fig


def trend_figure(quarters: list[str], values: list[float],
                 title: str) -> go.Figure:
    """Line chart for a metric_trend observation (cost analyst)."""
    fig = go.Figure(go.Scatter(x=quarters, y=values, mode="lines+markers",
                               line=dict(color="#38bdf8", width=2),
                               marker=dict(size=6, color="#38bdf8")))
    fig.update_layout(title=title, height=260,
                      margin=dict(l=20, r=20, t=40, b=20),
                      xaxis_title=None, yaxis_title=None, **_DARK)
    return fig


def funnel_figure(stages: list[str], counts: list[int],
                  retentions: list[float], title: str) -> go.Figure:
    """Funnel chart for the portfolio-agent stage flow."""
    fig = go.Figure(go.Funnel(
        y=[f"{s} · {r:.0%}" for s, r in zip(stages, retentions)],
        x=counts, textinfo="value+percent initial+percent previous",
        marker=dict(color="#38bdf8")))
    fig.update_layout(title=title, height=320,
                      margin=dict(l=20, r=20, t=40, b=20), **_DARK)
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
                         line=dict(width=1, color="#334155"))]

    highlight = highlight or set()
    for ntype, color in NODE_COLORS.items():
        ids = [n for n in g.nodes if g.nodes[n].get("type") == ntype]
        if not ids:
            continue
        traces.append(go.Scatter(
            x=[pos[i][0] for i in ids], y=[pos[i][1] for i in ids],
            mode="markers+text", name=ntype,
            text=[i + (" ⚠" if g.nodes[i].get("known_fraud") else "") for i in ids],
            textposition="top center", textfont=dict(size=10,
                                                     color="#e6ebf4"),
            marker=dict(
                size=[26 if i in highlight else 16 for i in ids],
                color=["#dc2626" if g.nodes[i].get("known_fraud") else color
                       for i in ids],
                line=dict(width=[3 if i in highlight else 1 for i in ids],
                          color="#0b1120"))))
    fig = go.Figure(traces)
    fig.update_layout(showlegend=True, height=430, hovermode="closest",
                      margin=dict(l=10, r=10, t=10, b=10),
                      xaxis=dict(visible=False), yaxis=dict(visible=False),
                      legend=dict(orientation="h", y=-0.05), **_DARK)
    return fig

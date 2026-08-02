"""BLACKBOARD PANEL — the agent's working memory, live.

Turns the current run's trace into a *board* for the Live Run tab: the
four blackboard sections (case / evidence / hypotheses / decision)
rendered as sticky notes that fill in step order, colored by data
origin, plus the numbered step rail and the final verdict.

Works for all three agents: every loop yields the same event vocabulary
(plan / thought / tool_call / blackboard_write / observation / decision
/ ...). The panel reads the exact event list the execution feed renders,
so it is synced with the run by construction — no separate tab needed.
"""
from __future__ import annotations

import streamlit as st

from app.components import render_verdict

# ═════════════════════════════════════════════════════════════════════
# JOURNEY BUILDER — trace events -> numbered steps
# ═════════════════════════════════════════════════════════════════════

def _node(nid: str, ntype: str, name: str | None = None,
          **extra) -> dict:
    return {"id": nid, "type": ntype, "name": name, **extra}


def _touchpoints(domain: str, ev: dict) -> tuple[dict, dict]:
    """Graph nodes/edges this observation retrieved (raw payloads)."""
    raw = ev.get("raw") or {}
    nodes, edges = {}, {}
    step = ev.get("step", "")
    if domain == "fraud":
        if step == "network_analysis":
            for n in raw.get("nodes", []):
                nodes[n["id"]] = {"id": n["id"], "type": n.get("type"),
                                  "name": n.get("name"),
                                  "known_fraud": bool(n.get("known_fraud"))}
            for e in raw.get("edges", []):
                edges[(e["a"], e["b"])] = {"a": e["a"], "b": e["b"],
                                           "relation": e.get("relation")}
            # GraphRAG layer: rings the claimant belongs to (if approved
            # intel was retrieved) — MEMBER_OF edges from every claimant
            # already in view to each ring.
            claimants = [n["id"] for n in raw.get("nodes", [])
                         if n.get("type") == "claimant"]
            for ring in raw.get("graphrag_intel", []):
                rid = ring.get("ring_id")
                nodes[rid] = _node(rid, "fraud_ring",
                                   ring.get("ring_name"))
                for c in claimants:
                    edges[(c, rid)] = {"a": c, "b": rid,
                                       "relation": "MEMBER_OF"}
    elif domain == "cost":
        if step == "find_drivers":
            metric = raw.get("metric")
            if metric:
                nodes[metric] = _node(metric, "metric")
            for d in raw.get("drivers", []):
                nodes[d["driver_id"]] = _node(d["driver_id"], "driver",
                                              d.get("name"))
                if metric:
                    edges[(d["driver_id"], metric)] = {
                        "a": d["driver_id"], "b": metric,
                        "relation": "IMPACTS"}
        elif step == "gather_evidence":
            did = raw.get("driver_id")
            if did:
                nodes[did] = _node(did, "driver", raw.get("name"))
                for evt in raw.get("events", []):
                    eid = evt.get("event_id")
                    if eid:
                        nodes[eid] = _node(eid, "event", evt.get("name"))
                        edges[(eid, did)] = {"a": eid, "b": did,
                                             "relation": "CAUSES"}
    elif domain == "portfolio":
        if step == "predisposing_signals":
            for c in raw.get("candidates", []):
                sid = c.get("signal_id")
                nodes[sid] = _node(sid, "signal", c.get("name"),
                                   stage=c.get("stage"))
                out = c.get("outcome")
                if out:
                    nodes.setdefault(out, _node(out, "outcome"))
                    edges[(sid, out)] = {"a": sid, "b": out,
                                         "relation": "PREDISPOSES"}
        elif step == "stage_flow":
            funnel = raw.get("funnel", [])
            for i, f in enumerate(funnel):
                sid = f.get("stage")
                nodes[sid] = _node(sid, "stage")
                if i:
                    prev = funnel[i - 1].get("stage")
                    edges[(prev, sid)] = {"a": prev, "b": sid,
                                          "relation": "FLOWS_TO"}
        elif str(step).startswith("run_"):
            sid = raw.get("stage")
            if sid:
                nodes[sid] = _node(sid, "stage")
    return nodes, edges


def _triggers(domain: str, ev: dict) -> list[str]:
    """Key trigger lines for one observation/decision."""
    raw = ev.get("raw") or {}
    step = ev.get("step", "")
    if domain == "fraud":
        return list(ev.get("signals", []))
    if domain == "cost":
        if step == "find_drivers":
            return [f"{d['name']} (w={d['weight']}) IMPACTS "
                    f"{raw.get('metric')} — {d.get('direction', '+')}"
                    for d in raw.get("drivers", [])]
        if step == "gather_evidence":
            did = raw.get("driver_id")
            if did:
                evi = (raw.get("evidence") or "")[:90]
                return [f"{raw.get('name', did)}: {evi}"]
        return []
    if domain == "portfolio":
        if step == "predisposing_signals":
            return [f"{c['name']} (w={c['weight']}) → {c.get('outcome')}"
                    for c in raw.get("candidates", [])[:4]]
        if str(step).startswith("run_"):
            return [f"{raw.get('stage', '?')}: {raw.get('verdict_label', '?')} "
                    f"over {raw.get('n', 0)} files"]
        return []
    return []


def build_journey(events: list[dict], domain: str) -> dict:
    """Compile a trace into numbered steps + blackboard sections."""
    plan_ev = next((e for e in events if e["type"] == "plan"), None)
    plan_steps = plan_ev["steps"] if plan_ev else []
    steps = [{
        "no": i + 1, "name": s.get("name"), "purpose": s.get("purpose"),
        "skill": s.get("skill"), "tool": s.get("tool"),
        "skipped": None, "errors": [],
        "retrieved": {"nodes": {}, "edges": {}},
        "posted": [], "triggers": [],
        "next_action": None, "last_index": 0, "thought": None,
    } for i, s in enumerate(plan_steps)]
    name_to_idx = {s["name"]: i for i, s in enumerate(steps)}
    sections = {"case": [], "evidence": [], "hypotheses": [],
                "decision": []}
    decision_ev = None
    cur = 0

    def _absorb(dst: dict, src: tuple) -> None:
        nodes, edges = src
        dst["nodes"].update(nodes)
        dst["edges"].update(edges)

    for idx, ev in enumerate(events):
        t = ev["type"]
        if t == "plan":
            continue
        si = name_to_idx.get(ev.get("step"), cur) if steps else None
        if si is None:
            continue
        step = steps[si]
        step["last_index"] = idx
        cur = si

        if t == "thought":
            step["thought"] = ev.get("text")
        elif t == "step_skipped":
            step["skipped"] = ev.get("reason")
        elif t == "tool_error":
            step["errors"].append(ev.get("error"))
        elif t == "tool_call":
            step["last_tool_call"] = {"tool": ev.get("tool"),
                                      "args": ev.get("args")}
        elif t == "blackboard_write":
            rec = {"key": ev.get("key"), "summary": ev.get("summary"),
                   "origin": ev.get("origin")}
            step["posted"].append(rec)
            sections.setdefault(ev.get("section", "case"), []).append(
                {**rec, "step_no": si + 1})
        elif t == "observation":
            step["triggers"].extend(_triggers(domain, ev))
            _absorb(step["retrieved"], _touchpoints(domain, ev))
        elif t == "decision":
            decision_ev = ev
            cites = ev.get("citations") or []
            if cites:
                step["triggers"].extend(
                    f"cites {c['name']} (w={c['weight']})"
                    for c in cites)
            if ev.get("rationale"):
                step["triggers"].extend(ev["rationale"])
        elif t == "run_finished":
            decision_ev = decision_ev or ev

    # NEXT ACTION per step: first tool call / decision after its events
    for step in steps:
        for ev in events[step["last_index"] + 1:]:
            if ev["type"] == "tool_call":
                step["next_action"] = {"kind": "tool",
                                       "tool": ev.get("tool"),
                                       "args": ev.get("args")}
                break
            if ev["type"] in ("decision", "decision_override"):
                step["next_action"] = {"kind": "decide",
                                       "decision": ev.get("decision")}
                break
            if ev["type"] == "run_finished":
                step["next_action"] = {"kind": "finish"}
                break

    return {"steps": steps, "sections": sections,
            "decision": decision_ev, "domain": domain,
            "n_steps": len(steps)}


# ═════════════════════════════════════════════════════════════════════
# BOARD RENDERER
# ═════════════════════════════════════════════════════════════════════

def _rail_card(step: dict, current: int) -> str:
    cls = "stepcard"
    if step["no"] == current:
        cls += " current"
    if step["skipped"]:
        cls += " skipped"
    no_cls = "stepno skippedno" if step["skipped"] else "stepno"
    tool = (f"<span class='stepmeta'><code>{step['tool']}</code>"
            + (f" · {step['skill']}" if step.get("skill") else "")
            + "</span>")
    body = f"<div class='{cls}'>"
    body += (f"<span class='{no_cls}'>{step['no']}</span>"
             f"<b>{step['name']}</b>{tool}<br>")
    if step["skipped"]:
        body += f"<span style='opacity:.7'>skipped: {step['skipped']}</span>"
        return body + "</div>"
    n_ret = len(step["retrieved"]["nodes"])
    n_edges = len(step["retrieved"]["edges"])
    body += (f"<span class='boardtag'>Retrieved</span>"
             f"{n_ret} node(s), {n_edges} edge(s)")
    if step["posted"]:
        body += (f"&nbsp;&nbsp;<span class='boardtag'>Posted</span>"
                 f"{len(step['posted'])}")
    if step["triggers"]:
        body += "<br><span class='boardtag'>Triggers</span>"
        for t in step["triggers"][:5]:
            body += f"<span class='trigger'>{t}</span>"
    na = step.get("next_action")
    if na:
        body += "<br><span class='boardtag'>Next</span>"
        if na["kind"] == "tool":
            body += (f"<span class='postchip'>⚙ {na['tool']}"
                     f"({str(na.get('args'))[:60]})</span>")
        elif na["kind"] == "decide":
            body += (f"<span class='postchip'>🎯 DECIDE → "
                     f"{na['decision']}</span>")
        else:
            body += "<span class='postchip'>🏁 finish</span>"
    return body + "</div>"


def render_live_board(agent: str, events: list[dict]) -> None:
    """Live blackboard panel for the Live Run tab.

    Reads the same event list as the execution feed, so it fills in
    step order, synced with the run. Latest write per section pulses.
    """
    journey = build_journey(events, agent)
    steps = journey["steps"]
    if not steps:
        st.info("No plan steps in this trace yet.")
        return
    current = sum(1 for s in steps if s["last_index"] > 0)

    st.markdown("**Case blackboard** — working memory, filling live "
                "(colored by origin)")
    sections = journey["sections"]
    icons = {"case": "📋", "evidence": "🔎", "hypotheses": "🧩",
             "decision": "⚖️"}
    cols = st.columns(len(sections) or 1)
    for col, (sec, writes) in zip(cols, sections.items()):
        with col:
            body = f"<div class='sticky st-cat-{sec}'>"
            body += (f"<div class='sttitle'>{icons.get(sec, '')} "
                     f"{sec} · {len(writes)}</div>")
            for w in writes[-5:]:
                origin = w.get("origin") or "?"
                is_latest = w is writes[-1]
                highlight = ("outline:1px solid #3b82f6;border-radius:4px;"
                             "padding:1px 3px;") if is_latest else ""
                body += (f"<div style='{highlight}'><span class='postchip'>"
                         f"{w['key']}</span><span class='originchip'>"
                         f"{origin}</span> {w['summary'][:60]}</div>")
            body += "</div>"
            st.markdown(body, unsafe_allow_html=True)

    with st.expander("Step rail — planning path, numbered", expanded=False):
        for step in steps:
            st.markdown(_rail_card(step, current), unsafe_allow_html=True)

    dec = journey.get("decision")
    if dec:
        if "confidence" in dec:
            render_verdict(dec.get("decision"), dec.get("confidence"),
                           score_label="confidence")
        elif "risk_score" in dec:
            render_verdict(dec.get("decision"), dec.get("risk_score"))
        else:
            st.markdown(f"**Run finished** — {dec.get('decision')}")

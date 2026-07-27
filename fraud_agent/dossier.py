"""ANATOMY COMPONENT: DETERMINATION DOSSIER

The dossier is the auditable answer to "show me *exactly* what happened":
one artifact per run that a human reviewer (or a regulator) can read
end-to-end — what case was presented, which skills fired, what the agent
thought, which data it touched (grouped by ORIGIN: persisted database /
knowledge graph / model brain / human / ephemeral), what it decided, and
what it cost.

Compiled purely from the run trace + blackboard journal: observability
is not a dashboard bolted on afterwards, it is a re-view of the event
sourcing the harness already does.
"""
from __future__ import annotations

from fraud_agent.lifecycle import Run


def compile_dossier(run: Run) -> dict:
    trace = run.trace
    thoughts = [e for e in trace if e["type"] == "thought"]
    calls = [e for e in trace if e["type"] == "tool_call"]
    observations = [e for e in trace if e["type"] == "observation"]
    writes = [e for e in trace if e["type"] == "blackboard_write"]
    checkpoints = [e for e in trace if e["type"] == "checkpoint"]
    decisions = [e for e in trace if e["type"] in
                 ("decision", "decision_override")]
    plan = next((e for e in trace if e["type"] == "plan"), None)
    aborted = next((e for e in trace if e["type"] == "aborted"), None)

    # pair each observation with its tool call (same step, ordered)
    data_access = []
    for call in calls:
        obs = next((o for o in observations if o["step"] == call["step"]
                    and observations.index(o) > trace.index(call)), None)
        data_access.append({
            "tool": call["tool"], "args": call["args"], "step": call["step"],
            "origin": call.get("origin", "unknown"),
            "cost_units": call.get("cost_units"),
            "latency_ms": call.get("latency_ms"),
            "summary": obs["summary"] if obs else "(no result)",
        })

    lineage: dict[str, list[str]] = {}
    for w in writes:
        lineage.setdefault(w["origin"], []).append(
            f"{w['section']}.{w['key']}: {w['summary']}")

    decision = decisions[-1] if decisions else None
    total_cost = sum(c.get("cost_units") or 0 for c in calls)

    return {
        "case": {"subject": run.subject if isinstance(run.subject, str)
                 else run.subject.get("text", str(run.subject)),
                 "run_id": run.run_id, "state": run.state.value},
        "goal": plan["goal"] if plan else None,
        "plan_skills": [{"step": s["name"], "skill": s.get("skill"),
                         "tool": s.get("tool")}
                        for s in plan["steps"]] if plan else [],
        "reasoning": [{"step": t["step"], "thought": t["text"]}
                      for t in thoughts],
        "data_access": data_access,
        "lineage": lineage,
        "human_interactions": [{"prompt": c["prompt"]} for c in checkpoints],
        "decision": decision,
        "cost": {"total_units": total_cost, "per_call": [
            {"tool": d["tool"], "cost_units": d["cost_units"],
             "latency_ms": d["latency_ms"]} for d in data_access]},
        "lifecycle": [{"state": s, "t": t} for s, t in run.history],
        "aborted": aborted,
    }


def render_markdown(d: dict) -> str:
    lines = [f"# Determination Dossier — {d['case']['run_id']}",
             f"**Case:** {d['case']['subject']}  ",
             f"**Final state:** {d['case']['state']}  ",
             f"**Goal:** {d['goal']}", "", "## Plan & skills"]
    for s in d["plan_skills"]:
        lines.append(f"- **{s['step']}**"
                     + (f" — skill `{s['skill']}`" if s["skill"] else "")
                     + (f" — tool `{s['tool']}`" if s["tool"] else ""))
    lines += ["", "## Reasoning log"]
    for r in d["reasoning"]:
        lines.append(f"- [{r['step']}] {r['thought']}")
    lines += ["", "## Data accessed (by origin)"]
    by_origin: dict[str, list[dict]] = {}
    for a in d["data_access"]:
        by_origin.setdefault(a["origin"], []).append(a)
    for origin, items in by_origin.items():
        lines.append(f"### {origin}")
        for a in items:
            lines.append(f"- `{a['tool']}` {a['args']} → {a['summary']}")
    if d["human_interactions"]:
        lines += ["", "## Human interactions"]
        for h in d["human_interactions"]:
            lines.append(f"- ⏸️ {h['prompt']}")
    lines += ["", "## Decision"]
    if d["decision"]:
        lines.append(f"```json\n{d['decision']}\n```")
    lines += ["", "## Cost",
              f"Total: {d['cost']['total_units']} units", ""]
    lines.append("| tool | units | latency (ms) |")
    lines.append("|---|---|---|")
    for c in d["cost"]["per_call"]:
        lines.append(f"| {c['tool']} | {c['cost_units']} "
                     f"| {c['latency_ms']} |")
    if d["aborted"]:
        lines += ["", f"⚠️ **Aborted by harness:** {d['aborted']['reason']}"]
    return "\n".join(lines)

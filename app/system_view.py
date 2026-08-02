"""System overview — the architecture-aware live view for the Live Run tab.

The overview is tied to the selected agent's architecture, so you watch
the *system*, not just a log:

  🕵️ fraud      — linear pipeline   (deterministic workflow)
  📈 cost       — think→act→observe loop (research cycle + verification)
  🎯 portfolio  — orchestrator graph (assembly → workers → compose)

Every state is derived from the run's event list — the exact same list
the side execution feed renders — so the two panes are synchronized by
construction: when Autoplay runs, the pipeline fills, the ring spins,
the graph fans out, and the feed scrolls beside it.

The component-level strip (anatomy_map.render_strip) sits underneath:
the architecture path above, the internals that fired below.
"""
from __future__ import annotations

from app.anatomy_map import hits_for

# ── shared CSS ───────────────────────────────────────────────────────
CSS = """
<style>
.sv {font-family:ui-sans-serif,system-ui,sans-serif; font-size:.8rem;
     color:#e6ebf4;}
.svhead {font-weight:700; margin-bottom:8px; color:#e6ebf4;}
.svhead .svtag {display:inline-block; font-size:.62rem; font-weight:700;
       letter-spacing:.08em; text-transform:uppercase; background:#22314f;
       color:#a5b4cf; border-radius:10px; padding:1px 8px; margin-left:6px;}
/* pipeline (horizontal, wraps) */
.svpipe {display:flex; flex-direction:row; align-items:center;
         flex-wrap:wrap; gap:6px;}
.svnode {display:flex; gap:8px; border-radius:8px; padding:6px 10px;
         border:1px solid #22314f; background:rgba(148,163,184,.06);
         opacity:.5; flex:0 1 auto; min-width:150px; max-width:250px;
         color:#e6ebf4;}
.svnode.done {opacity:1; background:rgba(34,197,94,.13); border-color:#22c55e;}
.svnode.running {opacity:1; background:rgba(245,158,11,.13);
         border-color:#f59e0b; outline:2px solid #f59e0b;
         animation:svpulse 1.1s ease-out 2;}
.svnode.pending {opacity:.4;}
.svnode.skipped {opacity:.45; background:rgba(148,163,184,.07);}
.svnum {min-width:20px; height:20px; border-radius:10px; background:#3d4d6f;
        color:#e6ebf4; font-weight:800; font-size:.68rem; text-align:center;
        line-height:20px; flex:0 0 auto;}
.svnode.done .svnum {background:#22c55e;}
.svnode.running .svnum {background:#f59e0b;}
.svnode.skipped .svnum {background:#3d4d6f;}
.svname {font-weight:700;}
.svtool {font-family:ui-monospace,monospace; font-size:.66rem; color:#d8b4fe;
         background:rgba(139,92,246,.18); border-radius:8px; padding:0 6px;
         margin-left:4px;}
.svpurpose {font-size:.68rem; opacity:.7;}
.svchips {display:flex; gap:4px; flex-wrap:wrap; margin-top:3px;}
.svchip {font-size:.64rem; border-radius:8px; padding:0 7px;}
.svchip.sig {background:rgba(239,68,68,.16); color:#fca5a5;}
.svchip.delta {background:rgba(245,158,11,.16); color:#fbbf24; font-weight:700;}
.svchip.verdict {background:rgba(34,197,94,.16); color:#4ade80; font-weight:700;}
.svchip.skip {background:#22314f; color:#a5b4cf;}
.svlink {width:12px; height:3px; background:#22314f; flex:0 0 auto;}
.svlink.done {background:#22c55e;}
.svlink.running {background:#f59e0b;}
/* loop ring */
.svring {display:flex; align-items:center; gap:10px; flex-wrap:wrap;
         border:1px dashed #2a3a5c; border-radius:10px; padding:10px 12px;
         background:rgba(20,29,51,.5);}
.svphase {border-radius:8px; padding:6px 12px; font-weight:700; font-size:.78rem;
          background:rgba(148,163,184,.08); color:#8ea0bd; opacity:.55;}
.svphase.active {opacity:1; outline:2px solid #8b5cf6; background:rgba(139,92,246,.16);
                 color:#d8b4fe; animation:svpulse 1.1s ease-out 2;}
.svarrow {color:#3d4d6f; font-weight:800;}
.svcenter {flex:1 1 160px; text-align:center; font-size:.74rem; color:#8ea0bd;}
.svcenter b {color:#e6ebf4;}
.sviter {font-weight:800; font-size:.9rem;}
.svverify {font-size:.64rem; color:#7dd3fc; background:rgba(56,189,248,.12);
           border-radius:8px; padding:1px 8px; display:inline-block;
           margin-top:4px;}
.svsteps {display:flex; gap:4px; flex-wrap:wrap; margin-top:8px;}
.svstepchip {font-size:.66rem; border-radius:8px; padding:2px 8px;
             background:rgba(148,163,184,.08); color:#8ea0bd;}
.svstepchip.done {background:rgba(34,197,94,.15); color:#4ade80;}
.svstepchip.running {background:rgba(245,158,11,.16); color:#fbbf24;
             font-weight:700; outline:1px solid #f59e0b;}
.svstepchip.skipped {background:rgba(148,163,184,.06); color:#64748b;
             text-decoration:line-through;}
/* workers row */
.svworkers {display:flex; gap:8px; flex-wrap:wrap;}
.svworker {flex:0 1 auto; min-width:140px;}
.svnote {font-size:.66rem; color:#8ea0bd; margin-top:6px;}
@keyframes svpulse {
  0% {box-shadow:0 0 0 0 rgba(245,158,11,.5);}
  70% {box-shadow:0 0 0 8px rgba(245,158,11,0);}
  100% {box-shadow:0 0 0 0 rgba(245,158,11,0);}
}
</style>
"""


# ── state derivation (shared by all three views) ────────────────────
def step_states(events: list[dict]) -> tuple[list[dict], dict, dict, str | None]:
    """Per plan-step status, signals and outcomes, from the event list."""
    plan_ev = next((e for e in events if e["type"] == "plan"), None)
    steps = list(plan_ev["steps"]) if plan_ev else []
    statuses = {s["name"]: "pending" for s in steps}
    info = {s["name"]: {"signals": [], "delta": 0, "verdict": None,
                        "n": None, "summary": "", "tool": None,
                        "purpose": s.get("purpose", "")}
            for s in steps}
    started = set()
    for ev in events:
        name = ev.get("step")
        if not name or name not in statuses:
            continue
        t = ev["type"]
        if t == "tool_call":
            info[name]["tool"] = ev.get("tool")
            started.add(name)
        elif t == "thought":
            started.add(name)
        elif t == "observation":
            started.add(name)
            info[name]["signals"] = ev.get("signals") or info[name]["signals"]
            info[name]["summary"] = ev.get("summary") or info[name]["summary"]
            if ev.get("risk_points") is not None:
                info[name]["delta"] += ev["risk_points"]
            raw = ev.get("raw")
            if isinstance(raw, dict):
                if raw.get("verdict_label"):
                    info[name]["verdict"] = raw["verdict_label"]
                    info[name]["n"] = raw.get("n")
        elif t == "step_skipped":
            statuses[name] = "skipped"
    current = None
    for ev in reversed(events):
        if ev.get("step") in statuses:
            current = ev["step"]
            break
    for name, s in statuses.items():
        if s == "skipped":
            continue
        if name == current:
            statuses[name] = "running"
        elif name in started:
            statuses[name] = "done"
    return steps, statuses, info, current


def _phase(events: list[dict]) -> str | None:
    if not events:
        return None
    t = events[-1]["type"]
    if t == "thought":
        return "think"
    if t == "tool_call":
        return "act"
    if t in ("observation", "blackboard_write"):
        return "observe"
    return None


def _node_html(i: int, name: str, status: str, info: dict) -> str:
    chips = []
    if info.get("tool"):
        chips.append(f'<span class="svtool">{info["tool"]}</span>')
    for s in (info.get("signals") or [])[:3]:
        chips.append(f'<span class="svchip sig">▸ {s}</span>')
    if info.get("delta"):
        d = info["delta"]
        chips.append(f'<span class="svchip delta">{"+" if d > 0 else ""}'
                     f'{d} risk</span>')
    if info.get("verdict"):
        chips.append(f'<span class="svchip verdict">{info["verdict"]}'
                     f'{" · " + str(info["n"]) + " runs" if info.get("n") else ""}'
                     f'</span>')
    if status == "skipped":
        chips.append('<span class="svchip skip">skipped</span>')
    purpose = (f'<div class="svpurpose">{info["purpose"]}</div>'
               if info.get("purpose") else "")
    return (f'<div class="svnode {status}" id="svn-{name}">'
            f'<div class="svnum">{i}</div>'
            f'<div><div class="svname">{name}{"".join(chips)}</div>'
            f'{purpose}</div></div>')


# ── fraud: linear pipeline ───────────────────────────────────────────
def _linear_view(events: list[dict]) -> str:
    steps, statuses, info, current = step_states(events)
    parts = [('<div class="svhead">🏗️ System overview — '
              '<b>Deterministic workflow</b>'
              '<span class="svtag">linear · chain</span></div>'),
             '<div class="svpipe">']
    for i, s in enumerate(steps):
        if i:
            prev = steps[i - 1]["name"]
            link = ("done" if statuses[prev] == "done"
                    else "running" if statuses[prev] == "running" else "")
            parts.append(f'<div class="svlink {link}"></div>')
        parts.append(_node_html(i + 1, s["name"], statuses[s["name"]],
                                info[s["name"]]))
    parts.append("</div>")
    if current:
        parts.append(f'<div class="svnote">⏵ now at step '
                     f'<b>{current}</b> — the connector ahead lights as it '
                     f'completes. Step order is fixed by the planner; only '
                     f'the evidence differs per claim.</div>')
    return "".join(parts)


# ── cost: think → act → observe loop ─────────────────────────────────
def _loop_view(events: list[dict]) -> str:
    steps, statuses, info, current = step_states(events)
    phase = _phase(events)
    iters = sum(1 for e in events if e["type"] == "tool_call")
    parts = ['<div class="svhead">🏗️ System overview — '
             '<b>Research loop</b>'
             '<span class="svtag">think → act → observe ↻</span></div>',
             '<div class="svring">']
    for key, label, arrow in (("think", "💭 think", "→"),
                              ("act", "🧰 act", "→"),
                              ("observe", "👁 observe", "↻")):
        cls = "active" if phase == key else ""
        parts.append(f'<div class="svphase {cls}">{label}</div>')
        parts.append(f'<div class="svarrow">{arrow}</div>')
    parts.append('<div class="svcenter">'
                 f'<div class="sviter">iteration <b>{iters + 1}</b></div>'
                 f'<div>step: <b>{current or "—"}</b></div>'
                 '<div class="svverify">📊 verification ring — citations '
                 'scored vs warehouse truth</div>'
                 '</div></div>')
    parts.append('<div class="svsteps">')
    for s in steps:
        st = statuses[s["name"]]
        parts.append(f'<div class="svstepchip {st}">{s["name"]}</div>')
    parts.append("</div>")
    if phase:
        parts.append(f'<div class="svnote">⏵ the loop is in the '
                     f'<b>{phase}</b> phase — the ring lights the active '
                     f'phase, the chips track plan progress. The same loop '
                     f'answers open-ended questions because the *content* '
                     f'is free, only the cycle is fixed.</div>')
    return "".join(parts)


# ── portfolio: orchestrator → workers → compose ──────────────────────
def _graph_view(events: list[dict]) -> str:
    steps, statuses, info, current = step_states(events)
    workers = (("sub_submissions", "run_submissions", "📥 Submissions"),
               ("sub_underwriting", "run_underwriting", "🔍 Underwriting"),
               ("sub_settlement", "run_settlement", "💸 Settlement"))
    last = events[-1] if events else {}
    t = last.get("type")
    assembly = ("done" if t in ("run_finished", "decision")
                else "running" if events else "pending")
    compose = ("done" if t == "run_finished"
               else "running" if t == "decision" else "pending")
    toolsg = ("running" if last.get("step") in ("stage_flow",
                                                "predisposing_signals")
              else "done" if t in ("run_finished", "decision") else "pending")

    parts = ['<div class="svhead">🏗️ System overview — '
             '<b>Orchestrator–workers</b>'
             '<span class="svtag">graph · fan-out → synthesize</span></div>',
             '<div class="svpipe">']
    parts.append(_node_html(1, "🎛️ Assembly loop (orchestrator)", assembly, {
        "tool": "run_* · stage_flow · predisposing_signals",
        "purpose": "Drives the three stage sub-harnesses as tools, then "
                   "composes the margin thesis over the lineage graph."}))
    parts.append('<div class="svlink ' + ("done" if assembly == "done"
                                          else "running" if assembly == "running"
                                          else "") + '"></div>')
    parts.append('<div class="svworkers">')
    for cid, step, label in workers:
        st = statuses.get(step, "pending")
        parts.append('<div class="svworker">' +
                     _node_html({"sub_submissions": 2, "sub_underwriting": 3,
                                 "sub_settlement": 4}[cid], label, st,
                                info.get(step, {})) + "</div>")
    parts.append("</div>")
    parts.append('<div class="svlink ' + ("done" if all(
        statuses.get(w[1], "pending") in ("done", "skipped") for w in workers)
        else "running") + '"></div>')
    parts.append(_node_html(5, "🧰 Tools + knowledge graph", toolsg, {
        "tool": "stage_flow · predisposing_signals",
        "purpose": "Funnel + lineage edges (FLOWS_TO / PREDISPOSES) — the "
                   "evidence the thesis is built on."}))
    parts.append('<div class="svlink ' + ("done" if toolsg == "done"
                                          else "running" if toolsg == "running"
                                          else "") + '"></div>')
    parts.append(_node_html(6, "🧠 Compose margin thesis", compose, {
        "purpose": "Reflection over aggregated verdicts + lineage signals → "
                   "PROFIT EDGE / MARGINAL / NO EDGE."}))
    parts.append("</div>")
    parts.append('<div class="svnote">⏵ <b>harness-as-tool</b> — each '
                 'worker is a full sub-agent (own plan, brain, harness) '
                 'driven by the assembly loop via <code>run_auto</code>. '
                 'Worker boxes fill with stage verdicts as their '
                 '<code>run_*</code> steps land.</div>')
    return "".join(parts)


# ── entry point ──────────────────────────────────────────────────────
def render_system_view(agent: str, events: list[dict] | None = None,
                       run_state: str | None = None) -> str:
    events = events or []
    if agent == "fraud":
        body = _linear_view(events)
    elif agent == "cost":
        body = _loop_view(events)
    else:
        body = _graph_view(events)
    return CSS + body

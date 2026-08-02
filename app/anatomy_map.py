"""The live anatomy map — "watch it think" (waku-agent style).

A self-describing component map per agent: the boxes are generated from
the same registry the Anatomy tab's source cards read, so the picture
cannot drift from the code. During a run, the boxes touched by the latest
event pulse; each box carries its event count and the real file path.

Three agents, three implementation styles — three topologies:

  🕵️ fraud      — deterministic workflow chain (+ reflection gate)
  📈 cost       — autonomous research loop (ReAct cycle + verification)
  🎯 portfolio  — orchestrator–workers (assembly drives 3 sub-harnesses)

Practitioner grounding (see README "Implementation styles"):
  Ng's agentic design patterns (DeepLearning.AI, 2024), Anthropic
  "Building Effective Agents" (2024), Harrison Chase / LangChain
  (plan-and-execute 2024; harness anatomy 2026; loop & graph engineering
  2026), Karpathy (verifiability 2025; autonomy slider), Zaremba
  (verifiable reliability), Howard/Answer.AI (deterministic guardrails).
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── component registry: the single source of truth the map + cards read ──
COMPONENTS: dict[str, list[dict]] = {
    "fraud": [
        {"id": "goal", "label": "🎯 Goal", "files": ["config/goal.yaml"],
         "color": "rgba(59,130,246,.13)", "desc": "Objective, budgets, thresholds."},
        {"id": "skills", "label": "📚 Skills", "files": ["skills/"],
         "color": "rgba(59,130,246,.13)", "desc": "Playbooks — edit a file, behaviour changes."},
        {"id": "plan", "label": "📝 Plan", "files": ["fraud_agent/planner.py"],
         "color": "rgba(139,92,246,.13)", "desc": "Goal + skills → ordered steps."},
        {"id": "loop", "label": "🔁 Loop", "files": ["fraud_agent/loop.py"],
         "color": "rgba(245,158,11,.13)", "desc": "Observe → think → act generator."},
        {"id": "brain", "label": "🧠 Brain", "files": ["fraud_agent/brain/"],
         "color": "rgba(245,158,11,.13)", "desc": "What next + how to score. Mock-LLM seam."},
        {"id": "harness", "label": "🛟 Harness", "files": ["fraud_agent/harness.py"],
         "color": "rgba(239,68,68,.13)", "desc": "Executes tools, budgets, autonomy gate."},
        {"id": "lifecycle", "label": "⏱️ Lifecycle", "files": ["fraud_agent/lifecycle.py"],
         "color": "rgba(239,68,68,.13)", "desc": "CREATED→…→PAUSED→COMPLETED/ESCALATED."},
        {"id": "tools", "label": "🧰 Tools", "files": ["fraud_agent/tools/"],
         "color": "rgba(34,197,94,.12)", "desc": "Registry + claims/policy/graph tools."},
        {"id": "graph", "label": "🕸️ Graph", "files": ["data/entities.json"],
         "color": "rgba(34,197,94,.12)", "desc": "Claimant/phone/address/shop entities."},
        {"id": "blackboard", "label": "🗂️ Blackboard", "files": ["fraud_agent/blackboard.py"],
         "color": "rgba(99,102,241,.13)", "desc": "Typed working memory, journaled by origin."},
        {"id": "dossier", "label": "📄 Dossier", "files": ["fraud_agent/dossier.py"],
         "color": "rgba(99,102,241,.13)", "desc": "One auditable artifact per run."},
        {"id": "eval", "label": "📊 Eval", "files": ["fraud_agent/eval/"],
         "color": "rgba(148,163,184,.10)", "desc": "Precision/recall vs labeled claims."},
        {"id": "learning", "label": "🎓 Learning", "files": ["fraud_agent/learning.py"],
         "color": "rgba(250,204,21,.12)", "desc": "Outcomes → weight proposals → human."},
    ],
    "cost": [
        {"id": "goal", "label": "🎯 Goal", "files": ["config/cost_goal.yaml"],
         "color": "rgba(59,130,246,.13)", "desc": "Objective, budgets, thresholds."},
        {"id": "skills", "label": "📚 Skills", "files": ["skills_cost/"],
         "color": "rgba(59,130,246,.13)", "desc": "Playbooks — edit a file, behaviour changes."},
        {"id": "plan", "label": "📝 Plan", "files": ["cost_agent/planner.py"],
         "color": "rgba(139,92,246,.13)", "desc": "Goal + skills → ordered steps."},
        {"id": "loop", "label": "🔁 Loop", "files": ["cost_agent/loop.py"],
         "color": "rgba(245,158,11,.13)", "desc": "Think → act → observe research cycle."},
        {"id": "brain", "label": "🧠 Brain", "files": ["cost_agent/brain/cost_brain.py"],
         "color": "rgba(245,158,11,.13)", "desc": "Question answering + driver hunting."},
        {"id": "harness", "label": "🛟 Harness", "files": ["fraud_agent/harness.py"],
         "color": "rgba(239,68,68,.13)", "desc": "Shared runtime shell (agent-agnostic)."},
        {"id": "lifecycle", "label": "⏱️ Lifecycle", "files": ["fraud_agent/lifecycle.py"],
         "color": "rgba(239,68,68,.13)", "desc": "Run state machine + registry."},
        {"id": "tools", "label": "🧰 Tools", "files": ["cost_agent/tools/cost_tools.py"],
         "color": "rgba(34,197,94,.12)", "desc": "Catalog/trend/guarded SQL/driver tools."},
        {"id": "graph", "label": "🕸️ Graph", "files": ["data/cost_entities.json"],
         "color": "rgba(34,197,94,.12)", "desc": "Driver tree = knowledge + semantic layer."},
        {"id": "blackboard", "label": "🗂️ Blackboard", "files": ["fraud_agent/blackboard.py"],
         "color": "rgba(99,102,241,.13)", "desc": "Typed working memory, journaled by origin."},
        {"id": "dossier", "label": "📄 Dossier", "files": ["fraud_agent/dossier.py"],
         "color": "rgba(99,102,241,.13)", "desc": "One auditable artifact per run."},
        {"id": "eval", "label": "📊 Eval", "files": ["cost_agent/eval/"],
         "color": "rgba(148,163,184,.10)", "desc": "Citations, numeric accuracy, faithfulness."},
        {"id": "learning", "label": "🎓 Learning", "files": ["cost_agent/learning.py"],
         "color": "rgba(250,204,21,.12)", "desc": "Validate drivers vs next-quarter actuals."},
    ],
    "portfolio": [
        {"id": "goal", "label": "🎯 Goal", "files": ["config/portfolio_assembly_goal.yaml"],
         "color": "rgba(59,130,246,.13)", "desc": "Assembly goal (3 stage goals alongside)."},
        {"id": "skills", "label": "📚 Skills", "files": ["skills_portfolio/"],
         "color": "rgba(59,130,246,.13)", "desc": "Playbooks — edit a file, behaviour changes."},
        {"id": "plan", "label": "📝 Plan", "files": ["portfolio_agent/assembly/planner.py"],
         "color": "rgba(139,92,246,.13)", "desc": "Stage runs + graph traversal + compose."},
        {"id": "assembly", "label": "🎛️ Assembly loop", "files": ["portfolio_agent/assembly/loop.py"],
         "color": "rgba(245,158,11,.13)", "desc": "Orchestrator: drives sub-harnesses AS tools."},
        {"id": "sub_submissions", "label": "📥 Submissions", "files": ["portfolio_agent/submissions/"],
         "color": "rgba(251,146,60,.13)", "desc": "Stage sub-agent (own plan/brain/harness)."},
        {"id": "sub_underwriting", "label": "🔍 Underwriting", "files": ["portfolio_agent/underwriting/"],
         "color": "rgba(251,146,60,.13)", "desc": "Stage sub-agent (risk score, pricing)."},
        {"id": "sub_settlement", "label": "💸 Settlement", "files": ["portfolio_agent/settlement/"],
         "color": "rgba(251,146,60,.13)", "desc": "Stage sub-agent (reserves, leakage)."},
        {"id": "harness", "label": "🛟 Harness", "files": ["portfolio_agent/assembly/harness.py"],
         "color": "rgba(239,68,68,.13)", "desc": "Drives the 3 sub-harnesses via run_auto."},
        {"id": "lifecycle", "label": "⏱️ Lifecycle", "files": ["fraud_agent/lifecycle.py"],
         "color": "rgba(239,68,68,.13)", "desc": "Run state machine + registry."},
        {"id": "tools", "label": "🧰 Tools", "files": ["portfolio_agent/assembly/tools.py"],
         "color": "rgba(34,197,94,.12)", "desc": "stage_flow + predisposing_signals."},
        {"id": "graph", "label": "🕸️ Graph", "files": ["data/portfolio_entities.json"],
         "color": "rgba(34,197,94,.12)", "desc": "Stage-flow lineage: FLOWS_TO + PREDISPOSES."},
        {"id": "blackboard", "label": "🗂️ Blackboard", "files": ["fraud_agent/blackboard.py"],
         "color": "rgba(99,102,241,.13)", "desc": "Typed working memory, journaled by origin."},
        {"id": "dossier", "label": "📄 Dossier", "files": ["fraud_agent/dossier.py"],
         "color": "rgba(99,102,241,.13)", "desc": "One auditable artifact per run."},
        {"id": "eval", "label": "📊 Eval", "files": ["portfolio_agent/eval/"],
         "color": "rgba(148,163,184,.10)", "desc": "Sub-agent + assembly + thesis-stage metrics."},
        {"id": "learning", "label": "🎓 Learning", "files": ["portfolio_agent/learning.py"],
         "color": "rgba(250,204,21,.12)", "desc": "Validate PREDISPOSES edges vs next-q actuals."},
    ],
}

# steps whose observation reads the knowledge graph
GRAPH_STEPS = {"network_analysis", "find_drivers", "gather_evidence",
               "stage_flow", "predisposing_signals", "driver_tree",
               "driver_event"}

# ── implementation styles (the pedagogy) ─────────────────────────────
STYLES = {
    "fraud": {
        "name": "Deterministic workflow + reflection + human gate",
        "lineage": "Ng · Reflection + Planning · Anthropic 'workflow' · "
                   "Karpathy's autonomy slider · Howard's tool allow-lists",
        "axis": 0.15,  # 0 = fully deterministic, 1 = fully agentic
        "wins": "Predictable · auditable · cheap per run · safe: every "
                "side-effect is gated, every step is a fixed, reviewable path.",
        "costs": "Inflexible: novel fraud schemes need a new step. The plan "
                 "is fixed before evidence arrives — the loop can't re-route.",
        "watch": "Run C-1011 with autonomy gated → the 🛟 Harness + ⏱️ "
                 "Lifecycle boxes pulse and the run PAUSES for your approval "
                 "(Karpathy's autonomy slider).",
    },
    "cost": {
        "name": "Autonomous research loop + verification",
        "lineage": "Ng · Tool Use + Planning · Anthropic 'agent' + "
                   "evaluator-optimizer · Chase's verification loop · "
                   "Zaremba/Karpathy verifiability",
        "axis": 0.6,
        "wins": "Flexible: answers open-ended 'why is X rising?' questions; "
                "guarded SQL + citation scoring keep it honest (verifiable "
                "outputs, Zaremba-style).",
        "costs": "More expensive per run; compounding-error risk without "
                 "guardrails; the reflect step re-derives numbers (Ng's "
                 "reflection pattern) before the verdict.",
        "watch": "Run Q3 → watch the research cycle spin; the 📊 Eval box "
                 "is the verification ring — every citation is scored "
                 "against warehouse truth.",
    },
    "portfolio": {
        "name": "Orchestrator–workers multi-agent",
        "lineage": "Ng · Multi-agent collaboration · Anthropic "
                   "orchestrator-workers · Chase 'a node can be a full "
                   "agent run' · Zaremba delegation",
        "axis": 0.8,
        "wins": "Parallelism + specialization: three stage experts + an "
                "assembly analyst = whole-journey scope no single agent "
                "could hold.",
        "costs": "Coordination overhead, isolated contexts, hardest to "
                 "trace and eval; a worker failure cascades into the thesis.",
        "watch": "Run BRO-W → the 🎛️ Assembly box fans out to the three "
                 "worker boxes, then synthesizes a margin thesis (harness "
                 "used as a tool).",
    },
}

# ── event → component mapping ────────────────────────────────────────
EDGE_BY_ID = {
    "goal": "#60a5fa", "skills": "#60a5fa", "plan": "#a78bfa",
    "loop": "#fbbf24", "brain": "#fbbf24", "assembly": "#fbbf24",
    "harness": "#f87171", "lifecycle": "#f87171",
    "tools": "#4ade80", "graph": "#4ade80",
    "blackboard": "#818cf8", "dossier": "#818cf8",
    "eval": "#94a3b8", "learning": "#facc15",
    "sub_submissions": "#fb923c", "sub_underwriting": "#fb923c",
    "sub_settlement": "#fb923c",
}


def hits_for(agent: str, ev: dict) -> set[str]:
    """Which component boxes light up for this event."""
    t = ev["type"]
    if t == "plan":
        return {"goal", "skills", "plan"}
    if t == "thought":
        return {"assembly", "brain"} if agent == "portfolio" else {"loop", "brain"}
    if t == "tool_call":
        return {"assembly", "tools"} if agent == "portfolio" else {"harness", "tools", "brain"}
    if t == "observation":
        if agent == "portfolio":
            step = ev.get("step", "")
            hits = {"assembly", "blackboard"}
            if step.startswith("run_"):
                hits.add(f"sub_{step[len('run_'):]}")
            if step in GRAPH_STEPS:
                hits.add("graph")
            return hits
        hits = {"loop", "blackboard"}
        if ev.get("step") in GRAPH_STEPS:
            hits.add("graph")
        return hits
    if t == "blackboard_write":
        return {"blackboard"}
    if t == "checkpoint":
        return {"harness", "lifecycle"}
    if t in ("decision", "decision_override"):
        return {"brain", "lifecycle"} if agent != "portfolio" else {"assembly", "lifecycle"}
    if t == "run_finished":
        return {"lifecycle", "dossier"}
    if t == "aborted":
        return {"harness", "lifecycle"}
    if t == "step_skipped":
        return {"loop", "brain"} if agent != "portfolio" else {"assembly"}
    if t == "tool_error":
        return {"harness", "tools"} if agent != "portfolio" else {"assembly", "tools"}
    return set()

# ── topologies: rows of boxes joined by arrows ───────────────────────
def _rows(agent: str) -> list[list]:
    if agent == "fraud":
        return [
            [("goal", None), ("skills", None), ("plan", None)],
            [("loop", "think/act"), ("brain", None)],
            [("harness", None), ("tools", "executes"), ("graph", "queries")],
            [("lifecycle", None), ("blackboard", None), ("dossier", None)],
            [("eval", None), ("learning", None)],
        ]
    if agent == "cost":
        return [
            [("goal", None), ("skills", None), ("plan", None)],
            [("loop", "↻ think→act→observe"), ("brain", None)],
            [("harness", None), ("tools", "guarded"), ("graph", "queries")],
            [("eval", "↻ verification ring"), ("blackboard", None), ("dossier", None)],
            [("learning", None)],
        ]
    # portfolio
    return [
        [("goal", None), ("skills", None), ("plan", None)],
        [("assembly", None)],
        [("sub_submissions", None), ("sub_underwriting", None), ("sub_settlement", None)],
        [("harness", None), ("tools", None), ("graph", None)],
        [("lifecycle", None), ("blackboard", None), ("dossier", None)],
        [("eval", None), ("learning", None)],
    ]

# ── HTML rendering ───────────────────────────────────────────────────
CSS = """
<style>
.ammap {display:flex; flex-direction:column; gap:6px; font-family:ui-sans-serif,system-ui,sans-serif;}
.amrow {display:flex; align-items:center; gap:6px; flex-wrap:wrap;}
.amarrow {color:#3d4d6f; font-size:1.1rem; font-weight:700; padding:0 2px;}
.ambox {border-radius:8px; padding:6px 10px; min-width:118px; flex:0 0 auto;
        border:1px solid #22314f; border-left:4px solid #94a3b8;
        font-size:.78rem; line-height:1.25; transition:all .25s;
        color:#e6ebf4;}
.ambox .amtitle {font-weight:700; font-size:.8rem;}
.ambox .amfile {font-family:ui-monospace,monospace; font-size:.62rem; opacity:.65;}
.ambox .amcount {font-size:.64rem; opacity:.75; margin-top:2px;}
.ambox .amlast {font-size:.62rem; margin-top:2px; font-weight:600;}
.ambox.idle {opacity:.5;}
.ambox.amstrip {min-width:92px; flex:1 1 0; padding:4px 8px;}
.ambox.amstrip .amtitle {font-size:.68rem;}
.ambox.amstrip .amcount {font-size:.6rem; margin-top:0;}
@keyframes ampulse {
  0% {box-shadow:0 0 0 0 rgba(139,92,246,.6);}
  70% {box-shadow:0 0 0 9px rgba(139,92,246,0);}
  100% {box-shadow:0 0 0 0 rgba(139,92,246,0);}
}
.ambox.hot {animation:ampulse 1.1s ease-out 2; outline:2px solid #8b5cf6; opacity:1;}
.ambox.paused {outline:2px solid #f59e0b; animation:ampulse 1.1s ease-out 2;}
.amstyle {font-size:.74rem; color:#8ea0bd; padding:4px 2px;}
.amstyle b {color:#e6ebf4;}
.amsub {display:flex; gap:8px; margin:6px 0;}
.amsublabel {font-size:.66rem; font-weight:700; color:#fbbf24;
             background:rgba(245,158,11,.15); border-radius:10px;
             padding:1px 8px; align-self:center;}
</style>
"""


def render_map(agent: str, events: list[dict] | None = None,
               run_state: str | None = None) -> str:
    """HTML string for st.markdown(unsafe_allow_html=True)."""
    events = events or []
    counts: dict[str, int] = {}
    hot: set[str] = set()
    last_line = ""
    for ev in events:
        for cid in hits_for(agent, ev):
            counts[cid] = counts.get(cid, 0) + 1
    if events:
        hot = hits_for(agent, events[-1])
        last = events[-1]
        if last["type"] == "tool_call":
            last_line = f"🧰 {last['tool']}"
        elif last["type"] == "observation":
            last_line = f"👁 {last['step']}"
        elif last["type"] == "thought":
            last_line = f"💭 {last['step']}"
        elif last["type"] == "blackboard_write":
            last_line = f"🗂️ {last['section']}.{last['key']}"
        elif last["type"] == "decision":
            last_line = f"✅ {last['decision']}"
        else:
            last_line = last["type"]

    style = STYLES[agent]
    boxes = {c["id"]: c for c in COMPONENTS[agent]}
    parts = [CSS,
             f'<div class="amstyle">🧭 <b>{style["name"]}</b> — '
             f'{style["lineage"]}</div>']
    for row in _rows(agent):
        parts.append('<div class="amrow">')
        for i, (cid, arrow) in enumerate(row):
            if i:
                parts.append('<span class="amarrow">→</span>')
            b = boxes[cid]
            hot_cls = "hot" if cid in hot else ("idle" if not counts.get(cid) else "")
            if run_state == "PAUSED" and cid == "lifecycle":
                hot_cls = "paused"
            n = counts.get(cid, 0)
            last = f'<div class="amlast">⏵ {last_line}</div>' if cid in hot and last_line else ""
            parts.append(
                f'<div class="ambox {hot_cls}" id="ambox-{cid}" '
                f'style="background:{b["color"]};'
                f'border-left-color:{EDGE_BY_ID.get(cid, "#94a3b8")}">'
                f'<div class="amtitle">{b["label"]}</div>'
                f'<div class="amfile">{b["files"][0]}</div>'
                f'<div class="amcount">{n} event{"s" if n != 1 else ""} '
                f'{("· pulsing" if cid in hot else "")}</div>{last}</div>')
            if arrow:
                parts.append(f'<span class="amarrow">[{arrow}]</span>')
        parts.append('</div>')
    if agent == "portfolio":
        parts.append('<div class="amsub"><span class="amsublabel">HARNESS-AS-TOOL</span>'
                     '<span style="font-size:.72rem;color:#8ea0bd;">the assembly '
                     'loop drives each stage sub-harness via <code>run_auto</code> — '
                     'the harness is itself a tool (Chase: "a node can be a full '
                     'agent run").</span></div>')
    return "".join(parts)


def render_strip(agent: str, events: list[dict] | None = None,
                 run_state: str | None = None) -> str:
    """Slim single-row component strip — which internals fired, at a glance.

    The component-level companion to the architecture view: same registry,
    same event mapping, no file paths or counts, so it stays a thin strip.
    """
    events = events or []
    counts: dict[str, int] = {}
    for ev in events:
        for cid in hits_for(agent, ev):
            counts[cid] = counts.get(cid, 0) + 1
    hot = hits_for(agent, events[-1]) if events else set()
    boxes = {c["id"]: c for c in COMPONENTS[agent]}
    parts = [CSS, '<div class="amrow amstrip-row">']
    for cid, b in boxes.items():
        hot_cls = "hot" if cid in hot else ("idle" if not counts.get(cid) else "")
        if run_state == "PAUSED" and cid == "lifecycle":
            hot_cls = "paused"
        n = counts.get(cid, 0)
        parts.append(
            f'<div class="ambox amstrip {hot_cls}" id="ambox-{cid}" '
            f'style="background:{b["color"]};'
            f'border-left-color:{EDGE_BY_ID.get(cid, "#94a3b8")}">'
            f'<div class="amtitle">{b["label"]}</div>'
            f'<div class="amcount">{n}</div></div>')
    parts.append("</div>")
    return "".join(parts)


def files_for(agent: str, cid: str) -> list[Path]:
    """Repo-relative paths for one component (existence-checked)."""
    comp = next(c for c in COMPONENTS[agent] if c["id"] == cid)
    out = []
    for f in comp["files"]:
        p = ROOT / f
        if p.is_dir():
            out += sorted(list(p.glob("*.py")) + list(p.glob("*.md")))[:10]
        else:
            out.append(p)
    return [p for p in out if p.exists()]

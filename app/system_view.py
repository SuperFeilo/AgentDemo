"""System overview — the architecture-aware live view for the Live Run tab.

The overview is tied to the selected agent's architecture, so you watch
the *system*, not just a log — each theme renders its true topology as
an SVG activation graphic, with the goal metric and exit condition
always visible:

  🕵️ fraud      — LINEAR: the action arrow travels the chain left→right;
                   a risk track under the chain shows how close the run
                   is to the REVIEW/ESCALATE thresholds.
  📈 cost       — LOOP with goal: a horizontal think→act→observe cycle
                   (arcs bowed between a phase row, orbiting activation),
                   with the confidence dial under the return arc showing
                   distance to the EXPLAINED ≥ 70 threshold; the
                   verification ring wraps the whole cycle.
  🎯 portfolio  — GRAPH: assembly fans out to three workers (solid
                   edges), verdicts pull back in (dashed return edges),
                   lineage signals are traversed (inset graph), then the
                   thesis is composed — with a confidence dial vs the
                   EDGE ≥ 70 threshold.

All three SVGs are wide-and-short so the diagram, the 📡 broadcast log
panel and the goal strip fit one screen together (the loop and graph
views additionally cap their rendered height with `.svsvg.compact`).

Every state is derived from the run's event list — the exact same list
the side execution feed renders — so the panes are synchronized by
construction. Metrics mirror the brains' own math (noisy_or over the
same candidates), and thresholds come from the same goal yamls the
planners read. Pure SVG + SMIL + CSS: no JS, no dependencies, offline.
"""
from __future__ import annotations

import math
from pathlib import Path

from fraud_agent.brain.rule_based import noisy_or
from fraud_agent.planner import load_goal
from fraud_agent.paths import GOAL_PATH
from cost_agent.planner import COST_GOAL_PATH

ROOT = Path(__file__).resolve().parent.parent
PORTFOLIO_GOAL = ROOT / "config" / "portfolio_assembly_goal.yaml"

# ── goal contract per agent (same files the planners read) ───────────
_GOALS = {
    "fraud": load_goal(GOAL_PATH),
    "cost": load_goal(COST_GOAL_PATH),
    "portfolio": load_goal(PORTFOLIO_GOAL),
}
CONSTRAINTS = {a: _GOALS[a]["constraints"] for a in _GOALS}


def _short_goal(agent: str, limit: int = 150) -> str:
    text = " ".join(_GOALS[agent]["statement"].split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


# ── shared CSS ───────────────────────────────────────────────────────
CSS = """
<style>
.sv {font-family:ui-sans-serif,system-ui,sans-serif; font-size:.8rem;
     color:#e6ebf4;}
.svhead {font-weight:700; margin-bottom:8px; color:#e6ebf4;}
.svhead .svtag {display:inline-block; font-size:.62rem; font-weight:700;
       letter-spacing:.08em; text-transform:uppercase; background:#22314f;
       color:#a5b4cf; border-radius:10px; padding:1px 8px; margin-left:6px;}
.svsvg {width:100%; height:auto; display:block; margin-top:6px;}
.svsvg.compact {width:auto; max-width:100%; max-height:44vh;
                margin-left:auto; margin-right:auto;}
.svsvg.loop {max-width:94%;}
.svsvg text {font-family:ui-sans-serif,system-ui,sans-serif;}
/* nodes */
.svn rect {transition: all .3s; rx:9px;}
.svn.pending rect {fill:rgba(148,163,184,.05); stroke:#22314f;}
.svn.done rect {fill:rgba(34,197,94,.13); stroke:#22c55e;}
.svn.running rect {fill:rgba(245,158,11,.15); stroke:#f59e0b;
                   animation:svnodepulse 1.2s ease-out infinite;}
.svn.skipped rect {fill:rgba(148,163,184,.04); stroke:#22314f; opacity:.5;}
.svn.paused rect {fill:rgba(245,158,11,.2); stroke:#f59e0b; stroke-width:2.5;
                  animation:svnodepulse 1s ease-out infinite;}
@keyframes svnodepulse {0%,100%{opacity:1;} 50%{opacity:.55;}}
.svn .svnum {font-weight:800; fill:#e6ebf4;}
.svn .svlab {font-weight:700; fill:#e6ebf4;}
.svn .svsub {fill:#a5b4cf; font-size:11.5px;}
.svn.skipped .svlab {text-decoration:line-through; fill:#64748b;}
/* edges */
.svedge {stroke:#22314f; stroke-width:2; fill:none;}
.svedge.done {stroke:#22c55e;}
.svedge.active {stroke:#f59e0b; stroke-width:2.5; stroke-dasharray:7 7;
                animation:svdash 1s linear infinite;}
.svedge.return {stroke-dasharray:5 5; stroke:#3d4d6f;}
.svedge.return.done {stroke:#22c55e; stroke-dasharray:5 5;}
.svedge.return.active {stroke:#22c55e; stroke-dasharray:5 5;
                       animation:svdash .8s linear infinite;}
@keyframes svdash {to {stroke-dashoffset:-14;}}
.svcomet {fill:#fbbf24; filter:drop-shadow(0 0 5px rgba(251,191,36,.9));}
.svcap {font-size:.68rem; fill:#8ea0bd;}
.svverif {font-size:.66rem; fill:#7dd3fc;}
/* goal / metric / exit strip */
.svgoal {font-size:.74rem; color:#8ea0bd; padding:2px 2px;}
.svgoal b {color:#e6ebf4;}
.svgoal .svgband {display:inline-block; font-size:.68rem; font-weight:700;
        border-radius:9px; padding:0 7px; margin-left:4px;}
/* live broadcast — the agent's own log, inline (scrollable) */
.svcastpanel {border:1px dashed #2a3a5c; border-radius:10px; padding:8px 12px;
              margin-top:10px; background:rgba(20,29,51,.45);
              max-height:340px; overflow-y:auto;}
.svcasttitle {font-size:.64rem; font-weight:700; letter-spacing:.08em;
              text-transform:uppercase; color:#8ea0bd; margin-bottom:4px;
              position:sticky; top:0; background:rgba(20,29,51,.92);
              padding:2px 0;}
.svcast {font-size:.76rem; color:#a5b4cf; padding:4px 6px; line-height:1.45;
         border-bottom:1px solid rgba(34,49,79,.6);}
.svcast:last-child {border-bottom:none;}
.svcast-latest {color:#e6ebf4; font-weight:600; border-radius:8px;
                padding:5px 8px; background:rgba(59,130,246,.10);
                outline:1px solid #3d4d6f; border-bottom:none; margin:2px 0;}
.svcast .svcstep {color:#fbbf24; font-weight:700;}
.svcast .svctool {font-family:ui-monospace,monospace; color:#d8b4fe;}
.svnote {font-size:.66rem; color:#8ea0bd; margin-top:6px;}
.svsteps {display:flex; gap:4px; flex-wrap:wrap; margin-top:8px;}
.svstepchip {font-size:.66rem; border-radius:8px; padding:2px 8px;
             background:rgba(148,163,184,.08); color:#8ea0bd;}
.svstepchip.done {background:rgba(34,197,94,.15); color:#4ade80;}
.svstepchip.running {background:rgba(245,158,11,.16); color:#fbbf24;
             font-weight:700; outline:1px solid #f59e0b;}
.svstepchip.skipped {background:rgba(148,163,184,.06); color:#64748b;
             text-decoration:line-through;}
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


def _last(events: list[dict], *types: str) -> dict | None:
    for e in reversed(events):
        if e["type"] in types:
            return e
    return None


# ── SVG builders ─────────────────────────────────────────────────────
def _pt(cx: float, cy: float, r: float, theta: float) -> tuple[float, float]:
    a = math.radians(theta)
    return (cx + r * math.cos(a), cy - r * math.sin(a))


def _arc_d(cx: float, cy: float, r: float, t0: float, t1: float,
           steps: int = 24) -> str:
    """Polyline arc (sampled — direction-unambiguous), angles in degrees
    with 0 = right, 90 = top, 270 = bottom."""
    step = (t1 - t0) / steps
    pts = [_pt(cx, cy, r, t0 + step * i) for i in range(steps + 1)]
    return ("M %.1f %.1f " % pts[0]
            + " ".join("L %.1f %.1f" % p for p in pts[1:]))


def _defs() -> str:
    return ('<defs>'
            '<marker id="svarr" viewBox="0 0 10 10" refX="8" refY="5" '
            'markerWidth="7" markerHeight="7" orient="auto">'
            '<path d="M0,0 L10,5 L0,10 z" fill="#3d4d6f"/></marker>'
            '<marker id="svarr-done" viewBox="0 0 10 10" refX="8" refY="5" '
            'markerWidth="7" markerHeight="7" orient="auto">'
            '<path d="M0,0 L10,5 L0,10 z" fill="#22c55e"/></marker>'
            '<marker id="svarr-active" viewBox="0 0 10 10" refX="8" refY="5" '
            'markerWidth="8" markerHeight="8" orient="auto">'
            '<path d="M0,0 L10,5 L0,10 z" fill="#f59e0b"/></marker>'
            "</defs>")


def _svg_node(cx: float, cy: float, w: float, h: float, num: int | None,
              label: str, status: str, sub: str = "", tip: str = "") -> str:
    tip_s = f"<title>{tip}</title>" if tip else ""
    cls = status if status in ("pending", "done", "running", "skipped",
                               "paused") else "pending"
    num_s = ""
    if num is not None:
        nx, ny = cx - w / 2 + 12, cy - h / 2 + 13
        num_s = (f'<circle cx="{nx:.1f}" cy="{ny:.1f}" r="9" '
                 f'fill="#3d4d6f"/>'
                 f'<text class="svnum" x="{nx:.1f}" y="{ny:.1f}" '
                 f'text-anchor="middle" dominant-baseline="central" '
                 f'font-size="10">{num}</text>')
    sub_s = (f'<text class="svsub" x="{cx:.1f}" y="{cy + 17:.1f}" '
             f'text-anchor="middle">{sub}</text>' if sub else "")
    return (f'<g class="svn {cls}">{tip_s}'
            f'<rect x="{cx - w / 2:.1f}" y="{cy - h / 2:.1f}" width="{w}" '
            f'height="{h}"/>{num_s}'
            f'<text class="svlab" x="{cx:.1f}" y="{cy + 1:.1f}" '
            f'text-anchor="middle" dominant-baseline="middle" '
            f'font-size="13.5">{label}</text>{sub_s}</g>')


def _svg_edge(d: str, state: str = "pending",
              returning: bool = False) -> str:
    marker = {"pending": "url(#svarr)", "done": "url(#svarr-done)",
              "active": "url(#svarr-active)"}[state]
    cls = f"svedge {state}" + (" return" if returning else "")
    return f'<path d="{d}" class="{cls}" marker-end="{marker}"/>'


def _comet(path_d: str, dur: str = "5s", begin: str = "0s",
           r: float = 6) -> str:
    inner = (f'<circle class="svcomet" r="{r:.0f}"><animateMotion dur="{dur}" '
             f'begin="{begin}" repeatCount="indefinite" path="{path_d}"/>'
             f"</circle>")
    halo = (f'<circle r="{r + 4:.0f}" fill="none" stroke="#fbbf24" '
            f'stroke-width="2" opacity=".45">'
            f'<animateMotion dur="{dur}" begin="{begin}" '
            f'repeatCount="indefinite" path="{path_d}"/></circle>')
    return halo + inner


def _band_badge(text: str, color: str) -> str:
    return (f'<span class="svgband" style="background:{color};'
            f'color:#0b1120;">{text}</span>')


def _dial(cx: float, cy: float, r: float, value: int,
          zones: list[tuple[int, int, str]],
          ticks: list[tuple[int, str]], label: str, sub: str) -> str:
    """Upper-semicircle gauge: colored zones, threshold ticks, pointer."""
    parts = []
    for v0, v1, color in zones:
        parts.append(f'<path d="{_arc_d(cx, cy, r, 180 - v0 * 1.8, 180 - v1 * 1.8)}" '
                     f'stroke="{color}" stroke-width="13" fill="none" '
                     f'stroke-opacity=".8"/>')
    for v, tlabel in ticks:
        x0, y0 = _pt(cx, cy, r - 5, 180 - v * 1.8)
        x1, y1 = _pt(cx, cy, r + 5, 180 - v * 1.8)
        tx, ty = _pt(cx, cy, r + 21, 180 - v * 1.8)
        parts.append(f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" '
                     f'y2="{y1:.1f}" stroke="#e6ebf4" stroke-width="1.5"/>')
        parts.append(f'<text class="svcap" x="{tx:.1f}" y="{ty:.1f}" '
                     f'text-anchor="middle">{tlabel}</text>')
    a = 180 - min(max(value, 0), 100) * 1.8
    px, py = _pt(cx, cy, r * 0.82, a)
    parts.append(f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{px:.1f}" '
                 f'y2="{py:.1f}" stroke="#e6ebf4" stroke-width="2.5"/>')
    parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="4.5" fill="#e6ebf4"/>')
    parts.append(f'<text x="{cx:.1f}" y="{cy + 38:.1f}" text-anchor="middle" '
                 f'font-size="27" font-weight="800" fill="#e6ebf4">{value}</text>')
    parts.append(f'<text class="svcap" x="{cx:.1f}" y="{cy + 56:.1f}" '
                 f'text-anchor="middle">{label}</text>')
    parts.append(f'<text class="svcap" x="{cx:.1f}" y="{cy + 70:.1f}" '
                 f'text-anchor="middle">{sub}</text>')
    return "".join(parts)


def _risk_track(x0: float, x1: float, y: float, value: int,
                esc: int, rev: int, label: str) -> str:
    w = x1 - x0
    parts = [f'<rect x="{x0}" y="{y - 4}" width="{w * esc / 100}" height="8" '
             f'rx="4" fill="rgba(34,197,94,.5)"/>',
             f'<rect x="{x0 + w * esc / 100}" y="{y - 4}" '
             f'width="{w * (rev - esc) / 100}" height="8" rx="4" '
             f'fill="rgba(245,158,11,.5)"/>',
             f'<rect x="{x0 + w * rev / 100}" y="{y - 4}" '
             f'width="{w * (100 - rev) / 100}" height="8" rx="4" '
             f'fill="rgba(239,68,68,.5)"/>']
    for v, tlabel in ((esc, f"REVIEW ≥ {esc}"), (rev, f"ESCALATE ≥ {rev}")):
        x = x0 + w * v / 100
        parts.append(f'<line x1="{x:.1f}" y1="{y - 12}" x2="{x:.1f}" '
                     f'y2="{y + 16}" stroke="#e6ebf4" stroke-width="1.5"/>')
        parts.append(f'<text class="svcap" x="{x:.1f}" y="{y + 30:.1f}" '
                     f'text-anchor="middle">{tlabel}</text>')
    mx = x0 + w * min(max(value, 0), 100) / 100
    parts.append(f'<polygon points="{mx:.1f},{y - 22} {mx - 7:.1f},{y - 8} '
                 f'{mx + 7:.1f},{y - 8}" fill="#e6ebf4"/>')
    parts.append(f'<text x="{x0}" y="{y - 22}" class="svcap" '
                 f'text-anchor="start">{label}</text>')
    return "".join(parts)


def _goal_strip(goal: str, metric: str, exit_: str) -> str:
    return (f'<div class="svgoal">🎯 <b>Goal:</b> {goal}</div>'
            f'<div class="svgoal">{metric}</div>'
            f'<div class="svgoal">🚪 {exit_}</div>')


# ── live broadcast: the agent's own log, inline (last 3, newest first) ─
_CAST_TYPES = ("thought", "tool_call", "observation", "step_skipped",
               "decision", "decision_override", "checkpoint", "run_finished",
               "aborted", "tool_error")


def _cast_line(ev: dict) -> str:
    t = ev["type"]
    step = ev.get("step")
    step_s = f'<span class="svcstep">{step}</span>' if step else ""
    def clip(s: str, n: int = 150) -> str:
        s = str(s).strip()
        return s if len(s) <= n else s[: n - 1] + "…"
    if t == "thought":
        return f"💭 think · {step_s} — {clip(ev['text'])}"
    if t == "tool_call":
        args = clip(str(ev.get("args")), 90)
        return f"🧰 act · {step_s} — <span class='svctool'>{ev['tool']}</span> {args}"
    if t == "observation":
        extra = " ⚠ self-corrected" if ev.get("corrected") else ""
        sig = ""
        sigs = ev.get("signals")
        if sigs:
            sig = " ▸ " + clip(" · ".join(sigs), 100)
        return f"👁 observe · {step_s} — {clip(ev.get('summary', ''), 140)}{sig}{extra}"
    if t == "step_skipped":
        return f"⏭ skip · {step_s} — {clip(ev.get('reason', ''), 120)}"
    if t == "decision":
        score = ev.get("risk_score", ev.get("confidence"))
        return f"✅ decide — <b>{ev['decision']}</b>" + (
            f" ({score})" if score is not None else "")
    if t == "decision_override":
        return f"🖐 override — → <b>{ev['decision']}</b> · {clip(ev.get('reason', ''), 100)}"
    if t == "checkpoint":
        return f"⏸ human checkpoint — {clip(ev.get('prompt', ''), 110)}"
    if t == "run_finished":
        return f"🏁 run finished — <b>{ev.get('decision')}</b>"
    if t == "aborted":
        return f"⛔ aborted — {clip(ev.get('reason', ''), 110)}"
    if t == "tool_error":
        return f"⚠ tool error · {step_s} — {clip(ev.get('error', ''), 110)}"
    return f"{t} — {clip(str(ev), 120)}"


def _broadcast_html(events: list[dict], limit: int = 3) -> str:
    """The agent's own log, inline — current event + the last 2, newest
    first, latest highlighted. Scrollable if a run produces more."""
    material = [e for e in events if e["type"] in _CAST_TYPES]
    if not material:
        return ""
    latest = material[-1]
    rows = []
    for ev in reversed(material[-limit:]):
        cls = "svcast-latest" if ev is latest else "svcast"
        rows.append(f'<div class="{cls}">{_cast_line(ev)}</div>')
    return ('<div class="svcastpanel"><div class="svcasttitle">📡 broadcast — '
            f'current step & findings (last {min(len(material), limit)})</div>'
            + "".join(rows) + "</div>")


# ── fraud: linear chain — travelling action arrow + risk-to-goal track ─
def _linear_view(events: list[dict], run_state: str | None) -> str:
    steps, statuses, info, current = step_states(events)
    c = CONSTRAINTS["fraud"]
    esc, rev = c["escalation_threshold"], c["review_threshold"]

    final = _last(events, "decision", "decision_override")
    risk = (final.get("risk_score") if final and "risk_score" in final
            else next((e.get("score", 0) for e in reversed(events)
                       if e["type"] == "observation" and e.get("score")),
                      None) or 0)
    band = final["decision"] if final else (
        "ESCALATE" if risk >= esc else "REVIEW" if risk >= rev else "APPROVE")
    band_color = ({"APPROVE": "rgba(34,197,94,.9)",
                   "REVIEW": "rgba(245,158,11,.9)",
                   "ESCALATE": "rgba(239,68,68,.9)"}.get(band, "#64748b"))

    n = len(steps)
    W, H, node_w, node_h, pitch, cy = 1180, 210, 118, 64, 150, 56
    x0 = 24
    centers = [x0 + i * pitch + node_w / 2 for i in range(n)]

    parts = [('<div class="svhead">🏗️ System overview — '
              '<b>Deterministic workflow</b>'
              '<span class="svtag">linear · chain</span></div>'),
             f'<svg class="svsvg" viewBox="0 0 {W} {H}">{_defs()}']

    for i, s in enumerate(steps):
        st = statuses[s["name"]]
        node_status = "paused" if (run_state == "PAUSED" and st == "running") \
            else st
        tip = info[s["name"]]["summary"] or info[s["name"]]["purpose"]
        parts.append(_svg_node(centers[i], cy, node_w, node_h, i + 1,
                               s["name"], node_status,
                               sub=info[s["name"]]["tool"] or "",
                               tip=tip))

    for i in range(n - 1):
        st = statuses[steps[i]["name"]]
        state = "done" if st == "done" else ("active" if st == "running"
                                             else "pending")
        parts.append(_svg_edge(f"M {centers[i] + node_w / 2:.1f} {cy}"
                               f" L {centers[i + 1] - node_w / 2:.1f} {cy}",
                               state))

    parts.append(_risk_track(60, 1120, 140, risk, esc, rev,
                             f"🎯 goal metric — risk score {risk}/100 → "
                             f"{band}"))
    parts.append("</svg>")
    parts.append(_broadcast_html(events))

    metric = (f"📏 <b>Metric:</b> risk score <b>{risk}/100</b> → "
              f"{_band_badge(band, band_color)} "
              + (f"({esc - risk} more to ESCALATE)" if risk < esc
                 else "(ESCALATE band reached — human gate ahead)"))
    exit_ = (f"<b>Exit:</b> all {n} steps complete → decision <b>{band}</b> · "
             f"harness stop: max_steps {c['max_steps']} · max_cost "
             f"{c['max_cost_units']}u · max_errors {c['max_tool_errors']}")
    parts.append(_goal_strip(_short_goal("fraud"), metric, exit_))
    if current:
        parts.append(f'<div class="svnote">⏵ now at step <b>{current}</b> — '
                     "the connector ahead lights as each step completes; the "
                     "broadcast above is the agent's own log, live. Step "
                     "order is fixed by the planner; only the evidence "
                     "differs per claim.</div>")
    return "".join(parts)


# ── cost: loop with goal — cycle ring + confidence-to-threshold dial ──
def _running_confidence(events: list[dict]) -> tuple[int, int, str]:
    """Recomputed exactly as the brain does: noisy_or over evidenced
    candidates (weight ≥ 0.40, direction matching the trend)."""
    c = CONSTRAINTS["cost"]
    trend = next((e for e in reversed(events)
                  if e["type"] == "observation"
                  and e.get("step") == "read_trend"), None)
    cum = trend["raw"]["cumulative_pct"] if trend else 0
    raw_t = trend["raw"] if trend else {}
    quarters = raw_t.get("quarters") or []
    peak = raw_t.get("peak_dev_pct") or 0
    pquarter = raw_t.get("peak_quarter")
    sustained = abs(cum) >= 5
    episodic = (not sustained and peak >= 5 and quarters and
                pquarter not in (quarters[0], quarters[-1]))
    if sustained:
        trend_dir = "+" if cum > 0 else "-"
    elif episodic:
        trend_dir = "+"
    else:
        return 0, 0, "UNEXPLAINED"  # flat — nothing to explain

    fd = next((e for e in reversed(events)
               if e["type"] == "observation"
               and e.get("step") == "find_drivers"), None)
    candidates = [d for d in (fd["raw"].get("drivers") if fd else [])
                  if d.get("weight", 0) >= 0.40 and d.get("direction") == trend_dir]
    evidenced = {e["raw"].get("driver_id") for e in events
                 if e["type"] == "observation"
                 and e.get("step") == "gather_evidence"}
    weights = [d["weight"] for d in candidates
               if d.get("driver_id") in evidenced]
    conf = round(100 * noisy_or(weights)) if weights else 0
    verdict = ("EXPLAINED" if conf >= c["explained_threshold"]
               else "PARTIALLY EXPLAINED" if conf >= c["partial_threshold"]
               else "UNEXPLAINED")
    return conf, len(candidates), verdict


def _loop_view(events: list[dict], run_state: str | None) -> str:
    steps, statuses, info, current = step_states(events)
    phase = _phase(events)
    iters = sum(1 for e in events if e["type"] == "tool_call")
    c = CONSTRAINTS["cost"]
    conf, ncand, verdict = _running_confidence(events)
    final = _last(events, "decision")
    if final:  # the brain's own verdict once it lands
        conf = final.get("confidence", conf)
        verdict = final.get("decision", verdict)

    # horizontal cycle: the three phases in a row, arcs between, the
    # confidence dial under the return arc — wide like the fraud chain
    node_w, node_h, py = 150, 62, 150
    phases = (("think", "💭 think", 200), ("act", "🧰 act", 590),
              ("observe", "👁 observe", 980))

    parts = [('<div class="svhead">🏗️ System overview — '
              '<b>Research loop</b>'
              '<span class="svtag">think → act → observe ↻</span></div>'),
             f'<svg class="svsvg compact loop" viewBox="0 0 1180 400">'
             f'{_defs()}']

    # the cycle: forward arcs bowed up, the long return arc below the row
    arcs = (("think", "act", 275, 515, 88), ("act", "observe", 665, 905, 88),
            ("observe", "think", 905, 275, 300))
    for src, dst, xa, xb, ctl in arcs:
        d = f"M {xa:.1f} {py} Q {(xa + xb) / 2:.1f} {ctl} {xb:.1f} {py}"
        state = "active" if phase == src else "done" if phase else "pending"
        parts.append(_svg_edge(d, state))

    # verification ring (evaluator-optimizer) — a flat band hugging the row
    parts.append(f'<ellipse cx="590" cy="{py}" rx="505" ry="85" fill="none" '
                 f'stroke="#2a3a5c" stroke-width="2" stroke-dasharray="4 7"/>')
    parts.append(f'<text class="svverif" x="590" y="{py - 62}" '
                 f'text-anchor="middle">verification ring — citations '
                 f"scored vs warehouse truth</text>")

    # orbiting activation around the cycle
    if events and run_state not in ("COMPLETED", "FAILED"):
        orbit = ("M 275 150 Q 395 88 515 150 "
                 "M 665 150 Q 785 88 905 150 "
                 "M 905 150 Q 590 300 275 150")
        parts.append(_comet(orbit, dur="6s"))

    # the three phases (drawn over the ring)
    for key, label, x in phases:
        st = "active" if phase == key else ""
        parts.append(_svg_node(x, py, node_w, node_h, None, label, st))

    # below the return arc: goal dial + iteration counter
    zones = [(0, c["partial_threshold"], "#ef4444"),
             (c["partial_threshold"], c["explained_threshold"], "#f59e0b"),
             (c["explained_threshold"], 100, "#22c55e")]
    ticks = [(c["partial_threshold"], f"≥{c['partial_threshold']}"),
             (c["explained_threshold"], f"≥{c['explained_threshold']}")]
    sub = (f"goal EXPLAINED ≥ {c['explained_threshold']} — "
           f"{'+' + str(c['explained_threshold'] - conf) + ' to go' if conf < c['explained_threshold'] else 'reached ✓'}")
    parts.append(_dial(590, 306, 52, conf, zones, ticks,
                       "confidence (goal metric)", sub))
    parts.append(f'<text class="svcap" x="980" y="350" '
                 f'text-anchor="middle">iteration <b>{iters + 1}</b> · step: '
                 f"<b>{current or '—'}</b></text>")
    parts.append("</svg>")
    parts.append(_broadcast_html(events, limit=5))

    chips = "".join(
        f'<div class="svstepchip {statuses[s["name"]]}">{s["name"]}</div>'
        for s in steps)
    parts.append(f'<div class="svsteps">{chips}</div>')
    distance = (f"+{c['explained_threshold'] - conf} to EXPLAINED"
                if conf < c["explained_threshold"] else "threshold reached ✓")
    metric = (f"📏 <b>Metric:</b> confidence <b>{conf}/100</b> → "
              f"<b>{verdict}</b> · {distance}"
              + (f" · {ncand} candidate driver(s)" if ncand else ""))
    exit_ = (f"<b>Exit:</b> compose once evidence is exhausted (flat trend "
             f"short-circuits to UNEXPLAINED) · harness stop: max_steps "
             f"{c['max_steps']} · max_cost {c['max_cost_units']}u · "
             f"max_errors {c['max_tool_errors']}")
    parts.append(_goal_strip(_short_goal("cost"), metric, exit_))
    if phase:
        parts.append(f'<div class="svnote">⏵ the loop is in the '
                     f'<b>{phase}</b> phase — the comet travels the cycle to '
                     "the active phase, the confidence dial fills as evidence "
                     "lands (same noisy_or the brain uses), the chips track "
                     "plan progress. Only the cycle is fixed; the content is "
                     "free.</div>")
    return "".join(parts)


# ── portfolio: orchestrator graph — fan-out → pull-in → decide ───────
def _running_portfolio_confidence(events: list[dict]) -> tuple[int, str]:
    c = CONSTRAINTS["portfolio"]
    sig = _last(events, "observation")
    while sig and sig.get("step") != "predisposing_signals":
        sig = None
    cands = (sig["raw"].get("candidates") or []) if sig else []
    top = [x for x in cands if x.get("weight", 0) >= c["min_signal_weight"]]
    conf = round(100 * noisy_or([x["weight"] for x in top])) if top else 0
    verdict = ("PROFIT EDGE IDENTIFIED" if conf >= c["edge_threshold"]
               else "MARGINAL" if conf >= c["marginal_threshold"]
               else "NO EDGE")
    return conf, verdict


def _lineage_inset(x0: float, y0: float, lit: bool, pulsing: bool,
                   pitch: int = 72) -> str:
    stages = (("submission", "📥 submission"), ("bind", "🔒 bind"),
              ("claim", "⚖️ claim"), ("settlement", "💸 settlement"))
    node_w, node_h = 150, 40
    parts = []
    for i, (sid, label) in enumerate(stages):
        if pulsing and i == len(stages) - 1:
            st = "running"
        else:
            st = "done" if lit else "pending"
        parts.append(_svg_node(x0 + node_w / 2, y0 + i * pitch, node_w,
                               node_h, None, label, st))
    for i in range(len(stages) - 1):
        parts.append(_svg_edge(
            f"M {x0 + node_w / 2:.1f} {y0 + i * pitch + node_h / 2:.1f}"
            f" L {x0 + node_w / 2:.1f} {y0 + (i + 1) * pitch - node_h / 2:.1f}",
            "done" if lit else "pending"))
    parts.append(f'<text class="svcap" x="{x0 + node_w / 2}" y="{y0 - 30}" '
                 f'text-anchor="middle">lineage graph · FLOWS_TO '
                 f'{"· traversed" if lit else "· idle"}</text>')
    return "".join(parts)


def _graph_view(events: list[dict], run_state: str | None) -> str:
    steps, statuses, info, current = step_states(events)
    c = CONSTRAINTS["portfolio"]

    workers = (("run_submissions", "sub_submissions", "📥 Submissions", 120),
               ("run_underwriting", "sub_underwriting", "🔍 Underwriting", 340),
               ("run_settlement", "sub_settlement", "💸 Settlement", 560))
    node_w, node_h = 200, 56
    ax, ay = 250, 78          # assembly center
    wy, ww = 200, node_w      # worker row
    tx, ty = 250, 300         # tools + lineage graph
    cx2, cy2 = 250, 392       # compose
    dx, dy = 800, 84          # goal dial

    last = events[-1] if events else {}
    t = last.get("type")
    run_done = t in ("run_finished", "decision")
    n_in = sum(1 for e in events if e["type"] == "observation"
               and str(e.get("step", "")).startswith("run_"))
    assembled = "done" if run_done else ("running" if events else "pending")
    compose_st = ("done" if run_done
                  else "running" if t == "decision" else "pending")
    lin_obs = next((e for e in reversed(events)
                    if e["type"] == "observation"
                    and e.get("step") in ("stage_flow",
                                          "predisposing_signals")), None)
    toolsg = ("done" if lin_obs else
              "running" if last.get("step") in ("stage_flow",
                                                "predisposing_signals")
              else "pending")

    final = _last(events, "decision")
    if final:
        conf, verdict = final["confidence"], final["decision"]
    else:
        conf, verdict = _running_portfolio_confidence(events)

    parts = [('<div class="svhead">🏗️ System overview — '
              '<b>Orchestrator–workers</b>'
              '<span class="svtag">graph · fan-out → pull-in → decide</span>'
              "</div>"),
             '<svg class="svsvg compact" viewBox="0 0 1180 440">' + _defs()]

    # goal dial (top right)
    zones = [(0, c["marginal_threshold"], "#ef4444"),
             (c["marginal_threshold"], c["edge_threshold"], "#f59e0b"),
             (c["edge_threshold"], 100, "#22c55e")]
    ticks = [(c["marginal_threshold"], f"≥{c['marginal_threshold']}"),
             (c["edge_threshold"], f"≥{c['edge_threshold']}")]
    sub = (f"edge ≥ {c['edge_threshold']} & top signal ≥ "
           f"{c['min_signal_weight']}"
           + (f" · {c['edge_threshold'] - conf} to go"
              if conf < c["edge_threshold"] else " · reached ✓"))
    parts.append(_dial(dx, dy, 52, conf, zones, ticks,
                       "confidence (goal metric)", sub))

    # lineage inset (right) — the graph-style retrieval
    lit = any(e["type"] == "observation" and e.get("step") == "stage_flow"
              for e in events)
    pulsing = last.get("step") == "predisposing_signals"
    parts.append(_lineage_inset(960, 175, lit, pulsing, pitch=60))

    # ── nodes ──
    sub_a = (f"{n_in}/3 verdicts pulled in" if n_in else
             "orchestrates the stage sub-agents as tools")
    parts.append(_svg_node(ax, ay, node_w, node_h, None, "🎛️ Assembly loop",
                           assembled, sub=sub_a,
                           tip="Drives the three stage sub-harnesses, pulls "
                               "their verdicts back in, then composes."))
    for step, cid, label, x in workers:
        st = statuses.get(step, "pending")
        raw = None
        for e in reversed(events):
            if e["type"] == "observation" and e.get("step") == step:
                raw = e["raw"]
                break
        if raw:
            sub = (f"{raw['verdict_label']} · {raw['n']} runs")
        elif st == "running":
            sub = "running…"
        else:
            sub = "idle"
        parts.append(_svg_node(x, wy, node_w, node_h, None, label, st,
                               sub=sub))
    parts.append(_svg_node(tx, ty, node_w, node_h, None,
                           "🧰 Tools + lineage graph", toolsg,
                           sub="stage_flow · predisposing_signals"))
    if final:
        comp_sub = f"{verdict} · conf {conf}"
    elif compose_st == "running":
        comp_sub = "composing…"
    else:
        comp_sub = "margin thesis"
    parts.append(_svg_node(cx2, cy2, 220, node_h, None,
                           "🧠 Compose margin thesis", compose_st,
                           sub=comp_sub))

    # ── edges: fan-out (solid) ──
    fan_ds: dict[str, str] = {}
    for step, cid, label, x in workers:
        st = statuses.get(step, "pending")
        state = "done" if st == "done" else (
            "active" if last.get("step") == step and t == "thought"
            else "pending")
        d = f"M {ax} {ay + node_h / 2} L {x} {wy - node_h / 2}"
        fan_ds[step] = d
        parts.append(_svg_edge(d, state))

    # ── edges: verdicts pull back in (dashed) ──
    ret_ds: dict[str, str] = {}
    for step, cid, label, x in workers:
        obs = any(e["type"] == "observation" and e.get("step") == step
                  for e in events)
        state = ("active" if (last.get("step") == step
                              and t in ("observation", "blackboard_write"))
                 else "done" if obs else "pending")
        if x == 120:
            d = (f"M {x} {wy + node_h / 2} C {x} 340 6 340 6 "
                 f"{ay + 8} L {ax - node_w / 2} {ay + 8}")
        elif x == 340:
            d = (f"M {x} {wy + node_h / 2} C 440 400 700 400 700 "
                 f"{wy + node_h / 2} L 700 {ay - 18} "
                 f"L {ax + node_w / 2} {ay - 18}")
        else:
            d = (f"M {x} {wy + node_h / 2} C {x} 340 680 340 680 "
                 f"{ay + 8} L {ax + node_w / 2} {ay + 8}")
        ret_ds[step] = d
        parts.append(_svg_edge(d, state, returning=True))

    # ── activation comets: delegation (fan-out) and pull-in (return) ──
    if events and run_state not in ("COMPLETED", "ESCALATED", "FAILED"):
        for step, cid, label, x in workers:
            if last.get("step") == step and t == "thought":
                parts.append(_comet(fan_ds[step], dur="1.1s"))
        for step, cid, label, x in workers:
            if last.get("step") == step and t in ("observation",
                                                  "blackboard_write"):
                parts.append(_comet(ret_ds[step], dur="0.9s", begin="0.1s"))

    # ── edges: lineage traversal (through the worker gap) + compose ──
    lstate = ("done" if lit else
              "active" if last.get("step") in ("stage_flow",
                                               "predisposing_signals")
              else "pending")
    parts.append(_svg_edge(f"M {ax + 8} {ay + node_h / 2} "
                           f"C {ax - 28} 168 {ax - 28} 252 "
                           f"{tx + 8} {ty - node_h / 2}",
                           lstate))
    cstate = ("done" if run_done else
              "active" if last.get("step") in ("compose", "reflect", "decision")
              else "pending")
    parts.append(_svg_edge(f"M {tx} {ty + node_h / 2} L {cx2} {cy2 - node_h / 2}",
                           cstate))
    parts.append("</svg>")
    parts.append(_broadcast_html(events, limit=5))

    metric = (f"📏 <b>Metric:</b> confidence <b>{conf}/100</b> → "
              f"<b>{verdict}</b> · top signal ≥ {c['min_signal_weight']} "
              "required")
    exit_ = (f"<b>Exit:</b> compose after all 3 stage verdicts + lineage "
             f"signals are pulled in · harness stop: max_steps "
             f"{c['max_steps']} · max_cost {c['max_cost_units']}u · "
             f"max_errors {c['max_tool_errors']}")
    parts.append(_goal_strip(_short_goal("portfolio"), metric, exit_))
    parts.append('<div class="svnote">⏵ <b>harness-as-tool</b> — solid '
                 'edges = delegation (fan-out to each stage sub-agent), '
                 'dashed edges = the verdicts <b>pulling back in</b> before '
                 'the next decision, right panel = the FLOWS_TO lineage '
                 'graph being traversed. Only after all three verdicts + '
                 'lineage signals land does the thesis compose.</div>')
    return "".join(parts)


# ── entry point ──────────────────────────────────────────────────────
def render_system_view(agent: str, events: list[dict] | None = None,
                       run_state: str | None = None) -> str:
    events = events or []
    if agent == "fraud":
        body = _linear_view(events, run_state)
    elif agent == "cost":
        body = _loop_view(events, run_state)
    else:
        body = _graph_view(events, run_state)
    return CSS + body

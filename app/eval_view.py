"""Eval Lab visual kit — the scoreboard.

Purpose made visible: every metric as a card with a Δ chip (vs the last
evaluation), a confusion heatmap (fraud), a per-case ✓/✗ grid, a
restyled release gate (grouped status table), a drill-in that renders
the run with the SAME cockpit Live Run uses, and an eval history that
makes learning's impact visible ("eval shows the delta").
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.components import _DARK
from app import ui

HISTORY_PATH = Path(__file__).resolve().parent.parent / "data" / \
    "eval_history.jsonl"

# ── delta chips / eval history ───────────────────────────────────────
def record_eval(agent: str, label: str, metrics: dict) -> dict:
    """Append this evaluation to the history; return {metrics, prev}."""
    prev = None
    if HISTORY_PATH.exists():
        for line in HISTORY_PATH.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
                if r.get("agent") == agent and r.get("label") == label:
                    prev = r
            except Exception:
                continue
    try:
        HISTORY_PATH.parent.mkdir(exist_ok=True)
        with HISTORY_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "ts": datetime.now().isoformat(timespec="seconds"),
                "agent": agent, "label": label, "metrics": metrics}) + "\n")
    except Exception:
        pass
    return {"metrics": metrics,
            "prev": (prev or {}).get("metrics")}


def delta_chip(cur: float, prev: float | None,
               higher_is_better: bool = True) -> str:
    if prev is None:
        return "<span class='postchip'>first run</span>"
    diff = cur - prev
    if abs(diff) < 1e-9:
        return "<span class='postchip'>= unchanged</span>"
    good = (diff > 0) == higher_is_better
    cls = "kvchip ok" if good else "kvchip hot"
    arrow = "▲" if diff > 0 else "▼"
    return (f'<span class="{cls}">{arrow} {diff:+.2f}</span>')


def metric_card(col, label: str, value, prev: float | None = None,
                higher_is_better: bool = True) -> None:
    with col:
        st.markdown(f"**{label}**")
        st.markdown(f'<div style="font-size:2rem;font-weight:800;'
                    f'color:#e6ebf4;">{value}</div>'
                    + delta_chip(float(value), prev, higher_is_better),
                    unsafe_allow_html=True)


# ── visual results ───────────────────────────────────────────────────
def confusion_heatmap(cm: dict) -> go.Figure:
    """2×2 confusion matrix: actual rows × predicted columns."""
    z = [[1, 0], [0, 1]]  # good cells = diagonal
    text = [[f"TP\n{cm['tp']}", f"FP\n{cm['fp']}"],
            [f"FN\n{cm['fn']}", f"TN\n{cm['tn']}"]]
    fig = go.Figure(go.Heatmap(
        z=z, x=["flagged", "not flagged"], y=["fraud", "legit"],
        text=text, texttemplate="%{text}",
        colorscale=[[0, "rgba(239,68,68,.30)"], [1, "rgba(34,197,94,.32)"]],
        showscale=False, xgap=6, ygap=6,
        hoverinfo="skip"))
    fig.update_layout(height=300, margin=dict(l=10, r=10, t=30, b=10),
                      xaxis_title="predicted", yaxis_title="actual",
                      **_DARK)
    return fig


def case_grid(rows: list[dict], id_key: str, ok_key: str,
              extra_keys: list[str] | None = None,
              pred_key: str = "verdict",
              truth_key: str = "ground_truth_verdict") -> None:
    """Per-case ✓/✗ chips — scannable, not a raw dataframe."""
    extra_keys = extra_keys or []
    html = ['<div class="kvchain"><div class="kvchaintitle">per case</div>'
            '<div class="kvrow">']
    for r in rows:
        ok = bool(r.get(ok_key))
        mark = '<span class="kvchip ok">✓ correct</span>' if ok else \
            '<span class="kvchip hot">✗ wrong</span>'
        chips = "".join(f'<span class="kvchip">{r.get(k, "?")}</span>'
                        for k in extra_keys)
        pred = r.get(pred_key, "?")
        if isinstance(pred, bool):
            pred = "flagged" if pred else "passed"
        html.append(
            f'<div class="kvnode"><div class="kvname">{r.get(id_key, "?")}'
            f' {mark}</div>{chips}'
            f'<div class="kvsub">pred {pred} · truth '
            f'{r.get(truth_key, "?")}</div></div>')
    html.append("</div></div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def distribution_bar(counts: dict[str, int], title: str) -> go.Figure:
    items = sorted(counts.items(), key=lambda kv: -kv[1])
    fig = go.Figure(go.Bar(
        x=[v for _, v in items], y=[k for k, _ in items],
        orientation="h", marker=dict(color="#a78bfa"),
        text=[str(v) for _, v in items], textposition="outside"))
    fig.update_layout(title=title, height=80 + 36 * len(items),
                      margin=dict(l=10, r=30, t=40, b=10),
                      yaxis=dict(autorange="reversed"), **_DARK)
    return fig


# ── release gate (restyled) ──────────────────────────────────────────
_GATE_GROUPS = [
    ("Core run", ("blackboard", "dossier", "origins", "latency")),
    ("Autonomy & budgets", ("autonomy", "gated", "checkpoint", "budget")),
    ("Reflection", ("reflect", "self-correct", "restored", "bug")),
    ("Learning", ("learning", "weights", "still green")),
]


def _gate_group(name: str) -> str:
    low = name.lower()
    for group, keys in _GATE_GROUPS:
        if any(k in low for k in keys):
            return group
    return "Core run"


def render_release_gate(agent: str) -> None:
    """Deterministic regression gate + bug sweep (Karpathy verifiability),
    as a grouped status table with a progress bar."""
    st.markdown("**🚦 Release gate** — deterministic, resettable checks "
                "(Karpathy's verifiability: *resettable, efficient, "
                "rewardable*). A bug found live is locked here so it can "
                "never come back (`python scripts/test_packs.py`).")
    if st.button("🧪 Run regression checks", key=f"gate_{agent}",
                 type="primary"):
        from fraud_agent.eval.regression import run_regression
        st.session_state[f"gate_report_{agent}"] = run_regression(agent)
    rep = st.session_state.get(f"gate_report_{agent}")
    if rep:
        c1, c2 = st.columns([2, 3])
        ok = rep["passed"] == rep["total"]
        with c1:
            st.metric("Checks passed", f"{rep['passed']}/{rep['total']}")
        with c2:
            st.markdown(f'<div style="font-size:1.1rem;font-weight:800;'
                        f'color:{"#4ade80" if ok else "#f87171"};">'
                        f'{"✅ RELEASE" if ok else "🚫 BLOCK"}</div>',
                        unsafe_allow_html=True)
        st.progress(rep["passed"] / rep["total"])
        rows = [{"group": _gate_group(c["name"]), "check": c["name"],
                 "status": "✅" if c["passed"] else "❌",
                 "detail": str(c["detail"])[:70]}
                for c in rep["checks"]]
        st.dataframe(pd.DataFrame(rows), hide_index=True,
                     use_container_width=True,
                     column_config={"detail": st.column_config.TextColumn(
                         width="medium")})
    st.markdown("**🐛 Bug sweep** — every planted reasoning bug, injected, "
                "and the reflect step must catch it.")
    if st.button("🧪 Run bug sweep", key=f"sweep_{agent}"):
        from fraud_agent.eval.regression import run_bug_sweep
        st.session_state[f"sweep_report_{agent}"] = run_bug_sweep(agent)
    sweep = st.session_state.get(f"sweep_report_{agent}")
    if sweep:
        ok = sweep["passed"] == sweep["total"]
        st.markdown(f"{'✅' if ok else '❌'} **Reflection caught "
                    f"{sweep['passed']}/{sweep['total']} planted bugs** — "
                    f"without the reflect step these leak into the verdict.")
        for c in sweep["checks"]:
            st.markdown(f"{'✅' if c['passed'] else '❌'} {c['name']} — "
                        f"{c['detail']}")


# ── drill-in: the run, rendered like Live Run ────────────────────────
def render_drill_in(agent: str, harness, key_suffix: str,
                    subjects: list, fmt) -> None:
    labels = [fmt(s) for s in subjects]
    pick = st.selectbox("Drill into a run — rendered exactly like "
                        "Live Run", labels,
                        key=f"drill_sel_{agent}_{key_suffix}")
    subject = subjects[labels.index(pick)]
    result_key = f"drill_{agent}_{key_suffix}"
    if st.button("▶ Run & inspect", key=f"drill_run_{agent}_{key_suffix}"):
        drill = harness.start_run(subject)
        driver = harness.drive(drill)
        events, send, started = [], None, False
        while True:
            try:
                ev = driver.send(send) if started else next(driver)
                started = True
            except StopIteration:
                break
            events.append(ev)
            send = True if ev["type"] == "checkpoint" else None
        st.session_state[result_key] = {"events": events, "run": drill}
    held = st.session_state.get(result_key)
    if held:
        from app.run_view import render_run_cockpit
        render_run_cockpit(agent, {"events": held["events"],
                                   "run": held["run"]}, harness,
                           toggle_suffix=f"drill_{key_suffix}")


# ── eval history ─────────────────────────────────────────────────────
def render_history(agent: str) -> None:
    if not HISTORY_PATH.exists():
        return
    rows = []
    for line in HISTORY_PATH.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
            if r.get("agent") == agent:
                rows.append(r)
        except Exception:
            continue
    if not rows:
        return
    with st.expander("🗂️ Eval history (persisted — the delta loop)"):
        st.caption("Each run of an eval appends here; the scoreboard's "
                   "▲▼ chips compare against the previous run of the "
                   "same eval. Change knowledge in 🎓 Learning, come "
                   "back and re-run — the delta shows learning's impact.")
        for r in reversed(rows[-8:]):
            m = r.get("metrics", {})
            line = " · ".join(f"{k}={v}" for k, v in list(m.items())[:6])
            st.markdown(f"`{r['ts']}` **{r['label']}** — {line}")

"""Agent workspace pages — one page set, three agents.

Each page function renders for exactly one agent (partial-applied into
st.Page by app/nav.py), so "same UI concept across all agents" holds by
construction: the layout is identical, only data and brains differ.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd
import streamlit as st

from app.anatomy_map import COMPONENTS, files_for, render_map
from app.demo_guide import guide_hint
from app import ui
from fraud_agent.paths import DATA_DIR, GOAL_PATH

ROOT = Path(__file__).resolve().parent.parent
CLAIMS = ui.load_claims()


# ════════════════════════════════════════════════════════════════════
# 🧠 ANATOMY
# ════════════════════════════════════════════════════════════════════
def anatomy_page(agent: str) -> None:
    ui.render_sidebar_controls(agent)
    ui.agent_header(agent, "Anatomy")
    st.markdown('<div class="pagemuted">Every component of agent anatomy '
                "is real code you can read — and you can watch them work "
                "together live in Live Run.</div>", unsafe_allow_html=True)

    ui.section("How the components connect — live")
    _live_here = st.session_state.get("live")
    _live_evts = (_live_here["events"] if _live_here
                  and _live_here["agent"] == agent else None)
    _live_state = (_live_here["run"].state.value if _live_here
                   and _live_here["agent"] == agent else None)
    st.markdown(render_map(agent, _live_evts, _live_state),
                unsafe_allow_html=True)
    st.caption("Nothing here is hand-drawn: the boxes are generated from "
               "the same registry the component cards below read, so the "
               "picture cannot drift from the code. Start a run in "
               "▶️ Live Run and come back — the boxes pulse with the trace.")

    ui.section("Component → real code (every box maps to a file)")
    st.caption("Each box on the map opens the actual source it was "
               "generated from — the waku-agent promise, 'code you can "
               "read in an afternoon', made literal.")
    cols = st.columns(2)
    for i, comp in enumerate(COMPONENTS[agent]):
        files = files_for(agent, comp["id"])
        with cols[i % 2]:
            with st.expander(
                    f"{comp['label']} — "
                    f"`{' · '.join(f for f in comp['files'])}`",
                    expanded=False):
                st.markdown(comp["desc"])
                for p in files:
                    st.code(p.read_text(encoding="utf-8"),
                            language="python" if p.suffix == ".py" else None)

    with st.expander("🗂️ Agent skeleton — the whole file tree, readable"):
        _tree = {}
        for comp in COMPONENTS[agent]:
            for p in files_for(agent, comp["id"]):
                _tree[str(p.relative_to(ROOT))] = p
        for rel, p in sorted(_tree.items()):
            with st.expander(f"`{rel}`", expanded=False):
                st.code(p.read_text(encoding="utf-8"),
                        language="python" if p.suffix == ".py" else None)

    goal_path = GOAL_PATH if agent == "fraud" else (
        ROOT / "config" / "portfolio_assembly_goal.yaml"
        if agent == "portfolio" else ROOT / "config" / "cost_goal.yaml")
    t1, t2 = st.tabs(["🎯 The goal (loaded at planning time)",
                      "📚 Skill playbooks"])
    with t1:
        st.code(goal_path.read_text(), language="yaml")
    with t2:
        harness = ui.get_harness(agent)
        for name, text in harness.plan.skills.items():
            with st.expander(f"📚 {name}"):
                st.markdown(text)


# ════════════════════════════════════════════════════════════════════
# ▶️ LIVE RUN
# ════════════════════════════════════════════════════════════════════
def live_page(agent: str) -> None:
    _live_pre = st.session_state.get("live")
    _events_before = (len(_live_pre["events"]) if _live_pre
                      and _live_pre.get("agent") == agent else 0)
    ui.render_sidebar_controls(agent)
    ui.agent_header(agent, "Live Run")
    harness = ui.get_harness(agent)
    autonomy = st.session_state.get("autonomy", "gated")
    bug = st.session_state.get("bug", False)
    autoplay = st.session_state.get("autoplay", False)

    # 🎬 guided demo: a "Load & run" click pre-sets everything below
    guide_action = st.session_state.pop("guide_action", None)
    if guide_action and guide_action["agent"] != agent:
        guide_action = None
    _guide = guide_action["guide"] if guide_action else None
    _subj_id = _guide["subject"] if _guide else None

    if agent == "fraud":
        _opts = list(CLAIMS)
        _def = _opts.index(_subj_id) if _subj_id in _opts else 0
        subject = st.selectbox(
            "Claim to investigate", options=_opts, index=_def,
            key=f"subject_{agent}",
            format_func=lambda c: f"{c} · {CLAIMS[c]['claim_type']} · "
                                  f"${CLAIMS[c]['amount']:,} · "
                                  f"hint: {ui.PATTERN_HINTS[c]}")
    elif agent == "portfolio":
        segments = ui.get_segments()
        _opts = segments
        _def = next((i for i, s in enumerate(_opts)
                     if isinstance(_subj_id, dict)
                     and s["id"] == _subj_id["id"]), 0)
        subject = st.selectbox(
            "Market segment to analyse", options=_opts, index=_def,
            key=f"subject_{agent}",
            format_func=lambda s: f"{s['id']} — broker={s['segment']['broker']}"
                                  f" · class={s['segment']['class_code']}"
                                  f" · region={s['segment']['region']}")
    else:
        questions = ui.get_questions()
        _opts = questions
        _def = next((i for i, q in enumerate(_opts)
                     if q["id"] == _subj_id), 0)
        subject = st.selectbox(
            "Research question", options=_opts, index=_def,
            key=f"subject_{agent}",
            format_func=lambda q: f"{q['id']} — {q['text']}")
    st.caption("▶️ Run controls — Start / Step / Autoplay / autonomy / "
               "bug / human checkpoint — are pinned in the sidebar, "
               "always visible.")

    # auto-start a guided scenario if one was just loaded
    if guide_action and not (
            "live" in st.session_state
            and st.session_state.live["agent"] == agent):
        harness.brain.bug_injection = bug
        run = harness.start_run(subject,
                                autonomy_level=("full" if autonomy == "full"
                                                else "gated"))
        st.session_state.live = {"agent": agent, "run": run,
                                 "driver": harness.drive(run), "events": [],
                                 "done": False, "awaiting": False,
                                 "autoplay": autoplay}
        st.session_state.guide_hint = guide_action["guide"]
        st.rerun()

    if "live" in st.session_state and st.session_state.live["agent"] == agent:
        live = st.session_state.live
        live["autoplay"] = autoplay
        run = live["run"]

        if live["autoplay"] and not live["done"] and not live["awaiting"]:
            if len(live["events"]) == _events_before:
                if ui.advance_run(agent):
                    time.sleep(0.8)
                    st.rerun()

        from app.run_view import render_run_cockpit

        def _feed_footer() -> None:
            hint = guide_hint(agent,
                              st.session_state.pop("guide_hint", None))
            if hint:
                st.info(hint)
            if live["awaiting"] and live["events"] and \
                    live["events"][-1]["type"] == "checkpoint":
                st.warning("⏸️ Run paused at a human checkpoint — approve "
                           "or reject in the **▶️ Run controls** (sidebar, "
                           "always visible).")
            elif not live["done"] and not live["autoplay"]:
                st.info("Press **⏭️ Step** in the sidebar's ▶️ Run "
                        "controls (or enable Autoplay) to advance the "
                        "loop.")

        render_run_cockpit(agent, live, harness, feed_footer=_feed_footer,
                           toggle_suffix="live")
    else:
        if agent == "fraud":
            st.info("Pick a claim and press **▶️ Start run**. Step through "
                    "the loop and watch it think, call tools, and — when "
                    "risk is high — pause for your approval.")
        elif agent == "portfolio":
            st.info("Pick a market segment and press **▶️ Start run**. "
                    "Watch the assembly agent drive the three stage "
                    "sub-agents (submissions / underwriting / settlement), "
                    "then compose a margin thesis over the stage-flow "
                    "lineage graph.")
        else:
            st.info("Pick a research question and press **▶️ Start run**. "
                    "Watch the analyst quantify the trend from the "
                    "warehouse, then hunt for honest drivers in the "
                    "knowledge graph.")


# ════════════════════════════════════════════════════════════════════
# 📊 EVAL LAB
# ════════════════════════════════════════════════════════════════════
def eval_page(agent: str) -> None:
    ui.render_sidebar_controls(agent)
    ui.agent_header(agent, "Eval Lab")
    harness = ui.get_harness(agent)
    from app import eval_view as ev

    ui.section("🎯 Purpose — measure the agent against ground truth")
    st.caption("The verifiability pillar: run the agent over a labeled "
               "dataset and score every decision against the known "
               "truth — deterministic checks, no judge, no opinions "
               "(Karpathy: *'Software 2.0 easily automates what you can "
               "verify'*). The scoreboard shows where the agent is "
               "right, where it fails, and — thanks to the ▲▼ chips — "
               "how it changes as knowledge is learned in 🎓 Learning.")

    if agent == "fraud":
        _eval_fraud(ev, harness)
    elif agent == "portfolio":
        _eval_portfolio(ev, harness)
    else:
        _eval_cost(ev, harness)


def _eval_fraud(ev, harness) -> None:
    st.caption("**Dataset:** 6 fraud / 8 legit claims. A claim counts as "
               "*flagged* when its risk score ≥ threshold — sweep the "
               "threshold to trade precision for recall.")
    c1, c2 = st.columns([1, 3])
    threshold = c1.slider("Flag threshold (risk)", 10, 90, 40, 5,
                          key="eval_thr_fraud")
    if c2.button("🧪 Run eval — investigate all 14 claims",
                 type="primary", use_container_width=True,
                 key="eval_run_fraud"):
        from fraud_agent.eval.runner import run_eval
        rep = run_eval(threshold)
        st.session_state.eval_report = rep
        st.session_state.eval_delta = ev.record_eval(
            "fraud", f"threshold={threshold}",
            {k: round(v, 3) for k, v in rep["metrics"].items()})
    rep = st.session_state.get("eval_report")
    if not rep:
        st.info("Press **🧪 Run eval** — the agent investigates all 14 "
                "claims and each one is scored against its label.")
        ev.render_release_gate("fraud")
        ev.render_history("fraud")
        return
    m, cm = rep["metrics"], rep["confusion"]
    prev = (st.session_state.get("eval_delta") or {}).get("prev")
    ui.section("📈 Scoreboard")
    cols = st.columns(4)
    ev.metric_card(cols[0], "Precision", f"{m['precision']:.2f}",
                   prev and prev.get("precision"))
    ev.metric_card(cols[1], "Recall", f"{m['recall']:.2f}",
                   prev and prev.get("recall"))
    ev.metric_card(cols[2], "F1", f"{m['f1']:.2f}",
                   prev and prev.get("f1"))
    ev.metric_card(cols[3], "Accuracy", f"{m['accuracy']:.2f}",
                   prev and prev.get("accuracy"))
    st.caption(f"threshold {rep['flag_threshold']} — TP {cm['tp']} · "
               f"FP {cm['fp']} · TN {cm['tn']} · FN {cm['fn']}")

    ui.section("🔍 Where it fails — the confusion story")
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(ev.confusion_heatmap(cm), use_container_width=True)
    with c2:
        rows = [{**r, "ok": (r["label"] == "fraud") == r["flagged"]}
                for r in rep["results"]]
        ev.case_grid(rows, "claim_id", "ok", ["label", "risk_score"],
                     pred_key="flagged", truth_key="label")
    ui.section("🔬 Drill into a run")
    ev.render_drill_in("fraud", harness, "claims",
                       [r["claim_id"] for r in rep["results"]], str)
    ui.section("🚦 Release gate")
    ev.render_release_gate("fraud")
    ev.render_history("fraud")


def _eval_portfolio(ev, harness) -> None:
    st.caption("**Dataset:** the portfolio-journey system — two batch "
               "evals: the three stage sub-agents (verdict accuracy + "
               "citation recall) and the assembly agent (verdict + "
               "margin-thesis stage match + provenance coverage).")
    c1, c2 = st.columns(2)
    if c1.button("🧪 Sub-agent eval", type="primary",
                 key="pf_sub_eval_btn"):
        from portfolio_agent.eval.runner import run_eval as pf_sub_eval
        rep = pf_sub_eval()
        st.session_state.portfolio_sub_eval = rep
        st.session_state.pf_sub_delta = ev.record_eval(
            "portfolio", "sub-agents",
            {k: round(v, 3) for k, v in rep["metrics"].items()})
    if c2.button("🧪 Assembly eval", type="primary",
                 key="pf_assembly_eval_btn"):
        from portfolio_agent.eval.assembly_runner import \
            run_eval as pf_as_eval
        rep = pf_as_eval()
        st.session_state.portfolio_assembly_eval = rep
        st.session_state.pf_asm_delta = ev.record_eval(
            "portfolio", "assembly",
            {k: round(v, 3) for k, v in rep["metrics"].items()})

    rep = st.session_state.get("portfolio_sub_eval")
    if rep:
        m = rep["metrics"]
        prev = (st.session_state.get("pf_sub_delta") or {}).get("prev")
        ui.section("📈 Sub-agent scoreboard")
        cols = st.columns(2)
        ev.metric_card(cols[0], "Verdict accuracy",
                       f"{m['verdict_accuracy']:.2f}",
                       prev and prev.get("verdict_accuracy"))
        ev.metric_card(cols[1], "Citation recall",
                       f"{m['citation_recall']:.2f}",
                       prev and prev.get("citation_recall"))
        ok = sum(1 for r in rep["results"] if r["verdict_ok"])
        ev.distribution_bar({"correct": ok,
                             "wrong": len(rep["results"]) - ok},
                            "stage verdicts")
        ui.section("🔍 Per case")
        ev.case_grid(rep["results"], "id", "verdict_ok",
                     ["stage", "subject_id"])
        ui.section("🔬 Drill into a stage run")
        ev.render_drill_in(
            "portfolio", harness, "sub",
            [{"submission_id": r["subject_id"]} for r in rep["results"]],
            lambda s: f"submission {s['submission_id']}")

    rep = st.session_state.get("portfolio_assembly_eval")
    if rep:
        m = rep["metrics"]
        prev = (st.session_state.get("pf_asm_delta") or {}).get("prev")
        ui.section("📈 Assembly scoreboard")
        cols = st.columns(3)
        ev.metric_card(cols[0], "Verdict accuracy", f"{m['verdict_ok']:.2f}",
                       prev and prev.get("verdict_ok"))
        ev.metric_card(cols[1], "Margin thesis match",
                       f"{m['margin_thesis_ok']:.2f}",
                       prev and prev.get("margin_thesis_ok"))
        ev.metric_card(cols[2], "Provenance coverage",
                       f"{m['provenance_ok']:.2f}",
                       prev and prev.get("provenance_ok"))
        rows = [{**r, "lead_stage": (r.get("lead_signal") or {})
                 .get("stage", "?")} for r in rep["results"]]
        ui.section("🔍 Per case")
        ev.case_grid(rows, "id", "verdict_ok",
                     ["segment", "confidence", "lead_stage"])
        ui.section("🔬 Drill into an assembly run")
        ev.render_drill_in(
            "portfolio", harness, "asm",
            [r["segment"] for r in rep["results"]],
            lambda s: (f"{s['broker']}/{s['class_code']}/{s['region']}"))
    ev.render_release_gate("portfolio")
    ev.render_history("portfolio")


def _eval_cost(ev, harness) -> None:
    st.caption("**Dataset:** 6 research questions, scored on three axes "
               "each — citation precision/recall vs. ground-truth "
               "drivers, numeric accuracy vs. the warehouse, and "
               "faithfulness (the stated number literally appears in "
               "the explanation).")
    if st.button("🧪 Run eval — answer all questions",
                 type="primary", key="cost_eval_run"):
        from cost_agent.eval.runner import run_eval as cost_run_eval
        rep = cost_run_eval()
        st.session_state.cost_eval_report = rep
        st.session_state.cost_eval_delta = ev.record_eval(
            "cost", "full",
            {k: round(v, 3) for k, v in rep["metrics"].items()})
    rep = st.session_state.get("cost_eval_report")
    if not rep:
        st.info("Press **🧪 Run eval** — the analyst answers every "
                "question and each explanation is scored against the "
                "warehouse and the ground-truth drivers.")
        ev.render_release_gate("cost")
        ev.render_history("cost")
        return
    m = rep["metrics"]
    prev = (st.session_state.get("cost_eval_delta") or {}).get("prev")
    ui.section("📈 Scoreboard")
    cols = st.columns(6)
    ev.metric_card(cols[0], "Citation precision",
                   f"{m['citation_precision']:.2f}",
                   prev and prev.get("citation_precision"))
    ev.metric_card(cols[1], "Citation recall",
                   f"{m['citation_recall']:.2f}",
                   prev and prev.get("citation_recall"))
    ev.metric_card(cols[2], "Numeric accuracy",
                   f"{m['numeric_accuracy']:.2f}",
                   prev and prev.get("numeric_accuracy"))
    ev.metric_card(cols[3], "Faithfulness", f"{m['faithfulness']:.2f}",
                   prev and prev.get("faithfulness"))
    ev.metric_card(cols[4], "Provenance", f"{m['provenance_coverage']:.2f}",
                   prev and prev.get("provenance_coverage"))
    ev.metric_card(cols[5], "Mean confidence",
                   f"{m['mean_confidence']:.0f}",
                   prev and prev.get("mean_confidence"),
                   higher_is_better=True)

    ui.section("🔍 Where it fails")
    rows = [{**r, "ok": bool(r["numeric_ok"] and r["faithful"]
                             and r["provenance_ok"]),
             "truth": f"{len(r['required'])} driver(s)"}
            for r in rep["results"]]
    ok = sum(1 for r in rows if r["ok"])
    ev.distribution_bar({"clean explanations": ok,
                         "issues": len(rows) - ok}, "per question")
    ev.case_grid(rows, "id", "ok",
                 ["verdict", "confidence", "numeric_ok", "faithful"],
                 truth_key="truth")
    ui.section("🔬 Drill into a run")
    questions = [q for q in ui.get_questions()
                 if q["id"] in {r["id"] for r in rep["results"]}]
    ev.render_drill_in("cost", harness, "questions", questions,
                       lambda q: f"{q['id']} — {q['text'][:55]}")
    ui.section("🚦 Release gate")
    ev.render_release_gate("cost")
    ev.render_history("cost")


# ════════════════════════════════════════════════════════════════════
# 🧬 GRAPHRAG (Neo4j dual-mode + write path for all three agents)
# ════════════════════════════════════════════════════════════════════
def graphrag_page(agent: str) -> None:
    ui.render_sidebar_controls(agent)
    ui.agent_header(agent, "GraphRAG")

    from graphrag_neo4j.investigator import OFFERINGS, investigate
    from graphrag_neo4j.queries import QUERY_META
    from graphrag_neo4j.store import get_store as neo4j_get_store
    from app import knowledge_view as kv

    domain = agent
    store = neo4j_get_store(domain)

    status = ("🟢 **Neo4j mode** — live database" if store.mode == "neo4j"
              else "🟠 **Fallback mode** — in-memory (set `NEO4J_URI` in "
                   "`config/neo4j.yaml` for live Cypher)")
    st.caption(status + " — dual-mode GraphRAG: real Cypher against a "
               "live Neo4j, or an identical in-memory fallback. Every "
               "read enforces human curation; the UI always shows the "
               "exact Cypher each query runs.")
    if st.button("↻ Regenerate synthetic data (seeded)",
                 key="neo4j_regen"):
        from graphrag_neo4j.synthetic import generate_all
        from graphrag_neo4j.store import reset_stores
        files = generate_all(20260801, "full")
        st.success(f"Regenerated {len(files)} data files; stores will "
                   "reload on next query.")
        reset_stores()
        st.rerun()

    # ── 1 · KNOWLEDGE MAP — what the agent knows ────────────────────
    ui.section("🧠 Knowledge map — what the agent knows")
    st.caption("Everything this agent can retrieve, drawn as the graph "
               "it actually is: **color = entity type · size = knowledge "
               "importance · ghost = human-rejected** (no longer "
               "citable). Intel entities carry provenance — CITED_IN "
               "edges to the source memos that ground them.")
    ks = kv.knowledge_stats(store)
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Entities", f"{ks['entities']:,}")
    m2.metric("Relationships", f"{ks['relationships']:,}")
    m3.metric("Intel entities", f"{ks['intel']}")
    m4.metric("Source memos", f"{ks['source_docs']}")
    m5.metric("Human-rejected", f"{ks['rejected']}")
    v1, v2 = st.columns(2)
    view_mode = v1.radio("View", ["💡 Intel layer", "🌐 Everything"],
                         horizontal=True, key=f"kg_view_{domain}")
    map_color = v2.radio("Color", ["By type", "By source"],
                         horizontal=True, key=f"kg_color_{domain}")
    _c_mode = "source" if "source" in map_color.lower() else "type"
    kv.render_knowledge_map(store,
                            show_full=(view_mode == "🌐 Everything"),
                            color_mode=_c_mode,
                            source_map=kv.source_map(store))
    search = st.text_input(
        "Inspect an entity", key=f"kg_search_{domain}",
        placeholder="e.g. RING-SOUTH-1 · parts_inflation · "
                    "reserve_adequacy · CL-201")
    if search:
        kv.render_entity_detail(store, search.strip())

    ui.section("📚 Knowledge by source — what the agent knows & where "
               "it learned it")
    st.caption("Every admitted (citable) item grouped by where the "
               "knowledge came from: 📊 structured data, 📝 internal "
               "notes/memos, 📰 external newsfeed bulletins. Toggle the "
               "map above to **color by source**.")
    kv.render_source_ribbon(kv.knowledge_items(store))
    kv.render_by_source(kv.knowledge_items(store))

    st.divider()

    # ── 2 · INVESTIGATIVE ASSIGNMENTS (the RAG reader) ──────────────
    ui.section("🔍 Investigative assignments — the RAG reader")
    st.caption("Root-cause analysis, deep planning and journey tracing, "
               "answered from the knowledge graph — each step rendered "
               "as the picture it is; the exact Cypher + raw result live "
               "in the expander beneath.")
    offers = OFFERINGS[domain]
    col_btns = st.columns(len(offers))
    for i, offer in enumerate(offers):
        if col_btns[i].button(offer["label"], key=f"inv_{domain}_{i}"):
            st.session_state[f"assignment_{domain}"] = \
                investigate(domain, offer["id"], offer["params"])
    report = st.session_state.get(f"assignment_{domain}")
    if report:
        st.markdown(f"**{report.title}** — mode `{report.mode}`")
        for step in report.steps:
            st.markdown(f"**Step — `{step['query']}`** params "
                        f"`{step['params']}`")
            kv.render_result_visual(domain, step["query"], step["result"])
            with st.expander("Exact Cypher + raw result"):
                st.code(step["cypher"], language="cypher")
                st.json(step["result"])
        st.markdown(f"### Verdict\n{report.verdict}")
        for finding in report.findings:
            st.markdown(f"- {finding}")
        if report.citations:
            st.caption("citations: " + ", ".join(
                c["doc_id"] for c in report.citations))

    st.divider()

    # ── 3 · QUERY EXPLORER ──────────────────────────────────────────
    ui.section("📚 Query explorer")
    st.caption("Run any query in the library — results render by shape "
               "(graph / causal chain / ranked / table), with the Cypher "
               "that produced them.")
    with st.expander("Query library", expanded=False):
        qnames = [name for name, meta in QUERY_META.items()
                  if meta["domain"] in ("all", domain)]
        qname = st.selectbox("Query", qnames, key=f"qsel_{domain}")
        meta = QUERY_META[qname]
        qparams = {}
        for p in meta["params"]:
            key = f"qp_{domain}_{qname}_{p['name']}"
            if p["type"] == "int":
                qparams[p["name"]] = st.number_input(
                    p["name"], value=int(p.get("default", 2)), step=1,
                    key=key)
            else:
                qparams[p["name"]] = st.text_input(
                    p["name"], value=str(p.get("default", "")), key=key)
        if st.button("▶ Run", key=f"qrun_{domain}_{qname}"):
            result = store.run(qname, **qparams)
            st.session_state[f"qresult_{domain}"] = (qname, qparams, result)
        if f"qresult_{domain}" in st.session_state:
            qn, qp, qres = st.session_state[f"qresult_{domain}"]
            st.markdown(f"**`{qn}`** params: `{qp}`")
            kv.render_result_visual(domain, qn, qres)
            with st.expander("Exact Cypher + raw result"):
                st.code(store.cypher_for(qn, qp), language="cypher")
                st.json(qres)

    st.divider()

    # ── 4 · WRITE PATH — extract → curate → cite ────────────────────
    ui.section("✍️ Write path — extract → curate → cite")
    st.caption("LLM-style extraction from source memos produces staged "
               "candidates; a human curation checkpoint decides what "
               "becomes citable. Watch the knowledge graph grow: new "
               "entities appear ringed, rejected ones turn to ghosts.")
    memo_files = {"fraud": "neo4j_fraud_memos.json",
                  "cost": "neo4j_cost_memos.json",
                  "portfolio": "neo4j_portfolio_memos.json"}
    memos = json.loads((DATA_DIR / memo_files[domain]).read_text())
    left, right = st.columns([2, 3])
    with left:
        st.markdown("**Source documents**")
        for m in memos:
            with st.expander(f"{m['doc_id']} — {m['title']} ({m['date']})"):
                st.caption(m["publisher"])
                st.write(m["text"])
    with right:
        from llm_client import available, model_id, usage
        engine = (f"🤖 DeepSeek LLM (`{model_id()}`)"
                  if available() else "⚙️ mock (set DEEPSEEK_API_KEY for "
                                      "the real LLM)")
        st.markdown(f"**Extraction** — engine: **{engine}**")
        if st.button("🔍 Run extraction over documents", type="primary",
                     key=f"neo4j_extract_{domain}"):
            if domain == "fraud":
                from fraud_agent.graphrag.extractor import (
                    MockLLMFraudGraphExtractor, LLMFraudGraphExtractor,
                    merge_candidates as merge)
            elif domain == "cost":
                from cost_agent.graphrag.extractor import (
                    MockLLMGraphExtractor, LLMGraphExtractor,
                    merge_candidates as merge)
            else:
                from portfolio_agent.graphrag.extractor import (
                    MockLLMPortfolioGraphExtractor,
                    LLMPortfolioGraphExtractor,
                    merge_candidates as merge)
            if domain == "fraud":
                extractor = LLMFraudGraphExtractor() if available() \
                    else MockLLMFraudGraphExtractor()
            elif domain == "cost":
                extractor = LLMGraphExtractor() if available() \
                    else MockLLMGraphExtractor()
            else:
                extractor = LLMPortfolioGraphExtractor() if available() \
                    else MockLLMPortfolioGraphExtractor()
            tokens_before = usage.totals()["total_tokens"]
            _t0 = time.perf_counter()
            merged = merge(extractor.extract(memos))
            _dt = time.perf_counter() - _t0
            tokens_used = usage.totals()["total_tokens"] - tokens_before
            st.session_state[f"neo4j_tokens_{domain}"] = tokens_used
            st.session_state[f"neo4j_dt_{domain}"] = _dt
            st.session_state[f"neo4j_extraction_{domain}"] = merged
            upserted = store.upsert_intel(list(merged.values()),
                                          kind=domain)
            st.session_state[f"neo4j_delta_{domain}"] = upserted
        if f"neo4j_extraction_{domain}" not in st.session_state:
            st.info("Run the extraction to see staged candidates with "
                    "their provenance, then curate them below.")
        else:
            merged = st.session_state[f"neo4j_extraction_{domain}"]
            ups = st.session_state.get(f"neo4j_delta_{domain}", {})
            tok = st.session_state.get(f"neo4j_tokens_{domain}")
            _dt = st.session_state.get(f"neo4j_dt_{domain}")
            tok_s = (f" — `{model_id()}` consumed "
                     f"**{tok:,} tokens** in **{_dt:.1f}s** "
                     f"({len(memos)} docs, 4-way parallel)"
                     if available() and tok and _dt else "")
            st.success(
                f"**{ups.get('upserted', len(merged))} entities extracted "
                f"and MERGE'd into the graph**{tok_s} — new intel is "
                f"ringed on the map below, CITED_IN to their source memos.")
            kv.render_knowledge_map(store, highlight=set(merged))
            approval = store.load_approval()
            st.markdown("**Curation** — toggle and save; only approved "
                        "entities are citable in every query above "
                        "(rejected ones ghost out on the map).")
            new_state = {}
            for eid, c in sorted(merged.items(),
                                 key=lambda kv: -kv[1].get(
                                     "confidence",
                                     kv[1].get("weight", 0))):
                name = c["name"]
                meta_line = (f"confidence "
                             f"{c.get('confidence', c.get('weight', 0)):.2f} "
                             f"(\"{c['strength_word']}\")")
                with st.expander(
                        f"{'✅' if approval.get(eid, True) else '🚫'} "
                        f"**{name}** — {meta_line}"):
                    st.write(f"“{c.get('quote', '')}”")
                    st.caption("figures: " + ", ".join(c.get("figures", [])))
                    if domain == "fraud":
                        st.caption("linked: " + ", ".join(
                            c.get("linked_entities", [])))
                    for prov in c["provenance"]:
                        st.caption(f"📄 {prov['doc_id']} · "
                                   f"{prov.get('title', '')} · "
                                   f"{prov.get('publisher', '')} · "
                                   f"{prov.get('date', '')}")
                    new_state[eid] = st.toggle(
                        "Approved for citation",
                        value=approval.get(eid, True),
                        key=f"neo4j_apr_{domain}_{eid}")
            if new_state and st.button("💾 Save curation",
                                       key=f"neo4j_save_{domain}"):
                store.save_approval({**approval, **new_state})
                st.success("Curation saved. Every GraphRAG query above "
                           "now enforces it — re-run an assignment to "
                           "see knowledge state change the verdict.")
                st.rerun()


# ════════════════════════════════════════════════════════════════════
# 🎓 LEARNING (continuous learning loop)
# ════════════════════════════════════════════════════════════════════
def learning_page(agent: str) -> None:
    ui.render_sidebar_controls(agent)
    ui.agent_header(agent, "Learning")
    st.markdown("**The feedback loop:** real-world outcomes arrive → the "
                "agent's past decisions are scored against them → weight "
                "adjustments are *proposed* → a **human approves** → "
                "knowledge updates → eval shows the delta. Everything "
                "here is **persisted** — close the app, come back, and "
                "the agent still carries what it learned.")
    from app import learning_lab as ll
    from app.knowledge_view import render_by_source, render_source_ribbon

    # ── 1 · KNOWLEDGE LEDGER (by source, with toggles) ───────────────
    ui.section("🧠 Knowledge ledger — what the agent believes & where it "
               "learned it")
    st.caption("Every knowledge item, grouped by where it came from "
               "(📊 data · 📝 notes · 📰 newsfeed · 🧪 learned · "
               "🧑‍🎓 human-written). **Toggle an item off** to suppress it "
               "— persisted in `data/knowledge_toggles_<agent>.json`, "
               "originals kept for restore.")
    items = ll.items(agent)
    render_source_ribbon(items)
    import hashlib

    def _toggler(it: dict) -> None:
        key = f"lt_{agent}_{hashlib.md5(it['id'].encode()).hexdigest()[:8]}"
        cur = st.toggle("use", value=it["active"], key=key,
                        help="Suppress this knowledge item (persisted).")
        if cur != it["active"]:
            ll.toggle(agent, it["id"], cur, value=it["value"])
            st.rerun()

    render_by_source(items, toggler=_toggler)
    if st.button("↺ Reset all toggles", key=f"tgl_reset_{agent}"):
        n = ll.reset_toggles(agent)
        st.success(f"Restored {n} suppressed item(s) to their original "
                   "values.")
        st.rerun()

    # ── 2 · WRITE IN KNOWLEDGE ───────────────────────────────────────
    ui.section("✍️ Write in knowledge — feed the agent a new fact")
    st.caption("Appended to the agent's knowledge files (the tools "
               "re-read them per call → **immediate effect**) and "
               "upserted into the GraphRAG store (visible on the "
               "knowledge map). Persisted across restarts.")
    if agent == "fraud":
        with st.form(f"write_{agent}", clear_on_submit=True):
            c1, c2 = st.columns(2)
            claimant = c1.text_input(
                "Claimant", value="CL-104", key=f"wf_{agent}_claimant",
                help="CL-104 = C-1004's claimant (starts clean at "
                     "APPROVE, score 10) — the demo link that flips it "
                     "to REVIEW/ESCALATE")
            relation = c1.selectbox(
                "Relation", ["uses_phone", "lives_at", "repaired_at",
                             "member_of"], key=f"wf_{agent}_rel")
            target = c2.text_input(
                "Target entity", value="PH-900",
                key=f"wf_{agent}_target",
                help="e.g. PH-900 (phone shared by known-fraud CL-201 / "
                     "CL-202) — linking CL-104 to it flips clean claim "
                     "C-1004")
            target_type = c2.selectbox(
                "Target type", ["phone", "address", "repair_shop",
                                "claimant"], key=f"wf_{agent}_ttype")
            c3, c4 = st.columns(2)
            strength = c3.selectbox(
                "Strength", ["confirmed", "strongly_suspected",
                             "suspected", "possible"],
                key=f"wf_{agent}_strength")
            source_kind = c4.selectbox(
                "Source kind", ["notes", "data", "newsfeed", "human"],
                key=f"wf_{agent}_src")
            note = st.text_input(
                "Note (why you believe it)", value="Seen at a known ring "
                "member's address", key=f"wf_{agent}_note")
            if st.form_submit_button("💾 Write into knowledge",
                                     key=f"wf_{agent}_submit"):
                ll.write_knowledge("fraud", {
                    "claimant": claimant, "relation": relation,
                    "target": target, "target_type": target_type,
                    "strength": strength, "source_kind": source_kind,
                    "note": note})
                st.success(f"Written & persisted: {claimant} "
                           f"{relation} {target} — run the same claim "
                           "below and watch it react.")
                st.rerun()
    elif agent == "cost":
        with st.form(f"write_{agent}", clear_on_submit=True):
            c1, c2 = st.columns(2)
            driver = c1.text_input("Driver id", value="labor_shortage",
                                   key=f"wf_{agent}_driver")
            name = c2.text_input("Driver name", value="Skilled labor "
                                 "shortage", key=f"wf_{agent}_name")
            metric = c1.selectbox("Metric", ["severity", "frequency",
                                             "loss_ratio"],
                                  key=f"wf_{agent}_metric")
            weight = c2.slider("Weight", 0.05, 1.0, 0.5, 0.05,
                               key=f"wf_{agent}_weight")
            c3, c4, c5 = st.columns(3)
            direction = c3.selectbox("Direction", ["+", "-"],
                                     key=f"wf_{agent}_dir")
            lag = c4.selectbox("Lag (quarters)", [0, 1, 2, 3, 4],
                               key=f"wf_{agent}_lag")
            region = c5.text_input("Region", value="ALL",
                                   key=f"wf_{agent}_region")
            c6, c7 = st.columns(2)
            coverage = c6.selectbox("Coverage", ["auto_pd", "auto_bi",
                                                 "home", "ALL"],
                                    key=f"wf_{agent}_cov")
            source_kind = c7.selectbox("Source kind",
                                       ["notes", "data", "newsfeed",
                                        "human"],
                                       key=f"wf_{agent}_src")
            quote = st.text_input("Quote / evidence", key=f"wf_{agent}_q")
            if st.form_submit_button("💾 Write into knowledge",
                                     key=f"wf_{agent}_submit"):
                ll.write_knowledge("cost", {
                    "driver": driver, "name": name, "metric": metric,
                    "weight": weight, "direction": direction, "lag": lag,
                    "region": region, "coverage": coverage,
                    "source_kind": source_kind, "quote": quote,
                    "doc_id": "HUMAN-01"})
                st.success(f"Written & persisted: {driver} IMPACTS "
                           f"{metric} (w={weight}) — the driver tree now "
                           "serves it.")
                st.rerun()
    else:
        pf = json.loads((DATA_DIR / "portfolio_entities.json").read_text())
        stages = [n["id"] for n in pf["nodes"] if n["type"] == "stage"]
        outcomes = [n["id"] for n in pf["nodes"] if n["type"] == "outcome"]
        with st.form(f"write_{agent}", clear_on_submit=True):
            c1, c2 = st.columns(2)
            signal = c1.text_input("Signal id", value="reserve_adequacy",
                                   key=f"wf_{agent}_signal")
            name = c2.text_input("Signal name", value="Reserve adequacy",
                                 key=f"wf_{agent}_name")
            stage = c1.selectbox("Stage", stages,
                                 key=f"wf_{agent}_stage")
            outcome = c2.selectbox("Outcome", outcomes,
                                   key=f"wf_{agent}_outcome")
            c3, c4 = st.columns(2)
            weight = c3.slider("Weight", 0.05, 1.0, 0.5, 0.05,
                               key=f"wf_{agent}_weight")
            source_kind = c4.selectbox("Source kind",
                                       ["notes", "data", "newsfeed",
                                        "human"],
                                       key=f"wf_{agent}_src")
            quote = st.text_input("Quote / evidence", key=f"wf_{agent}_q")
            if st.form_submit_button("💾 Write into knowledge",
                                     key=f"wf_{agent}_submit"):
                ll.write_knowledge("portfolio", {
                    "signal": signal, "name": name, "stage": stage,
                    "outcome": outcome, "weight": weight,
                    "region": "ALL", "class_code": "ALL",
                    "source_kind": source_kind, "quote": quote,
                    "doc_id": "HUMAN-01"})
                st.success(f"Written & persisted: {signal} PREDISPOSES "
                           f"{outcome} (w={weight}).")
                st.rerun()

    # ── 3 · VERIFY REACTIVITY (persisted) ────────────────────────────
    ui.section("🔁 Verify reactivity — will it react next time?")
    st.caption("The point of persisted learning: **run the same subject "
               "before and after a knowledge change**. Capture a "
               "baseline, then toggle / write / apply above, then "
               "re-run — if the decision or score moved, the agent "
               "reacted to what it learned. Every step is recorded to "
               "the append-only evidence ledger.")
    if agent == "fraud":
        _opts = list(CLAIMS)
        _idx = _opts.index("C-1004") if "C-1004" in _opts else 0
        subject = st.selectbox(
            "Subject", _opts, index=_idx, key=f"verify_subject_{agent}",
            format_func=lambda c: f"{c} · {ui.PATTERN_HINTS[c]}")
    elif agent == "portfolio":
        _opts = ui.get_segments()
        subject = st.selectbox(
            "Segment", _opts, key=f"verify_subject_{agent}",
            format_func=lambda s: f"{s['id']} — broker="
                                  f"{s['segment']['broker']} · class="
                                  f"{s['segment']['class_code']}")
    else:
        _opts = ui.get_questions()
        subject = st.selectbox(
            "Question", _opts, key=f"verify_subject_{agent}",
            format_func=lambda q: f"{q['id']} — {q['text'][:60]}")
    b1, b2 = st.columns(2)
    if b1.button("📸 Capture baseline", key=f"vb_{agent}"):
        st.session_state[f"baseline_{agent}"] = ll.baseline(agent, subject)
        st.rerun()
    if b2.button("🔁 Re-run & compare", key=f"vr_{agent}"):
        st.session_state[f"verify_{agent}"] = ll.verify_reactivity(
            agent, subject,
            before=st.session_state.get(f"baseline_{agent}"))
        st.rerun()
    base = st.session_state.get(f"baseline_{agent}")
    ver = st.session_state.get(f"verify_{agent}")
    if base:
        st.markdown(f"**Baseline:** `{base['decision']}` @ score "
                    f"{base['score']} — {base['subject']}")
    if ver:
        b, a = ver["before"], ver["after"]
        if b["decision"] != a["decision"]:
            st.success(f"⚡ **{b['decision']} → {a['decision']}** — the "
                       f"agent reacted to the updated knowledge (score "
                       f"{b['score']} → {a['score']}). This is what "
                       "persisted learning looks like.")
            try:
                from app.nav import get_pages
                st.page_link(get_pages()[agent]["eval"],
                             label="📊 See the score move → Eval Lab")
            except Exception:
                pass
        elif b["score"] != a["score"]:
            st.success(f"📈 **Decision held** ({a['decision']} both runs) "
                       f"but the risk score moved {b['score']} → "
                       f"{a['score']} — the agent reacted, just not past "
                       "the decision threshold yet. Toggle a heavier "
                       "weight or write a stronger fact to cross it.")
        else:
            st.info(f"No change ({a['decision']} both runs, "
                    f"score {b['score']} → {a['score']}) — try a "
                    "stronger toggle or a new fact, then re-run.")
    hist = ll.evidence_history(agent)
    if hist:
        with st.expander("🗂️ Evidence ledger (append-only, persists)"):
            st.caption("Every knowledge action + verification, in order "
                       f"({len(hist)} records).")
            st.dataframe(pd.DataFrame(hist[:20]), hide_index=True,
                         use_container_width=True)
            if len(hist) > 20:
                st.caption(f"… {len(hist) - 20} older records — "
                           "`data/learning_evidence.jsonl`")

    st.divider()

    # ── 4 · OUTCOME ANALYSIS (the proposals feed) ────────────────────
    if agent == "fraud":
        from fraud_agent import learning as fraud_learning
        st.caption("Outcomes: `data/outcomes.jsonl` (post-payment audits, "
                   "SIU dispositions). Weights: "
                   "`config/fraud_weights.yaml`.")
        if st.button("📊 Analyze outcomes", type="primary"):
            st.session_state.fraud_learning = fraud_learning.analyze()
        if "fraud_learning" in st.session_state:
            rep = st.session_state.fraud_learning
            st.markdown("**Per-signal precision on real outcomes** "
                        "(a signal that fires mostly on legit claims is a "
                        "false-alarm factory)")
            st.dataframe(pd.DataFrame(rep["proposals"]), hide_index=True,
                         use_container_width=True)
            a, b = st.columns(2)
            if a.button("✅ Approve & apply to fraud_weights.yaml"):
                fraud_learning.apply_proposals(rep)
                ui.get_harness.clear()  # brains reload weights on construction
                ll.record_evidence("fraud", "proposals_applied",
                                   {"n": len(rep["proposals"])})
                st.success("Applied. Agents reconstructed with new "
                           "weights.")
                st.rerun()
            if b.button("↺ Reset weights to defaults"):
                import yaml as _yaml
                from fraud_agent.brain.rule_based import _DEFAULT_WEIGHTS
                from fraud_agent.paths import ROOT as _ROOT
                (_ROOT / "config" / "fraud_weights.yaml").write_text(
                    _yaml.safe_dump({"scoring": _DEFAULT_WEIGHTS},
                                    sort_keys=False))
                ui.get_harness.clear()
                st.success("Weights reset to defaults.")
                st.rerun()
    elif agent == "portfolio":
        from portfolio_agent import learning as pf_learning
        st.caption("Actuals: `data/portfolio_outcomes_nextq.json` "
                   "(next-quarter realized transformations of each "
                   "signal). Knowledge: PREDISPOSES edge weights in "
                   "`data/portfolio_entities.json`.")
        if st.button("📊 Validate signals vs next-quarter outcomes",
                     type="primary"):
            st.session_state.pf_learning = pf_learning.analyze()
        if "pf_learning" in st.session_state:
            rep = st.session_state.pf_learning
            st.markdown("**Signal validation → edge-weight proposals** "
                        "(validated signals reinforced, contradicted "
                        "signals decayed)")
            st.dataframe(pd.DataFrame(rep["proposals"]), hide_index=True,
                         use_container_width=True)
            if st.button("✅ Approve & apply to lineage graph"):
                result = pf_learning.apply_proposals(rep)
                ll.record_evidence("portfolio", "proposals_applied",
                                   {"changed": result["changed"]})
                st.success(f"{result['changed']} PREDISPOSES edge(s) "
                           "updated — `predisposing_signals` serves the "
                           "new weights immediately. Re-run an assembly "
                           "eval to see confidence shift.")
    else:
        from cost_agent import learning as cost_learning
        st.caption("Actuals: `data/outcomes_nextq.json` (next-quarter "
                   "realized movements). Knowledge: graph edge weights in "
                   "`data/cost_entities.json`.")
        if st.button("📊 Validate drivers vs next-quarter actuals",
                     type="primary"):
            st.session_state.cost_learning = cost_learning.analyze()
        if "cost_learning" in st.session_state:
            rep = st.session_state.cost_learning
            st.markdown("**Driver validation → edge-weight proposals** "
                        "(validated drivers reinforced, contradicted "
                        "drivers decayed)")
            st.dataframe(pd.DataFrame(rep["proposals"]), hide_index=True,
                         use_container_width=True)
            if st.button("✅ Approve & apply to knowledge graph"):
                result = cost_learning.apply_proposals(rep)
                ll.record_evidence("cost", "proposals_applied",
                                   {"changed": result["changed"]})
                st.success(f"{result['changed']} edge(s) updated — "
                           "driver_tree serves the new weights "
                           "immediately. Re-run a question to see "
                           "confidence shift.")

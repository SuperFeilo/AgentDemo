"""Agent Anatomy Explorer — two agents, one skeleton.

🕵️ Fraud Investigator: decides APPROVE / REVIEW / ESCALATE on a claim.
📈 Cost Trend Analyst: explains a cost trend with cited drivers.

Tabs:
  🧠 Anatomy   — every agent-anatomy component, where it lives
  ▶️ Live Run  — watch the loop work, step-by-step or autoplay
  🕸️ Graph     — the knowledge graph the selected agent reasons over
  📊 Eval Lab  — score the selected agent against ground truth
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.components import (CSS, gauge_figure, graph_figure, render_event,
                            render_verdict, trend_figure)
from fraud_agent.paths import DATA_DIR, GOAL_PATH, SKILLS_DIR

st.set_page_config(page_title="Agent Anatomy Explorer", page_icon="🧠",
                   layout="wide")
st.markdown(CSS, unsafe_allow_html=True)

CLAIMS = {c["claim_id"]: c for c in json.loads((DATA_DIR / "claims.json").read_text())}
PATTERN_HINTS = {
    "C-1001": "clean", "C-1002": "clean", "C-1003": "clean", "C-1004": "clean",
    "C-1005": "velocity", "C-1006": "fraud ring", "C-1007": "shaky notes",
    "C-1008": "fresh policy", "C-1009": "clean", "C-1010": "clean",
    "C-1011": "ring + notes", "C-1012": "velocity + notes",
    "C-1013": "clean", "C-1014": "clean",
}

AGENTS = {"fraud": "🕵️ Fraud Investigator", "cost": "📈 Cost Trend Analyst"}


@st.cache_resource
def get_harness(agent: str):
    if agent == "fraud":
        from fraud_agent.harness import FraudHarness
        return FraudHarness()
    from cost_agent.harness import CostHarness
    return CostHarness()


@st.cache_data
def get_questions() -> list[dict]:
    from cost_agent.eval.dataset import QUESTIONS
    return QUESTIONS


# ── sidebar: pick the agent ─────────────────────────────────────────
agent_label = st.sidebar.radio("Choose your agent", list(AGENTS.values()))
agent = next(k for k, v in AGENTS.items() if v == agent_label)
harness = get_harness(agent)
st.sidebar.markdown("---")
st.sidebar.markdown(
    "**Same skeleton, two crafts.**" if agent == "fraud" else
    "**Same skeleton, two crafts.**")
st.sidebar.caption(
    "Goal, plan, skills, loop, tools, harness, lifecycle, graph knowledge "
    "and eval — reused. Only the playbooks, tools and brains differ.")

st.title(f"{agent_label} — Agent Anatomy Explorer")
st.caption("Every component of agent anatomy is real code you can read — "
           "and you can watch them work together live.")

_tabs = st.tabs(["🧠 Anatomy", "▶️ Live Run", "🕸️ Knowledge Graph",
                 "📊 Eval Lab", "🧬 GraphRAG", "🎓 Learning"])
tab_anatomy, tab_live, tab_graph, tab_eval, tab_graphrag = _tabs[0], _tabs[1], _tabs[2], _tabs[3], _tabs[4]
tab_learning = _tabs[-1]

# ════════════════════════════════════════════════════════════════════
# TAB 1 — ANATOMY
# ════════════════════════════════════════════════════════════════════
with tab_anatomy:
    st.subheader("How the components connect")
    st.graphviz_chart("""
    digraph {
        rankdir=LR; node [shape=box, style="rounded,filled", fontname="Helvetica"];
        Goal [fillcolor="#dbeafe"]; Skills [fillcolor="#dbeafe"];
        Plan [fillcolor="#ede9fe"];
        Loop [fillcolor="#fef3c7"]; Brain [fillcolor="#fef3c7"];
        Harness [fillcolor="#fee2e2"]; Lifecycle [fillcolor="#fee2e2"];
        Tools [fillcolor="#dcfce7"]; Graph [fillcolor="#dcfce7"];
        Eval [fillcolor="#f1f5f9"]; Docs [fillcolor="#fce7f3"];
        Blackboard [fillcolor="#e0e7ff"]; Dossier [fillcolor="#e0e7ff"];
        Learning [fillcolor="#fef9c3"];
        Goal -> Plan; Skills -> Plan; Plan -> Loop;
        Loop -> Brain [label="think"]; Brain -> Loop [label="act"];
        Loop -> Harness [label="events"]; Harness -> Tools [label="execute"];
        Tools -> Graph [label="query"]; Harness -> Lifecycle [label="states"];
        Eval -> Harness [label="batch runs"];
        Docs -> Graph [label="GraphRAG: extract + curate"];
        Loop -> Blackboard [label="posts findings"];
        Harness -> Dossier [label="trace compiles"];
        Eval -> Learning [label="outcomes"];
        Learning -> Skills [label="approved weight updates"];
        Harness -> Harness [label="autonomy gate + cost budgets"];
    }""")

    st.subheader("Two agents, one skeleton")
    st.markdown("""
    | Component | 🕵️ Fraud Investigator | 📈 Cost Trend Analyst |
    |---|---|---|
    | **Goal** | `config/goal.yaml` | `config/cost_goal.yaml` |
    | **Plan** | `fraud_agent/planner.py` | `cost_agent/planner.py` |
    | **Skills** | `skills/*.md` | `skills_cost/*.md` |
    | **Loop** | `fraud_agent/loop.py` | `cost_agent/loop.py` |
    | **Brain** | `brain/rule_based.py` + mock-LLM `notes_llm.py` | `brain/cost_brain.py` |
    | **Tools** | claims / policies / graph / notes / escalate | catalog / trend / SQL (guarded) / driver graph |
    | **Graph knowledge** | `data/entities.json` (fraud rings) | `data/cost_entities.json` (driver tree + semantic layer) |
    | **GraphRAG write path** | — | `data/memos.json` → `cost_agent/graphrag/` → curated graph + provenance |
    | **Harness / Lifecycle** | `fraud_agent/harness.py` + `lifecycle.py` — **shared** | same |
    | **Eval** | precision/recall on labeled claims | citation precision/recall, numeric accuracy, faithfulness |
    """)

    st.subheader("Component → code map")
    cards = [
        ("🎯 Goal", "config/*.yaml", "Objective, success criteria, budgets "
         "and thresholds. The planner reads it; the harness enforces it."),
        ("📝 Plan", "*/planner.py", "Turns the goal + loaded skills into an "
         "ordered list of steps."),
        ("📚 Skills (SKILLS.md)", "skills*/", "Human-readable playbooks (when "
         "to act, which tool, how to score). Edit a skill → behaviour changes, "
         "no code edits."),
        ("🔁 Loop", "*/loop.py", "Observe → think → act, as a generator. "
         "Yields events; receives tool results and human answers back via "
         ".send()."),
        ("🧠 Brains", "*/brain/", "Rule-based brains walk the plan and "
         "interpret evidence; the fraud agent adds a mock-LLM brain that "
         "reads adjuster notes (seam marked for a real LLM)."),
        ("🧰 Tool calls", "*/tools/", "Registry with schemas (what an LLM "
         "would 'see') + implementations. The analyst's sql_query tool shows "
         "guardrails enforced by the tool itself."),
        ("🕸️ Graph knowledge", "*/knowledge/ + data/*.json", "Fraud: entity "
         "graph for ring detection. Analyst: driver tree (what impacts what) "
         "doubling as a semantic layer for metrics."),
        ("🧬 GraphRAG write path", "cost_agent/graphrag/", "LLM-style "
         "extraction from source documents into staged graph candidates; a "
         "human curation checkpoint decides what becomes citable; every "
         "citation carries provenance back to the source document."),
        ("🛟 Harness", "fraud_agent/harness.py", "Shared runtime shell: "
         "executes every tool call, enforces budgets, records the trace. "
         "Both agents plug in plan+brain+loop."),
        ("⏱️ Lifecycle", "fraud_agent/lifecycle.py", "Run state machine and "
         "registry. Powers the fraud agent's human checkpoint (the analyst "
         "is read-only, so it never pauses)."),
        ("📊 Eval", "*/eval/", "Classifier eval: precision/recall vs labels. "
         "Analyst eval: citation precision/recall, numeric accuracy vs the "
         "warehouse, faithfulness."),
        ("🗂️ Case blackboard", "fraud_agent/blackboard.py", "Typed working "
         "memory (case / evidence / hypotheses / decision); every write "
         "journaled with its data origin — the traceable context."),
        ("📄 Determination dossier", "fraud_agent/dossier.py", "One auditable "
         "artifact per run: case → skills → thoughts → data by origin → "
         "decision → cost. JSON + Markdown export."),
        ("🚦 Autonomy gate", "fraud_agent/harness.py + tool registry", "Tools "
         "declare auto|gated; the harness pauses on gated calls unless the "
         "run's autonomy slider says full. SIU escalation is one instance."),
        ("💰 Cost control", "harness + goal.yaml", "Real latency timing + "
         "declared cost units per tool, budgeted by the goal; the harness "
         "aborts runs that overspend."),
        ("🎓 Learning loop", "*/learning.py + outcomes", "Decisions scored "
         "against real-world outcomes; weight adjustments proposed and "
         "human-approved; skills/weights are data, not constants."),
    ]
    for row in range(0, len(cards), 2):
        cols = st.columns(2)
        for col, (title, path, desc) in zip(cols, cards[row:row + 2]):
            col.markdown(f"**{title}** — `{path}`\n\n{desc}")

    goal_path = GOAL_PATH if agent == "fraud" else \
        Path(__file__).resolve().parent.parent / "config" / "cost_goal.yaml"
    st.subheader(f"The {agent_label.split(' ', 1)[1].lower()}'s goal "
                 "(loaded at planning time)")
    st.code(goal_path.read_text(), language="yaml")

    st.subheader("Loaded skill playbooks")
    for name, text in harness.plan.skills.items():
        with st.expander(f"📚 {name}"):
            st.markdown(text)

# ════════════════════════════════════════════════════════════════════
# TAB 2 — LIVE RUN
# ════════════════════════════════════════════════════════════════════
with tab_live:
    controls = st.columns([3, 1.6, 1, 1, 1, 1])
    if agent == "fraud":
        subject = controls[0].selectbox(
            "Claim to investigate", options=list(CLAIMS),
            format_func=lambda c: f"{c} · {CLAIMS[c]['claim_type']} · "
                                  f"${CLAIMS[c]['amount']:,} · "
                                  f"hint: {PATTERN_HINTS[c]}")
    else:
        questions = get_questions()
        subject = controls[0].selectbox(
            "Research question", options=questions,
            format_func=lambda q: f"{q['id']} — {q['text']}")
    autonomy = controls[1].select_slider(
        "Autonomy", options=["step", "gated", "full"], value="gated",
        help="Karpathy's autonomy slider: step = advance manually; gated = "
             "pause on side-effecting tools; full = never pause.")
    bug = controls[2].toggle("🐛 bug", value=False,
                             help="Inject a reasoning bug so the reflection "
                                  "step can catch it (demo).")
    autoplay = controls[3].toggle("Autoplay", value=False,
                                  disabled=(autonomy == "step"))
    if controls[4].button("▶️ Start run", type="primary",
                          use_container_width=True):
        harness.brain.bug_injection = bug
        run = harness.start_run(subject,
                                autonomy_level=("full" if autonomy == "full"
                                                else "gated"))
        st.session_state.live = {"agent": agent, "run": run,
                                 "driver": harness.drive(run), "events": [],
                                 "done": False, "awaiting": False,
                                 "autoplay": autoplay}
        st.rerun()
    if controls[5].button("⏭️ Step", use_container_width=True,
                          disabled="live" not in st.session_state
                          or st.session_state.live.get("done", True)
                          or st.session_state.live.get("awaiting", True)
                          or st.session_state.live.get("autoplay", False)):
        live = st.session_state.live
        try:
            live["events"].append(next(live["driver"]))
            live["awaiting"] = live["events"][-1]["type"] == "checkpoint"
        except StopIteration:
            live["done"] = True
        st.rerun()

    if "live" in st.session_state and st.session_state.live["agent"] == agent:
        live = st.session_state.live
        live["autoplay"] = autoplay
        run = live["run"]

        if live["autoplay"] and not live["done"] and not live["awaiting"]:
            try:
                ev = next(live["driver"])
                live["events"].append(ev)
                if ev["type"] == "checkpoint":
                    live["awaiting"] = True
                    live["autoplay"] = False
            except StopIteration:
                live["done"] = True
            time.sleep(0.8)
            st.rerun()

        left, right = st.columns([3, 2])
        with right:
            st.markdown(f"**Lifecycle state:** `{run.state.value}`  ·  "
                        f"run `{run.run_id}`  ·  "
                        f"autonomy `{run.autonomy_level}`")
            budget = harness.plan.constraints.get("max_cost_units")
            st.metric("Cost meter", f"{run.cost_units} units",
                      help=f"Budget from goal.yaml: {budget} units — the "
                           "harness aborts the run if it is exceeded.")
            if agent == "fraud":
                score = max([e.get("score", 0) for e in live["events"]
                             if e["type"] == "observation"] + [run.risk_score])
                st.plotly_chart(gauge_figure(score), use_container_width=True)
                nets = [e for e in live["events"]
                        if e["type"] == "observation"
                        and e["step"] == "network_analysis"]
                if nets:
                    st.markdown("**Fraud-ring subgraph** (knowledge graph)")
                    raw = nets[-1]["raw"]
                    hot = {CLAIMS[run.subject]["claimant_id"]} | {
                        l["entity"] for l in raw["fraud_links"]} | {
                        l["via"] for l in raw["fraud_links"]}
                    st.plotly_chart(graph_figure(raw["nodes"], raw["edges"], hot),
                                    use_container_width=True)
            else:
                decisions = [e for e in live["events"] if e["type"] == "decision"]
                conf = decisions[-1]["confidence"] if decisions else 0
                st.plotly_chart(gauge_figure(conf, title="Confidence",
                                             good="high"),
                                use_container_width=True)
                trends = [e for e in live["events"]
                          if e["type"] == "observation"
                          and e["step"] == "read_trend"]
                if trends:
                    raw = trends[-1]["raw"]
                    st.plotly_chart(
                        trend_figure(raw["quarters"], raw["values"],
                                     f"{raw['metric']} · {raw['region']} · "
                                     f"{raw['coverage']}"),
                        use_container_width=True)
                drivers = [e for e in live["events"]
                           if e["type"] == "observation"
                           and e["step"] == "find_drivers"]
                if drivers:
                    st.markdown("**Candidate drivers** (from knowledge graph)")
                    st.dataframe(pd.DataFrame(drivers[-1]["raw"]["drivers"]),
                                 hide_index=True, use_container_width=True)

            decisions = [e for e in live["events"]
                         if e["type"] in ("decision", "decision_override")]
            if decisions and agent == "fraud":
                render_verdict(run.decision or decisions[-1]["decision"],
                               run.risk_score)

        with left:
            for i, ev in enumerate(live["events"]):
                render_event(ev, key_prefix=f"e{i}")

            if live["awaiting"] and live["events"] and \
                    live["events"][-1]["type"] == "checkpoint":
                st.warning("⏸️ The lifecycle manager paused the run. "
                           "Your call, human:")
                yes, no = st.columns(2)
                if yes.button("✅ Approve SIU escalation",
                              use_container_width=True):
                    live["events"].append(live["driver"].send(True))
                    live["awaiting"] = live["events"][-1]["type"] == "checkpoint"
                    st.rerun()
                if no.button("🚫 Reject (downgrade to REVIEW)",
                             use_container_width=True):
                    live["events"].append(live["driver"].send(False))
                    live["awaiting"] = live["events"][-1]["type"] == "checkpoint"
                    st.rerun()
            elif not live["done"] and not live["autoplay"]:
                st.info("Press **⏭️ Step** (or enable Autoplay) to advance "
                        "the loop.")

        # ── DETERMINATION DOSSIER (full width) ──────────────────────
        if live["events"]:
            from fraud_agent.dossier import compile_dossier, render_markdown
            d = compile_dossier(run)
            with st.expander("📄 Determination Dossier — one auditable "
                             "artifact for this run", expanded=live["done"]):
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
    else:
        if agent == "fraud":
            st.info("Pick a claim and press **▶️ Start run**. Step through "
                    "the loop and watch it think, call tools, and — when "
                    "risk is high — pause for your approval.")
        else:
            st.info("Pick a research question and press **▶️ Start run**. "
                    "Watch the analyst quantify the trend from the warehouse, "
                    "then hunt for honest drivers in the knowledge graph.")

# ════════════════════════════════════════════════════════════════════
# TAB 3 — KNOWLEDGE GRAPH
# ════════════════════════════════════════════════════════════════════
with tab_graph:
    if agent == "fraud":
        from fraud_agent.knowledge.graph import KnowledgeGraph

        kg = KnowledgeGraph()
        nodes = [{"id": n, **kg.g.nodes[n]} for n in kg.g.nodes]
        edges = [{"a": a, "b": b, **kg.g.edges[a, b]} for a, b in kg.g.edges]
        frauds = {n for n in kg.g.nodes if kg.g.nodes[n].get("known_fraud")}
        st.markdown("**claimants** (blue), **phones** (purple), **addresses** "
                    "(green), **repair shops** (amber). Red = known fraud. "
                    "The `fraud_ring_network` tool traverses this graph.")
        st.plotly_chart(graph_figure(nodes, edges, frauds),
                        use_container_width=True)
        pick = st.selectbox("Inspect an entity", sorted(kg.g.nodes))
        attrs = kg.g.nodes[pick]
        neighbors = [f"{n} *(rel: {kg.g.edges[pick, n]['relation']})*"
                     for n in kg.g.neighbors(pick)]
        st.markdown(f"**{pick}** — type `{attrs.get('type')}`"
                    + (" · 🚨 **KNOWN FRAUD**" if attrs.get("known_fraud") else "")
                    + (f" · name: {attrs['name']}" if attrs.get("name") else ""))
        st.markdown("Connections: " + (", ".join(neighbors) or "none"))
    else:
        payload = json.loads((DATA_DIR / "cost_entities.json").read_text())
        st.markdown("**metrics** (blue) and **drivers** (orange). Edges "
                    "labelled IMPACTS carry weight/direction/lag — the "
                    "`driver_tree` tool filters them by region & coverage. "
                    "Metric definitions double as the agent's semantic layer.")
        st.plotly_chart(graph_figure(payload["nodes"], payload["edges"]),
                        use_container_width=True)
        pick = st.selectbox("Inspect a node",
                            [n["id"] for n in payload["nodes"]])
        node = next(n for n in payload["nodes"] if n["id"] == pick)
        st.markdown(f"**{pick}** — type `{node['type']}`")
        if node["type"] == "metric":
            st.markdown(f"Definition: *{node['definition']}* · "
                        f"`{node['sql_hint']}`")
        else:
            st.info(f"{node['evidence']}  \n**Figures:** "
                    f"{', '.join(node['figures'])} · **Source:** {node['source']}")
        rel = [f"{e['a']} → {e['b']} (w={e['weight']}, {e['region']}/"
               f"{e['coverage']})" for e in payload["edges"]
               if e["a"] == pick or e["b"] == pick]
        st.markdown("Edges: " + (", ".join(rel) or "none"))

# ════════════════════════════════════════════════════════════════════
# TAB 4 — EVAL LAB
# ════════════════════════════════════════════════════════════════════
with tab_eval:
    if agent == "fraud":
        st.markdown("Scored against **labeled ground truth** (6 fraud, "
                    "8 legit). A claim counts as *flagged* when its risk "
                    "score ≥ threshold. Sweep the threshold to trade "
                    "precision for recall.")
        threshold = st.slider("Flag threshold (risk score)", 10, 90, 40, 5)
        if st.button("🧪 Run eval", type="primary"):
            from fraud_agent.eval.runner import run_eval
            st.session_state.eval_report = run_eval(threshold)

        if "eval_report" in st.session_state:
            rep = st.session_state.eval_report
            m, cm = rep["metrics"], rep["confusion"]
            cols = st.columns(4)
            cols[0].metric("Precision", f"{m['precision']:.2f}")
            cols[1].metric("Recall", f"{m['recall']:.2f}")
            cols[2].metric("F1", f"{m['f1']:.2f}")
            cols[3].metric("Accuracy", f"{m['accuracy']:.2f}")
            st.caption(f"Confusion matrix — TP {cm['tp']} · FP {cm['fp']} · "
                       f"TN {cm['tn']} · FN {cm['fn']} "
                       f"(threshold {rep['flag_threshold']})")
            df = pd.DataFrame(rep["results"])
            st.dataframe(
                df.style.map(lambda v: "background-color:#fee2e2" if v == "fraud"
                             else "background-color:#dcfce7", subset=["label"]),
                use_container_width=True, hide_index=True)
            pick = st.selectbox("Drill into a run's full trace",
                                df["claim_id"].tolist())
            if pick:
                drill = harness.start_run(pick)
                driver = harness.drive(drill)
                send, started = None, False
                while True:
                    try:
                        ev = driver.send(send) if started else next(driver)
                        started = True
                    except StopIteration:
                        break
                    send = True if ev["type"] == "checkpoint" else None
                    render_event(ev)
    else:
        st.markdown("Scored on **three axes** per research question: "
                    "*citation* precision/recall vs. ground-truth drivers, "
                    "*numeric accuracy* vs. the warehouse, and "
                    "*faithfulness* (the stated number literally appears in "
                    "the explanation).")
        if st.button("🧪 Run eval", type="primary"):
            from cost_agent.eval.runner import run_eval as cost_run_eval
            st.session_state.cost_eval_report = cost_run_eval()

        if "cost_eval_report" in st.session_state:
            rep = st.session_state.cost_eval_report
            m = rep["metrics"]
            cols = st.columns(6)
            cols[0].metric("Citation precision", f"{m['citation_precision']:.2f}")
            cols[1].metric("Citation recall", f"{m['citation_recall']:.2f}")
            cols[2].metric("Numeric accuracy", f"{m['numeric_accuracy']:.2f}")
            cols[3].metric("Faithfulness", f"{m['faithfulness']:.2f}")
            cols[4].metric("Provenance", f"{m['provenance_coverage']:.2f}")
            cols[5].metric("Mean confidence", f"{m['mean_confidence']:.0f}")
            df = pd.DataFrame(rep["results"])[
                ["id", "question", "verdict", "confidence", "cited",
                 "required", "stated", "truth", "numeric_ok", "faithful",
                 "provenance_ok"]]
            st.dataframe(df, use_container_width=True, hide_index=True)
            pick = st.selectbox("Drill into a run's full trace",
                                [q["id"] for q in get_questions()])
            if pick:
                question = next(q for q in get_questions() if q["id"] == pick)
                drill = harness.start_run(question)
                driver = harness.drive(drill)
                while True:
                    try:
                        ev = next(driver)
                    except StopIteration:
                        break
                    render_event(ev)

# ════════════════════════════════════════════════════════════════════
# TAB 5 — GRAPHRAG (both agents)
# ════════════════════════════════════════════════════════════════════
with tab_graphrag:
    if agent == "fraud":
        from fraud_agent.graphrag import store as fraud_store
        from fraud_agent.graphrag.extractor import (
            MockLLMFraudGraphExtractor, merge_candidates as merge_fraud)

        memos = json.loads((DATA_DIR / "fraud_memos.json").read_text())
        st.markdown("**The write path behind the fraud knowledge graph.** "
                    "SIU memos / NICB bulletins → mock-LLM extraction → "
                    "staged candidates → **human curation** → citable "
                    "intel with provenance. The investigator's tools only "
                    "return intel a human has approved (plus baseline "
                    "curated entities from `entities.json`).")

        left, right = st.columns([2, 3])
        with left:
            st.markdown("**1 · Source documents**")
            for m in memos:
                with st.expander(f"{m['doc_id']} — {m['title']} ({m['date']})"):
                    st.caption(m["publisher"])
                    st.write(m["text"])
        with right:
            st.markdown("**2 · Extraction** (mock-LLM — real-LLM seam marked "
                        "in `fraud_agent/graphrag/extractor.py`)")
            if st.button("🔍 Run extraction over documents", type="primary",
                         key="fraud_extract_btn"):
                st.session_state.fraud_extraction = merge_fraud(
                    MockLLMFraudGraphExtractor().extract(memos))
            if "fraud_extraction" not in st.session_state:
                st.info("Run the extraction to see staged candidates with "
                        "their provenance, then curate them below.")
            else:
                merged = st.session_state.fraud_extraction
                approval = fraud_store.load_approval()
                st.markdown("**3 · Staged candidates & curation** — toggle "
                            "and save; new intel merges into the knowledge "
                            "graph and becomes visible to the investigator's "
                            "`fraud_ring_network` tool only after approval.")

                new_state = {}
                type_icons = {
                    "fraud_ring": "🕸️", "suspect_shop": "🏪",
                    "scam_type": "🔍",
                }
                for eid, c in sorted(merged.items(),
                                     key=lambda kv: -kv[1]["confidence"]):
                    icon = type_icons.get(c["type"], "📌")
                    approved = approval.get(eid, True)
                    status = "✅ approved" if approved else "🚫 rejected"
                    with st.expander(
                            f"{status} · {icon} **{c['name']}** — "
                            f"type: {c['type']} · "
                            f"confidence {c['confidence']:.2f} "
                            f"(“{c['strength_word']}”)"):
                        st.write(f"“{c['quote']}”")
                        st.caption("figures: " + ", ".join(c["figures"])
                                   if c["figures"] else "figures: none")
                        st.caption("linked: " +
                                   ", ".join(c["linked_entities"]))
                        for prov in c["provenance"]:
                            st.caption(f"📄 {prov['doc_id']} · "
                                       f"{prov['title']} · "
                                       f"{prov['publisher']} · "
                                       f"{prov['date']}")
                        new_state[eid] = st.toggle(
                            "Approved for citation", value=approved,
                            key=f"fraud_apr_{eid}")
                if new_state and st.button("💾 Save curation",
                                          key="fraud_save_btn"):
                    fraud_store.save_approval({**approval, **new_state})
                    st.success("Curation saved. `fraud_ring_network` now "
                               "reflects it — try re-running a claim eval "
                               "with a key ring rejected and watch the risk "
                               "score shift.")

    else:  # cost
        from cost_agent.graphrag import store
        from cost_agent.graphrag.extractor import (MockLLMGraphExtractor,
                                                   merge_candidates)

        memos = json.loads((DATA_DIR / "memos.json").read_text())
        st.markdown("**The write path behind the knowledge graph.** Raw "
                    "documents → mock-LLM extraction → staged candidates → "
                    "**human curation** → citable knowledge with provenance. "
                    "The analyst's `driver_tree` tool only returns drivers a "
                    "human has approved (plus baseline curated ones).")
        left, right = st.columns([2, 3])
        with left:
            st.markdown("**1 · Source documents**")
            for m in memos:
                with st.expander(f"{m['doc_id']} — {m['title']} ({m['date']})"):
                    st.caption(m["publisher"])
                    st.write(m["text"])
        with right:
            st.markdown("**2 · Extraction** (mock-LLM — real-LLM seam marked "
                        "in `cost_agent/graphrag/extractor.py`)")
            if st.button("🔍 Run extraction over documents", type="primary"):
                st.session_state.extraction = merge_candidates(
                    MockLLMGraphExtractor().extract(memos))
            if "extraction" not in st.session_state:
                st.info("Run the extraction to see staged candidates with "
                        "their provenance, then curate them below.")
            else:
                merged = st.session_state.extraction
                graph_nodes = {n["id"]: n for n in json.loads(
                    (DATA_DIR / "cost_entities.json").read_text())["nodes"]}
                approval = store.load_approval()
                st.markdown("**3 · Staged candidates & curation** — toggle "
                            "and save; then re-run a question in Live Run or "
                            "the eval to see knowledge state change the "
                            "agent's verdicts.")
                new_state = {}
                for did, c in sorted(merged.items(),
                                     key=lambda kv: -kv[1]["weight"]):
                    curated = graph_nodes[did].get("curated", False)
                    approved = curated or approval.get(did, True)
                    status = "📌 curated" if curated else \
                        ("✅ approved" if approved else "🚫 rejected")
                    with st.expander(
                            f"{status} · **{c['name']}** — IMPACTS "
                            f"{c['metric']} ({c['region']}/{c['coverage']}) · "
                            f"weight {c['weight']} (“{c['strength_word']}”)"):
                        st.write(f"“{c['quote']}”")
                        st.caption("figures: " + ", ".join(c["figures"]))
                        for p in c["provenance"]:
                            st.caption(f"📄 {p['doc_id']} · {p['title']} · "
                                       f"{p['publisher']} · {p['date']}")
                        if curated:
                            st.caption("Baseline curated driver — always "
                                       "citable.")
                        else:
                            new_state[did] = st.toggle(
                                "Approved for citation", value=approved,
                                key=f"apr_{did}")
                if new_state and st.button("💾 Save curation"):
                    store.save_approval({**approval, **new_state})
                    st.success("Curation saved. `driver_tree` now reflects "
                               "it — try re-running Q1 with a key driver "
                               "rejected and watch recall drop.")

# ════════════════════════════════════════════════════════════════════
# TAB 6 — LEARNING (continuous learning loop, both agents)
# ════════════════════════════════════════════════════════════════════
with tab_learning:
    st.markdown("**The feedback loop:** real-world outcomes arrive → the "
                "agent's past decisions are scored against them → weight "
                "adjustments are *proposed* → a **human approves** → "
                "knowledge updates → eval shows the delta.")
    if agent == "fraud":
        from fraud_agent import learning as fraud_learning
        st.caption("Outcomes: `data/outcomes.jsonl` (post-payment audits, "
                   "SIU dispositions). Weights: `config/fraud_weights.yaml`.")
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
                get_harness.clear()  # brains reload weights on construction
                st.success("Applied. Agents reconstructed with new weights.")
                st.rerun()
            if b.button("↺ Reset weights to defaults"):
                import yaml as _yaml
                from fraud_agent.brain.rule_based import _DEFAULT_WEIGHTS
                from fraud_agent.paths import ROOT as _ROOT
                (_ROOT / "config" / "fraud_weights.yaml").write_text(
                    _yaml.safe_dump({"scoring": _DEFAULT_WEIGHTS},
                                    sort_keys=False))
                get_harness.clear()
                st.success("Weights reset to defaults.")
                st.rerun()
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
                st.success(f"{result['changed']} edge(s) updated — "
                           "driver_tree serves the new weights immediately. "
                           "Re-run a question to see confidence shift.")

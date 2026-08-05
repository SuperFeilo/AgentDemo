"""ANATOMY COMPONENT: EVAL — release gate (deterministic regression)

The "release gate": deterministic, resettable, fast checks — Karpathy's
verifiability made concrete ("resettable, efficient, rewardable"). The
Eval Lab tab renders these inline; `scripts/test_packs.py` runs the same
suite headless. A bug found live is locked here so it can never come
back (the waku / LangChain discipline).
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from fraud_agent.dossier import compile_dossier
from fraud_agent.harness import FraudHarness
from fraud_agent.lifecycle import RunState
from fraud_agent.paths import DATA_DIR, ROOT
from cost_agent.harness import CostHarness
from cost_agent.eval.dataset import QUESTIONS


def run_regression(agent: str = "fraud") -> dict:
    """Baseline gate: every deterministic check, bug-injected ones included.

    Returns {"checks": [{name, passed, detail, bug_context}], ...}.
    """
    from llm_client.config import mock_mode
    with mock_mode():  # the gate asserts the deterministic brain, always
        checks: list[dict] = []

        def check(name: str, passed: bool, detail: str = "",
                  bug_context: bool = False) -> None:
            checks.append({"name": name, "passed": bool(passed),
                           "detail": detail, "bug_context": bug_context})

        if agent == "fraud":
            _fraud_checks(check)
        elif agent == "cost":
            _cost_checks(check)
        else:
            raise ValueError(agent)
    return {"checks": checks, "passed": sum(c["passed"] for c in checks),
            "total": len(checks), "agent": agent}


def run_bug_sweep(agent: str = "fraud") -> dict:
    """Every planted reasoning bug, injected and caught by reflection."""
    from llm_client.config import mock_mode
    with mock_mode():
        checks: list[dict] = []

        def check(name: str, passed: bool, detail: str = "",
                  bug_context: bool = True) -> None:
            checks.append({"name": name, "passed": bool(passed),
                           "detail": detail, "bug_context": bug_context})

        if agent == "fraud":
            _fraud_reflection_checks(check, bug_on=True)
        elif agent == "cost":
            _cost_reflection_checks(check, bug_on=True)
        else:
            raise ValueError(agent)
    return {"checks": checks, "passed": sum(c["passed"] for c in checks),
            "total": len(checks), "agent": agent}


# ── fraud: blackboard, dossier, autonomy gate, budgets, reflection ───
def _fraud_checks(check) -> None:
    h = FraudHarness()
    run = h.run_auto("C-1011")  # auto-approves the gate
    writes = [e for e in run.trace if e["type"] == "blackboard_write"]
    origins = {w["origin"] for w in writes}
    check("blackboard writes present", len(writes) >= 5, f"({len(writes)} writes)")
    check("origins tagged",
          {"persistent_db", "knowledge_graph", "model_brain", "human"} <= origins,
          f"({sorted(origins)})")
    d = compile_dossier(run)
    check("dossier keys",
          {"case", "plan_skills", "reasoning", "data_access", "lineage",
           "decision", "cost"} <= set(d))
    check("dossier lineage graph + model",
          "knowledge_graph" in d["lineage"] and "model_brain" in d["lineage"])
    check("dossier cost per-call populated",
          all(c["cost_units"] is not None for c in d["cost"]["per_call"]))

    h2 = FraudHarness()
    run_full = h2.run_auto("C-1011", autonomy_level="full")
    ckpts_full = [e for e in run_full.trace if e["type"] == "checkpoint"]
    check("full autonomy: no checkpoints", not ckpts_full)
    check("full autonomy: ESCALATED", run_full.decision == "ESCALATE"
          and run_full.state == RunState.ESCALATED)

    h3 = FraudHarness()
    run_rej = h3.run_auto("C-1011", auto_approve=False)  # human rejects
    check("gated + reject: degraded to REVIEW", run_rej.decision == "REVIEW")
    ckpt = next(e for e in run_rej.trace if e["type"] == "checkpoint")
    check("gated: checkpoint names the tool", "siu_escalate" in ckpt["prompt"])

    h4 = FraudHarness()
    h4.plan.constraints["max_cost_units"] = 10  # force overspend
    run_cost = h4.run_auto("C-1011", autonomy_level="full")
    aborted = [e for e in run_cost.trace if e["type"] == "aborted"]
    check("cost budget aborts run", bool(aborted)
          and run_cost.state == RunState.FAILED,
          f"({aborted[0]['reason'] if aborted else 'none'})")
    check("latency metered on calls",
          all("latency_ms" in e for e in run_cost.trace
              if e["type"] == "tool_call"))

    _fraud_reflection_checks(check, bug_on=True)
    _fraud_learning_checks(check)


def _fraud_reflection_checks(check, bug_on: bool = True) -> None:
    h = FraudHarness()
    h.brain.bug_injection = True
    run_bug = h.run_auto("C-1005", autonomy_level="full")
    refl = next(e for e in run_bug.trace if e["type"] == "observation"
                and e["step"] == "reflect")
    check("reflection fired (bug injected)", refl is not None, bug_context=bug_on)
    check("reflection self-corrects", refl["corrected"] is True,
          f"({refl['summary'][:90]}...)", bug_context=bug_on)
    check("final risk restored to signal sum", run_bug.risk_score == 55,
          f"(risk={run_bug.risk_score})", bug_context=bug_on)


def _fraud_learning_checks(check) -> None:
    from fraud_agent import learning as fl
    weights_path = ROOT / "config" / "fraud_weights.yaml"
    w_backup = weights_path.read_text()
    try:
        rep = fl.analyze()
        shared = next(p for p in rep["proposals"]
                      if p["signal"] == "network.shared_attribute")
        check("learning: noisy signal halved",
              shared["precision"] == 0.0
              and shared["proposed_weight"] == shared["current_weight"] // 2,
              f"(precision {shared['precision']}, "
              f"{shared['current_weight']} -> {shared['proposed_weight']})")
        fl.apply_proposals(rep)
        new_w = yaml.safe_load(weights_path.read_text())["scoring"]
        check("learning: weights file updated",
              new_w["network"]["shared_attribute"] == shared["proposed_weight"])
        from fraud_agent.eval.runner import run_eval as fraud_eval
        check("learning: fraud eval still green",
              fraud_eval()["metrics"]["f1"] == 1.0)
    finally:
        weights_path.write_text(w_backup)


# ── cost: reflection + learning + eval ──────────────────────────────
def _cost_checks(check) -> None:
    _cost_reflection_checks(check, bug_on=True)
    _cost_learning_checks(check)


def _cost_reflection_checks(check, bug_on: bool = True) -> None:
    h = CostHarness()
    h.brain.bug_injection = True
    run_bug = h.run_auto(QUESTIONS[0], autonomy_level="full")
    refl = next(e for e in run_bug.trace if e["type"] == "observation"
                and e["step"] == "reflect")
    check("analyst reflection restates number", refl["corrected"] is True,
          bug_context=bug_on)
    hb = CostHarness()
    clean = hb.run_auto(QUESTIONS[0], autonomy_level="full")
    dec_clean = next(e for e in clean.trace if e["type"] == "decision")
    dec_bug = next(e for e in run_bug.trace if e["type"] == "decision")
    check("analyst final number identical after self-correction",
          dec_clean["numbers"] == dec_bug["numbers"], bug_context=bug_on)


def _cost_learning_checks(check) -> None:
    from cost_agent import learning as cl
    graph_path = DATA_DIR / "cost_entities.json"
    g_backup = graph_path.read_text()
    try:
        crep = cl.analyze()
        sc = next(p for p in crep["proposals"]
                  if p["driver_id"] == "supply_chain")
        check("learning: supply_chain decayed",
              sc["proposed_weight"] < sc["current_weight"],
              f"({sc['current_weight']} -> {sc['proposed_weight']})")
        cl.apply_proposals(crep)
        g = json.loads(graph_path.read_text())
        edge = next(e for e in g["edges"] if e["a"] == "supply_chain")
        check("learning: graph edge weight updated",
              edge["weight"] == sc["proposed_weight"])
        from cost_agent.eval.runner import run_eval as cost_eval
        check("learning: cost eval still green",
              cost_eval()["metrics"]["citation_recall"] == 1.0)
    finally:
        graph_path.write_text(g_backup)
        (DATA_DIR / "graph_approval.json").unlink(missing_ok=True)

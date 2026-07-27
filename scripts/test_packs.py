"""End-to-end tests for Packs A/B/C:
blackboard + dossier, autonomy gate, cost budgets, reflection, learning.
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import yaml

from fraud_agent.dossier import compile_dossier
from fraud_agent.harness import FraudHarness
from fraud_agent.lifecycle import RunState
from fraud_agent.paths import DATA_DIR, ROOT
from cost_agent.harness import CostHarness
from cost_agent.eval.dataset import QUESTIONS

PASS = []


def check(name, cond, detail=""):
    PASS.append(cond)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name} {detail}")


print("== Pack A: blackboard + dossier (fraud C-1011) ==")
h = FraudHarness()
run = h.run_auto("C-1011")  # auto-approves the gate
writes = [e for e in run.trace if e["type"] == "blackboard_write"]
origins = {w["origin"] for w in writes}
check("blackboard writes present", len(writes) >= 5, f"({len(writes)} writes)")
check("origins tagged", {"persistent_db", "knowledge_graph", "model_brain",
                         "human"} <= origins, f"({sorted(origins)})")
d = compile_dossier(run)
check("dossier keys", {"case", "plan_skills", "reasoning", "data_access",
                       "lineage", "decision", "cost"} <= set(d))
check("dossier lineage has graph + model entries",
      "knowledge_graph" in d["lineage"] and "model_brain" in d["lineage"])
check("dossier cost per-call populated",
      all(c["cost_units"] is not None for c in d["cost"]["per_call"]))

print("\n== Pack B: autonomy gate ==")
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
check("gated: checkpoint mentions the gated tool",
      "siu_escalate" in ckpt["prompt"])

print("\n== Pack B: cost budget ==")
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

print("\n== Pack C: reflection catches injected bug (fraud C-1005) ==")
h5 = FraudHarness()
h5.brain.bug_injection = True
run_bug = h5.run_auto("C-1005", autonomy_level="full")
refl = next(e for e in run_bug.trace if e["type"] == "observation"
            and e["step"] == "reflect")
check("reflection fired", refl is not None)
check("reflection self-corrected", refl["corrected"] is True,
      f"({refl['summary'][:90]}...)")
check("final risk restored to signal sum", run_bug.risk_score == 55)

h6 = CostHarness()
h6.brain.bug_injection = True
run_bug2 = h6.run_auto(QUESTIONS[0], autonomy_level="full")
refl2 = next(e for e in run_bug2.trace if e["type"] == "observation"
             and e["step"] == "reflect")
check("analyst reflection restated number", refl2["corrected"] is True)
truth = 14.4  # ballpark; compare against clean run instead
h6b = CostHarness()
clean = h6b.run_auto(QUESTIONS[0], autonomy_level="full")
dec_clean = next(e for e in clean.trace if e["type"] == "decision")
dec_bug = next(e for e in run_bug2.trace if e["type"] == "decision")
check("analyst final number identical after self-correction",
      dec_clean["numbers"] == dec_bug["numbers"])

print("\n== Pack C: learning loops ==")
from fraud_agent import learning as fl
from cost_agent import learning as cl

weights_path = ROOT / "config" / "fraud_weights.yaml"
graph_path = DATA_DIR / "cost_entities.json"
w_backup = weights_path.read_text()
g_backup = graph_path.read_text()
try:
    rep = fl.analyze()
    shared = next(p for p in rep["proposals"]
                  if p["signal"] == "network.shared_attribute")
    check("fraud proposal: shared_attribute halved",
          shared["current_weight"] == 20 and shared["proposed_weight"] == 10,
          f"(precision {shared['precision']})")
    fl.apply_proposals(rep)
    new_w = yaml.safe_load(weights_path.read_text())["scoring"]
    check("weights file updated", new_w["network"]["shared_attribute"] == 10)
    from fraud_agent.eval.runner import run_eval as fraud_eval
    check("fraud eval still green after learning",
          fraud_eval()["metrics"]["f1"] == 1.0)

    crep = cl.analyze()
    sc = next(p for p in crep["proposals"] if p["driver_id"] == "supply_chain")
    check("cost proposal: supply_chain decayed",
          sc["proposed_weight"] < sc["current_weight"],
          f"({sc['current_weight']} -> {sc['proposed_weight']})")
    cl.apply_proposals(crep)
    g = json.loads(graph_path.read_text())
    edge = next(e for e in g["edges"] if e["a"] == "supply_chain")
    check("graph edge weight updated", edge["weight"] == sc["proposed_weight"])
    from cost_agent.eval.runner import run_eval as cost_eval
    check("cost eval still green after learning",
          cost_eval()["metrics"]["citation_recall"] == 1.0)
finally:
    weights_path.write_text(w_backup)
    graph_path.write_text(g_backup)
    (DATA_DIR / "graph_approval.json").unlink(missing_ok=True)
    print("\n(state restored: default weights, default graph)")

print(f"\n{'ALL PACK TESTS PASSED' if all(PASS) else 'SOME TESTS FAILED'} "
      f"({sum(PASS)}/{len(PASS)})")
sys.exit(0 if all(PASS) else 1)

"""ANATOMY COMPONENT: EVAL (3/3 — batch runner)

Runs the agent headlessly over the whole labeled dataset and scores it.
The flag threshold is a parameter so the Eval Lab UI can sweep it live
and show how precision/recall trade off — the same agent, measured
under different operating points.

Usage:
    python -m fraud_agent.eval.runner [threshold]
"""
from __future__ import annotations

import sys

from fraud_agent.eval.dataset import LABELS
from fraud_agent.eval.metrics import confusion, scores
from fraud_agent.harness import FraudHarness


def run_eval(flag_threshold: int = 40) -> dict:
    harness = FraudHarness()
    results = []
    for claim_id, label in LABELS.items():
        run = harness.run_auto(claim_id, auto_approve=True)
        results.append({
            "claim_id": claim_id, "label": label,
            "risk_score": run.risk_score, "decision": run.decision,
            "flagged": run.risk_score >= flag_threshold,
            "state": run.state.value, "run_id": run.run_id,
        })
    cm = confusion(results)
    return {"flag_threshold": flag_threshold, "results": results,
            "confusion": cm, "metrics": scores(cm)}


if __name__ == "__main__":
    threshold = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    report = run_eval(threshold)
    print(f"\nEval @ flag threshold {report['flag_threshold']}\n" + "=" * 46)
    for r in report["results"]:
        mark = {"tp": "[caught]", "fp": "[FALSE ALARM]",
                "tn": "[passed]", "fn": "[MISSED]"}
        cm_key = ("tp" if r["flagged"] else "fn") if r["label"] == "fraud" \
            else ("fp" if r["flagged"] else "tn")
        print(f"  {r['claim_id']} [{r['label']:5s}] risk={r['risk_score']:3d} "
              f"{r['decision']:8s} {mark[cm_key]}")
    print("=" * 46)
    m = report["metrics"]
    print(f"  precision {m['precision']:.2f}   recall {m['recall']:.2f}   "
          f"f1 {m['f1']:.2f}   accuracy {m['accuracy']:.2f}\n")

"""ANATOMY COMPONENT: EVAL (agent #3, 3/4 — batch runner per sub-agent)"""
from __future__ import annotations

from portfolio_agent.eval.dataset import (
    SUBMISSIONS_DATASET, UNDERWRITING_DATASET, SETTLEMENT_DATASET,
)
from portfolio_agent.eval.metrics import aggregate, sub_scores


def _score_one(q, decision, run):
    """Compute sub-scores from a verdict case."""
    citations = decision.get("citations", []) or []
    cited_ids = {c.get("signal_id") for c in citations if isinstance(c, dict)}
    required = q.get("required_signals", [])
    cite_recall = (sum(1 for s in required if s in cited_ids) /
                   len(required)) if required else 1.0
    verdict_ok = run.decision == q["ground_truth_verdict"]
    return {"verdict_ok": verdict_ok, "citation_recall": cite_recall,
            "verdict_accuracy": int(verdict_ok)}


def run_eval() -> dict:
    from portfolio_agent.submissions.harness import SubmissionsHarness
    from portfolio_agent.underwriting.harness import UnderwritingHarness
    from portfolio_agent.settlement.harness import SettlementHarness

    sub_h = SubmissionsHarness()
    uw_h = UnderwritingHarness()
    st_h = SettlementHarness()

    rows = []
    for q in SUBMISSIONS_DATASET:
        run = sub_h.run_auto({"submission_id": q["submission_id"]})
        d = next(e for e in run.trace if e["type"] == "decision")
        row = {"id": q["id"], "stage": "submissions",
               "subject_id": q["submission_id"], "verdict": run.decision,
               "score": run.risk_score, "citations": d.get("citations", []),
               "ground_truth_verdict": q["ground_truth_verdict"],
               "required_signals": q["required_signals"]}
        row.update(_score_one(q, d, run))
        rows.append(row)
    for q in UNDERWRITING_DATASET:
        run = uw_h.run_auto({"submission_id": q["submission_id"]})
        d = next(e for e in run.trace if e["type"] == "decision")
        row = {"id": q["id"], "stage": "underwriting",
               "subject_id": q["submission_id"], "verdict": run.decision,
               "score": run.risk_score, "citations": d.get("citations", []),
               "ground_truth_verdict": q["ground_truth_verdict"],
               "required_signals": q["required_signals"]}
        row.update(_score_one(q, d, run))
        rows.append(row)
    for q in SETTLEMENT_DATASET:
        run = st_h.run_auto({"policy_id": q["policy_id"]})
        d = next(e for e in run.trace if e["type"] == "decision")
        row = {"id": q["id"], "stage": "settlement",
               "subject_id": q["policy_id"], "verdict": run.decision,
               "score": run.risk_score, "citations": d.get("citations", []),
               "ground_truth_verdict": q["ground_truth_verdict"],
               "required_signals": q["required_signals"]}
        row.update(_score_one(q, d, run))
        rows.append(row)
    metrics = aggregate(rows, ["verdict_ok", "verdict_accuracy",
                               "citation_recall"])
    return {"results": rows, "metrics": metrics}


if __name__ == "__main__":
    rep = run_eval()
    print("\nSub-agent eval\n" + "=" * 60)
    for r in rep["results"]:
        print(f"  {r['id']} [{r['stage']:14s}] verdict={r['verdict']:22s}"
              f" truth={r['ground_truth_verdict']:22s} "
              f"verdict_ok={r['verdict_ok']} cite_recall="
              f"{r['citation_recall']:.2f}")
    m = rep["metrics"]
    print("=" * 60)
    print(f"  verdict_accuracy {m['verdict_accuracy']:.2f}   "
          f"citation_recall {m['citation_recall']:.2f}\n")
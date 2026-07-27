"""ANATOMY COMPONENT: EVAL (agent #2, 3/3 — batch runner)

Runs the analyst agent over the research-question dataset and scores
citations, numbers and faithfulness.

Usage:
    python -m cost_agent.eval.runner
"""
from __future__ import annotations

from cost_agent.eval.dataset import QUESTIONS
from cost_agent.eval.metrics import aggregate, citation_scores
from cost_agent.harness import CostHarness
from cost_agent.tools.cost_tools import metric_trend


def run_eval() -> dict:
    harness = CostHarness()
    rows = []
    for q in QUESTIONS:
        truth = metric_trend(q["metric"], q["region"], q["coverage"])
        truth_value = truth[q["numeric_field"]]

        run = harness.run_auto(q)
        decision = next(e for e in run.trace if e["type"] == "decision")
        cited = [c["driver_id"] for c in decision["citations"]]
        stated = decision["numbers"][q["numeric_field"]]

        scores = citation_scores(q["required_drivers"],
                                 q["acceptable_drivers"], cited)
        with_docs = [c for c in decision["citations"] if c.get("docs")]
        rows.append({
            "id": q["id"], "question": q["text"], "verdict": run.decision,
            "confidence": decision["confidence"], "cited": cited,
            "required": q["required_drivers"],
            "stated": stated, "truth": truth_value,
            "numeric_ok": abs(stated - truth_value) <= q["tolerance"],
            "faithful": f"{stated:+.1f}%" in decision["explanation"]
                        or f"{stated:.1f}%" in decision["explanation"],
            "provenance_ok": len(with_docs) == len(decision["citations"]),
            **scores,
        })
    return {"results": rows, "metrics": aggregate(rows)}


if __name__ == "__main__":
    report = run_eval()
    print("\nCost-analyst eval\n" + "=" * 60)
    for r in report["results"]:
        print(f"  {r['id']} [{r['verdict']:20s}] conf={r['confidence']:3d} "
              f"cited={','.join(r['cited']) or '-'}")
        print(f"      precision={r['citation_precision']:.2f} "
              f"recall={r['citation_recall']:.2f} "
              f"numeric_ok={r['numeric_ok']} faithful={r['faithful']} "
              f"provenance={r['provenance_ok']}")
    print("=" * 60)
    m = report["metrics"]
    print(f"  citation precision {m['citation_precision']:.2f}   "
          f"recall {m['citation_recall']:.2f}   "
          f"numeric accuracy {m['numeric_accuracy']:.2f}   "
          f"faithfulness {m['faithfulness']:.2f}   "
          f"provenance {m['provenance_coverage']:.2f}\n")

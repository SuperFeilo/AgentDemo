"""ANATOMY COMPONENT: EVAL (agent #3, 4/4 — assembly batch runner)"""
from __future__ import annotations

from portfolio_agent.eval.dataset import ASSEMBLY_DATASET
from portfolio_agent.eval.metrics import assembly_scores, aggregate


def run_eval() -> dict:
    from portfolio_agent.assembly.harness import PortfolioHarness

    h = PortfolioHarness()
    rows = []
    for q in ASSEMBLY_DATASET:
        run = h.run_auto(q["segment"])
        d = next(e for e in run.trace if e["type"] == "decision")
        row = {"id": q["id"], "segment": q["segment"],
               "verdict": run.decision, "confidence": d["confidence"],
               "lead_signal": d.get("lead_signal"),
               "citations": d.get("citations", []),
               "stage_verdicts": d.get("stage_verdicts", {}),
               "ground_truth_verdict": q["ground_truth_verdict"],
               "expected_signal_stage": q["expected_signal_stage"]}
        row.update(assembly_scores(row))
        rows.append(row)
    metrics = aggregate(rows, ["verdict_ok", "margin_thesis_ok",
                               "provenance_ok"])
    return {"results": rows, "metrics": metrics}


if __name__ == "__main__":
    rep = run_eval()
    print("\nAssembly eval\n" + "=" * 60)
    for r in rep["results"]:
        lead = r.get("lead_signal") or {}
        print(f"  {r['id']} segment={r['segment']} "
              f"verdict={r['verdict']:22s} conf={r['confidence']:3d} "
              f"lead_stage={lead.get('stage','?')} "
              f"(expected {r['expected_signal_stage']}) -> thesis?"
              f"{r['margin_thesis_ok']} provenance?{r['provenance_ok']}")
    m = rep["metrics"]
    print("=" * 60)
    print(f"  verdict_ok {m['verdict_ok']:.2f}   "
          f"margin_thesis_ok {m['margin_thesis_ok']:.2f}   "
          f"provenance_ok {m['provenance_ok']:.2f}\n")
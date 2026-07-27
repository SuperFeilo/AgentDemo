"""ANATOMY COMPONENT: EVAL (agent #2, 2/3 — metrics)

Analyst-agent metrics:
  - citation precision: cited drivers that are legit (required ∪ acceptable)
  - citation recall:    required drivers actually cited
  - numeric accuracy:   the agent's headline number matches the warehouse
  - faithfulness:       the headline number literally appears in the
                        explanation text (anti-fabrication check)
"""
from __future__ import annotations


def citation_scores(required: list[str], acceptable: list[str],
                    cited: list[str]) -> dict:
    legit = set(required) | set(acceptable)
    tp = [d for d in cited if d in legit]
    prec = len(tp) / len(cited) if cited else 0.0
    rec = len([d for d in required if d in cited]) / len(required) \
        if required else 1.0
    return {"citation_precision": prec, "citation_recall": rec}


def aggregate(rows: list[dict]) -> dict:
    n = len(rows)
    return {
        "citation_precision": sum(r["citation_precision"] for r in rows) / n,
        "citation_recall": sum(r["citation_recall"] for r in rows) / n,
        "numeric_accuracy": sum(r["numeric_ok"] for r in rows) / n,
        "faithfulness": sum(r["faithful"] for r in rows) / n,
        "provenance_coverage": sum(r["provenance_ok"] for r in rows) / n,
        "mean_confidence": sum(r["confidence"] for r in rows) / n,
    }

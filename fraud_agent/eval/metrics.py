"""ANATOMY COMPONENT: EVAL (2/3 — metrics)

Binary classification metrics with 'fraud' as the positive class.
A run is 'flagged' when the agent refused to auto-approve it
(REVIEW or ESCALATE — i.e. risk score >= the review threshold).
"""
from __future__ import annotations


def confusion(results: list[dict]) -> dict:
    cm = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
    for r in results:
        actual, flagged = r["label"] == "fraud", r["flagged"]
        if actual and flagged:
            cm["tp"] += 1
        elif not actual and flagged:
            cm["fp"] += 1
        elif not actual and not flagged:
            cm["tn"] += 1
        else:
            cm["fn"] += 1
    return cm


def scores(cm: dict) -> dict:
    tp, fp, fn, tn = cm["tp"], cm["fp"], cm["fn"], cm["tn"]
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if precision + recall else 0.0)
    accuracy = (tp + tn) / sum(cm.values()) if sum(cm.values()) else 0.0
    return {"precision": precision, "recall": recall, "f1": f1,
            "accuracy": accuracy}

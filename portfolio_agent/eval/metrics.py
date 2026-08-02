"""ANATOMY COMPONENT: EVAL (agent #3, 2/4 — metrics)

Sub-agent metrics: verdict_accuracy — share of runs whose verdict
matches the dataset verdict. Plus citation recall: required_signals
that appear in the citations list.

Assembly metrics: verdict_accuracy + margin-thesis correctness (the
lead signal's stage matches expected_signal_stage), plus lineage
citation provenance coverage.
"""
from __future__ import annotations


def sub_scores(row: dict) -> dict:
    cited = [c.get("signal_id") for c in row.get("citations", [])]
    required = row.get("required_signals", [])
    cite_recall = (sum(1 for s in required if s in cited) / len(required)
                    if required else 1.0)
    verdict_ok = row["verdict"] == row["ground_truth_verdict"]
    return {"verdict_ok": verdict_ok, "citation_recall": cite_recall,
            "verdict_accuracy": int(verdict_ok)}


def assembly_scores(row: dict) -> dict:
    lead = row.get("lead_signal") or {}
    verdict_ok = row["verdict"] == row["ground_truth_verdict"]
    stage_ok = lead.get("stage") == row["expected_signal_stage"]
    cite_provenance_ok = all(
        c.get("docs") for c in row.get("citations", []))
    return {"verdict_ok": verdict_ok,
            "margin_thesis_ok": int(stage_ok),
            "provenance_ok": int(cite_provenance_ok)}


def aggregate(rows: list[dict], keys: list[str]) -> dict:
    n = len(rows) or 1
    return {k: sum(r.get(k, 0) for r in rows) / n for k in keys}
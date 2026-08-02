"""ANATOMY COMPONENT: EVAL (agent #3, 1/4 — ground truth)

Three sub-agent eval ground-truth datasets + one assembly dataset.
Tiny and tight — each question is keyed to the planted patterns.

Subscriptions and underwriting eval datasets are keyed to specific
submission_ids; settlement is keyed to specific policy_ids. Each has
`ground_truth_verdict` (the cardinal verdict the agent should reach)
and `required_signals` (signals the citations must include for those
where the verdict penalises omission).
"""
from __future__ import annotations

import sqlite3

from portfolio_agent import warehouse

SUBMISSIONS_DATASET = [
    # BRO-W complete sub still gets the broker-pattern penalty since
    # broker-level completeness < 70%.
    {"id": "S1", "submission_id": 1003, "broker": "BRO-W",
     "ground_truth_verdict": "ACCEPTABLE",
     "required_signals": ["exposure_completeness"]},
    {"id": "S2", "submission_id": 1002, "broker": "BRO-S",
     "ground_truth_verdict": "STRONG SUBMISSION",
     "required_signals": ["exposure_completeness"]},
    {"id": "S3", "submission_id": 1001, "broker": "BRO-S",
     "ground_truth_verdict": "WEAK SUBMISSION",
     "required_signals": ["exposure_completeness"]},
]

UNDERWRITING_DATASET = [
    {"id": "U1", "submission_id": 1018, "broker": "BRO-W",
     "class_code": "5437",
     "ground_truth_verdict": "MISPRICED",
     "required_signals": ["risk_score_override"]},
    {"id": "U2", "submission_id": 1002, "broker": "BRO-S",
     "class_code": "5411",
     "ground_truth_verdict": "ACCEPTABLE", "required_signals": []},
]

SETTLEMENT_DATASET = [
    # policy 5068 was hand-picked earlier as having a settled claim
    # with high leakage
    {"id": "T1", "policy_id": 5068,
     "ground_truth_verdict": "LEAKAGE DETECTED",
     "required_signals": ["reserve_adequacy"]},
    {"id": "T2", "policy_id": 5065,
     "ground_truth_verdict": "LEAKAGE DETECTED",
     "required_signals": []},
]

# Assembly eval — keyed to segments (broker / class / region). Each
# question asserts the assembly verdict criterion and the expected top
# signal stage.
ASSEMBLY_DATASET = [
    {"id": "A1", "segment": {"broker": "ALL", "class_code": "5437",
                             "region": "ALL"},
     "ground_truth_verdict": "PROFIT EDGE IDENTIFIED",
     "expected_signal_stage": "risk_scoring"},
    {"id": "A2", "segment": {"broker": "BRO-W", "class_code": "ALL",
                             "region": "ALL"},
     "ground_truth_verdict": "PROFIT EDGE IDENTIFIED",
     "expected_signal_stage": "claim"},
    {"id": "A3", "segment": {"broker": "ALL", "class_code": "ALL",
                             "region": "ALL"},
     "ground_truth_verdict": "MARGINAL",
     "expected_signal_stage": "claim"},
]
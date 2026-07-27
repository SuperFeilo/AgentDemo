"""ANATOMY COMPONENT: CONTINUOUS LEARNING LOOP (fraud investigator)

Real feedback loop, small data:

  1. OUTCOMES arrive from the real world (post-payment audits, SIU
     dispositions) — data/outcomes.jsonl.
  2. ANALYSIS replays decisions vs outcomes and computes, per *signal*,
     how often the signal fired and how often the claim was actually
     fraudulent (signal precision).
  3. PROPOSAL: signals with poor precision get their weights adjusted in
     config/fraud_weights.yaml — but only after a HUMAN approves the
     proposal (the same governance instinct as the autonomy gate).
  4. Eval before/after shows the delta.

Usage:
    python -m fraud_agent.learning            # analyse + propose
    python -m fraud_agent.learning --apply    # apply proposals to weights
"""
from __future__ import annotations

import json
import sys

import yaml

from fraud_agent.brain.rule_based import load_weights
from fraud_agent.harness import FraudHarness
from fraud_agent.paths import DATA_DIR, ROOT

OUTCOMES_PATH = DATA_DIR / "outcomes.jsonl"
PROPOSALS_PATH = DATA_DIR / "skill_proposals.json"
WEIGHTS_PATH = ROOT / "config" / "fraud_weights.yaml"

# signal content -> (weight section, weight key)
def _classify(signal: str) -> tuple[str, str] | None:
    s = signal.lower()
    if "prior claim" in s:
        return ("velocity", "three_plus_priors_90d")
    if "days old" in s:
        return ("policy_timing", "in_force_le_14d")
    if "known fraud" in s:
        return ("network", "known_fraud_link")
    if s.startswith("shares"):
        return ("network", "shared_attribute")
    if "hedging" in s:
        return ("notes", "hedging_points")
    if "contradiction" in s or "revision" in s:
        return ("notes", "per_contradiction")
    return None


def analyze() -> dict:
    outcomes = {json.loads(line)["claim_id"]: json.loads(line)["actual"]
                for line in OUTCOMES_PATH.read_text().splitlines() if line.strip()}
    harness = FraudHarness()
    stats: dict[tuple[str, str], dict] = {}
    per_claim = {}

    for claim_id, actual in outcomes.items():
        run = harness.run_auto(claim_id)
        signals = [sig for e in run.trace if e["type"] == "observation"
                   for sig in e.get("signals", [])]
        per_claim[claim_id] = {"actual": actual, "risk": run.risk_score,
                               "decision": run.decision,
                               "signals": len(signals)}
        for sig in signals:
            key = _classify(sig)
            if not key:
                continue
            st = stats.setdefault(key, {"fired": 0, "on_fraud": 0})
            st["fired"] += 1
            st["on_fraud"] += (actual == "fraud")

    weights = load_weights()
    proposals = []
    for (section, wkey), st in sorted(stats.items()):
        precision = st["on_fraud"] / st["fired"] if st["fired"] else 0.0
        current = weights[section][wkey]
        proposal = None
        if st["fired"] >= 3 and precision < 0.5:
            proposal = max(5, current // 2)
        elif st["fired"] >= 2 and precision == 1.0:
            proposal = current  # validated — leave unchanged
        if proposal is not None:
            proposals.append({
                "signal": f"{section}.{wkey}", "fired": st["fired"],
                "on_fraud": st["on_fraud"], "precision": round(precision, 2),
                "current_weight": current, "proposed_weight": proposal,
                "rationale": ("fires mostly on legit claims — halve weight"
                              if proposal < current else
                              "perfect precision on outcomes — keep"),
            })
    return {"claims": per_claim, "proposals": proposals,
            "weights_path": str(WEIGHTS_PATH)}


def apply_proposals(report: dict) -> dict:
    weights = load_weights()
    for p in report["proposals"]:
        section, wkey = p["signal"].split(".")
        weights[section][wkey] = p["proposed_weight"]
    WEIGHTS_PATH.write_text(yaml.safe_dump({"scoring": weights},
                                           sort_keys=False))
    return weights


if __name__ == "__main__":
    rep = analyze()
    print("\nOutcome analysis (decisions vs real-world outcomes)\n" + "=" * 56)
    for p in rep["proposals"]:
        print(f"  {p['signal']:32s} fired={p['fired']} "
              f"precision={p['precision']:.2f} "
              f"weight {p['current_weight']} -> {p['proposed_weight']}  "
              f"({p['rationale']})")
    if "--apply" in sys.argv:
        apply_proposals(rep)
        print("\nApplied to config/fraud_weights.yaml")
    else:
        print("\n(dry run — pass --apply, or approve in the UI, to write)")

"""ANATOMY COMPONENT: RULE-BASED BRAIN (+ REFLECTION)

The brain makes three kinds of decisions:
  1. WHAT to do next (walk the plan, pick the tool + arguments, and
     explain itself in a "thought").
  2. HOW to score what came back (apply the scoring rules — which live
     in config/fraud_weights.yaml as DATA, so the learning loop can
     propose changes and humans can audit them).
  3. REFLECT on its own work (Ng's reflection pattern): re-verify the
     score arithmetic against the emitted signals and the threshold
     logic before the decision is allowed to stand. If verification
     finds a mismatch, the brain corrects itself and says so.
"""
from __future__ import annotations

import re

import yaml

from fraud_agent.paths import ROOT

_WEIGHTS_PATH = ROOT / "config" / "fraud_weights.yaml"

_DEFAULT_WEIGHTS = {
    "velocity": {"one_prior_90d": 15, "two_priors_90d": 30,
                 "three_plus_priors_90d": 55},
    "policy_timing": {"in_force_le_14d": 40, "in_force_le_45d": 20},
    "network": {"known_fraud_link": 50, "shared_attribute": 20},
    "notes": {"per_contradiction": 15, "contradiction_cap": 45,
              "hedging_min_phrases": 3, "hedging_points": 10},
}


def load_weights() -> dict:
    if _WEIGHTS_PATH.exists():
        return yaml.safe_load(_WEIGHTS_PATH.read_text())["scoring"]
    return _DEFAULT_WEIGHTS


def noisy_or(weights: list[float]) -> float:
    """Shared probabilistic-merge helper (1 - prod(1 - w)): the combined
    confidence of several independent signals. Used by the cost and
    portfolio brains (was duplicated 2x)."""
    prod = 1.0
    for w in weights:
        prod *= (1 - w)
    return 1 - prod


class RuleBasedBrain:
    def __init__(self, plan) -> None:
        self.plan = plan
        self.thresholds = {
            "escalate": plan.constraints["escalation_threshold"],
            "review": plan.constraints["review_threshold"],
        }
        self.weights = load_weights()
        # DEMO ONLY: when True, the brain secretly adds phantom points so
        # you can watch the reflection step catch and repair its work.
        self.bug_injection = False

    # ── WHAT next ───────────────────────────────────────────────────
    def arguments_for(self, step, ctx: dict) -> dict:
        claim = ctx.get("claim", {})
        if step.tool == "claims_db_lookup":
            return {"claim_id": ctx["claim_id"]}
        if step.tool == "claims_history":
            return {"claimant_id": claim["claimant_id"]}
        if step.tool == "policy_check":
            return {"policy_id": claim["policy_id"],
                    "incident_date": claim["incident_date"]}
        if step.tool == "fraud_ring_network":
            return {"claimant_id": claim["claimant_id"]}
        if step.tool == "notes_inconsistency_detector":
            return {"claim_id": ctx["claim_id"]}
        if step.tool == "siu_escalate":
            return {"claim_id": ctx["claim_id"], "risk_score": ctx["risk_score"],
                    "rationale": ctx["signals"]}
        return {}

    def thought_for(self, step, ctx: dict) -> str:
        claim = ctx.get("claim")
        match step.name:
            case "load_claim":
                return (f"I need to investigate claim {ctx['claim_id']}. "
                        "First, load the record.")
            case "velocity_check":
                return (f"Claimant {claim['claimant_id']} filed a "
                        f"{claim['claim_type']} claim. Per my velocity_check "
                        "skill, I should check how often they claim.")
            case "policy_timing":
                return ("Per my policy_timing skill: was the policy suspiciously "
                        "new when the loss occurred?")
            case "network_analysis":
                return ("Per my network_analysis skill: does this claimant share "
                        "a phone, address, or repair shop with known fraud "
                        "entities in the knowledge graph?")
            case "notes_analysis":
                return ("Per my notes_analysis skill: I'll have the language-model "
                        "brain read the adjuster notes for contradictions.")
            case "reflect":
                return ("Per my verification skill: before deciding, I re-check "
                        "my own arithmetic — does the running total equal the "
                        "sum of the signals I cited? Is the threshold logic "
                        "sound?")
            case "decide":
                return (f"All evidence gathered. Total risk: {ctx['risk_score']}. "
                        f"Thresholds: review >= {self.thresholds['review']}, "
                        f"escalate >= {self.thresholds['escalate']}.")
            case "escalate":
                return (f"Risk {ctx['risk_score']} meets the escalation threshold. "
                        "Per my escalation_policy skill, filing an SIU case "
                        "requires human approval.")
        return f"Executing step {step.name}."

    def should_skip(self, step, ctx: dict) -> str | None:
        if step.name == "notes_analysis" and ctx.get("note_count", 0) < 2:
            return "fewer than 2 adjuster notes — nothing to compare"
        if step.name == "escalate" and ctx["risk_score"] < self.thresholds["escalate"]:
            return (f"risk {ctx['risk_score']} is below the escalation threshold "
                    f"of {self.thresholds['escalate']}")
        return None

    # ── HOW to score (weights are data, not code) ───────────────────
    def score_result(self, step_name: str, result: dict, ctx: dict) -> dict:
        w = self.weights
        points, signals = 0, []

        if step_name == "velocity_check":
            n = result["priors_in_90d"]
            v = w["velocity"]
            points = 0 if n == 0 else (v["one_prior_90d"] if n == 1 else
                     (v["two_priors_90d"] if n == 2 else v["three_plus_priors_90d"]))
            if self.bug_injection and points:
                points += 17  # phantom points with NO signal line — reflection bait
            if n:
                signals.append(f"{n} prior claim(s) in the last 90 days "
                               f"(+{v['three_plus_priors_90d'] if n >= 3 else (v['two_priors_90d'] if n == 2 else v['one_prior_90d'])})"
                               " — velocity_check")

        elif step_name == "policy_timing":
            days = result["days_in_force_at_loss"]
            p = w["policy_timing"]
            points = p["in_force_le_14d"] if days <= 14 else \
                     (p["in_force_le_45d"] if days <= 45 else 0)
            if points:
                signals.append(f"Policy was only {days} days old at the date of "
                               f"loss (+{points}) — policy_timing")

        elif step_name == "network_analysis":
            nw = w["network"]
            if result["fraud_links"]:
                points = nw["known_fraud_link"] * len(result["fraud_links"])
                for link in result["fraud_links"]:
                    signals.append(f"Shares {link['via_type']} {link['via']} with "
                                   f"{link['entity']}, a KNOWN FRAUD entity "
                                   f"(+{nw['known_fraud_link']}) — network_analysis")
            elif result["shared_attributes"]:
                points = nw["shared_attribute"]
                for attr in result["shared_attributes"]:
                    signals.append(f"Shares {attr['type']} {attr['attribute']} with "
                                   f"{', '.join(attr['shared_with'])} "
                                   f"(+{nw['shared_attribute']}) — network_analysis")

        elif step_name == "notes_analysis":
            nt = w["notes"]
            contra = result["inconsistencies"]
            points += min(nt["contradiction_cap"],
                          nt["per_contradiction"] * len(contra))
            for c in contra:
                signals.append(f"{c['type'].replace('_', ' ')}: {c['detail']} "
                               f"(+{nt['per_contradiction']}) — notes_analysis")
            if result["hedging_count"] >= nt["hedging_min_phrases"]:
                points += nt["hedging_points"]
                signals.append(f"Heavy hedging in statements "
                               f"({result['hedging_count']} hedging phrases) "
                               f"(+{nt['hedging_points']}) — notes_analysis")

        return {"risk_points": points, "signals": signals}

    # ── REFLECTION (Ng's pattern): verify before deciding ───────────
    def reflect(self, ctx: dict) -> dict:
        checks, corrected = [], False

        # 1. score arithmetic: every signal carries "(+N)"; the running
        #    total must equal their sum (capped at 100 — the risk score
        #    contract). Real recomputation, real fix.
        expected = sum(int(m.group(1)) for s in ctx["signals"]
                       if (m := re.search(r"\+(\d+)", s)))
        checks.append(f"signals sum to {expected}; running total is "
                      f"{ctx['risk_score']}")
        expected = min(expected, 100)
        if expected != ctx["risk_score"]:
            ctx["risk_score"] = expected
            corrected = True
            checks.append(f"MISMATCH — corrected running total to {expected}")

        # 2. threshold logic: decision preview must be consistent
        preview = self.decide(ctx["risk_score"])
        checks.append(f"threshold logic verified: {ctx['risk_score']} → "
                      f"{preview}")

        verdict = "corrected an error" if corrected else "no errors found"
        return {"summary": f"Self-check {verdict}: " + "; ".join(checks),
                "corrected": corrected, "checks": checks}

    def decide(self, risk_score: int) -> str:
        if risk_score >= self.thresholds["escalate"]:
            return "ESCALATE"
        if risk_score >= self.thresholds["review"]:
            return "REVIEW"
        return "APPROVE"

"""ANATOMY COMPONENT: RULE-BASED BRAIN (agent #3c — Settlement Quality)"""
from __future__ import annotations

from portfolio_agent._common import map_score_to_verdict


class SettlementBrain:
    def __init__(self, plan) -> None:
        c = plan.constraints
        self.high, self.mid = c["clean_threshold"], c["acceptable_threshold"]
        self.bug_injection = False

    # ── WHAT next ───────────────────────────────────────────────────
    def arguments_for(self, step, ctx: dict) -> dict:
        policy = ctx.get("policy", {})
        match step.tool:
            case "settlement_catalog":
                return {}
            case "policy_lookup":
                return {"policy_id": ctx["subject"]["policy_id"]}
            case "claim_lookup":
                return {"policy_id": policy.get("policy_id",
                                                 ctx["subject"].get("policy_id"))}
            case "settlement_lookup":
                return {"policy_id": policy.get("policy_id",
                                                 ctx["subject"].get("policy_id"))}
            case "reserve_adequacy_sql":
                policy = ctx.get("policy") or {}
                cls = ctx.get("claims", {}).get("claims", [{}])[0].get(
                    "class_code", "")
                return {"sql": (
                    "SELECT c.class_code, "
                    "CASE WHEN s.settlement_vs_reserve_ratio < 1.2 "
                    "THEN 'adequate' ELSE 'inadequate' END reserve_bucket, "
                    "AVG(s.leakage_amount) avg_leakage, "
                    "AVG(s.settlement_vs_reserve_ratio) avg_ratio "
                    "FROM fact_settlement s JOIN fact_claim c "
                    "ON c.claim_id=s.claim_id "
                    "GROUP BY c.class_code, reserve_bucket "
                    "ORDER BY avg_ratio DESC")}
        return {}

    def thought_for(self, step, ctx: dict) -> str:
        match step.name:
            case "consult_catalog":
                return "Per the settlement_quality skill, consult the semantic layer."
            case "load_policy":
                return "Load the bind so we can pull its claims."
            case "claim_lookup":
                return ("Pull claims on this policy. No claims attached => "
                        "CLEAN SETTLEMENT by absence by construct.")
            case "settlement_lookup":
                return ("Pull settlements. Reserve adequacy, cycle time and "
                        "leakage figures come from here.")
            case "reserve_adequacy":
                return ("Guarded SQL across the warehouse: which class/bucket "
                        "drives leakage? Numbers cited must trace to this.")
            case "reflect":
                return ("Self-check: re-derive leakage from raw rows before "
                        "composing the verdict.")
            case "compose":
                return ("Compose the settlement-quality verdict. CLEAN "
                        "SETTLEMENT, ACCEPTABLE, or LEAKAGE DETECTED.")
        return f"Executing step {step.name}."

    def should_skip(self, step, ctx: dict) -> str | None:
        if step.name in ("claim_lookup", "settlement_lookup",
                         "reserve_adequacy") and not ctx.get("policy"):
            return "no policy loaded yet"
        if step.name == "settlement_lookup" and ctx.get("claims", {}).get(
                "claim_count", 0) == 0:
            return "no claims on policy — no settlements"
        if step.name == "reserve_adequacy" and ctx.get("claims", {}).get(
                "claim_count", 0) == 0:
            return "no claims on policy — reserve adequacy not applicable"
        return None

    # ── HOW ─────────────────────────────────────────────────────────
    def interpret(self, step_name, result, ctx):
        if step_name == "consult_catalog":
            ctx["catalog"] = result
            return {"summary": f"Catalog: {result['n_policies']} policies, "
                               f"{result['n_claims']} claims, "
                               f"{result['n_settlements']} settlements."}

        if step_name == "load_policy":
            ctx["policy"] = result
            return {"summary": f"Policy {result['policy_id']} bound "
                               f"{result['bind_quarter']} at premium "
                               f"${result['premium']:,}."}

        if step_name == "claim_lookup":
            ctx["claims"] = result
            if result["claim_count"] == 0:
                return {"summary": "No claims attached — CLEAN SETTLEMENT "
                                   "by absence."}
            summary = "; ".join(
                f"claim {c['claim_id']}: ${c['severity']:,.0f} "
                f"reserve ${c['reserved_amount']:,.0f} "
                f"(settle ${c['settlement_amount']:,.0f})"
                for c in result["claims"][:6])
            return {"summary": f"{result['claim_count']} claim(s): {summary}."}

        if step_name == "settlement_lookup":
            if self.bug_injection:
                result = dict(result)
                for s in result.get("settlements", []):
                    if s.get("leakage_amount"):
                        s["leakage_amount"] = round(
                            s["leakage_amount"] * 2)
            ctx["settlements"] = result
            if result["settlement_count"] == 0:
                return {"summary": "No settlements to review."}
            summary = "; ".join(
                f"claim {s['claim_id']}: ${s['settlement_amount']:,.0f}"
                f", leakage ${s['leakage_amount']:,.0f}"
                f", ratio {s['settlement_vs_reserve_ratio']:.2f}"
                f", {s['days_to_settle']}d" for s in
                result["settlements"][:6])
            return {"summary": f"{result['settlement_count']} settlement(s): "
                               f"{summary}."}

        if step_name == "reserve_adequacy":
            ctx["reserve_adequacy"] = result
            inadequate = [r for r in result["rows"] if r[1] == "inadequate"]
            if not inadequate:
                return {"summary": "All reserve buckets adequate in portfolio."}
            lines = "; ".join(
                f"class {r[0]} inadequate avg_ratio {r[3]:.2f} "
                f"avg_leak ${r[2]:,.0f}" for r in inadequate[:5])
            return {"summary": lines}

        return {"summary": "Done."}

    # ── score ───────────────────────────────────────────────────────
    def score(self, ctx):
        score = 0
        signals = []
        claims = ctx.get("claims") or {}
        if claims.get("claim_count", 0) == 0:
            return 100, ["no_claims_clean_by_absence"]
        settlements = (ctx.get("settlements") or
                       {"settlements": []})["settlements"]
        if not settlements:
            return 80, ["claims_unsettled_so_far_extra_review"]

        adequates = sum(1 for s in settlements if 0.85 <=
                        s["settlement_vs_reserve_ratio"] <= 1.4)
        adequates_share = adequates / len(settlements)
        if adequates_share >= 0.75:
            score += 25; signals.append("adequate_reserves_majority")
        else:
            inadequate_share = 1 - adequates_share
            if inadequate_share >= 0.5:
                score -= 15; signals.append("inadequate_reserves_majority")
            else:
                score -= 5; signals.append("mixed_reserve_adequacy")

        days = sum(s["days_to_settle"] for s in settlements)
        avg_days = days / len(settlements)
        if avg_days <= 180:
            score += 15; signals.append("cycle_within_target")
        else:
            score -= 10; signals.append("slow_settlement")

        total_leak = sum(s["leakage_amount"] for s in settlements)
        total_sett = sum(s["settlement_amount"] for s in settlements) or 1
        leak_pct = total_leak / total_sett
        ctx["leak_pct"] = round(leak_pct, 3)
        if leak_pct <= 0.05:
            score += 25; signals.append("low_leakage")
        elif leak_pct <= 0.15:
            score += 5; signals.append("moderate_leakage")
        elif leak_pct <= 0.30:
            score -= 10; signals.append(f"high_leakage_{leak_pct:.0%}")
        else:
            score -= 25; signals.append(f"severe_leakage_{leak_pct:.0%}")

        late = sum(1 for s in settlements if s.get("fnol_lag_days", 0) > 14)
        if late:
            score -= 10 * late
            signals.append(f"late_fnol_{late}_claims")

        return max(0, min(100, score + 35)), signals

    def reflect(self, ctx) -> dict:
        checks, corrected = [], False
        settlements = (ctx.get("settlements") or
                       {"settlements": []}).get("settlements", [])
        if settlements:
            recomputed_leak = sum(s["leakage_amount"] for s in settlements)
            recomputed_sett = sum(s["settlement_amount"] for s in settlements)
            if recomputed_sett:
                recomputed_pct = round(recomputed_leak / recomputed_sett, 3)
                if recomputed_pct != ctx.get("leak_pct"):
                    checks.append(f"leak pct RESTATED -> {recomputed_pct:.0%}")
                    ctx["leak_pct"] = recomputed_pct
                    corrected = True
                else:
                    checks.append(f"leak pct {recomputed_pct:.0%} verified ✓")
        verdict = "corrected an error" if corrected else "no errors found"
        return {"summary": f"Self-check {verdict}: " +
                            "; ".join(checks) if checks else "Self-check: ok",
                "corrected": corrected, "checks": checks}

    def compose(self, ctx):
        score, signals = self.score(ctx)
        verdict = map_score_to_verdict(
            score, self.high, self.mid,
            "CLEAN SETTLEMENT", "ACCEPTABLE", "LEAKAGE DETECTED")
        settlements = (ctx.get("settlements") or
                       {"settlements": []}).get("settlements", [])
        citations = []
        if any(s["settlement_vs_reserve_ratio"] > 1.4 for s in settlements):
            citations.append({
                "signal_id": "reserve_adequacy",
                "name": "Reserve adequacy (low reserve)",
                "weight": 0.65,
                "evidence": f"{ctx.get('leak_pct', 0):.0%} leakage, "
                            "ratio > 1.4", "source": "warehouse"})
        if any(s["days_to_settle"] > 180 for s in settlements):
            citations.append({
                "signal_id": "settlement_slowness",
                "name": "Settlement slowness",
                "weight": 0.45,
                "evidence": "settlements exceeding 180 days",
                "source": "warehouse"})
        if any(s.get("fnol_lag_days", 0) > 14 for s in settlements):
            citations.append({
                "signal_id": "late_fnol",
                "name": "Late FNOL",
                "weight": 0.40,
                "evidence": "claim(s) with FNOL > 14 days",
                "source": "warehouse"})
        policy = ctx.get("policy") or {}
        lines = [f"Settlement verdict for policy {policy.get('policy_id', '?')}: "
                 f"{verdict} (score {score})."]
        if settlements:
            lines.append(f"{len(settlements)} settlement(s); leakage "
                         f"{ctx.get('leak_pct', 0):.0%} of total paid.")
        elif (ctx.get("claims") or {}).get("claim_count", 0) == 0:
            lines.append("No claims — CLEAN SETTLEMENT by absence.")
        if signals:
            lines.append("Signals: " + ", ".join(signals) + ".")
        return {"decision": verdict, "score": score, "signals": signals,
                "explanation": "\n".join(lines), "citations": citations}
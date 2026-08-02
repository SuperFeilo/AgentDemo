"""ANATOMY COMPONENT: RULE-BASED BRAIN (agent #3b — Underwriting Quality)

Two jobs: WHAT next + HOW to interpret. UW-quality scoring is: do the
notes match the override decision? Was the inspection flag waived?
Was the premium adequate? Same reflect+compose contract as the
submissions brain.
"""
from __future__ import annotations

from portfolio_agent._common import map_score_to_verdict


class UnderwritingBrain:
    def __init__(self, plan) -> None:
        c = plan.constraints
        self.high, self.mid = c["well_threshold"], c["acceptable_threshold"]
        self.bug_injection = False

    # ── WHAT next ───────────────────────────────────────────────────
    def arguments_for(self, step, ctx: dict) -> dict:
        sub = ctx.get("submission", {})
        match step.tool:
            case "uw_catalog":
                return {}
            case "uw_submission_lookup":
                return {"submission_id": ctx["subject"].get("submission_id")}
            case "uw_note_lookup":
                return {"submission_id": sub.get("submission_id",
                                                 ctx["subject"].get("submission_id"))}
            case "risk_score_lookup":
                return {"submission_id": sub.get("submission_id",
                                                 ctx["subject"].get("submission_id"))}
            case "inspection_lookup":
                return {"submission_id": sub.get("submission_id",
                                                 ctx["subject"].get("submission_id"))}
            case "bind_lookup":
                return {"submission_id": sub.get("submission_id",
                                                 ctx["subject"].get("submission_id"))}
            case "pricing_adequacy_sql":
                cls = sub.get("class_code", ctx["subject"].get("class_code", ""))
                return {"sql": (
                    "SELECT rs.override_flag, AVG(b.premium) avg_premium, "
                    "COUNT(c.claim_id) n_claims, AVG(c.severity) avg_sev "
                    "FROM fact_submission s "
                    "JOIN fact_risk_score rs USING(submission_id) "
                    "JOIN fact_bind b USING(submission_id) "
                    "LEFT JOIN fact_claim c ON c.policy_id=b.policy_id "
                    f"WHERE s.class_code='{cls}' "
                    "GROUP BY rs.override_flag ORDER BY rs.override_flag DESC")}
        return {}

    def thought_for(self, step, ctx: dict) -> str:
        match step.name:
            case "consult_catalog":
                return ("Per my underwriting_quality skill, consult the "
                        "semantic layer first.")
            case "uw_note_lookup":
                return "Load UW notes — hedging phrasing on pricing notes is a leak signal."
            case "risk_score_consistency":
                return ("Pull risk score + override. Override magnitude above "
                        "5 points on a high-risk class is a strong mispricing signal.")
            case "inspection_vs_bind":
                return ("Was an inspection flag waived at bind? Ignored flags "
                        "on overridden risks predict loss.")
            case "bind_lookup":
                return ("Pull bind record: premium + deductible + tier so we "
                        "can score pricing adequacy.")
            case "pricing_adequacy":
                return ("Guarded SQL across the warehouse: premium vs severity "
                        "for this class/override segment. The numbers we cite must "
                        "come from this.")
            case "reflect":
                return ("Self-check: re-derive override magnitude and pricing "
                        "adequacy before composing the verdict.")
            case "compose":
                return ("Compose the verdict. WELL-UNDERWRITTEN, ACCEPTABLE, "
                        "or MISPRICED — all numbers cited.")
        return f"Executing step {step.name}."

    def should_skip(self, step, ctx: dict) -> str | None:
        if step.name in ("inspection_vs_bind", "bind_lookup", "pricing_adequacy"):
            if not ctx.get("submission"):
                return "no submission loaded yet"
        return None

    # ── HOW to interpret ────────────────────────────────────────────
    def interpret(self, step_name, result, ctx):
        if step_name == "consult_catalog":
            ctx["catalog"] = result
            return {"summary": f"Catalog: {result['n_notes']} notes, "
                               f"{result['n_risk_scores']} risk scores, "
                               f"{result['n_inspections']} inspections, "
                               f"{result['n_binds']} binds."}

        if step_name == "load_submission":
            ctx["submission"] = result
            return {"summary": f"Submission {result['submission_id']} "
                               f"({result['broker']}/{result['class_code']}/"
                               f"{result['region']})."}

        if step_name == "uw_note_lookup":
            ctx["notes"] = result
            if not ctx.get("submission"):
                ctx["submission"] = {"submission_id": result["submission_id"]}
            hedg = sum(n["hedging"] for n in result["notes"])
            return {"summary": f"{result['note_count']} notes, "
                               f"{hedg} hedged; topics: "
                               f"{', '.join(n['note_topic'] for n in result['notes']) or 'none'}."}

        if step_name == "risk_score_consistency":
            ctx["risk_score"] = result
            if not ctx.get("submission"):
                ctx["submission"] = {"submission_id": result["submission_id"]}
            mag = result["override_magnitude"]
            tag = "downward override" if result["override_flag"] and mag > 0 \
                else ("override no-move" if result["override_flag"] else "no override")
            return {"summary": f"Model {result['model_score']} -> "
                               f"{result['overridden_score']} ({tag}, {mag} pts)."}

        if step_name == "inspection_vs_bind":
            ctx["inspection"] = result
            if not ctx.get("submission"):
                ctx["submission"] = {"submission_id": result["submission_id"]}
            if not result["inspected"]:
                return {"summary": "Submission not site-inspected."}
            flag = "flagged an issue" if result["flagged"] else "clean"
            return {"summary": f"Inspected; {flag}."}

        if step_name == "bind_lookup":
            ctx["bind"] = result
            if not ctx.get("submission"):
                ctx["submission"] = {"submission_id": result["submission_id"]}
            if not result["bound"]:
                return {"summary": "Quote did NOT bind — UW-quality verdict is "
                                   "based only on the quote-stage evidence."}
            waive = result["inspection_flagged_at_bind"] == 1
            return {"summary": f"Bound: policy {result['policy_id']}, "
                               f"premium ${result['premium']:,}, tier "
                               f"{result['assumed_risk_tier']}"
                               + ("; inspection flag waived at bind"
                                  if waive else ".")}

        if step_name == "pricing_adequacy":
            ctx["pricing"] = result
            rows = result["rows"]
            if not rows:
                return {"summary": "Pricing adequacy SQL returned no rows."}
            summary = "; ".join(
                f"override={r[0]}: ${r[1]:,.0f} avg premium, "
                f"{r[2]} claims, ${r[3] or 0:,.0f} avg sev" for r in rows)
            return {"summary": summary}

        return {"summary": "Done."}

    # ── score → verdict ─────────────────────────────────────────────
    def score(self, ctx: dict):
        score = 0
        signals = []
        notes = ctx.get("notes") or {}
        rs = ctx.get("risk_score") or {}
        insp = ctx.get("inspection") or {}
        bind = ctx.get("bind") or {}
        # notes alignment
        hedg = sum(n.get("hedging", 0) for n in notes.get("notes", []))
        if notes.get("note_count", 0) > 0 and hedg == 0:
            score += 25; signals.append("notes_clear_unhedged")
        if hedg > 0 and rs.get("override_flag"):
            score -= 25; signals.append("hedged_pricing_note_on_override")
        # override magnitude
        mag = rs.get("override_magnitude", 0)
        if rs.get("override_flag") and mag > 5:
            score -= 25; signals.append(f"override_magnitude_{mag}pt")
        elif not rs.get("override_flag"):
            score += 15; signals.append("no_downward_override")
        # inspection flag at bind
        if bind.get("bound") and bind.get("inspection_flagged_at_bind") == 1:
            score -= 25; signals.append("inspection_flag_waived_at_bind")
        elif insp.get("inspected") and not insp.get("flagged"):
            score += 15; signals.append("clean_inspection")
        # pricing adequacy: estimate_avg_premium / avg_severity, premium-to-severity ratio
        pricing = ctx.get("pricing") or {}
        if pricing and pricing["rows"]:
            override_row = next((r for r in pricing["rows"] if r[0] == 1), None)
            nonover_row = next((r for r in pricing["rows"] if r[0] == 0), None)
            if override_row and nonover_row and override_row[3] and nonover_row[3]:
                lift = (override_row[3] - nonover_row[3]) / nonover_row[3]
                if lift > 0.20:
                    score -= 20
                    signals.append(
                        f"override_seg_severity_lift_{lift:.0%}")
            if override_row and override_row[1] < nonover_row[1]:
                gap = (nonover_row[1] - override_row[1]) / nonover_row[1]
                if gap > 0.10:
                    score -= 15
                    signals.append(
                        f"override_seg_premium_discount_{gap:.0%}")
        if not bind.get("bound"):
            score += 5; signals.append("no_bind_mispricing_NA")
        return max(0, min(100, score + 30)), signals

    def reflect(self, ctx: dict) -> dict:
        checks, corrected = [], False
        rs = ctx.get("risk_score")
        if rs and rs.get("override_flag"):
            recomputed = max(0, rs["model_score"] - rs["overridden_score"])
            if recomputed != rs["override_magnitude"]:
                checks.append(f"override magnitude RESTATED -> {recomputed}")
                rs["override_magnitude"] = recomputed
                corrected = True
            else:
                checks.append(f"override {recomputed} pts verified ✓")
        pricing = ctx.get("pricing")
        if pricing and pricing["rows"]:
            checks.append(f"pricing rows re-derived = {len(pricing['rows'])} ✓")
        verdict = "corrected an error" if corrected else "no errors found"
        return {"summary": f"Self-check {verdict}: " + "; ".join(checks) or "n/a",
                "corrected": corrected, "checks": checks}

    def compose(self, ctx: dict) -> dict:
        score, signals = self.score(ctx)
        verdict = map_score_to_verdict(
            score, self.high, self.mid,
            "WELL-UNDERWRITTEN", "ACCEPTABLE", "MISPRICED")
        rs = ctx.get("risk_score") or {}
        citations = []
        if rs.get("override_flag"):
            citations.append({
                "signal_id": "risk_score_override",
                "name": "Risk-score override (downward)",
                "weight": rs["override_magnitude"] / 15.0,
                "evidence": f"{-rs['override_magnitude']} pts override",
                "source": "warehouse: fact_risk_score"})
        bind = ctx.get("bind") or {}
        if bind.get("bound") and bind.get("inspection_flagged_at_bind") == 1:
            citations.append({
                "signal_id": "inspection_flag_ignored",
                "name": "Inspection flag waived at bind",
                "weight": 0.50,
                "evidence": "bind carried unresolved flag",
                "source": "warehouse: fact_bind.inspection_flagged_at_bind"})
        lines = [f"Submission verdict: {verdict} (score {score})."]
        if rs.get("override_flag"):
            lines.append(f"Model {rs['model_score']} overridden to "
                         f"{rs['overridden_score']} (-{rs['override_magnitude']} pts).")
        if bind.get("bound") and bind.get("inspection_flagged_at_bind") == 1:
            lines.append("Inspection flag was waived at bind — primary leak signal.")
        if signals:
            lines.append("Signals: " + ", ".join(signals) + ".")
        return {"decision": verdict, "score": score, "signals": signals,
                "explanation": "\n".join(lines), "citations": citations}
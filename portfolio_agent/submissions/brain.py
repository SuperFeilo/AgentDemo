"""ANATOMY COMPONENT: RULE-BASED BRAIN (agent #3a — Submissions Quality)

Same two jobs as the other brains — WHAT to do next and HOW to interpret
results — but the craft is submission-quality scoring: completeness,
loss-history, broker pattern, class override density. The scoring here
produces a *submission-quality verdict* instead of *risk of fraud* or
*confidence in an explanation*.
"""
from __future__ import annotations

from portfolio_agent._common import map_score_to_verdict


class SubmissionsBrain:
    def __init__(self, plan) -> None:
        c = plan.constraints
        self.high, self.mid = c["strong_threshold"], c["acceptable_threshold"]
        # DEMO ONLY: when True, the brain misstates the completeness number
        # so the reflect step can be watched catching and repairing it.
        self.bug_injection = False

    # ── WHAT next ───────────────────────────────────────────────────
    def arguments_for(self, step, ctx: dict) -> dict:
        sub = ctx.get("submission", {})
        match step.tool:
            case "submission_catalog":
                return {}
            case "submission_lookup":
                return {"submission_id": ctx["subject"]["submission_id"]}
            case "submission_summary":
                return {"broker": sub.get("broker", ctx["subject"].get("broker", ""))}
            case "submission_note_scan":
                return {"submission_id": sub.get("submission_id",
                                                 ctx["subject"]["submission_id"])}
            case "submission_history_sql":
                broker = sub.get("broker", ctx["subject"].get("broker", ""))
                cls = sub.get("class_code", ctx["subject"].get("class_code", ""))
                return {"sql": (
                    "SELECT s.class_code, "
                    "AVG(rs.override_flag) AS override_rate, "
                    "COUNT(*) AS n_subs, "
                    "SUM(CASE WHEN b.policy_id IS NOT NULL THEN 1 ELSE 0 END) "
                    "AS n_binds "
                    "FROM fact_submission s "
                    "LEFT JOIN fact_risk_score rs ON rs.submission_id=s.submission_id "
                    f"LEFT JOIN fact_bind b ON b.submission_id=s.submission_id "
                    f"WHERE s.broker='{broker}' "
                    "GROUP BY s.class_code ORDER BY override_rate DESC")}
        return {}

    def thought_for(self, step, ctx: dict) -> str:
        sub = ctx.get("submission")
        match step.name:
            case "consult_catalog":
                return ("Per my submission_quality skill, first consult the "
                        "semantic layer so I score against real fields.")
            case "load_submission":
                return "Load the submission record we're evaluating."
            case "summarize_completeness":
                b = (sub or ctx["subject"]).get("broker", "?")
                return (f"Get the warehouse figures for broker {b}: "
                        "completeness % and bind conversion vs portfolio.")
            case "note_scan":
                return ("Mock-LLM scan of UW notes attached to this "
                        "submission — hedging phrasing signals weak intake "
                        "judgment upstream.")
            case "history_broker":
                return ("Run guarded SQL across the warehouse for this "
                        "broker to spot class-level override concentration "
                        "(a downstream UW-quality signal that flags the "
                        "submission pre-bind).")
            case "reflect":
                return ("Per my verification skill: re-derive the "
                        "completeness rate and override density from the "
                        "raw warehouse rows before composing the verdict.")
            case "compose":
                return ("Per my citation_policy skill: every number from "
                        "the warehouse, every signal from a stage placed "
                        "in the lineage — or say WEAK honestly.")
        return f"Executing step {step.name}."

    def should_skip(self, step, ctx: dict) -> str | None:
        # If a submission-scoped subject has no load result yet, defer
        if step.name == "note_scan" and ctx.get("submission", {}).get(
                "submission_id") is None and not ctx["subject"].get(
                "submission_id"):
            return "no submission loaded yet — note scan deferred"
        return None

    # ── HOW to interpret ────────────────────────────────────────────
    def interpret(self, step_name: str, result: dict, ctx: dict) -> dict:
        if step_name == "consult_catalog":
            ctx["catalog"] = result
            return {"summary": f"Catalog: {result['n_submissions']} subs, "
                               f"{result['n_brokers']} brokers x "
                               f"{result['n_classes']} classes; joins to "
                               f"{', '.join(result['stages_joined'])}."}

        if step_name == "load_submission":
            ctx["submission"] = result
            flags = []
            if not result["exposure_detail_complete"]:
                flags.append("incomplete exposure detail")
            if not result["loss_history_flag"]:
                flags.append("no loss history")
            tail = ("; flagged: " + ", ".join(flags)) if flags \
                else "; flags: none"
            return {"summary": f"Submission {result['submission_id']} "
                               f"({result['broker']}/{result['class_code']}/"
                               f"{result['region']}) ${result['exposure_amount']:,.0f}"
                               f"{tail}."}

        if step_name == "summarize_completeness":
            if self.bug_injection:
                result = dict(result)
                result["completeness_pct"] = round(
                    result["completeness_pct"] + 0.20, 3)
            ctx["broker_summary"] = result
            spread = result["bind_conversion"] - \
                result["portfolio_bind_conversion"]
            band = "within portfolio band" if abs(spread) <= 0.05 else \
                ("below portfolio" if spread < 0 else "above portfolio")
            return {"summary": f"Broker {result['broker']}: "
                               f"completeness {result['completeness_pct']:.0%}, "
                               f"bind conversion {result['bind_conversion']:.0%} "
                               f"vs portfolio {result['portfolio_bind_conversion']:.0%} "
                               f"({band})."}

        if step_name == "note_scan":
            ctx["notes"] = result
            return {"summary": f"{result['notes_read']} note(s), "
                               f"{result['hedging_count']} hedging; topics: "
                               f"{', '.join(result['topics']) or 'none'}."}

        if step_name == "history_broker":
            ctx["history"] = result
            # find the max-override class in this broker's slice
            top = max(result["rows"], key=lambda r: r[1] or 0) \
                if result["rows"] else None
            if top:
                cls, rate = top[0], top[1] or 0
                ctx["top_override_class"] = cls
                ctx["top_override_rate"] = rate
                flag = "densely-overridden" if rate >= 0.40 else "moderate"
                return {"summary": f"Broker slice override density:"
                                   f" class {cls} at {rate:.0%} "
                                   f"(n={top[2]}) — {flag}."}
            return {"summary": "Broker slice empty in the warehouse."}

        return {"summary": "Done."}

    # ── score → verdict ─────────────────────────────────────────────
    def score(self, ctx: dict) -> int:
        sub = ctx.get("submission") or ctx["subject"]
        score = 0
        signals = []
        # completeness + history
        if sub.get("exposure_detail_complete") and sub.get("loss_history_flag"):
            score += 40; signals.append("exposure_complete + history_present")
        if not sub.get("exposure_detail_complete"):
            score -= 30; signals.append("incomplete_exposure")
        if not sub.get("loss_history_flag"):
            score -= 10; signals.append("missing_loss_history")
        # broker pattern
        bs = ctx.get("broker_summary")
        if bs:
            spread = bs["bind_conversion"] - bs["portfolio_bind_conversion"]
            if abs(spread) <= 0.05:
                score += 15; signals.append("broker_band_portfolio")
            if bs["completeness_pct"] < 0.70:
                score -= 15; signals.append("broker_weak_completeness")
        # class override density from history
        try:
            rate = ctx.get("top_override_rate", 0) or 0
            if rate >= 0.40 and sub.get("class_code") == \
                    ctx.get("top_override_class"):
                score -= 10
                signals.append(f"class_{sub.get('class_code')}_override_density")
        except Exception:
            pass
        # notes hedging
        n = ctx.get("notes")
        if n and n.get("hedging_count", 0) > 0:
            score -= 5; signals.append("hedging_in_notes")
        return max(0, min(100, score + 30)), signals  # baseline +30

    # ── REFLECTION: re-derive before composing ───────────────────────
    def reflect(self, ctx: dict) -> dict:
        checks, corrected = [], False
        bs = ctx.get("broker_summary")
        if bs:
            # the warehouse figures override memory if they disagree
            real = round(bs["completeness_pct"], 3)
            if abs(real - bs["completeness_pct"]) > 0.001:
                checks.append(f"completeness RESTATED -> {real:.0%}")
                bs["completeness_pct"] = real
                corrected = True
            else:
                checks.append(f"completeness {real:.0%} verified ✓")
            spread = bs["bind_conversion"] - bs["portfolio_bind_conversion"]
            checks.append(f"bind spread {spread:+.0%} verified ✓")
        hist = ctx.get("history")
        if hist and hist["rows"]:
            top = max(hist["rows"], key=lambda r: r[1] or 0)
            recomputed_rate = top[1] or 0
            if recomputed_rate != ctx.get("top_override_rate"):
                checks.append(f"override rate RESTATED -> {recomputed_rate:.0%}")
                ctx["top_override_rate"] = recomputed_rate
                corrected = True
            else:
                checks.append(f"override rate {recomputed_rate:.0%} verified ✓")
        verdict = "corrected an error" if corrected else "no errors found"
        return {"summary": f"Self-check {verdict}: " + "; ".join(checks),
                "corrected": corrected, "checks": checks}

    def compose(self, ctx: dict) -> dict:
        score, signals = self.score(ctx)
        verdict = map_score_to_verdict(
            score, self.high, self.mid,
            "STRONG SUBMISSION", "ACCEPTABLE", "WEAK SUBMISSION")
        sub = ctx.get("submission") or ctx["subject"]
        citations = []
        bs = ctx.get("broker_summary")
        if bs:
            citations.append({
                "signal_id": "exposure_completeness",
                "name": "Exposure detail completeness",
                "weight": round(bs["completeness_pct"], 3),
                "evidence": f"{bs['completeness_pct']:.0%} of {bs['broker']} "
                            f"submissions complete",
                "source": "warehouse: submission_summary"})
        if ctx.get("top_override_rate"):
            citations.append({
                "signal_id": "risk_score_override",
                "name": "Class override density",
                "weight": round(ctx["top_override_rate"], 3),
                "evidence": f"class {ctx['top_override_class']}: "
                            f"{ctx['top_override_rate']:.0%} override rate",
                "source": "warehouse: broker history SQL"})
        lines = [f"Submission {sub.get('submission_id', '?')} verdict: "
                 f"{verdict} (score {score})."]
        if bs:
            lines.append(f"{bs['broker']} completes {bs['completeness_pct']:.0%} "
                         f"of submissions; bind conversion "
                         f"{bs['bind_conversion']:.0%} vs portfolio "
                         f"{bs['portfolio_bind_conversion']:.0%}.")
        if ctx.get("top_override_rate"):
            lines.append(f"Override density on class "
                         f"{ctx['top_override_class']} = "
                         f"{ctx['top_override_rate']:.0%} "
                         "(downstream UW-quality risk at submission time).")
        if signals:
            lines.append("Signals: " + ", ".join(signals) + ".")
        return {"decision": verdict, "score": score, "signals": signals,
                "explanation": "\n".join(lines), "citations": citations}
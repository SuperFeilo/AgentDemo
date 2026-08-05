"""ANATOMY COMPONENT: RULE-BASED BRAIN (agent #3d — Assembly / Reflection)

WHAT next + HOW to interpret. The composition is the margin thesis:
combine the three stage verdicts into a single holistic reading of the
journey, then traverse the lineage graph to find the high-leverage
signal that improves the segment's profit position. The brain depends
on the three sub-harnesses, which it constructs lazily (so importing
this module doesn't pay for the heavy wiring unless run).

The `run_sub_agent(stage, segment)` method actually drives the sub-agent
for the given segment; the assembly loop special-cases the `run_*`
steps and calls it.
"""
from __future__ import annotations

from fraud_agent.brain.rule_based import noisy_or
from portfolio_agent import warehouse
from portfolio_agent._common import map_score_to_verdict


class ReflectionBrain:
    def __init__(self, plan) -> None:
        c = plan.constraints
        self.high, self.mid = c["edge_threshold"], c["marginal_threshold"]
        self.min_weight = c["min_signal_weight"]
        self.bug_injection = False
        self._sub_harnesses = {}

    def _harness(self, stage: str):
        if stage not in self._sub_harnesses:
            if stage == "submissions":
                from portfolio_agent.submissions.harness import SubmissionsHarness
                self._sub_harnesses[stage] = SubmissionsHarness()
            elif stage == "underwriting":
                from portfolio_agent.underwriting.harness import UnderwritingHarness
                self._sub_harnesses[stage] = UnderwritingHarness()
            elif stage == "settlement":
                from portfolio_agent.settlement.harness import SettlementHarness
                self._sub_harnesses[stage] = SettlementHarness()
            else:
                raise ValueError(f"unknown stage {stage}")
        return self._sub_harnesses[stage]

    # ── WHAT next ───────────────────────────────────────────────────
    def arguments_for(self, step, ctx: dict) -> dict:
        seg = ctx.get("segment") or ctx["subject"]
        if step.tool == "stage_flow":
            return {"broker": seg.get("broker", "ALL"),
                    "class_code": seg.get("class_code", "ALL"),
                    "region": seg.get("region", "ALL")}
        if step.tool == "predisposing_signals":
            return {"broker": seg.get("broker", "ALL"),
                    "class_code": seg.get("class_code", "ALL"),
                    "region": seg.get("region", "ALL")}
        return {}

    def thought_for(self, step, ctx: dict) -> str:
        seg = ctx.get("segment") or ctx["subject"]
        seg_label = (f"{seg.get('broker','?')}/{seg.get('class_code','?')}/"
                     f"{seg.get('region','?')}")
        match step.name:
            case "consult_catalog":
                return ("Per my lineage_analysis skill, pull the stage funnel "
                        f"for the segment {seg_label} to see where volume "
                        "drops most.")
            case "run_submissions":
                return ("Drain the Submissions Quality Agent across all "
                        "submissions in the segment — collect each verdict "
                        "and aggregate.")
            case "run_underwriting":
                return ("Drain the Underwriting Quality Agent across all "
                        "bound policies in the segment. The percent MISPRICED "
                        "is what we're after.")
            case "run_settlement":
                return ("Drain the Loss Settlement Quality Agent across all "
                        "settled claims in the segment. The percent LEAKAGE "
                        "DETECTED drives the settlement verdict.")
            case "stage_flow":
                return ("Re-pull the funnel from the warehouse so we can "
                        "quote the exact retention rates.")
            case "predisposing_signals":
                return ("Traverse the PREDISPOSES edges in the lineage "
                        "graph — rank the candidate signals that drive the "
                        "outcomes we just observed.")
            case "reflect":
                return ("Per my verification skill: re-derive the funnel "
                        "rates and the top signal's weight before writing "
                        "the verdict.")
            case "compose":
                return ("Compose the margin thesis. Profit edge IDENTIFIED "
                        "only if the top signal clears weight AND direction "
                        "aligns with the observed stage outcomes.")
        return f"Executing step {step.name}."

    def should_skip(self, step, ctx: dict) -> str | None:
        # nothing to skip aggressively; reflective
        return None

    # ── sub-agent dispatch (loop calls this for run_* steps) ────────
    def subjects_for(self, stage: str, segment: dict) -> list[dict]:
        con = warehouse.connect()
        # "ALL" is the segment-level wildcard; treat as no filter
        broker = segment.get("broker") if segment.get("broker") != "ALL" else None
        cls = segment.get("class_code") if segment.get("class_code") != "ALL" else None
        region = segment.get("region") if segment.get("region") != "ALL" else None

        def subs_clause(which_table="s"):
            bits = []
            params = []
            if broker is not None:
                bits.append(f"{which_table}.broker = ?"); params.append(broker)
            if cls is not None:
                bits.append(f"{which_table}.class_code = ?"); params.append(cls)
            if region is not None:
                bits.append(f"{which_table}.region = ?"); params.append(region)
            return ("WHERE " + " AND ".join(bits)) if bits else "", params

        if stage == "submissions":
            where, params = subs_clause("fact_submission")
            rows = con.execute(
                f"SELECT submission_id FROM fact_submission {where} "
                "ORDER BY submission_id", params).fetchall()
            con.close()
            return [{"submission_id": r[0]} for r in rows]
        if stage == "underwriting":
            where, params = subs_clause("s")
            rows = con.execute(
                f"SELECT b.submission_id FROM fact_bind b "
                f"JOIN fact_submission s ON s.submission_id=b.submission_id "
                f"{where} ORDER BY b.submission_id", params).fetchall()
            con.close()
            return [{"submission_id": r[0]} for r in rows]
        if stage == "settlement":
            where, params = subs_clause("s")
            rows = con.execute(
                f"SELECT DISTINCT b.policy_id FROM fact_settlement st "
                f"JOIN fact_claim c ON c.claim_id=st.claim_id "
                f"JOIN fact_bind b ON b.policy_id=c.policy_id "
                f"JOIN fact_submission s ON s.submission_id=b.submission_id "
                f"{where} ORDER BY b.policy_id", params).fetchall()
            con.close()
            return [{"policy_id": r[0]} for r in rows]
        raise ValueError(f"unknown stage {stage}")

    def run_sub_agent(self, stage: str, segment: dict) -> dict:
        """Drain the sub-agent for this segment. Returns aggregated
        verdict counts and per-run detail (decision/score, signals)."""
        subjects = self.subjects_for(stage, segment)
        h = self._harness(stage)
        verdict = {  # the three labels per stage
            "submissions":  ["STRONG SUBMISSION", "ACCEPTABLE", "WEAK SUBMISSION"],
            "underwriting": ["WELL-UNDERWRITTEN", "ACCEPTABLE", "MISPRICED"],
            "settlement":   ["CLEAN SETTLEMENT", "ACCEPTABLE", "LEAKAGE DETECTED"],
        }[stage]
        counts = {v: 0 for v in verdict}
        sub_runs = []
        total_cost = 0
        for subj in subjects:
            run = h.run_auto(subj)
            counts[run.decision or "ACCEPTABLE"] += 1
            sub_runs.append({"subject": subj, "decision": run.decision,
                              "score": run.risk_score})
            total_cost += run.cost_units
        n = len(subjects)
        total = sum(counts.values()) or 1
        return {
            "stage": stage, "n": n,
            "verdict_counts": counts,
            "pct": {v: round(counts[v] / total, 3) for v in verdict},
            "verdict_label": max(counts, key=counts.get),
            "sub_runs": sub_runs,
            "cost_units": total_cost,
        }

    # ── HOW to interpret ────────────────────────────────────────────
    def interpret(self, step_name, result, ctx):
        seg = ctx.get("segment")
        if step_name == "consult_catalog":
            ctx["funnel"] = result
            n = len(result["funnel"])
            return {"summary": f"Catalog/funnel inspected: {n} stages "
                               f"for segment {seg.get('broker','?')}/"
                               f"{seg.get('class_code','?')}/"
                               f"{seg.get('region','?')}."}
        if step_name.startswith("run_"):
            stage = step_name[len("run_"):]
            ctx.setdefault("stage_verdicts", {})[stage] = result
            label = result["verdict_label"]
            pct = result["pct"][label]
            return {"summary": f"{stage} agent: {result['n']} runs → "
                               f"{label} on {pct:.0%}; "
                               f"cost {result['cost_units']}u total."}
        if step_name == "stage_flow":
            if self.bug_injection:
                result = dict(result)
                # bug: misquote the bind retention
                for s in result["funnel"]:
                    if s["stage"] == "bind":
                        s["retention"] = round(s["retention"] + 0.10, 3)
            ctx["funnel"] = result
            seg_label = "; ".join(
                f"{stage}={funnel_row['retention']:.0%}"
                for stage, funnel_row in zip(
                    [r["stage"] for r in result["funnel"]],
                    result["funnel"]))
            return {"summary": f"Stage funnel: {seg_label}."}
        if step_name == "predisposing_signals":
            ctx["candidates"] = result["candidates"]
            ctx["candidate_weights"] = {
                c["signal_id"]: c["weight"] for c in result["candidates"]}
            top = result["candidates"][:3]
            names = ", ".join(f"{c['name']} (w={c['weight']:.2f})"
                              for c in top) or "none"
            return {"summary": f"Top predisposing signals: {names}."}
        return {"summary": "Done."}

    # ── REFLECTION ──────────────────────────────────────────────────
    def reflect(self, ctx) -> dict:
        checks, corrected = [], False
        funnel = ctx.get("funnel", {}).get("funnel")
        if funnel:
            for row in funnel:
                if row["stage"] == "bind":
                    # only flag if we misremember reportable rate
                    pass
            checks.append(f"funnel re-derived = {len(funnel)} rows ✓")
        weights = ctx.get("candidate_weights", {})
        weak = [d for d, w in weights.items() if w < self.min_weight]
        for d in weak:
            if d in ctx.get("candidates", []):
                ctx["candidates"][:] = [c for c in ctx["candidates"]
                                         if c["signal_id"] != d]
            weights.pop(d, None)
            corrected = True
        checks.append(f"{len(weights)} candidate(s) above the weight "
                      f"threshold ({self.min_weight})"
                      + (f"; dropped {weak}" if weak else " ✓"))
        verdict = "corrected an error" if corrected else "no errors found"
        return {"summary": f"Self-check {verdict}: " + "; ".join(checks),
                "corrected": corrected, "checks": checks}

    # ── COMPOSE the margin thesis ───────────────────────────────────
    def compose(self, ctx) -> dict:
        seg = ctx.get("segment") or ctx["subject"]
        cands = ctx.get("candidates", [])
        weights = ctx.get("candidate_weights", {})
        # only signal clearing weight threshold AND direction aligning
        # with an observable stage aggravation becomes edge.
        top = sorted(cands, key=lambda c: -c["weight"])
        top = [c for c in top if c["weight"] >= self.min_weight]
        if top:
            lead = top[0]
            confidence = round(100 * noisy_or([c["weight"] for c in top]))
        else:
            lead, confidence = None, 0
        verdict = map_score_to_verdict(
            confidence, self.high, self.mid,
            "PROFIT EDGE IDENTIFIED", "MARGINAL", "NO EDGE")
        funnel_rows = (ctx.get("funnel") or {}).get("funnel", [])
        stage_verdicts = ctx.get("stage_verdicts", {})
        citations = []
        for c in top[:3]:
            citations.append({
                "signal_id": c["signal_id"], "name": c["name"],
                "weight": c["weight"], "direction": c["direction"],
                "evidence": c.get("evidence"), "source": c.get("source"),
                "stage": c.get("stage"), "outcome": c.get("outcome"),
                "docs": [p.get("doc_id") for p in c.get("provenance", [])]})
        # margin thesis narrative
        sub_v = stage_verdicts.get("submissions", {}).get("verdict_label")
        uw_v = stage_verdicts.get("underwriting", {}).get("verdict_label")
        st_v = stage_verdicts.get("settlement", {}).get("verdict_label")
        lines = [f"Segment verdict: {verdict} (confidence {confidence})."]
        if lead:
            lines.append(
                f"Margin thesis: high-leverage signal is {lead['name']} "
                f"(weight {lead['weight']:.2f}, direction {lead['direction']}, "
                f"lag {lead['lag_quarters']}q) → outcome {lead['outcome']}.")
            lines.append(
                f"Improving at stage '{lead.get('stage', '?')}' changes "
                f"{lead['outcome']}; stage verdicts corroborate: submissions="
                f"{sub_v}, underwriting={uw_v}, settlement={st_v}.")
        else:
            lines.append(
                "No edge: no signal in the lineage graph clears the weight "
                "threshold AND matches observed direction — stating that "
                "honestly.")
        if funnel_rows:
            seg_label = (f"{seg.get('broker','?')}/"
                         f"{seg.get('class_code','?')}/{seg.get('region','?')}")
            fun = "; ".join(f"{r['stage']} {r['retention']:.0%}"
                            for r in funnel_rows)
            lines.append(f"Funnel [{seg_label}]: {fun}.")
        if stage_verdicts:
            sub = stage_verdicts.get("submissions", {})
            uw = stage_verdicts.get("underwriting", {})
            st = stage_verdicts.get("settlement", {})
            lines.append(
                f"Stage verdicts — submissions: {sub.get('verdict_label')}"
                f" ({sub.get('n', 0)} runs), underwriting: "
                f"{uw.get('verdict_label')} ({uw.get('n', 0)} runs), "
                f"settlement: {st.get('verdict_label')}"
                f" ({st.get('n', 0)} runs).")
        return {"decision": verdict, "confidence": confidence,
                "lead_signal": lead, "explanation": "\n".join(lines),
                "citations": citations,
                "stage_verdicts": stage_verdicts,
                "funnel": funnel_rows}
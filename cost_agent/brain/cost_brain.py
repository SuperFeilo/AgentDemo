"""ANATOMY COMPONENT: RULE-BASED BRAIN (agent #2 — analyst variant)

Same two jobs as the fraud brain — WHAT to do next and HOW to interpret
results — but the craft is analytic: quantify before explaining,
decompose averages into segments, and cite only drivers whose evidence
matches the observed trend. The scoring here produces *confidence in an
explanation* instead of *risk of fraud*.
"""
from __future__ import annotations


class CostAnalystBrain:
    def __init__(self, plan) -> None:
        self.thresholds = {
            "explained": plan.constraints["explained_threshold"],
            "partial": plan.constraints["partial_threshold"],
        }
        # DEMO ONLY: when True, the brain misstates the trend number in
        # working memory so you can watch reflection catch and repair it.
        self.bug_injection = False

    # ── WHAT next ───────────────────────────────────────────────────
    def arguments_for(self, step, ctx: dict) -> dict:
        q = ctx["question"]
        match step.tool:
            case "metric_catalog":
                return {}
            case "metric_trend":
                return {"metric": q["metric"], "region": q["region"],
                        "coverage": q["coverage"]}
            case "sql_query":
                return {"sql": (
                    "SELECT region, "
                    "ROUND(AVG(CASE WHEN quarter IN ('2023Q1','2023Q2') "
                    "THEN value END), 1) AS base, "
                    "ROUND(AVG(CASE WHEN quarter IN ('2025Q3','2025Q4') "
                    "THEN value END), 1) AS recent "
                    "FROM fact_metric "
                    f"WHERE metric='{q['metric']}' AND coverage='{q['coverage']}' "
                    "GROUP BY region ORDER BY region")}
            case "driver_tree":
                return {"metric": q["metric"], "region": q["region"],
                        "coverage": q["coverage"]}
        return {}

    def next_evidence_call(self, ctx: dict) -> str | None:
        """Evidence step iterates: one driver_event call per candidate."""
        pending = ctx.setdefault("evidence_pending", list(ctx.get("candidates", [])))
        return pending.pop(0) if pending else None

    def thought_for(self, step, ctx: dict) -> str:
        q = ctx["question"]
        match step.name:
            case "consult_catalog":
                return (f"Research question: “{q['text']}” Per my trend_reading "
                        "skill, first I consult the semantic layer so I query "
                        "real metrics, not invented ones.")
            case "read_trend":
                return ("Numbers before story: quantify the trend for "
                        f"{q['metric']} in {q['region']}/{q['coverage']} — "
                        "cumulative change, recent change, peak quarter.")
            case "decompose":
                return ("The question is national. Per my decomposition skill, "
                        "is this trend broad-based or concentrated in one "
                        "region? That tells me where to look for drivers.")
            case "find_drivers":
                return ("Now the 'why'. Per my driver_analysis skill, I "
                        "traverse the driver knowledge graph for candidates "
                        "that IMPACT this metric in this segment.")
            case "reflect":
                return ("Per my verification skill: before I write anything "
                        "down, I re-derive the headline numbers from the raw "
                        "warehouse series and re-screen every citation.")
            case "gather_evidence":
                return (f"{len(ctx.get('candidates', []))} candidate driver(s) "
                        "passed the weight/direction screen. Pulling the "
                        "citable evidence for each.")
            case "compose":
                return ("Per my citation_policy skill: every number from the "
                        "warehouse, every driver from the graph with evidence "
                        "— or say UNEXPLAINED honestly.")
        return f"Executing step {step.name}."

    def should_skip(self, step, ctx: dict) -> str | None:
        if step.name == "decompose" and ctx["question"]["region"] != "ALL":
            return "question targets a single region — no decomposition needed"
        if step.name in ("find_drivers", "gather_evidence") and ctx.get("flat"):
            return "trend is flat (|cumulative| < 5%) — nothing to explain"
        return None

    # ── HOW to interpret ────────────────────────────────────────────
    def interpret(self, step_name: str, result: dict, ctx: dict) -> dict:
        """Returns {'summary': str} shown as the observation, and mutates ctx."""
        q = ctx["question"]

        if step_name == "consult_catalog":
            metrics = ", ".join(m["id"] for m in result["metrics"])
            return {"summary": f"Catalog: metrics [{metrics}]; grain "
                               f"{result['grain']}; {len(result['regions'])} "
                               f"regions x {len(result['coverages'])} coverages."}

        if step_name == "read_trend":
            if self.bug_injection:
                result = dict(result)
                result["cumulative_pct"] = round(result["cumulative_pct"] + 6.3, 1)
            ctx["trend"] = result
            cum = result["cumulative_pct"]
            sustained = abs(cum) >= 5
            episodic = (not sustained and result["peak_dev_pct"] >= 5
                        and result["peak_quarter"] not in
                        (result["quarters"][0], result["quarters"][-1]))
            ctx["flat"] = not (sustained or episodic)
            ctx["episodic"] = episodic
            if sustained:
                ctx["trend_dir"] = "+" if cum > 0 else "-"
                shape = f"sustained {'rising' if cum > 0 else 'falling'} trend"
            elif episodic:
                ctx["trend_dir"] = "+"
                shape = "episodic spike (reverted)"
            else:
                ctx["trend_dir"] = "+"
                shape = "flat"
            return {"summary": f"{q['metric']} ({q['region']}/{q['coverage']}): "
                               f"{cum:+.1f}% cumulative, "
                               f"{result['recent4q_pct']:+.1f}% last 4 quarters, "
                               f"peak {result['peak_quarter']} "
                               f"({result['peak_dev_pct']:+.1f}% vs start) → {shape}."}

        if step_name == "decompose":
            changes = {r[0]: round(100 * (r[2] / r[1] - 1), 1) for r in result["rows"]}
            ctx["decomposition"] = changes
            spread = max(changes.values()) - min(changes.values())
            ctx["concentrated"] = spread > 6
            detail = ", ".join(f"{k} {v:+.1f}%" for k, v in changes.items())
            verdict = ("concentrated — one region dominates" if ctx["concentrated"]
                       else "broad-based — all regions move together")
            return {"summary": f"By region: {detail} → {verdict}."}

        if step_name == "find_drivers":
            trend_dir = ctx.get("trend_dir", "+")
            candidates = [d for d in result["drivers"]
                          if d["weight"] >= 0.40 and d["direction"] == trend_dir]
            ctx["candidates"] = [d["driver_id"] for d in candidates]
            ctx["candidate_weights"] = {d["driver_id"]: d["weight"] for d in candidates}
            names = ", ".join(d["name"] for d in candidates) or "none"
            return {"summary": f"{len(candidates)} candidate driver(s) pass the "
                               f"weight/direction screen: {names}."}

        if step_name == "gather_evidence":
            ctx.setdefault("evidence", {})[result["driver_id"]] = result
            return {"summary": f"{result['name']}: {result['evidence']} "
                               f"(source: {result['source']})"}

        return {"summary": "Done."}

    # ── REFLECTION (Ng's pattern): re-derive before composing ───────
    def reflect(self, ctx: dict) -> dict:
        checks, corrected = [], False
        trend = ctx.get("trend")

        # 1. number fidelity: recompute from the raw warehouse series
        if trend:
            values = trend["values"]
            recomputed_cum = round(100 * (values[-1] / values[0] - 1), 1)
            if recomputed_cum != trend["cumulative_pct"]:
                checks.append(f"cumulative RESTATED {trend['cumulative_pct']}% "
                              f"→ {recomputed_cum}% (recomputed from series)")
                trend["cumulative_pct"] = recomputed_cum
                corrected = True
            else:
                checks.append(f"cumulative {recomputed_cum}% re-derived from "
                              f"the warehouse series ✓")
            recomputed_dev = round(100 * (max(values) / values[0] - 1), 1)
            if recomputed_dev != trend["peak_dev_pct"]:
                checks.append(f"peak deviation RESTATED {trend['peak_dev_pct']}% "
                              f"→ {recomputed_dev}%")
                trend["peak_dev_pct"] = recomputed_dev
                corrected = True
            else:
                checks.append(f"peak deviation {recomputed_dev}% verified ✓")

        # 2. citation validity: re-screen candidates
        weights = ctx.get("candidate_weights", {})
        dropped = [d for d, w in weights.items() if w < 0.40]
        for d in dropped:
            weights.pop(d)
            ctx.get("candidates", []).remove(d) if d in ctx.get("candidates", []) else None
            corrected = True
        checks.append(f"{len(weights)} citation candidate(s) pass the "
                      f"weight screen" + (f"; dropped {dropped}" if dropped
                                          else " ✓"))

        verdict = "corrected an error" if corrected else "no errors found"
        return {"summary": f"Self-check {verdict}: " + "; ".join(checks),
                "corrected": corrected, "checks": checks}

    # ── compose the final answer ────────────────────────────────────
    def compose(self, ctx: dict) -> dict:
        q, trend = ctx["question"], ctx["trend"]
        weights = ctx.get("candidate_weights", {})
        evidence = ctx.get("evidence", {})

        confidence = round(100 * _noisy_or(list(weights.values()))) \
            if weights else 0
        verdict = ("EXPLAINED" if confidence >= self.thresholds["explained"]
                   else "PARTIALLY EXPLAINED" if confidence >= self.thresholds["partial"]
                   else "UNEXPLAINED")

        citations = [{"driver_id": did,
                      "name": evidence[did]["name"],
                      "weight": weights[did],
                      "evidence": evidence[did]["evidence"],
                      "source": evidence[did]["source"],
                      "docs": [p["doc_id"] for p in
                               evidence[did].get("provenance", [])]}
                     for did in evidence]

        if ctx.get("episodic"):
            lines = [f"{q['metric']} in {q['region']}/{q['coverage']} spiked "
                     f"{trend['peak_dev_pct']:+.1f}% at peak "
                     f"{trend['peak_quarter']} before reverting (net "
                     f"{trend['cumulative_pct']:+.1f}% over the full period)."]
        else:
            lines = [f"{q['metric']} in {q['region']}/{q['coverage']} moved "
                     f"{trend['cumulative_pct']:+.1f}% cumulatively "
                     f"({trend['quarters'][0]} → {trend['quarters'][-1]}, "
                     f"peak {trend['peak_quarter']})."]
        if "decomposition" in ctx:
            dec = ", ".join(f"{k} {v:+.1f}%" for k, v in ctx["decomposition"].items())
            lines.append(f"Decomposition by region: {dec}.")
        if citations:
            lines.append("Drivers: " + "; ".join(
                f"{c['name']} ({c['evidence']} — {c['source']})"
                for c in citations) + ".")
        else:
            lines.append("No driver in the knowledge graph matches this "
                         "trend — stating that honestly.")

        return {"decision": verdict, "confidence": confidence,
                "explanation": "\n".join(lines), "citations": citations,
                "numbers": {"cumulative_pct": trend["cumulative_pct"],
                            "recent4q_pct": trend["recent4q_pct"],
                            "peak_quarter": trend["peak_quarter"],
                            "peak_dev_pct": trend["peak_dev_pct"],
                            "pattern": "episodic" if ctx.get("episodic")
                                       else "sustained"}}


def _noisy_or(weights: list[float]) -> float:
    prod = 1.0
    for w in weights:
        prod *= (1 - w)
    return 1 - prod

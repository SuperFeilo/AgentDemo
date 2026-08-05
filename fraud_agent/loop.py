"""ANATOMY COMPONENT: LOOP

The agentic loop: OBSERVE -> THINK -> ACT -> OBSERVE ... until done.

It is written as a *generator*, which is what makes the system
interactive: every event (thought, tool call, observation, blackboard
write) is yielded to the harness, and the harness injects values back in
(tool results, human gate answers) with `generator.send(...)`.

The loop contains control flow only. It never executes tools itself —
it *requests* a tool call and the harness executes it. Gated tools
(SIU escalation) are just ordinary requests to the loop; the HARNESS
owns the autonomy gate and sends back either the tool result or a
`RejectedByHuman`, which the loop turns into a degraded decision.

Along the way the loop keeps the CASE BLACKBOARD up to date: every
material finding is posted with its data origin, which is what makes the
run auditable (see dossier.py).
"""
from __future__ import annotations

from fraud_agent.blackboard import (CaseBlackboard, Origin, origin_of_tool,
                                    write_event)


class ToolError(Exception):
    """Wraps any exception raised while the harness executed a tool."""


class RejectedByHuman(Exception):
    """Sent back into the loop when a human rejects a gated tool call at
    an autonomy checkpoint. The loop turns it into a degraded decision
    (e.g. ESCALATE -> REVIEW) rather than a failure."""


def _summarize(step_name: str, result: dict) -> str:
    match step_name:
        case "load_claim":
            return (f"{result['claim_type']} claim for ${result['amount']:,}; "
                    f"incident {result['incident_date']}, filed "
                    f"{result['filed_date']}; {result['note_count']} adjuster "
                    f"notes on file.")
        case "velocity_check":
            return (f"{result['priors_total']} prior claim(s) on file, "
                    f"{result['priors_in_90d']} within the last 90 days.")
        case "policy_timing":
            return (f"Policy incepted {result['inception_date']}; "
                    f"{result['days_in_force_at_loss']} days in force at loss.")
        case "network_analysis":
            return (f"{len(result['fraud_links'])} known-fraud link(s), "
                    f"{len(result['shared_attributes'])} shared attribute(s) "
                    f"in the claimant's graph neighbourhood.")
        case "notes_analysis":
            engine = f" — {result['engine']}" if result.get("engine") else ""
            tok = result.get("tokens") or {}
            tok_s = (f" · {tok.get('total_tokens', 0):,} tok"
                     if tok.get("total_tokens") else "")
            return (f"{len(result['inconsistencies'])} inconsistency(ies) and "
                    f"{result['hedging_count']} hedging phrases across "
                    f"{result['notes_read']} notes." + engine + tok_s)
    return "Done."


def _llm_rationale(claim_id: str, signals: list[str]) -> tuple[str, dict] | None:
    """Non-scoring LLM commentary on the gathered evidence. Silent no-op
    when the LLM is unavailable or the call fails — the decision itself
    is always made by the deterministic brain. Returns (text, usage)."""
    try:
        from llm_client import available, chat_text, usage
        from llm_client.config import model_id
        if not available():
            return None
        bullets = "\n".join(f"- {s}" for s in signals) or "- (no signals)"
        system = (f"You are an SIU supervisor (model {model_id()}). Write "
                  "2-3 plain sentences commenting on the evidence for this "
                  "claim: what the signals suggest and what an investigator "
                  "should look at next. Do not use JSON; be factual and "
                  "specific to the listed signals.")
        text = chat_text(system, f"Claim {claim_id}.\nSignals:\n{bullets}",
                         tag=f"narrative:{claim_id}")
        return (text[:600] or None, usage.last())
    except Exception:
        return None


def agent_loop(claim_id: str, plan, brain):
    """Drive one investigation. Yields events; receives tool results /
    gate answers back via .send()."""
    bb = CaseBlackboard()
    ctx = {"claim_id": claim_id, "risk_score": 0, "signals": [], "decision": None}

    yield {"type": "plan", "goal": plan.goal_statement,
           "steps": [{"name": s.name, "purpose": s.purpose,
                      "skill": s.skill, "tool": s.tool} for s in plan.steps]}

    for step in plan.steps:
        reason = brain.should_skip(step, ctx)
        if reason:
            yield {"type": "step_skipped", "step": step.name, "reason": reason}
            continue

        # THINK
        yield {"type": "thought", "step": step.name,
               "text": brain.thought_for(step, ctx)}

        if step.name == "reflect":
            report = brain.reflect(ctx)
            bb.write("hypotheses", "reflection", report,
                     f"self-check: {report['summary']}",
                     Origin.EPHEMERAL, step.name)
            yield write_event(bb.journal[-1])
            yield {"type": "observation", "step": step.name,
                   "summary": report["summary"], "raw": report,
                   "corrected": report["corrected"]}
            continue

        if step.name == "decide":
            ctx["decision"] = brain.decide(ctx["risk_score"])
            bb.write("decision", "verdict", ctx["decision"],
                     f"{ctx['decision']} at risk {ctx['risk_score']} "
                     f"from {len(ctx['signals'])} signal(s)",
                     Origin.EPHEMERAL, step.name)
            yield write_event(bb.journal[-1])
            event = {"type": "decision", "decision": ctx["decision"],
                     "risk_score": ctx["risk_score"],
                     "rationale": list(ctx["signals"])}
            llm_rationale = _llm_rationale(claim_id, ctx["signals"])
            if llm_rationale:
                event["llm_rationale"] = llm_rationale[0]
                if llm_rationale[1]:
                    event["llm_tokens"] = llm_rationale[1]
            yield event
            continue

        # ACT (executed by the harness; gated tools may bounce back)
        args = brain.arguments_for(step, ctx)
        result = yield {"type": "tool_call", "step": step.name,
                        "skill": step.skill, "tool": step.tool, "args": args}

        if isinstance(result, RejectedByHuman):
            ctx["decision"] = "REVIEW"
            bb.write("decision", "gate_outcome", "REJECTED",
                     "Human rejected the SIU escalation; decision degraded "
                     "to REVIEW", Origin.HUMAN, step.name)
            yield write_event(bb.journal[-1])
            yield {"type": "decision_override", "decision": "REVIEW",
                   "reason": "Human reviewer rejected the SIU escalation; "
                             "downgraded to REVIEW."}
            continue
        if isinstance(result, ToolError):
            yield {"type": "tool_error", "step": step.name, "error": str(result)}
            continue

        # OBSERVE
        origin = origin_of_tool(step.tool)

        if step.name == "load_claim":
            ctx["claim"] = result
            ctx["note_count"] = result.get("note_count", 0)
            bb.write("case", "claim", result, _summarize(step.name, result),
                     origin, step.name)
            yield write_event(bb.journal[-1])

        if step.name == "siu_escalate":
            ctx["decision"] = "ESCALATE"
            bb.write("decision", "siu_case", result,
                     f"SIU case {result['case_id']} filed", origin, step.name)
            yield write_event(bb.journal[-1])
            yield {"type": "observation", "step": step.name,
                   "summary": f"SIU case {result['case_id']} filed.",
                   "risk_points": 0, "signals": [], "score": ctx["risk_score"],
                   "raw": result}
            yield {"type": "decision_override", "decision": "ESCALATE",
                   "reason": "Human approved the escalation."}
            continue

        scored = brain.score_result(step.name, result, ctx)
        ctx["risk_score"] += scored["risk_points"]
        ctx["signals"].extend(scored["signals"])
        summary = _summarize(step.name, result)
        if scored["signals"]:
            bb.write("evidence", step.name, result,
                     summary + " " + " | ".join(scored["signals"]),
                     origin, step.name)
        else:
            bb.write("evidence", step.name, result, summary, origin, step.name)
        yield write_event(bb.journal[-1])
        yield {"type": "observation", "step": step.name,
               "summary": summary,
               "risk_points": scored["risk_points"],
               "signals": scored["signals"], "score": ctx["risk_score"],
               "raw": result}

    yield {"type": "run_finished", "decision": ctx["decision"],
           "risk_score": ctx["risk_score"]}

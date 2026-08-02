"""ANATOMY COMPONENT: LOOP (agent #3b — Underwriting Quality)

Same generator pattern as the submissions loop. Differences:
  - compose produces a UW-quality verdict + a few citations.
  - reflect re-derives override magnitude + pricing adequacy rows.
"""
from __future__ import annotations

from fraud_agent.blackboard import CaseBlackboard, Origin, write_event
from fraud_agent.loop import ToolError
from fraud_agent.tools.registry import tool_meta


def _origin_of(tool_name: str) -> Origin:
    return Origin(tool_meta(tool_name)["origin"])


def underwriting_loop(subject: dict, plan, brain):
    bb = CaseBlackboard()
    ctx = {"subject": subject}

    yield {"type": "plan", "goal": plan.goal_statement,
           "steps": [{"name": s.name, "purpose": s.purpose,
                      "skill": s.skill, "tool": s.tool} for s in plan.steps]}

    bb.write("case", "subject", subject,
             f"UW review for submission "
             f"{subject.get('submission_id', subject.get('broker', '?'))}",
             Origin.EPHEMERAL, "init")
    yield write_event(bb.journal[-1])

    for step in plan.steps:
        reason = brain.should_skip(step, ctx)
        if reason:
            yield {"type": "step_skipped", "step": step.name, "reason": reason}
            continue

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

        if step.name == "compose":
            final = brain.compose(ctx)
            ctx.update(final)
            bb.write("decision", "verdict", final["decision"],
                     f"{final['decision']} at score {final['score']} "
                     f"from {len(final['signals'])} signal(s)",
                     Origin.EPHEMERAL, step.name)
            yield write_event(bb.journal[-1])
            yield {"type": "decision", **final}
            continue

        result = yield {"type": "tool_call", "step": step.name,
                        "skill": step.skill, "tool": step.tool,
                        "args": brain.arguments_for(step, ctx)}
        if isinstance(result, ToolError):
            yield {"type": "tool_error", "step": step.name, "error": str(result)}
            continue

        obs = brain.interpret(step.name, result, ctx)
        bb.write("evidence", step.name, result, obs["summary"],
                 _origin_of(step.tool) if step.tool else Origin.EPHEMERAL,
                 step.name)
        yield write_event(bb.journal[-1])
        yield {"type": "observation", "step": step.name,
               "summary": obs["summary"], "raw": result}

    yield {"type": "run_finished",
           "decision": ctx.get("decision"),
           "confidence": ctx.get("score", 0),
           "score": ctx.get("score", 0)}
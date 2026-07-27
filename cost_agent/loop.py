"""ANATOMY COMPONENT: LOOP (agent #2 — analyst variant)

Same generator pattern as the fraud loop: THINK -> request tool call ->
OBSERVE, with the harness executing tools and injecting results via
.send(). Same case blackboard discipline too: every material finding is
posted with its data origin (persistent warehouse / knowledge graph /
ephemeral computation) so the dossier can show exactly what fed the
explanation.

Differences from the fraud loop worth studying:
  1. No gated tools — the analyst is read-only, so the autonomy gate
     never fires (the harness would handle it identically if one were
     registered as gated).
  2. The evidence step *iterates* — one tool call per candidate driver.
  3. The reflect step re-derives the headline numbers from raw tool
     results before the explanation is composed.
"""
from __future__ import annotations

from fraud_agent.blackboard import CaseBlackboard, Origin, write_event
from fraud_agent.loop import ToolError
from fraud_agent.tools.registry import tool_meta


def _origin_of(tool_name: str) -> Origin:
    return Origin(tool_meta(tool_name)["origin"])


def cost_loop(question: dict, plan, brain):
    """Investigate one research question (dict with id/metric/region/
    coverage/text). Yields events; receives tool results via .send()."""
    bb = CaseBlackboard()
    ctx = {"question": question}

    yield {"type": "plan", "goal": plan.goal_statement,
           "steps": [{"name": s.name, "purpose": s.purpose,
                      "skill": s.skill, "tool": s.tool} for s in plan.steps]}

    bb.write("case", "question", question,
             f"{question['id']}: {question['text']}",
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
                     f"{final['decision']} at confidence {final['confidence']} "
                     f"with {len(final['citations'])} citation(s)",
                     Origin.EPHEMERAL, step.name)
            yield write_event(bb.journal[-1])
            yield {"type": "decision", **final}
            continue

        if step.tool == "driver_event":
            # iterate: one call per candidate driver
            while (driver_id := brain.next_evidence_call(ctx)) is not None:
                result = yield {"type": "tool_call", "step": step.name,
                                "skill": step.skill, "tool": step.tool,
                                "args": {"driver_id": driver_id}}
                if isinstance(result, ToolError):
                    yield {"type": "tool_error", "step": step.name,
                           "error": str(result)}
                    continue
                obs = brain.interpret(step.name, result, ctx)
                bb.write("evidence", driver_id, result, obs["summary"],
                         _origin_of(step.tool), step.name)
                yield write_event(bb.journal[-1])
                yield {"type": "observation", "step": step.name,
                       "summary": obs["summary"], "raw": result}
            continue

        result = yield {"type": "tool_call", "step": step.name,
                        "skill": step.skill, "tool": step.tool,
                        "args": brain.arguments_for(step, ctx)}
        if isinstance(result, ToolError):
            yield {"type": "tool_error", "step": step.name, "error": str(result)}
            continue

        obs = brain.interpret(step.name, result, ctx)
        section = "hypotheses" if step.name == "find_drivers" else "evidence"
        bb.write(section, step.name, result, obs["summary"],
                 _origin_of(step.tool) if step.tool else Origin.EPHEMERAL,
                 step.name)
        yield write_event(bb.journal[-1])
        yield {"type": "observation", "step": step.name,
               "summary": obs["summary"], "raw": result}

    yield {"type": "run_finished",
           "decision": ctx.get("decision"),
           "confidence": ctx.get("confidence")}

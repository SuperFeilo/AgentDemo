"""ANATOMY COMPONENT: LOOP (agent #3d — Assembly / Reflection)

The assembly loop *orchestrates* three sub-harnesses over a segment,
then traverses the lineage graph to assemble a margin thesis. The
`run_*` steps are NOT tool calls — they drive sub-harnesses via
`brain.run_sub_agent(stage, segment)` and aggregate verdicts. Each
sub-agent's aggregated verdict becomes a single observation in the
assembly trace (with the per-run detail attached in the raw payload).

Everything else mirrors cost_agent/loop.py: think -> tool -> observe
with the harness executing tools, the blackboard journaling writes, and
reflect/compose producing the verdict.
"""
from __future__ import annotations

from fraud_agent.blackboard import (CaseBlackboard, Origin, origin_of_tool,
                                    write_event)
from fraud_agent.loop import ToolError


def portfolio_loop(subject: dict, plan, brain):
    """Investigate one segment (dict with broker/class_code/region).
    Yields events; receives tool results via .send()."""
    bb = CaseBlackboard()
    ctx = {"subject": subject, "segment": subject}

    yield {"type": "plan", "goal": plan.goal_statement,
           "steps": [{"name": s.name, "purpose": s.purpose,
                      "skill": s.skill, "tool": s.tool} for s in plan.steps]}

    bb.write("case", "segment", subject,
             f"segment {subject.get('broker','?')}/"
             f"{subject.get('class_code','?')}/{subject.get('region','?')}",
             Origin.EPHEMERAL, "init")
    yield write_event(bb.journal[-1])

    for step in plan.steps:
        reason = brain.should_skip(step, ctx)
        if reason:
            yield {"type": "step_skipped", "step": step.name, "reason": reason}
            continue

        yield {"type": "thought", "step": step.name,
               "text": brain.thought_for(step, ctx)}

        # ── reflect ────────────────────────────────────────────────
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

        # ── compose ─────────────────────────────────────────────────
        if step.name == "compose":
            final = brain.compose(ctx)
            ctx.update(final)
            bb.write("decision", "verdict", final["decision"],
                     f"{final['decision']} at confidence {final['confidence']}"
                     f" from {len(final.get('citations', []))} signal(s)",
                     Origin.EPHEMERAL, step.name)
            yield write_event(bb.journal[-1])
            yield {"type": "decision", **final}
            continue

        # ── orchestration: run_* steps drive sub-harnesses ─────────
        if step.name.startswith("run_"):
            stage = step.name[len("run_"):]
            agg = brain.run_sub_agent(stage, ctx["segment"])
            obs = brain.interpret(step.name, agg, ctx)
            # post to the blackboard under evidence, journaling the
            # sub-agent's aggregated verdict as a finding whose origin
            # is the sub-agent (model_brain for now — the sub-agent's
            # decisions are the empirical fact we cite from).
            bb.write("evidence", f"sub_agent_{stage}", agg,
                     obs["summary"], Origin.MODEL_BRAIN, step.name)
            yield write_event(bb.journal[-1])
            yield {"type": "observation", "step": step.name,
                   "summary": obs["summary"], "raw": agg}
            continue

        # ── normal tool call ──────────────────────────────────────
        result = yield {"type": "tool_call", "step": step.name,
                        "skill": step.skill, "tool": step.tool,
                        "args": brain.arguments_for(step, ctx)}
        if isinstance(result, ToolError):
            yield {"type": "tool_error", "step": step.name, "error": str(result)}
            continue
        obs = brain.interpret(step.name, result, ctx)
        section = "hypotheses" if step.name == "find_signals" else "evidence"
        bb.write(section, step.name, result, obs["summary"],
                 origin_of_tool(step.tool), step.name)
        yield write_event(bb.journal[-1])
        yield {"type": "observation", "step": step.name,
               "summary": obs["summary"], "raw": result}

    yield {"type": "run_finished",
           "decision": ctx.get("decision"),
           "confidence": ctx.get("confidence", 0)}
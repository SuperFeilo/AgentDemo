"""ANATOMY COMPONENT: HARNESS (with AUTONOMY GATE + COST CONTROL)

The harness is the runtime shell around an agent loop. The loop decides
*what* to do; the harness decides *whether that is still allowed*:

  - executes every tool call (single choke point: errors caught here)
  - enforces the goal's budgets: max_steps, max_tool_errors, and
    max_cost_units (COST & OPERATIONAL CONTROL)
  - meters every call: real latency (perf_counter) + declared cost units
  - AUTONOMY GATE: tools registered as autonomy="gated" pause the run
    for human approval — unless the run's autonomy level is "full".
    (Karpathy's autonomy slider: full / gated / step, set per run.)
  - records every event into the run's trace (auditability; the dossier
    is compiled from it)
  - drives the LIFECYCLE state machine (CREATED -> PLANNING -> RUNNING
    -> PAUSED -> COMPLETED / ESCALATED / FAILED)

`Harness` is agent-agnostic: it takes a plan, a brain, and a loop
function. `FraudHarness` wires the fraud trio in; the cost analyst does
the same in `cost_agent/harness.py`.
"""
from __future__ import annotations

import time

from fraud_agent.blackboard import Origin
from fraud_agent.lifecycle import Run, RunRegistry, RunState
from fraud_agent.loop import RejectedByHuman, ToolError
from fraud_agent.tools.registry import call_tool, tool_meta


class Harness:
    """Agent-agnostic runtime: plan + brain + loop function plugged in."""

    def __init__(self, plan, brain, loop_fn) -> None:
        self.plan = plan
        self.brain = brain
        self.loop_fn = loop_fn
        self.registry = RunRegistry()

    # ── interactive: a generator the UI can step through ────────────
    def start_run(self, subject, autonomy_level: str = "gated") -> Run:
        run = self.registry.create(subject if isinstance(subject, str)
                                   else subject.get("id", str(subject)))
        run.subject = subject          # claim_id str OR question dict
        run.autonomy_level = autonomy_level
        self.registry.transition(run, RunState.PLANNING)
        return run

    def drive(self, run: Run):
        self.registry.transition(run, RunState.RUNNING)
        loop = self.loop_fn(run.subject, self.plan, self.brain)
        max_steps = self.plan.constraints["max_steps"]
        max_errors = self.plan.constraints["max_tool_errors"]
        max_cost = self.plan.constraints.get("max_cost_units")
        steps = errors = 0
        send_value, started = None, False

        while True:
            try:
                event = loop.send(send_value) if started else next(loop)
                started = True
            except StopIteration:
                break
            send_value = None

            run.trace.append(event)

            if event["type"] == "tool_call":
                steps += 1
                if steps > max_steps:
                    aborted = {"type": "aborted",
                               "reason": f"step budget exceeded ({max_steps})"}
                    run.trace.append(aborted)
                    yield aborted
                    self.registry.transition(run, RunState.FAILED)
                    loop.close()
                    return

                meta = tool_meta(event["tool"])
                event["origin"] = meta["origin"]
                event["cost_units"] = meta["cost_units"]

                # ── AUTONOMY GATE ───────────────────────────────────
                if meta["autonomy"] == "gated" and \
                        run.autonomy_level != "full":
                    checkpoint = {
                        "type": "checkpoint", "kind": "autonomy_gate",
                        "step": event["step"],
                        "prompt": f"Gated action '{event['tool']}' requested "
                                  f"with {event['args']}. Approve execution?",
                    }
                    run.trace.append(checkpoint)
                    run.checkpoint = checkpoint
                    self.registry.transition(run, RunState.PAUSED)
                    approval = yield checkpoint      # wait for the human
                    run.checkpoint = None
                    self.registry.transition(run, RunState.RUNNING)
                    answer = {"type": "blackboard_write", "section": "decision",
                              "key": f"human_gate_{event['step']}",
                              "summary": f"Human {'approved' if approval else 'REJECTED'} "
                                         f"gated tool {event['tool']}",
                              "origin": Origin.HUMAN.value,
                              "step": event["step"]}
                    run.trace.append(answer)
                    yield answer
                    if not approval:
                        send_value = RejectedByHuman(
                            f"gated tool {event['tool']} rejected by human")
                        continue

                # ── EXECUTE (metered) ───────────────────────────────
                started_at = time.perf_counter()
                try:
                    send_value = call_tool(event["tool"], **event["args"])
                except Exception as exc:  # tool failed — harness absorbs it
                    errors += 1
                    send_value = ToolError(str(exc))
                    if errors > max_errors:
                        aborted = {"type": "aborted",
                                   "reason": f"too many tool errors ({errors})"}
                        run.trace.append(aborted)
                        yield aborted
                        self.registry.transition(run, RunState.FAILED)
                        loop.close()
                        return
                event["latency_ms"] = round(
                    (time.perf_counter() - started_at) * 1000, 1)

                # ── COST BUDGET ─────────────────────────────────────
                run.cost_units += meta["cost_units"]
                if max_cost is not None and run.cost_units > max_cost:
                    aborted = {"type": "aborted",
                               "reason": f"cost budget exceeded "
                                         f"({run.cost_units}/{max_cost} units)"}
                    run.trace.append(aborted)
                    yield aborted
                    self.registry.transition(run, RunState.FAILED)
                    loop.close()
                    return

            elif event["type"] == "checkpoint":
                # loop-initiated checkpoint (e.g. GraphRAG curation)
                run.checkpoint = event
                self.registry.transition(run, RunState.PAUSED)
                approval = yield event
                run.checkpoint = None
                self.registry.transition(run, RunState.RUNNING)
                send_value = bool(approval)
                continue

            elif event["type"] == "decision":
                run.decision = event["decision"]
                run.risk_score = event.get("risk_score",
                                           event.get("confidence", 0))
            elif event["type"] == "decision_override":
                run.decision = event["decision"]
            elif event["type"] == "run_finished":
                run.risk_score = event.get("risk_score",
                                           event.get("confidence",
                                                     run.risk_score))
                final = RunState.ESCALATED if run.decision == "ESCALATE" \
                    else RunState.COMPLETED
                self.registry.transition(run, final)

            yield event

    # ── headless: drain the generator (evals, tests) ────────────────
    def run_auto(self, subject, auto_approve: bool = True,
                 autonomy_level: str = "gated") -> Run:
        run = self.start_run(subject, autonomy_level=autonomy_level)
        driver = self.drive(run)
        send_value, started = None, False
        while True:
            try:
                event = driver.send(send_value) if started else next(driver)
                started = True
            except StopIteration:
                break
            send_value = auto_approve if event["type"] == "checkpoint" else None
        return run


class FraudHarness(Harness):
    """The fraud investigator wired into the shared harness."""

    def __init__(self) -> None:
        import fraud_agent.tools.claims_tools  # noqa: F401 — registers tools
        from fraud_agent.brain.rule_based import RuleBasedBrain
        from fraud_agent.loop import agent_loop
        from fraud_agent.planner import build_plan

        plan = build_plan()
        super().__init__(plan, RuleBasedBrain(plan), agent_loop)

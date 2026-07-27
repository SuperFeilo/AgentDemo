"""ANATOMY COMPONENT: LIFECYCLE MANAGEMENT

An agent run is not a function call — it is a *lifecycle*: it is created,
it plans, it runs, it may PAUSE to wait for a human, and it terminates
in a well-defined end state. The RunRegistry tracks every run and every
state transition, which is what makes pausing/resuming (human-in-the-loop)
and post-hoc audit possible.

State machine:

    CREATED -> PLANNING -> RUNNING -> PAUSED (human checkpoint) -> RUNNING
                        -> RUNNING -> COMPLETED | ESCALATED | FAILED
"""
from __future__ import annotations

import itertools
import time
from dataclasses import dataclass, field
from enum import Enum


class RunState(str, Enum):
    CREATED = "CREATED"
    PLANNING = "PLANNING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"          # waiting on a human checkpoint
    COMPLETED = "COMPLETED"    # ended with APPROVE or REVIEW
    ESCALATED = "ESCALATED"    # ended with an approved SIU escalation
    FAILED = "FAILED"          # harness aborted (budget/errors)


@dataclass
class Run:
    run_id: str
    claim_id: str
    state: RunState = RunState.CREATED
    risk_score: int = 0
    decision: str | None = None
    trace: list[dict] = field(default_factory=list)
    history: list[tuple[str, float]] = field(default_factory=list)
    checkpoint: dict | None = None  # pending human checkpoint, if any
    autonomy_level: str = "gated"   # full | gated | step (Karpathy's slider)
    cost_units: int = 0             # metered by the harness per tool call
    subject: object = None          # claim_id str OR question dict


class RunRegistry:
    """In-memory registry of all runs (a real system persists this)."""

    def __init__(self) -> None:
        self._runs: dict[str, Run] = {}
        self._counter = itertools.count(1)

    def create(self, claim_id: str) -> Run:
        run = Run(run_id=f"run-{next(self._counter):03d}", claim_id=claim_id)
        self._runs[run.run_id] = run
        self.transition(run, RunState.CREATED)
        return run

    def get(self, run_id: str) -> Run:
        return self._runs[run_id]

    def all(self) -> list[Run]:
        return list(self._runs.values())

    @staticmethod
    def transition(run: Run, state: RunState) -> None:
        run.state = state
        run.history.append((state.value, time.time()))

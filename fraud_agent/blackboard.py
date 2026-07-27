"""ANATOMY COMPONENT: CASE BLACKBOARD

The blackboard is the case's shared working memory: a typed, inspectable
space where the brain posts intermediate findings and the tools' outputs
are organised by *origin* — persistent database, knowledge graph, model
brain, human input, or ephemeral computation. This is what Karpathy
calls "context engineering" made concrete: the context isn't a pile of
chat messages, it's a structured case file with sections.

Every write is journaled (who wrote what, from which origin, at which
step), and the journal becomes part of the run trace — which is what
makes the Determination Dossier possible (see dossier.py).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum


class Origin(str, Enum):
    PERSISTENT_DB = "persistent_db"      # claims DB, policies, warehouse
    KNOWLEDGE_GRAPH = "knowledge_graph"  # entity graph, driver tree
    MODEL_BRAIN = "model_brain"          # mock-LLM outputs (notes, extraction)
    HUMAN = "human"                      # checkpoint answers, curation
    SIDE_EFFECT = "side_effect"          # actions on the world (SIU filing)
    EPHEMERAL = "ephemeral"              # computed working state (scores, flags)


SECTIONS = ("case", "evidence", "hypotheses", "decision")


@dataclass
class Write:
    section: str
    key: str
    value_summary: str          # human-readable, for the trace/dossier
    origin: Origin
    step: str
    timestamp: float = field(default_factory=time.time)


class CaseBlackboard:
    def __init__(self) -> None:
        self._sections: dict[str, dict[str, object]] = {s: {} for s in SECTIONS}
        self.journal: list[Write] = []

    def write(self, section: str, key: str, value, summary: str,
              origin: Origin, step: str) -> None:
        assert section in SECTIONS, f"unknown blackboard section {section}"
        self._sections[section][key] = value
        self.journal.append(Write(section, key, summary, origin, step))

    def read(self, section: str, key: str, default=None):
        return self._sections[section].get(key, default)

    def section(self, section: str) -> dict:
        return dict(self._sections[section])

    def journal_events(self) -> list[dict]:
        """Trace-ready view of every write, in order."""
        return [write_event(w) for w in self.journal]


def write_event(w: Write) -> dict:
    """Convert one Write into a trace event (loops yield these inline so
    the trace preserves exact ordering with thoughts/tool calls)."""
    return {"type": "blackboard_write", "section": w.section,
            "key": w.key, "summary": w.value_summary,
            "origin": w.origin.value, "step": w.step}

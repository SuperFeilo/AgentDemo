"""ANATOMY COMPONENT: TRACING (always-on run ledger)

Every finished run is appended to `data/traces/<date>.jsonl` — one
readable line per run: agent, run id, subject, final state, decision,
cost units and per-tool latency. Append-only, like waku-agent's usage
ledger: demo resets never wipe history, and the sidebar's spend ledger
is compiled from it.
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

from fraud_agent.paths import DATA_DIR

TRACES_DIR = DATA_DIR / "traces"


def record_run(run, agent: str) -> None:
    """Append one run record. Never raises — tracing must not break runs."""
    try:
        TRACES_DIR.mkdir(exist_ok=True)
        date = datetime.now().strftime("%Y-%m-%d")
        tools = []
        for e in getattr(run, "trace", []):
            if e["type"] == "tool_call":
                tools.append({"tool": e.get("tool"), "step": e.get("step"),
                              "cost_units": e.get("cost_units"),
                              "latency_ms": e.get("latency_ms")})
        rec = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "agent": agent,
            "run_id": run.run_id,
            "subject": str(getattr(run, "subject", "?")),
            "state": getattr(run.state, "value", str(getattr(run, "state", "?"))),
            "decision": getattr(run, "decision", None),
            "score": getattr(run, "risk_score", None),
            "cost_units": getattr(run, "cost_units", 0),
            "tool_calls": tools,
            "n_events": len(getattr(run, "trace", [])),
        }
        with (TRACES_DIR / f"{date}.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
    except Exception:
        pass


def load_records(agent: str | None = None) -> list[dict]:
    """All recorded runs across trace files (newest first)."""
    if not TRACES_DIR.exists():
        return []
    rows = []
    for f in sorted(TRACES_DIR.glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    if agent:
        rows = [r for r in rows if r.get("agent") == agent]
    rows.sort(key=lambda r: r.get("ts", ""), reverse=True)
    return rows


def ledger_summary() -> dict[str, dict]:
    """Per-agent totals for the sidebar spend ledger."""
    out: dict[str, dict] = {}
    for r in load_records():
        a = r.get("agent", "?")
        s = out.setdefault(a, {"runs": 0, "cost_units": 0, "latency_ms": 0,
                               "decisions": []})
        s["runs"] += 1
        s["cost_units"] += r.get("cost_units", 0)
        lat = [t.get("latency_ms") or 0 for t in r.get("tool_calls", [])]
        s["latency_ms"] += sum(lat)
        if r.get("decision"):
            s["decisions"].append(r["decision"])
    return out

"""render_boot — pristine cold starts on Render.

Render's free tier has an ephemeral filesystem: runtime state written
during a session (learning toggles, written knowledge, evidence and
eval ledgers, traces, curation approvals) is lost on spin-down anyway,
so we make that deliberate — every boot wipes runtime state and the
demo starts clean. Pure file operations: no git required at runtime.
Warehouses regenerate idempotently on first use (ensure_built).
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fraud_agent.paths import DATA_DIR

cleared = []

traces = DATA_DIR / "traces"
if traces.exists():
    shutil.rmtree(traces)
    cleared.append("data/traces/")

for f in list(DATA_DIR.glob("knowledge_toggles_*.json")) + \
        list(DATA_DIR.glob("*_approval.json")) + \
        list(DATA_DIR.glob("graph_approval.json")) + \
        [DATA_DIR / "learning_evidence.jsonl",
         DATA_DIR / "eval_history.jsonl"]:
    if f.exists():
        f.unlink()
        cleared.append(str(f.relative_to(DATA_DIR.parent)))

if cleared:
    print("render_boot: reset runtime state ->", ", ".join(cleared))
else:
    print("render_boot: runtime state already clean")

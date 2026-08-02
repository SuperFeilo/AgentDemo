"""demo_reset — return the demo to a pristine, recordable state.

The waku-agent "demo_seed" analogue: the Learning tab and GraphRAG
curation mutate files under data/ and config/, so before recording a
demo you want everything back to its committed defaults.

What it does:
  1. backs up data/ -> data/backup_<timestamp>/
  2. restores tracked files under data/ and config/ from git
  3. regenerates the two SQLite warehouses (deterministic)
  4. clears the always-on run ledger (data/traces/)

Usage:
    python scripts/demo_reset.py --yes
"""
from __future__ import annotations

import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fraud_agent.paths import DATA_DIR, ROOT

if "--yes" not in sys.argv:
    print("demo_reset: this restores data/ and config/ to git defaults and")
    print("clears data/traces/. Re-run with --yes to confirm.")
    sys.exit(1)

backup = DATA_DIR / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
shutil.copytree(DATA_DIR, backup, ignore=shutil.ignore_patterns("traces"))
print(f"backed up data/ -> {backup.relative_to(ROOT)}")

import subprocess  # noqa: E402

for folder in ("data", "config"):
    r = subprocess.run(["git", "checkout", "--", folder],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  git checkout -- {folder}: {r.stderr.strip() or 'no tracked changes'}")
    else:
        print(f"  restored tracked files in {folder}/")

from cost_agent import warehouse as cost_wh          # noqa: E402
from portfolio_agent import warehouse as port_wh     # noqa: E402

for wh in (cost_wh, port_wh):                        # force a fresh build
    wh.DB_PATH.unlink(missing_ok=True)
print(f"  regenerated {cost_wh.ensure_built().relative_to(ROOT)}")
print(f"  regenerated {port_wh.ensure_built().relative_to(ROOT)}")

traces = DATA_DIR / "traces"
if traces.exists():
    shutil.rmtree(traces)
    print(f"  cleared {traces.relative_to(ROOT)}/ (run ledger)")

for f in list(DATA_DIR.glob("knowledge_toggles_*.json")) + \
        [DATA_DIR / "learning_evidence.jsonl",
         DATA_DIR / "eval_history.jsonl"]:
    if f.exists():
        f.unlink()
        print(f"  cleared {f.relative_to(ROOT)} (learning/eval state)")

print("\nClean slate ready: weights, approvals, outcomes, warehouses and")
print("knowledge graphs are back to the committed demo defaults.")

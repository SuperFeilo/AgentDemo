"""End-to-end regression — the release gate, headless.

Delegates to fraud_agent/eval/regression.py (the Eval Lab tab renders
the same checks inline). A bug found live gets locked here so it can
never come back.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from fraud_agent.eval.regression import run_bug_sweep, run_regression

all_ok = True
for agent in ("fraud", "cost"):
    rep = run_regression(agent)
    print(f"== Release gate: {agent} ({rep['passed']}/{rep['total']}) ==")
    for c in rep["checks"]:
        tag = "🐛" if c["bug_context"] else "  "
        print(f"  [{'PASS' if c['passed'] else 'FAIL'}] {tag} {c['name']}"
              f" {c['detail']}")
    all_ok &= rep["passed"] == rep["total"]

    sweep = run_bug_sweep(agent)
    print(f"== Bug sweep: {agent} — reflection catches every planted bug "
          f"({sweep['passed']}/{sweep['total']}) ==")
    for c in sweep["checks"]:
        print(f"  [{'PASS' if c['passed'] else 'FAIL'}] {c['name']} {c['detail']}")
    all_ok &= sweep["passed"] == sweep["total"]

print(f"\n{'ALL REGRESSION CHECKS PASSED' if all_ok else 'SOME CHECKS FAILED'}")
sys.exit(0 if all_ok else 1)

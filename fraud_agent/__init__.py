"""FraudAgent — a didactic fraud-investigation agent.

Every subpackage maps 1:1 to an agent-anatomy component:

    paths.py      — project layout
    lifecycle.py  — LIFECYCLE MANAGEMENT (run states, registry, checkpoints)
    planner.py    — PLAN (goal -> ordered investigation steps)
    loop.py       — LOOP (observe -> think -> act, generator based)
    harness.py    — HARNESS (budgets, error handling, event trace around the loop)
    brain/        — the decision makers (rule-based + mock-LLM)
    tools/        — TOOL CALLS (registry + implementations)
    knowledge/    — GRAPH KNOWLEDGE (entity graph for fraud rings)
    eval/         — EVAL (labeled dataset, batch runner, metrics)
"""

__version__ = "0.1.0"

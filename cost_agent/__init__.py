"""Cost Trend Analyst — agent #2 on the same skeleton as FraudAgent.

Same anatomy (goal, plan, skills, loop, tools, harness, lifecycle,
knowledge graph, eval), different craft:

    warehouse.py  — a tiny SQLite "internal data warehouse" (synthetic)
    tools/        — metric_catalog, metric_trend, sql_query (guarded),
                    driver_tree, driver_event
    brain/        — rule-based analyst brain (quantify -> decompose ->
                    find drivers -> cite honestly)
    loop.py       — the same generator pattern as the fraud loop
    eval/         — citation precision/recall + numeric accuracy
"""

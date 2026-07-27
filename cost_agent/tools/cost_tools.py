"""ANATOMY COMPONENT: TOOL CALLS (agent #2 — Cost Trend Analyst)

Five tools over two knowledge sources:
  - the SQLite warehouse  -> numbers (metric_trend, sql_query)
  - the driver knowledge graph -> explanations (metric_catalog,
    driver_tree, driver_event)

`sql_query` demonstrates TOOL GUARDRAILS: a text-to-SQL tool is
powerful and dangerous, so the tool itself enforces read-only,
single-statement SELECTs — the brain never has to be trusted.
"""
from __future__ import annotations

import json
import re

from fraud_agent.paths import DATA_DIR
from fraud_agent.tools.registry import tool

from cost_agent import warehouse
from cost_agent.graphrag.store import is_citable

def _graph() -> tuple[dict, list]:
    """Reload the driver graph per call — cheap, and it means
    learning-applied weight updates take effect immediately."""
    payload = json.loads((DATA_DIR / "cost_entities.json").read_text())
    nodes = {n["id"]: n for n in payload["nodes"]}
    return nodes, payload["edges"]

_BLOCKED = re.compile(r"\b(insert|update|delete|drop|alter|attach|pragma|"
                      r"create|replace|vacuum)\b", re.IGNORECASE)


@tool(
    name="metric_catalog",
    description="SEMANTIC LAYER: which metrics exist, how each is defined, "
                "and which segments (regions x coverages) are available. "
                "Consult before querying so you never invent a metric.",
    args={},
    origin="knowledge_graph", autonomy="auto", cost_units=2,
)
def metric_catalog() -> dict:
    con = warehouse.connect()
    segs = con.execute("SELECT DISTINCT region, coverage FROM fact_metric "
                       "ORDER BY region, coverage").fetchall()
    con.close()
    nodes, _ = _graph()
    return {
        "metrics": [{"id": n["id"], "definition": n["definition"],
                     "sql_hint": n["sql_hint"]}
                    for n in nodes.values() if n["type"] == "metric"],
        "regions": sorted({r for r, _ in segs}),
        "coverages": sorted({c for _, c in segs}),
        "grain": "quarterly, 2023Q1-2025Q4",
    }


@tool(
    name="metric_trend",
    description="Quarterly time series for one metric/segment from the "
                "warehouse, with cumulative % change, recent-4-quarter "
                "change, and peak quarter.",
    args={"metric": "severity|frequency|loss_ratio",
          "region": "Northeast|Midwest|South|West|ALL",
          "coverage": "auto_pd|auto_bi|home"},
    origin="persistent_db", autonomy="auto", cost_units=3,
)
def metric_trend(metric: str, region: str, coverage: str) -> dict:
    con = warehouse.connect()
    if region == "ALL":
        rows = con.execute(
            "SELECT quarter, AVG(value) FROM fact_metric "
            "WHERE metric=? AND coverage=? GROUP BY quarter ORDER BY quarter",
            (metric, coverage)).fetchall()
    else:
        rows = con.execute(
            "SELECT quarter, value FROM fact_metric "
            "WHERE metric=? AND region=? AND coverage=? ORDER BY quarter",
            (metric, region, coverage)).fetchall()
    con.close()
    if not rows:
        raise ValueError(f"No data for {metric}/{region}/{coverage}")

    quarters = [r[0] for r in rows]
    values = [round(r[1], 3) for r in rows]
    cumulative = round(100 * (values[-1] / values[0] - 1), 1)
    recent4 = round(100 * (values[-1] / values[-5] - 1), 1)
    peak_idx = values.index(max(values))
    peak_dev = round(100 * (max(values) / values[0] - 1), 1)
    return {"metric": metric, "region": region, "coverage": coverage,
            "quarters": quarters, "values": values,
            "cumulative_pct": cumulative, "recent4q_pct": recent4,
            "peak_quarter": quarters[peak_idx], "peak_dev_pct": peak_dev}


@tool(
    name="sql_query",
    description="GUARDED ad-hoc SQL against the warehouse "
                "(table: fact_metric(quarter, region, coverage, metric, "
                "value)). Read-only: a single SELECT/WITH statement.",
    args={"sql": "str"},
    origin="persistent_db", autonomy="auto", cost_units=3,
)
def sql_query(sql: str) -> dict:
    stripped = sql.strip().rstrip(";")
    if not re.match(r"^(select|with)\b", stripped, re.IGNORECASE):
        raise ValueError("guardrail: only SELECT/WITH statements allowed")
    if ";" in stripped:
        raise ValueError("guardrail: one statement at a time")
    if _BLOCKED.search(stripped):
        raise ValueError("guardrail: DDL/DML keywords are blocked")
    con = warehouse.connect()
    try:
        cur = con.execute(stripped)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchmany(500)
    finally:
        con.close()
    return {"columns": cols, "rows": [list(r) for r in rows],
            "row_count": len(rows)}


@tool(
    name="driver_tree",
    description="GRAPH KNOWLEDGE: traverse the driver knowledge graph for "
                "drivers that IMPACT a metric in this segment. Returns "
                "candidate drivers with edge weight, direction and lag.",
    args={"metric": "str", "region": "str", "coverage": "str"},
    origin="knowledge_graph", autonomy="auto", cost_units=5,
)
def driver_tree(metric: str, region: str, coverage: str) -> dict:
    nodes, edges = _graph()
    drivers = []
    for e in edges:
        if e["b"] != metric or e["relation"] != "IMPACTS":
            continue
        if e["coverage"] != coverage:
            continue
        if e["region"] not in ("ALL", region):
            continue
        node = nodes[e["a"]]
        if not is_citable(e["a"], node):
            continue  # staged driver a human has not approved is not citable
        drivers.append({"driver_id": e["a"], "name": node["name"],
                        "weight": e["weight"], "direction": e["direction"],
                        "lag_quarters": e["lag_quarters"]})
    drivers.sort(key=lambda d: -d["weight"])
    return {"metric": metric, "region": region, "coverage": coverage,
            "drivers": drivers}


@tool(
    name="driver_event",
    description="Quantitative evidence behind one driver (index changes, "
                "rates, event magnitudes) plus its source label — the "
                "citable proof for the final explanation.",
    args={"driver_id": "str"},
    origin="knowledge_graph", autonomy="auto", cost_units=2,
)
def driver_event(driver_id: str) -> dict:
    nodes, _ = _graph()
    node = nodes.get(driver_id)
    if not node or node["type"] != "driver":
        raise ValueError(f"Unknown driver: {driver_id}")
    return {"driver_id": driver_id, "name": node["name"],
            "evidence": node["evidence"], "figures": node["figures"],
            "source": node["source"],
            "provenance": node.get("provenance", [])}

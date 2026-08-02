"""ANATOMY COMPONENT: TOOL CALLS (agent #3c — Loss Settlement Quality)

Tools for the settlement stage. All read from the warehouse.
`reserve_adequacy_sql` mirrors the cost agent's `sql_query` guardrails.
"""
from __future__ import annotations

import re

from fraud_agent.tools.registry import tool

from portfolio_agent import warehouse

_BLOCKED = re.compile(r"\b(insert|update|delete|drop|alter|attach|pragma|"
                      r"create|replace|vacuum)\b", re.IGNORECASE)


@tool(
    name="settlement_catalog",
    description="SEMANTIC LAYER for the settlement stage: tables & fields "
                "the agent can query.",
    args={},
    origin="knowledge_graph", autonomy="auto", cost_units=2,
)
def settlement_catalog() -> dict:
    con = warehouse.connect()
    n_pol = con.execute("SELECT COUNT(*) FROM fact_bind").fetchone()[0]
    n_claims = con.execute("SELECT COUNT(*) FROM fact_claim").fetchone()[0]
    n_sett = con.execute("SELECT COUNT(*) FROM fact_settlement").fetchone()[0]
    con.close()
    return {
        "tables": [
            {"table": "fact_bind",
             "fields": ["policy_id", "submission_id", "premium"]},
            {"table": "fact_claim",
             "fields": ["claim_id", "policy_id", "class_code",
                        "bind_quarter", "occurrence_quarter",
                        "fnol_lag_days", "severity", "reserved_amount"]},
            {"table": "fact_settlement",
             "fields": ["claim_id", "settlement_quarter",
                        "settlement_amount", "leakage_amount",
                        "settlement_vs_reserve_ratio",
                        "days_to_settle"]},
        ],
        "joins": "claim_id (claim ⇆ settlement); policy_id (claim ⇆ bind)",
        "n_policies": n_pol, "n_claims": n_claims, "n_settlements": n_sett,
    }


@tool(
    name="policy_lookup",
    description="Load a bind record by policy_id (for a settled-policy "
                "review).",
    args={"policy_id": "int"},
    origin="persistent_db", autonomy="auto", cost_units=2,
)
def policy_lookup(policy_id: int) -> dict:
    con = warehouse.connect()
    row = con.execute(
        "SELECT policy_id, submission_id, bind_quarter, premium, "
        "deductible, limit_amount, assumed_risk_tier FROM fact_bind "
        "WHERE policy_id=?", (policy_id,)).fetchone()
    con.close()
    if not row:
        raise ValueError(f"no policy {policy_id}")
    return {"policy_id": row[0], "submission_id": row[1],
            "bind_quarter": row[2], "premium": row[3],
            "deductible": row[4], "limit_amount": row[5],
            "assumed_risk_tier": row[6]}


@tool(
    name="claim_lookup",
    description="Pull all claims attached to a policy, with reserve and "
                "settlement back-reference if present.",
    args={"policy_id": "int"},
    origin="persistent_db", autonomy="auto", cost_units=2,
)
def claim_lookup(policy_id: int) -> dict:
    con = warehouse.connect()
    rows = con.execute(
        "SELECT c.claim_id, c.class_code, c.bind_quarter, "
        "c.occurrence_quarter, c.fnol_lag_days, c.severity, "
        "c.reserved_amount, COALESCE(s.settlement_amount,0) "
        "FROM fact_claim c LEFT JOIN fact_settlement s "
        "ON s.claim_id=c.claim_id WHERE c.policy_id=? ORDER BY c.claim_id",
        (policy_id,)).fetchall()
    con.close()
    return {
        "policy_id": policy_id, "claim_count": len(rows),
        "claims": [{"claim_id": r[0], "class_code": r[1],
                    "occurrence_quarter": r[3], "fnol_lag_days": r[4],
                    "severity": r[5], "reserved_amount": r[6],
                    "settlement_amount": r[7]} for r in rows],
    }


@tool(
    name="settlement_lookup",
    description="Pull all settlements attached to a policy's claims.",
    args={"policy_id": "int"},
    origin="persistent_db", autonomy="auto", cost_units=2,
)
def settlement_lookup(policy_id: int) -> dict:
    con = warehouse.connect()
    rows = con.execute(
        "SELECT s.claim_id, s.settlement_quarter, s.settlement_amount, "
        "s.leakage_amount, s.settlement_vs_reserve_ratio, "
        "s.days_to_settle, c.fnol_lag_days "
        "FROM fact_settlement s JOIN fact_claim c ON c.claim_id=s.claim_id "
        "WHERE c.policy_id=? ORDER BY s.claim_id", (policy_id,)).fetchall()
    con.close()
    return {
        "policy_id": policy_id, "settlement_count": len(rows),
        "settlements": [{"claim_id": r[0], "settlement_quarter": r[1],
                          "settlement_amount": r[2], "leakage_amount": r[3],
                          "settlement_vs_reserve_ratio": r[4],
                          "days_to_settle": r[5],
                          "fnol_lag_days": r[6]} for r in rows],
    }


@tool(
    name="reserve_adequacy_sql",
    description="GUARDED ad-hoc SQL for reserve-adequacy analysis. Tables: "
                "fact_claim (c), fact_settlement (s), fact_bind (b), "
                "fact_submission (s2). Read-only single SELECT/WITH.",
    args={"sql": "str"},
    origin="persistent_db", autonomy="auto", cost_units=3,
)
def reserve_adequacy_sql(sql: str) -> dict:
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
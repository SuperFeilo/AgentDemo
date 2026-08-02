"""ANATOMY COMPONENT: TOOL CALLS (agent #3b — Underwriting Quality)

Tools for the underwriting stage. All read from the warehouse. The
guarded `pricing_adequacy_sql` mirrors the cost agent's `sql_query`.
"""
from __future__ import annotations

import re

from fraud_agent.tools.registry import tool

from portfolio_agent import warehouse

_BLOCKED = re.compile(r"\b(insert|update|delete|drop|alter|attach|pragma|"
                      r"create|replace|vacuum)\b", re.IGNORECASE)


@tool(
    name="uw_submission_lookup",
    description="Load the submission record (broker, region, class_code, "
                "exposure flags) so the UW agent can group by segment in "
                "later tools.",
    args={"submission_id": "int"},
    origin="persistent_db", autonomy="auto", cost_units=2,
)
def uw_submission_lookup(submission_id: int) -> dict:
    con = warehouse.connect()
    row = con.execute(
        "SELECT submission_id, quote_quarter, broker, region, class_code, "
        "exposure_amount, exposure_detail_complete, loss_history_flag "
        "FROM fact_submission WHERE submission_id=?",
        (submission_id,)).fetchone()
    con.close()
    if not row:
        raise ValueError(f"no submission {submission_id}")
    return {"submission_id": row[0], "quote_quarter": row[1], "broker": row[2],
            "region": row[3], "class_code": row[4], "exposure_amount": row[5],
            "exposure_detail_complete": row[6],
            "loss_history_flag": row[7]}


@tool(
    name="uw_catalog",
    description="SEMANTIC LAYER for the UW stage: which fields exist on "
                "fact_underwriting_note, fact_risk_score, "
                "fact_site_inspection and fact_bind, and how they join.",
    args={},
    origin="knowledge_graph", autonomy="auto", cost_units=2,
)
def uw_catalog() -> dict:
    con = warehouse.connect()
    n_notes = con.execute("SELECT COUNT(*) FROM fact_underwriting_note").fetchone()[0]
    n_rs = con.execute("SELECT COUNT(*) FROM fact_risk_score").fetchone()[0]
    n_insp = con.execute("SELECT COUNT(*) FROM fact_site_inspection").fetchone()[0]
    n_bind = con.execute("SELECT COUNT(*) FROM fact_bind").fetchone()[0]
    con.close()
    return {
        "tables": [
            {"table": "fact_underwriting_note",
             "fields": ["note_id", "submission_id", "note_quarter",
                        "note_topic", "hedging_flag"]},
            {"table": "fact_risk_score",
             "fields": ["submission_id", "score_quarter", "model_score",
                        "overridden_score", "override_flag"]},
            {"table": "fact_site_inspection",
             "fields": ["inspection_id", "submission_id",
                        "inspection_quarter", "inspection_performed",
                        "inspection_flagged_issue"]},
            {"table": "fact_bind",
             "fields": ["policy_id", "submission_id", "bind_quarter",
                        "premium", "deductible", "limit_amount",
                        "assumed_risk_tier", "override_at_bind",
                        "inspection_flagged_at_bind",
                        "exposure_incomplete_at_bind"]},
        ],
        "joins": "all ON submission_id; bind -> policy",
        "n_notes": n_notes, "n_risk_scores": n_rs,
        "n_inspections": n_insp, "n_binds": n_bind,
    }


@tool(
    name="uw_note_lookup",
    description="Pull all UW notes attached to a submission. Mock-LLM "
                "interpretation provided by the brain when scoring.",
    args={"submission_id": "int"},
    origin="persistent_db", autonomy="auto", cost_units=2,
)
def uw_note_lookup(submission_id: int) -> dict:
    con = warehouse.connect()
    rows = con.execute(
        "SELECT note_id, note_topic, hedging_flag FROM fact_underwriting_note "
        "WHERE submission_id=? ORDER BY note_id",
        (submission_id,)).fetchall()
    con.close()
    return {
        "submission_id": submission_id, "note_count": len(rows),
        "notes": [{"note_id": r[0], "note_topic": r[1], "hedging": r[2]}
                  for r in rows] or [],
    }


@tool(
    name="risk_score_lookup",
    description="Risk score record for a submission: model score, "
                "overridden score, override flag and magnitude.",
    args={"submission_id": "int"},
    origin="persistent_db", autonomy="auto", cost_units=2,
)
def risk_score_lookup(submission_id: int) -> dict:
    con = warehouse.connect()
    row = con.execute(
        "SELECT submission_id, model_score, overridden_score, override_flag "
        "FROM fact_risk_score WHERE submission_id=?",
        (submission_id,)).fetchone()
    con.close()
    if not row:
        return {"submission_id": submission_id, "model_score": None,
                "overridden_score": None, "override_flag": 0,
                "override_magnitude": 0}
    mag = max(0, row[1] - row[2])
    return {"submission_id": row[0], "model_score": row[1],
            "overridden_score": row[2], "override_flag": row[3],
            "override_magnitude": mag}


@tool(
    name="inspection_lookup",
    description="Site inspection record for a submission (if any).",
    args={"submission_id": "int"},
    origin="persistent_db", autonomy="auto", cost_units=2,
)
def inspection_lookup(submission_id: int) -> dict:
    con = warehouse.connect()
    row = con.execute(
        "SELECT inspection_id, inspection_performed, inspection_flagged_issue "
        "FROM fact_site_inspection WHERE submission_id=?",
        (submission_id,)).fetchone()
    con.close()
    if not row:
        return {"submission_id": submission_id, "inspected": 0,
                "flagged": 0}
    return {"submission_id": submission_id, "inspected": row[1],
            "flagged": row[2]}


@tool(
    name="bind_lookup",
    description="Bind record joining submission_id to policy_id, with "
                "premium and risk-tier.",
    args={"submission_id": "int"},
    origin="persistent_db", autonomy="auto", cost_units=2,
)
def bind_lookup(submission_id: int) -> dict:
    con = warehouse.connect()
    row = con.execute(
        "SELECT policy_id, premium, deductible, limit_amount, "
        "assumed_risk_tier, override_at_bind, inspection_flagged_at_bind, "
        "exposure_incomplete_at_bind FROM fact_bind WHERE submission_id=?",
        (submission_id,)).fetchone()
    con.close()
    if not row:
        return {"submission_id": submission_id, "bound": False}
    return {
        "submission_id": submission_id, "bound": True, "policy_id": row[0],
        "premium": row[1], "deductible": row[2], "limit_amount": row[3],
        "assumed_risk_tier": row[4], "override_at_bind": row[5],
        "inspection_flagged_at_bind": row[6],
        "exposure_incomplete_at_bind": row[7],
    }


@tool(
    name="pricing_adequacy_sql",
    description="GUARDED ad-hoc SQL for pricing-adequacy analysis. "
                "Tables: fact_bind (b), fact_submission (s), "
                "fact_risk_score (rs), fact_claim (c), fact_settlement (st). "
                "Read-only: single SELECT/WITH statement.",
    args={"sql": "str"},
    origin="persistent_db", autonomy="auto", cost_units=3,
)
def pricing_adequacy_sql(sql: str) -> dict:
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
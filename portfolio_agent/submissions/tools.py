"""ANATOMY COMPONENT: TOOL CALLS (agent #3a — Submissions Quality)

Five tools for the submission stage, all reading the warehouse:
  - submission_catalog        semantic layer (catalog of submission attrs)
  - submission_lookup         one submission by id
  - submission_summary        broker-level completeness / conversion
  - submission_note_scan      mock-LLM scan of UW notes attached to the sub
  - submission_history_sql    guarded read-only SQL over the warehouse

`submission_history_sql` mirrors the cost agent's `sql_query` guardrails:
read-only, single SELECT/WITH, blocked-DDL/DML keywords.
"""
from __future__ import annotations

import re

from fraud_agent.tools.registry import tool

from portfolio_agent import warehouse

_BLOCKED = re.compile(r"\b(insert|update|delete|drop|alter|attach|pragma|"
                       r"create|replace|vacuum)\b", re.IGNORECASE)


@tool(
    name="submission_catalog",
    description="SEMANTIC LAYER for the submission stage: which submission "
                "fields exist, which brokers/classes/regions are populated, "
                "and which downstream stages each joins to.",
    args={},
    origin="knowledge_graph", autonomy="auto", cost_units=2,
)
def submission_catalog() -> dict:
    con = warehouse.connect()
    subs = con.execute("SELECT COUNT(*), COUNT(DISTINCT broker), "
                       "COUNT(DISTINCT class_code) FROM fact_submission"
                       ).fetchone()
    brokers = [r[0] for r in con.execute(
        "SELECT DISTINCT broker FROM fact_submission ORDER BY broker")]
    classes = [r[0] for r in con.execute(
        "SELECT DISTINCT class_code FROM fact_submission ORDER BY class_code")]
    regions = [r[0] for r in con.execute(
        "SELECT DISTINCT region FROM fact_submission ORDER BY region")]
    con.close()
    return {
        "stages_joined": ["fact_underwriting_note", "fact_risk_score",
                           "fact_site_inspection", "fact_bind"],
        "fields": ["submission_id", "quote_quarter", "broker", "region",
                   "class_code", "exposure_amount",
                   "exposure_detail_complete", "loss_history_flag"],
        "n_submissions": subs[0], "n_brokers": subs[1],
        "n_classes": subs[2],
        "brokers": brokers, "classes": classes, "regions": regions,
    }


@tool(
    name="submission_lookup",
    description="Load a single submission record by submission_id.",
    args={"submission_id": "int"},
    origin="persistent_db", autonomy="auto", cost_units=2,
)
def submission_lookup(submission_id: int) -> dict:
    con = warehouse.connect()
    row = con.execute(
        "SELECT submission_id, quote_quarter, broker, region, class_code, "
        "exposure_amount, exposure_detail_complete, loss_history_flag "
        "FROM fact_submission WHERE submission_id=?",
        (submission_id,)).fetchone()
    con.close()
    if not row:
        raise ValueError(f"no submission {submission_id}")
    return {
        "submission_id": row[0], "quote_quarter": row[1], "broker": row[2],
        "region": row[3], "class_code": row[4], "exposure_amount": row[5],
        "exposure_detail_complete": row[6],
        "loss_history_flag": row[7],
    }


@tool(
    name="submission_summary",
    description="Broker-level completeness + bind conversion rates from "
                "the warehouse. Figures the agent quotes when scoring "
                "broker pattern.",
    args={"broker": "str"},
    origin="persistent_db", autonomy="auto", cost_units=3,
)
def submission_summary(broker: str) -> dict:
    con = warehouse.connect()
    base = con.execute(
        "SELECT AVG(exposure_detail_complete) AS pct_complete, "
        "COUNT(*) AS n_subs FROM fact_submission WHERE broker=?",
        (broker,)).fetchone()
    bound = con.execute(
        "SELECT COUNT(*) FROM fact_bind b JOIN fact_submission s "
        "ON b.submission_id=s.submission_id WHERE s.broker=?",
        (broker,)).fetchone()[0]
    portfolio_bound = con.execute(
        "SELECT 1.0*COUNT(b.policy_id)/COUNT(s.submission_id) "
        "FROM fact_submission s LEFT JOIN fact_bind b "
        "ON b.submission_id=s.submission_id").fetchone()[0]
    con.close()
    n_sub = base[1] if base and base[1] else 0
    conv = round(bound / n_sub, 3) if n_sub else 0
    return {
        "broker": broker,
        "completeness_pct": round(base[0] if base and base[0] is not None else 0, 3),
        "n_submissions": n_sub,
        "n_binds": bound,
        "bind_conversion": conv,
        "portfolio_bind_conversion": round(portfolio_bound, 3),
    }


@tool(
    name="submission_note_scan",
    description="MODEL-BASED scan of Underwriting notes attached to a "
                "submission: counts hedging phrases and topics. Real LLM "
                "when configured (capped at LLM_NOTE_SCAN_CAP per session, "
                "default 5 — later scans use the deterministic mock), "
                "deterministic mock otherwise.",
    args={"submission_id": "int"},
    origin="model_brain", autonomy="auto", cost_units=4,
)
def submission_note_scan(submission_id: int) -> dict:
    con = warehouse.connect()
    rows = con.execute(
        "SELECT note_topic, hedging_flag FROM fact_underwriting_note "
        "WHERE submission_id=?", (submission_id,)).fetchall()
    con.close()
    if not rows:
        return {"submission_id": submission_id, "notes_read": 0,
                "hedging_count": 0, "topics": []}
    try:
        from llm_client import LLMCallError, available, chat_json, usage
        if available() and _note_scans_used() < _note_scan_cap():
            _NOTE_SCANS["used"] += 1
            topics_in = [r[0] for r in rows]
            hedged_in = sum(r[1] for r in rows)
            system = ("You are an underwriting QA reviewer (model "
                      "deepseek). From the list of underwriting note topics "
                      "and how many are flagged as hedged, return ONLY JSON: "
                      '{"hedging_count": int, "topics": [str]} with the '
                      "hedging_count you believe from the flagged notes and "
                      "the deduplicated topics.")
            raw = chat_json(system, f"Topics: {topics_in!r}\n"
                                    f"Hedged-flagged count: {hedged_in}",
                            tag=f"note_scan:{submission_id}")
            hedging = max(int(raw.get("hedging_count", 0) or 0), 0)
            return {
                "submission_id": submission_id,
                "notes_read": len(rows),
                "hedging_count": hedging,
                "topics": [str(t) for t in (raw.get("topics") or [])
                           if isinstance(t, str) and t.strip()][:20] or topics_in,
                "tokens": usage.last(),
            }
    except LLMCallError:
        pass  # fall back to the deterministic mock
    return {
        "submission_id": submission_id,
        "notes_read": len(rows),
        "hedging_count": sum(r[1] for r in rows),
        "topics": [r[0] for r in rows],
    }


# ── per-session LLM cap: a run may scan dozens of submissions; the real
#    model is only worth K calls, the rest fall back to the mock ──────
_NOTE_SCANS = {"used": 0}


def _note_scan_cap() -> int:
    import os
    return int(os.environ.get("LLM_NOTE_SCAN_CAP", "5"))


def _note_scans_used() -> int:
    return _NOTE_SCANS["used"]


@tool(
    name="submission_history_sql",
    description="GUARDED ad-hoc SQL over the warehouse for the submission "
                "stage. Tables: fact_submission(s), fact_underwriting_note, "
                "fact_risk_score, fact_site_inspection, fact_bind. "
                "Read-only: a single SELECT/WITH statement.",
    args={"sql": "str"},
    origin="persistent_db", autonomy="auto", cost_units=3,
)
def submission_history_sql(sql: str) -> dict:
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
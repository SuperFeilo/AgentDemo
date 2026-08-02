"""ANATOMY COMPONENT: TOOL CALLS (agent #3d — Assembly / Reflection)

Two tools over the lineage graph + warehouse:
  - stage_flow                 funnel between stages for a segment
  - predisposing_signals       ranked candidate signals that PREDISPOSE
                               outcomes in the segment

`stage_flow` reads the warehouse for raw counts and the lineage graph for
the canonical stages; `predisposing_signals` traverses PREDISPOSES edges
in data/portfolio_entities.json, filtered by region/class.
"""
from __future__ import annotations

import json

from fraud_agent.paths import DATA_DIR
from fraud_agent.tools.registry import tool

from portfolio_agent import warehouse
from portfolio_agent.graphrag.store import is_citable


def _graph() -> tuple[dict, list]:
    """Reload the lineage graph per call so weight updates take effect
    immediately (mirrors cost_agent's _graph)."""
    payload = json.loads((DATA_DIR / "portfolio_entities.json").read_text())
    nodes = {n["id"]: n for n in payload["nodes"]}
    return nodes, payload["edges"]


@tool(
    name="stage_flow",
    description="GRAPH KNOWLEDGE: the funnel between stages for one segment "
                "(broker/region/class). Returns stage list with retention "
                "rate from the warehouse and the canonical lineage edge "
                "label. Figures quoted in composition must come from here.",
    args={"broker": "str|ALL", "class_code": "str|ALL",
          "region": "str|ALL"},
    origin="knowledge_graph", autonomy="auto", cost_units=5,
)
def stage_flow(broker: str, class_code: str, region: str) -> dict:
    con = warehouse.connect()
    base_where = []
    params = []
    if broker != "ALL":
        base_where.append("broker=?"); params.append(broker)
    if region != "ALL":
        base_where.append("region=?"); params.append(region)
    if class_code != "ALL":
        base_where.append("class_code=?"); params.append(class_code)
    where_clause = ("WHERE " + " AND ".join(base_where)) \
        if base_where else ""

    n_subs = con.execute(
        f"SELECT COUNT(*) FROM fact_submission {where_clause}",
        params).fetchone()[0]
    n_notes = con.execute(
        f"SELECT COUNT(DISTINCT n.submission_id) "
        f"FROM fact_underwriting_note n "
        f"JOIN fact_submission s USING(submission_id) {where_clause}",
        params).fetchone()[0]
    n_rs = con.execute(
        f"SELECT COUNT(*) FROM fact_risk_score r "
        f"JOIN fact_submission s USING(submission_id) {where_clause}",
        params).fetchone()[0]
    n_insp = con.execute(
        f"SELECT COUNT(DISTINCT i.submission_id) "
        f"FROM fact_site_inspection i "
        f"JOIN fact_submission s USING(submission_id) {where_clause}",
        params).fetchone()[0]
    n_binds = con.execute(
        f"SELECT COUNT(*) FROM fact_bind b "
        f"JOIN fact_submission s USING(submission_id) {where_clause}",
        params).fetchone()[0]
    n_claims = con.execute(
        f"SELECT COUNT(DISTINCT c.claim_id) FROM fact_claim c "
        f"JOIN fact_bind b ON c.policy_id=b.policy_id "
        f"JOIN fact_submission s ON s.submission_id=b.submission_id "
        f"{where_clause}",
        params).fetchone()[0]
    n_sett = con.execute(
        f"SELECT COUNT(DISTINCT st.claim_id) FROM fact_settlement st "
        f"JOIN fact_claim c ON c.claim_id=st.claim_id "
        f"JOIN fact_bind b ON c.policy_id=b.policy_id "
        f"JOIN fact_submission s ON s.submission_id=b.submission_id "
        f"{where_clause}",
        params).fetchone()[0]
    con.close()

    def rate(num, den):
        return round(num / den, 3) if den else 0.0

    return {
        "segment": {"broker": broker, "class_code": class_code,
                    "region": region},
        "funnel": [
            {"stage": "submission",       "count": n_subs,
             "retention": 1.0},
            {"stage": "underwriting",     "count": n_notes,
             "retention": rate(n_notes, n_subs)},
            {"stage": "risk_scoring",     "count": n_rs,
             "retention": rate(n_rs, n_subs)},
            {"stage": "site_inspection",  "count": n_insp,
             "retention": rate(n_insp, n_subs)},
            {"stage": "bind",             "count": n_binds,
             "retention": rate(n_binds, n_subs)},
            {"stage": "claim",            "count": n_claims,
             "retention": rate(n_claims, n_binds)},
            {"stage": "settlement",       "count": n_sett,
             "retention": rate(n_sett, n_claims)},
        ],
    }


@tool(
    name="predisposing_signals",
    description="GRAPH KNOWLEDGE: traverse the lineage graph's PREDISPOSES "
                "edges for this segment. Returns candidate signals (with "
                "stage, weight, direction, lag, provenance) sorted by "
                "weight. Only citable (curated/approved) signals appear.",
    args={"broker": "str|ALL", "class_code": "str|ALL",
          "region": "str|ALL"},
    origin="knowledge_graph", autonomy="auto", cost_units=5,
)
def predisposing_signals(broker: str, class_code: str,
                         region: str) -> dict:
    nodes, edges = _graph()
    out_region = "ALL" if region == "ALL" else region
    out_cov = "ALL" if class_code == "ALL" else class_code
    if broker == "BRO-W" and region == "ALL":
        out_region = "West"
    candidates = []
    for e in edges:
        if e["relation"] != "PREDISPOSES":
            continue
        if e.get("region") not in ("ALL", out_region):
            continue
        if e.get("coverage") not in ("ALL", out_cov):
            continue
        node = nodes[e["a"]]
        if not is_citable(e["a"], node):
            continue  # staged candidate a human has not approved
        candidates.append({
            "signal_id": e["a"], "name": node["name"],
            "weight": e["weight"], "direction": e["direction"],
            "lag_quarters": e["lag_quarters"], "stage": node.get("stage"),
            "evidence": node.get("evidence"), "source": node.get("source"),
            "provenance": node.get("provenance", []),
            "outcome": e["b"]})
    candidates.sort(key=lambda d: -d["weight"])
    return {"segment": {"broker": broker, "class_code": class_code,
                        "region": region},
            "candidates": candidates}
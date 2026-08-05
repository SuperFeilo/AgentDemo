"""ANATOMY COMPONENT: TOOL CALLS (2/2 — the implementations)

Six tools over three data sources (claims DB, policies DB, knowledge
graph) plus one *model-based* tool backed by the mock-LLM brain and one
*side-effecting* tool (SIU escalation), which is the only tool gated by
a human checkpoint.
"""
from __future__ import annotations

import json
from datetime import date

from fraud_agent.knowledge.graph import KnowledgeGraph
from fraud_agent.paths import DATA_DIR
from fraud_agent.tools.registry import tool

# ── tiny in-memory "databases" ──────────────────────────────────────
_CLAIMS = {c["claim_id"]: c for c in json.loads((DATA_DIR / "claims.json").read_text())}
_POLICIES = {p["policy_id"]: p for p in json.loads((DATA_DIR / "policies.json").read_text())}


def _graph():
    """Knowledge graph loaded per call — learned/written knowledge is
    seen immediately (mirrors cost_agent's _graph)."""
    return KnowledgeGraph()


def _days_between(d1: str, d2: str) -> int:
    y1, m1, dd1 = map(int, d1.split("-"))
    y2, m2, dd2 = map(int, d2.split("-"))
    return (date(y2, m2, dd2) - date(y1, m1, dd1)).days


@tool(
    name="claims_db_lookup",
    description="Fetch the full claim record (type, amount, dates, description).",
    args={"claim_id": "str"},
    origin="persistent_db", autonomy="auto", cost_units=1,
)
def claims_db_lookup(claim_id: str) -> dict:
    claim = _CLAIMS.get(claim_id)
    if not claim:
        raise ValueError(f"Claim {claim_id} not found")
    record = {k: v for k, v in claim.items() if k != "adjuster_notes"}
    record["note_count"] = len(claim["adjuster_notes"])
    return record


@tool(
    name="claims_history",
    description="List prior claims filed by this claimant (velocity signal).",
    args={"claimant_id": "str"},
    origin="persistent_db", autonomy="auto", cost_units=1,
)
def claims_history(claimant_id: str) -> dict:
    claim = next((c for c in _CLAIMS.values() if c["claimant_id"] == claimant_id), None)
    priors = claim["prior_claims"] if claim else []
    recent = [p for p in priors
              if claim and 0 <= _days_between(p["filed_date"], claim["filed_date"]) <= 90]
    return {"claimant_id": claimant_id, "priors_total": len(priors),
            "priors_in_90d": len(recent), "recent_priors": recent}


@tool(
    name="policy_check",
    description="Check policy inception date against the incident date "
                "(a policy taken out days before a loss is a classic flag).",
    args={"policy_id": "str", "incident_date": "str (YYYY-MM-DD)"},
    origin="persistent_db", autonomy="auto", cost_units=1,
)
def policy_check(policy_id: str, incident_date: str) -> dict:
    policy = _POLICIES.get(policy_id)
    if not policy:
        raise ValueError(f"Policy {policy_id} not found")
    days = _days_between(policy["inception_date"], incident_date)
    return {"policy_id": policy_id, "inception_date": policy["inception_date"],
            "days_in_force_at_loss": days}


@tool(
    name="fraud_ring_network",
    description="Traverse the knowledge graph around a claimant to find "
                "shared phones/addresses/repair shops, especially any link "
                "to known-fraud entities.",
    args={"claimant_id": "str"},
    origin="knowledge_graph", autonomy="auto", cost_units=5,
)
def fraud_ring_network(claimant_id: str) -> dict:
    result = _graph().neighborhood(claimant_id, hops=2)
    try:
        from fraud_agent.graphrag import store
        approval = store.load_approval()
        if approval:
            result["graphrag_intel_approved"] = approval
        # enrich with GraphRAG layer: rings this claimant belongs to
        rings = store.get_store().run("root_cause_claimant",
                                      claimant_id=claimant_id)
        if rings.get("rings"):
            result["graphrag_intel"] = rings["rings"]
    except Exception:
        pass
    return result


@tool(
    name="fraud_graph_intel",
    description="Query GraphRAG-extracted fraud intelligence (rings, "
                "suspect shops, scam patterns). Returns only intel a human "
                "has approved. Provenance traceable to source SIU memos.",
    args={},
    origin="knowledge_graph", autonomy="auto", cost_units=8,
)
def fraud_graph_intel() -> dict:
    """Approved fraud intel from the GraphRAG store (Cypher / fallback)."""
    try:
        from fraud_agent.graphrag import store as fraud_store
        catalog = fraud_store.get_store().run("intel_catalog")
    except Exception:
        catalog = {"rings": [], "suspect_shops": [], "scam_types": []}
    return {
        **catalog,
        "note": "GraphRAG-extracted intel — only entities a human has "
                "approved. Provenance from the source memos (use the "
                "GraphRAG tab to run extraction and curate candidates).",
    }


@tool(
    name="notes_inconsistency_detector",
    description="MODEL-BASED tool: a language-model brain reads the adjuster "
                "notes and returns typed inconsistencies (date/location/injury "
                "contradictions, story revisions, hedging).",
    args={"claim_id": "str"},
    origin="model_brain", autonomy="auto", cost_units=25,
)
def notes_inconsistency_detector(claim_id: str) -> dict:
    from fraud_agent.brain.notes_llm import LLMNotesAnalyzer  # lazy: keeps import cycle out
    from fraud_agent.brain.notes_llm import MockLLMNotesAnalyzer
    from llm_client import LLMCallError, available, usage
    from llm_client.config import model_id
    claim = _CLAIMS.get(claim_id)
    if not claim:
        raise ValueError(f"Claim {claim_id} not found")
    if available():
        try:
            result = LLMNotesAnalyzer().analyze(
                claim["adjuster_notes"], tag=f"notes:{claim_id}")
            result["engine"] = f"llm:{model_id()}"
            result["tokens"] = usage.last()
            return result
        except LLMCallError:
            pass  # fall back to the deterministic mock
    result = MockLLMNotesAnalyzer().analyze(claim["adjuster_notes"])
    result["engine"] = "mock"
    return result


@tool(
    name="siu_escalate",
    description="File a case with the Special Investigations Unit. "
                "SIDE-EFFECTING: requires human approval (autonomy gate).",
    args={"claim_id": "str", "risk_score": "int", "rationale": "list[str]"},
    origin="side_effect", autonomy="gated", cost_units=10,
)
def siu_escalate(claim_id: str, risk_score: int, rationale: list[str]) -> dict:
    return {"case_id": f"SIU-{claim_id[2:]}", "claim_id": claim_id,
            "risk_score": risk_score, "status": "FILED",
            "rationale": rationale}

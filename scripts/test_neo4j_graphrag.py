"""Tests for the Neo4j GraphRAG layer — green in BOTH modes.

Verifies (in the offline fallback by default, and against a live
Neo4j when NEO4J_URI is set):
  1. the synthetic data matches its ground truth (rings, exposure,
     levers, distractors)
  2. the query library returns the expected structures
  3. extraction -> upsert -> curation changes retrieval
  4. every investigative assignment answers with the planted truth
  5. the agent-facing curation API still works

Usage:
    python scripts/test_neo4j_graphrag.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fraud_agent.paths import DATA_DIR
from graphrag_neo4j.investigator import investigate, load_ground_truth
from graphrag_neo4j.store import get_store, reset_stores


def check(name: str, cond: bool) -> None:
    print(f"  {'PASS' if cond else 'FAIL':6s} {name}")
    assert cond, f"FAILED: {name}"


def main() -> int:
    gt = load_ground_truth()
    print("== synthetic data ground truth ==")
    fraud_store = get_store("fraud")
    cost_store = get_store("cost")
    pf_store = get_store("portfolio")
    print(f"mode: fraud={fraud_store.mode} cost={cost_store.mode} "
          f"portfolio={pf_store.mode}")

    # ── fraud structure ──────────────────────────────────────────────
    stats = fraud_store.stats()
    check("fraud graph volume (>=300 nodes)",
          stats["node_count"] >= 300)
    members = fraud_store.run("ring_members", ring_id="RING-SOUTH-1")
    check("RING-SOUTH-1 has >=16 members",
          len(members.get("members", [])) >= 16)
    check("RING-SOUTH-1 exposure 687000",
          fraud_store.run("root_cause_claimant",
                          claimant_id="CL-201")["rings"][0]["exposure"]
          == 687000)
    clean = gt["fraud"]["assignments"]["distractor_clean"]["subject"]
    check("clean claimant has no fraud paths",
          fraud_store.run("paths_to_fraud", claimant_id=clean)["paths"] == [])
    check("clean claimant has no ring",
          fraud_store.run("root_cause_claimant", claimant_id=clean)["rings"]
          == [])

    # ── cost structure ───────────────────────────────────────────────
    rc = cost_store.run("root_cause", metric="frequency", region="South",
                        coverage="auto_pd")
    check("cost: hurricane triggers cat_weather",
          any(t["driver_id"] == "cat_weather" for t in rc["triggers"]))
    check("cost: winter_weather excluded from South",
          all(t["driver_id"] != "winter_weather" for t in rc["triggers"]))

    # ── portfolio structure ──────────────────────────────────────────
    for seg_key, lever in [("leverage_bro_w", "reserve_adequacy"),
                           ("leverage_5437", "risk_score_override")]:
        g = gt["portfolio"]["assignments"][seg_key]
        winner = pf_store.run("leverage", **g["segment"]).get("winner")
        check(f"portfolio {seg_key} -> {lever}",
              (winner or {}).get("signal_id") == lever)
    jt = pf_store.run("journey_trace", entity_id="CLM-015")
    check("journey CLM-015 spans 4 stages",
          len(jt["nodes"]) >= 4 and any(
              n.get("type") == "submission" for n in jt["nodes"]))

    # ── write path: extraction -> upsert -> curation ─────────────────
    print("\n== write path (extraction -> curation) ==")
    from fraud_agent.graphrag.extractor import (MockLLMFraudGraphExtractor,
                                                merge_candidates)
    memos = json.loads((DATA_DIR / "neo4j_fraud_memos.json").read_text())
    merged = merge_candidates(MockLLMFraudGraphExtractor().extract(memos))
    check("extraction finds >=18 fraud candidates", len(merged) >= 18)
    before = fraud_store.run("intel_catalog")
    fraud_store.upsert_intel(list(merged.values()), kind="fraud")
    fraud_store.set_approval("RING-WEST-1", False)
    after = fraud_store.run("intel_catalog")
    check("rejecting RING-WEST-1 removes it from retrieval",
          len(after["rings"]) == len(before["rings"]) - 1 and
          all(r["entity_id"] != "RING-WEST-1" for r in after["rings"]))
    fraud_store.set_approval("RING-WEST-1", True)

    # ── assignments vs ground truth ──────────────────────────────────
    print("\n== assignments ==")
    g = gt["fraud"]["assignments"]["root_cause_cl201"]
    rep = investigate("fraud", "fraud_root_cause", {"claimant_id": "CL-201"})
    ring = rep.steps[0]["result"]["rings"][0]
    check("CL-201 root ring matches", ring["ring_id"] == g["ring"])
    check("CL-201 exposure matches", ring["exposure"] == g["exposure"])
    check("CL-201 cited docs present",
          set(g["cited_docs"]).issubset(set(ring["cited_docs"])))

    g = gt["fraud"]["assignments"]["plan_ring_member"]
    rep = investigate("fraud", "fraud_plan_investigation",
                      {"claimant_id": g["subject"]})
    ring = rep.steps[2]["result"]["rings"][0]
    check("plan subject belongs to RING-SE-1", ring["ring_id"] == g["ring"])

    g = gt["cost"]["assignments"]["root_cause_south_frequency"]
    rep = investigate("cost", "cost_root_cause", {"segment": {
        "metric": g["metric"], "region": g["region"],
        "coverage": g["coverage"]}})
    triggers = rep.steps[0]["result"]["triggers"]
    check("cost verdict cites M-04",
          any(d["doc_id"] == "M-04" for d in rep.citations))
    check("cost primary driver = cat_weather",
          triggers and triggers[0]["driver_id"] == g["primary_driver"])

    for seg_key, key in [("leverage_bro_w", "leverage"),
                         ("leverage_5437", "leverage")]:
        g = gt["portfolio"]["assignments"][seg_key]
        rep = investigate("portfolio", "portfolio_leverage",
                          {"segment": g["segment"]})
        winner = rep.steps[0]["result"]["winner"] or {}
        check(f"portfolio {seg_key} winner", winner.get("signal_id")
              == g["lever"])

    # ── agent-facing curation API unchanged ──────────────────────────
    print("\n== agent-facing store API ==")
    from fraud_agent.graphrag import store as fraud_store_mod
    from cost_agent.graphrag import store as cost_store_mod
    from portfolio_agent.graphrag import store as pf_store_mod
    for mod, eid in [(fraud_store_mod, "RING-SOUTH-1"),
                     (cost_store_mod, "adas_complexity"),
                     (pf_store_mod, "settlement_slowness")]:
        check(f"{mod.__name__} is_citable default True",
              mod.is_citable(eid, {}) is True)
        mod.set_approval(eid, False)
        check(f"{mod.__name__} is_citable after reject",
              mod.is_citable(eid, {}) is False)
        mod.save_approval({})

    print("\nALL NEO4J GRAPHRAG TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())

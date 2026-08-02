"""NEO4J GRAPHRAG — headless end-to-end demo.

Shows the full loop:
  1. connection status (Neo4j vs offline fallback)
  2. extraction over the source memos -> staged candidates
  3. human curation (reject one entity) -> query results change
  4. four investigative assignments with the actual Cypher, results,
     and cited verdicts
  5. ground-truth check

Usage:
    python scripts/demo_neo4j_graphrag.py          # offline fallback
    NEO4J_URI=bolt://... NEO4J_USER=neo4j \
        NEO4J_PASSWORD=... python scripts/demo_neo4j_graphrag.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fraud_agent.paths import DATA_DIR
from graphrag_neo4j.investigator import OFFERINGS, investigate
from graphrag_neo4j.store import get_store

BANNER = "=" * 78
RULE = "-" * 78


def section(title: str) -> None:
    print(f"\n{BANNER}\n{title}\n{BANNER}")


def main() -> None:
    print("NEO4J GRAPHRAG — dual-mode demo\n")
    store = get_store("fraud")
    print(f"[1] connection: mode={store.mode}")
    if store.mode == "neo4j":
        from graphrag_neo4j.config import connection
        cfg = connection()
        print(f"    connected to {cfg['uri']} (db: {cfg['database']})")
    else:
        print("    no Neo4j reachable -> in-memory networkx fallback "
              "(identical query semantics; see config/neo4j.yaml)")

    section("[2] WRITE PATH — extraction over source memos")
    from fraud_agent.graphrag.extractor import (MockLLMFraudGraphExtractor,
                                                merge_candidates)
    memos = json.loads((DATA_DIR / "neo4j_fraud_memos.json").read_text())
    print(f"    {len(memos)} source memos (SIU / NICB / audit)")
    merged = merge_candidates(MockLLMFraudGraphExtractor().extract(memos))
    print(f"    mock-LLM extraction -> {len(merged)} staged candidates")
    print("    (real-LLM seam: fraud_agent/graphrag/extractor.py)")
    upsert = store.upsert_intel(list(merged.values()), kind="fraud")
    print(f"    upserted into the graph: {upsert['upserted']} entities")

    section("[3] CURATION — reject one ring, watch the graph answer change")
    before = store.run("intel_catalog")
    print(f"    citable rings before: "
          f"{len(before['rings'])} (e.g. {[r['entity_id'] for r in before['rings']][:3]}...)")
    store.set_approval("RING-WEST-1", False)
    after = store.run("intel_catalog")
    print(f"    after rejecting RING-WEST-1: "
          f"{len(after['rings'])} rings citable")
    ok = len(after["rings"]) == len(before["rings"]) - 1
    print(f"    curation affects retrieval: {ok}")
    store.set_approval("RING-WEST-1", True)
    print("    (restored)")

    section("[4] READ PATH — investigative assignments")
    domains = ["fraud", "cost", "portfolio"]
    for domain in domains:
        for offer in OFFERINGS[domain]:
            print(f"\n{RULE}")
            print(f"[{domain}] {offer['label']}")
            report = investigate(domain, offer["id"], offer["params"])
            print(f"  mode: {report.mode} | {report.title}")
            for step in report.steps:
                print(f"  cypher: {step['query']}")
                print(f"    {step['cypher'].strip().splitlines()[0].strip()}"
                      f" ...")
            print(f"  verdict: {report.verdict}")
            for finding in report.findings:
                print(f"    - {finding}")
            if report.citations:
                print(f"  cited: {[c['doc_id'] for c in report.citations]}")

    section("[5] GROUND TRUTH CHECK")
    gt = json.loads((DATA_DIR / "neo4j_ground_truth.json").read_text())
    checks = []

    rep = investigate("fraud", "fraud_root_cause",
                      {"claimant_id": "CL-201"})
    g = gt["fraud"]["assignments"]["root_cause_cl201"]
    checks.append(("fraud root cause CL-201 -> RING-SOUTH-1",
                   any(r["ring_id"] == g["ring"] for r in
                       rep.steps[0]["result"].get("rings", []))))

    rep = investigate("fraud", "fraud_plan_investigation",
                      {"claimant_id": gt["fraud"]["assignments"]["plan_ring_member"]["subject"]})
    g = gt["fraud"]["assignments"]["plan_ring_member"]
    ring = rep.steps[2]["result"].get("rings", [])
    checks.append(("fraud plan -> RING-SE-1",
                   any(r["ring_id"] == g["ring"] for r in ring)))

    rep = investigate("fraud", "fraud_plan_investigation",
                      {"claimant_id": gt["fraud"]["assignments"]["distractor_clean"]["subject"]})
    checks.append(("clean distractor has no ring",
                   not rep.steps[2]["result"].get("rings")))

    rep = investigate("cost", "cost_root_cause", {"segment": {
        "metric": "frequency", "region": "South", "coverage": "auto_pd"}})
    g = gt["cost"]["assignments"]["root_cause_south_frequency"]
    triggers = rep.steps[0]["result"].get("triggers", [])
    checks.append(("cost root cause -> hurricane/cat_weather",
                   any(t["driver_id"] == g["primary_driver"]
                       for t in triggers)))
    checks.append(("cost distractor winter_weather excluded",
                   all(t["driver_id"] != "winter_weather"
                       for t in triggers)))

    for seg_key, key in [("leverage_bro_w", "leverage"), ("leverage_5437",
                                                          "leverage")]:
        g = gt["portfolio"]["assignments"][seg_key]
        rep = investigate("portfolio", "portfolio_leverage",
                          {"segment": g["segment"]})
        winner = rep.steps[0]["result"].get("winner") or {}
        checks.append((f"portfolio {seg_key} -> {g['lever']}",
                       winner.get("signal_id") == g["lever"]))

    all_ok = True
    for name, passed in checks:
        print(f"  {'PASS' if passed else 'FAIL':6s} {name}")
        all_ok &= passed
    print(f"\n{'ALL GROUND-TRUTH CHECKS PASSED' if all_ok else 'SOME CHECKS FAILED'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())

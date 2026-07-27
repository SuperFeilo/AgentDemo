"""Smoke test: extraction, curation impact on eval, restore defaults."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cost_agent.eval.runner import run_eval
from cost_agent.graphrag import store
from cost_agent.graphrag.extractor import MockLLMGraphExtractor, merge_candidates
from fraud_agent.paths import DATA_DIR

memos = json.loads((DATA_DIR / "memos.json").read_text())
merged = merge_candidates(MockLLMGraphExtractor().extract(memos))
print("== extraction ==")
for did, c in sorted(merged.items(), key=lambda kv: -kv[1]["weight"]):
    docs = [p["doc_id"] for p in c["provenance"]]
    print(f"  {did:20s} w={c['weight']:.2f} ({c['strength_word']:14s}) docs={docs}")

print("\n== eval with default curation (all approved) ==")
rep = run_eval()
m = rep["metrics"]
print(f"  recall={m['citation_recall']:.2f} precision={m['citation_precision']:.2f} "
      f"provenance={m['provenance_coverage']:.2f}")
assert m["citation_recall"] == 1.0 and m["provenance_coverage"] == 1.0

print("\n== reject adas_complexity + litigation_climate -> eval degrades ==")
store.save_approval({"adas_complexity": False, "litigation_climate": False})
rep2 = run_eval()
for r in rep2["results"]:
    print(f"  {r['id']} verdict={r['verdict']:20s} recall={r['citation_recall']:.2f} "
          f"cited={r['cited']}")
q1 = next(r for r in rep2["results"] if r["id"] == "Q1")
q2 = next(r for r in rep2["results"] if r["id"] == "Q2")
assert q1["citation_recall"] == 0.5 and q2["citation_recall"] == 0.5, \
    "expected recall to drop when key drivers are rejected"

print("\n== restore defaults (delete approval file) ==")
store.APPROVAL_PATH.unlink(missing_ok=True)
rep3 = run_eval()
assert rep3["metrics"]["citation_recall"] == 1.0
print("  recall back to 1.00 — OK")
print("\nALL GRAPHRAG TESTS PASSED")

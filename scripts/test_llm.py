"""test_llm — live smoke test for the DeepSeek LLM seams.

Without a key (or with LLM_FORCE_MOCK=1) it prints a skip notice and
exits 0. With a key it exercises every real-LLM seam headlessly:

  1. notes inconsistency analyzer (fraud, claim C-1007)
  2. GraphRAG extraction (fraud + cost memos)
  3. portfolio underwriting note scan
  4. a full fraud run (notes + decision narrative)

Usage:
    python scripts/test_llm.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _time(fn):
    t0 = time.perf_counter()
    result = fn()
    return result, round((time.perf_counter() - t0) * 1000, 1)


def main() -> int:
    from fraud_agent.paths import DATA_DIR
    from llm_client import available, model_id
    from llm_client import LLMCallError

    if not available():
        print(f"[skip] set DEEPSEEK_API_KEY (or unset LLM_FORCE_MOCK) to "
              f"run the live LLM smoke test. model={model_id()}")
        return 0

    print(f"== Live LLM smoke test — model {model_id()} ==")

    # 1 · notes analyzer
    from fraud_agent.tools import claims_tools as ct
    try:
        result, ms = _time(lambda: ct.notes_inconsistency_detector("C-1007"))
        assert set(result) >= {"notes_read", "inconsistencies", "hedging_count"}, \
            f"missing keys: {set(result)}"
        print(f"[ok] notes analyzer ({ms} ms): {len(result['inconsistencies'])} "
              f"inconsistencie(s), hedging={result['hedging_count']}, "
              f"engine={result.get('engine', 'mock')}")
    except LLMCallError as exc:
        print(f"[FAIL] notes analyzer: {exc}")
        return 1

    # 2 · GraphRAG extraction (fraud + cost)
    from fraud_agent.graphrag.extractor import LLMFraudGraphExtractor, merge_candidates as fmerge
    from cost_agent.graphrag.extractor import LLMGraphExtractor, merge_candidates as cmerge
    for label, extractor, memos_file, key, merge_fn in (
        ("fraud extractor", LLMFraudGraphExtractor(),
         "neo4j_fraud_memos.json", "entity_id", fmerge),
        ("cost extractor", LLMGraphExtractor(),
         "neo4j_cost_memos.json", "driver_id", cmerge),
    ):
        memos = json.loads((DATA_DIR / memos_file).read_text())[:2]
        cands, ms = _time(lambda e=extractor, m=memos: e.extract(m))
        assert all(c.get(key) for c in cands), "candidate missing id key"
        merged = merge_fn(cands)
        print(f"[ok] {label} ({ms} ms): {len(cands)} candidates from "
              f"{len(memos)} doc(s) -> {len(merged)} merged")

    # 3 · portfolio note scan
    from portfolio_agent import warehouse as pwh
    from portfolio_agent.submissions.tools import submission_note_scan
    con = pwh.connect()
    row = con.execute(
        "SELECT submission_id FROM fact_underwriting_note LIMIT 1").fetchone()
    con.close()
    if row:
        result, ms = _time(lambda: submission_note_scan(row[0]))
        assert set(result) >= {"notes_read", "hedging_count", "topics"}
        print(f"[ok] portfolio note scan ({ms} ms): submission {row[0]}, "
              f"{result['notes_read']} note(s), hedging={result['hedging_count']}, "
              f"topics={len(result['topics'])}")
    else:
        print("[skip] no underwriting notes in warehouse")

    # 4 · full fraud run (notes + narrative)
    from fraud_agent.harness import FraudHarness
    run, ms = _time(lambda: FraudHarness().run_auto(
        "C-1001", autonomy_level="full"))
    dec = next(e for e in run.trace if e["type"] == "decision")
    has_narrative = bool(dec.get("llm_rationale"))
    print(f"[ok] full run ({ms} ms): decision={run.decision} "
          f"score={run.risk_score}, llm_rationale={'yes' if has_narrative else 'NO'}")
    if has_narrative:
        print(f"     rationale: {dec['llm_rationale'][:120]}...")

    # 5 · session usage ledger
    from llm_client import usage
    u = usage.totals()
    print(f"[ok] usage ledger: {u['calls']} call(s), "
          f"{u['total_tokens']:,} tokens total "
          f"(prompt {u['prompt_tokens']:,} · completion "
          f"{u['completion_tokens']:,} · reasoning {u['reasoning_tokens']:,}) · "
          f"total {u['elapsed_ms'] / 1000:.1f}s")
    for r in usage.calls()[-6:]:
        print(f"     {r['tag'] or '-':20s} {r['total_tokens']:>6,} tok "
              f"({r['prompt_tokens']:,}p/{r['completion_tokens']:,}c/"
              f"{r['reasoning_tokens']:,}r) "
              f"{r.get('elapsed_ms', 0) / 1000:.1f}s")

    print("\nALL LLM SMOKE TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())

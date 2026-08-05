"""LLM CLIENT — extraction pipeline plumbing, shared by every GraphRAG seam.

Two halves:

  1. `extract_documents` — the LLM path: one call per source document;
     each parsed item is passed through the caller's `normalize(item,
     memo)` so the domain extractors can map LLM output onto their exact
     candidate shape (entity_id / driver_id / signal_id + strength-word
     policy + provenance). A failed call on one document is skipped,
     never fatal.

  2. The deterministic mock-side helpers the three extractors share
     (were duplicated 3x): `pick_strength`, `best_sentence`,
     `merge_candidates`. Each domain keeps its own strength table and
     ordering rule; only the boilerplate is shared here.
"""
from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor

from llm_client import LLMCallError, available, chat_json


def extract_documents(memos: list[dict], system: str,
                      normalize, list_key: str,
                      tag: str | None = None,
                      max_workers: int = 4) -> list[dict]:
    """Run the LLM over every memo (in parallel — one call per document,
    up to `max_workers` at a time), normalize the items, return the
    flattened candidate list in document order. `normalize` returns None
    to skip an item; a failed call on one document is skipped, never
    fatal."""
    if not available() or not memos:
        return []

    def _one(memo: dict):
        try:
            raw = chat_json(system, _doc_user(memo), tag=tag)
            items = []
            for item in raw.get(list_key) or []:
                if not isinstance(item, dict):
                    continue
                cand = normalize(item, memo)
                if cand is None:
                    continue
                if isinstance(cand, list):
                    items.extend(c for c in cand if c)
                else:
                    items.append(cand)
            return items, None
        except LLMCallError as exc:
            return [], exc

    started = time.perf_counter()
    results: list[tuple[list, Exception | None]] = [([], None)] * len(memos)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(_one, m) for m in memos]
        for i, future in enumerate(futures):
            results[i] = future.result()
    elapsed = round(time.perf_counter() - started, 2)
    candidates = [c for items, _ in results for c in items]
    failed = sum(1 for _, exc in results if exc)
    # cheap timing/intel probe for callers that want to report it
    extract_documents.last_run = {"docs": len(memos), "elapsed_s": elapsed,
                                  "failed": failed, "workers": max_workers}
    return candidates


# metadata of the most recent extraction run (set by extract_documents)
extract_documents.last_run = None


def _doc_user(memo: dict) -> str:
    return (f"Source document {memo.get('doc_id', '?')} — "
            f"{memo.get('title', '')} ({memo.get('publisher', '')}, "
            f"{memo.get('date', '')}).\n\n--- DOCUMENT ---\n"
            f"{memo.get('text', '')}\n--- END ---")


# ── deterministic mock-side helpers (shared by the 3 extractors) ─────
def pick_strength(text: str, pairs: list[tuple[str, float]],
                  default: float = 0.40) -> tuple[float, str]:
    """First strength word found in the text, per the domain's ordering
    rule; `(default)` when nothing matches."""
    lowered = text.lower()
    for word, weight in pairs:
        if word in lowered:
            return weight, word
    return default, "(default)"


def best_sentence(text: str, keywords: list[str], figure_re,
                  prefer_pct: bool = False) -> str:
    """The most evidence-dense sentence: keyword hit + a figure (or '%')
    wins; otherwise the first keyword sentence; else the first sentence."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text)
                 if s.strip()]
    for s in sentences:
        if any(k in s.lower() for k in keywords) and \
                (figure_re.search(s) or (prefer_pct and "%" in s)):
            return s
    for s in sentences:
        if any(k in s.lower() for k in keywords):
            return s
    return sentences[0] if sentences else ""


def merge_candidates(candidates: list[dict], id_key: str) -> dict[str, dict]:
    """Merge per-document candidates into one entry per id, keeping the
    strongest confidence/weight, ALL provenance docs, and (fraud) the
    union of linked entities."""
    merged: dict[str, dict] = {}
    for c in candidates:
        cid = c[id_key]
        if cid not in merged:
            merged[cid] = {**c, "provenance": [c["provenance"]]}
            continue
        m = merged[cid]
        m["provenance"].append(c["provenance"])
        if "linked_entities" in c and "linked_entities" in m:
            m["linked_entities"] = list(
                set(m["linked_entities"]) | set(c["linked_entities"]))
        strong_key = "confidence" if "confidence" in c else "weight"
        if c[strong_key] > m[strong_key]:
            m[strong_key] = c[strong_key]
            m["strength_word"] = c["strength_word"]
    return merged

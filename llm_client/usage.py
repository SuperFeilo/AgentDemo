"""LLM CLIENT — token usage ledger (session-scoped).

Every real completion is recorded here (in-memory only, nothing written
to disk): model, caller tag, prompt/completion/reasoning tokens, and
timestamp. The app's sidebar meter reads `totals()`; the notes tool and
the decision narrative read `last()` to attach tokens to their result.

Thread-safety: Streamlit serializes script runs, so a plain list is
fine; the appender is protected anyway so a stray background thread
cannot corrupt it.
"""
from __future__ import annotations

import threading
import time

_lock = threading.Lock()
_records: list[dict] = []


def record(model: str, tag: str | None, prompt_tokens: int,
           completion_tokens: int, reasoning_tokens: int = 0,
           total_tokens: int | None = None,
           elapsed_ms: float = 0.0) -> None:
    with _lock:
        _records.append({
            "ts": time.time(),
            "model": model,
            "tag": tag,
            "prompt_tokens": int(prompt_tokens or 0),
            "completion_tokens": int(completion_tokens or 0),
            "reasoning_tokens": int(reasoning_tokens or 0),
            "total_tokens": int(total_tokens
                                or (prompt_tokens or 0) + (completion_tokens or 0)),
            "elapsed_ms": float(elapsed_ms),
        })


def calls() -> list[dict]:
    with _lock:
        return list(_records)


def last() -> dict | None:
    with _lock:
        return _records[-1] if _records else None


def totals() -> dict:
    with _lock:
        return {
            "calls": len(_records),
            "prompt_tokens": sum(r["prompt_tokens"] for r in _records),
            "completion_tokens": sum(r["completion_tokens"] for r in _records),
            "reasoning_tokens": sum(r["reasoning_tokens"] for r in _records),
            "total_tokens": sum(r["total_tokens"] for r in _records),
            "elapsed_ms": round(sum(r["elapsed_ms"] for r in _records), 1),
        }


def by_tag(tag: str) -> list[dict]:
    with _lock:
        return [r for r in _records if r["tag"] == tag]


def reset() -> None:
    with _lock:
        _records.clear()

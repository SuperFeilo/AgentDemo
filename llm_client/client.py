"""LLM CLIENT — the one HTTP path to DeepSeek.

Thin wrapper over the openai SDK (OpenAI-compatible chat.completions).
Two call shapes:

  chat_json(system, user, tag=None)  -> dict  (json_object mode)
  chat_text(system, user, tag=None)  -> str

Every successful completion is recorded in the usage ledger
(`llm_client.usage`) with its model and real token counts. `tag` lets
callers attribute calls (e.g. "notes:C-1007", "extract:fraud").

Everything raises `LLMCallError`; callers decide to fall back to their
deterministic mock. The API key never appears in messages or logs.
"""
from __future__ import annotations

import json
import time

from llm_client import usage
from llm_client.config import settings


class LLMCallError(Exception):
    """Any failure talking to the LLM (network, HTTP, parse)."""


_client_cache: dict[tuple, object] = {}


def _client():
    try:
        from llm_client.config import _api_key
        from openai import OpenAI
    except Exception as exc:  # pragma: no cover - dependency missing
        raise LLMCallError(f"openai SDK unavailable: {exc}") from exc
    key = _api_key()
    if not key:
        raise LLMCallError("no DEEPSEEK_API_KEY configured")
    cfg = settings()
    cache_key = (cfg["base_url"], key)
    client = _client_cache.get(cache_key)
    if client is None:
        client = OpenAI(base_url=cfg["base_url"], api_key=key)
        _client_cache[cache_key] = client
    return client


def _transient(exc: Exception) -> bool:
    """True when a retry might help: transport/timeout/rate-limit/5xx."""
    try:
        import openai
    except Exception:  # pragma: no cover - dependency missing
        return False
    if isinstance(exc, (openai.APITimeoutError, openai.APIConnectionError,
                        openai.RateLimitError)):
        return True
    if isinstance(exc, openai.APIStatusError) and exc.status_code >= 500:
        return True
    return False


def _completion(messages: list[dict], json_mode: bool, tag: str | None):
    cfg = settings()
    client = _client()
    kwargs = dict(
        model=cfg["model"],
        messages=messages,
        temperature=cfg["temperature"],
    )
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    # NOTE: no max_tokens — the provider's default output limit applies.
    # A budget cap makes reasoning models truncate mid-thought
    # (finish_reason=length, content="") which used to waste retries.
    last_error: Exception | None = None
    for attempt in range(cfg["retries"] + 1):
        started = time.perf_counter()
        try:
            resp = client.chat.completions.create(
                timeout=cfg["timeout"], **kwargs)
            content = resp.choices[0].message.content
            elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
            if content and content.strip():
                _record_usage(resp, tag, elapsed_ms)
                return content
            # empty / truncated completion: NOT transient — never retry,
            # let the caller fall back to its deterministic mock
            reason = getattr(resp.choices[0], "finish_reason", None)
            raise LLMCallError(
                f"empty completion (finish_reason={reason}); max_tokens "
                "is not set — the model returned no content")
        except LLMCallError:
            raise
        except Exception as exc:
            last_error = exc
        if attempt < cfg["retries"] and _transient(last_error):
            continue
        raise LLMCallError(f"LLM call failed: {last_error}") from last_error
    raise LLMCallError(str(last_error))  # pragma: no cover - loop always raises


def _record_usage(resp, tag: str | None, elapsed_ms: float) -> None:
    u = getattr(resp, "usage", None)
    if not u:
        return
    details = getattr(u, "completion_tokens_details", None)
    reasoning = int(getattr(details, "reasoning_tokens", 0) or 0) \
        if details else 0
    usage.record(
        model=getattr(resp, "model", "") or settings()["model"],
        tag=tag,
        prompt_tokens=getattr(u, "prompt_tokens", 0),
        completion_tokens=getattr(u, "completion_tokens", 0),
        reasoning_tokens=reasoning,
        total_tokens=getattr(u, "total_tokens", None),
        elapsed_ms=elapsed_ms,
    )


def chat_text(system: str, user: str, tag: str | None = None) -> str:
    content = _completion([
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ], json_mode=False, tag=tag)
    return (content or "").strip()


def chat_json(system: str, user: str, tag: str | None = None) -> dict:
    content = _completion([
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ], json_mode=True, tag=tag)
    try:
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise ValueError("expected a JSON object")
        return parsed
    except Exception as exc:
        raise LLMCallError(f"LLM returned invalid JSON: {exc}") from exc

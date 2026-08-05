"""LLM CLIENT — shared DeepSeek access for every agent's real-LLM seams.

One OpenAI-compatible client, three callers, zero secrets on disk:

  - `fraud_agent/brain/notes_llm.py`   (notes inconsistency analysis)
  - `*_agent/graphrag/extractor.py`    (document -> knowledge-graph)
  - `portfolio_agent/submissions/tools.py` (underwriting note scan)
  - `fraud_agent/loop.py`              (non-scoring decision narrative)

MODE SWITCH (deterministic demo vs real LLM):
  - API key present  -> real DeepSeek calls
  - no key, or LLM_FORCE_MOCK=1 -> callers keep their deterministic mocks,
    so the regression suite (test_packs.py, f1==1.0) stays green offline.
"""
from __future__ import annotations

from llm_client.config import (available, force_mock, model_id, settings)
from llm_client.client import (LLMCallError, chat_json, chat_text)
from llm_client import usage

__all__ = ["available", "force_mock", "model_id", "settings", "usage",
           "LLMCallError", "chat_json", "chat_text"]

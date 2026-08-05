"""LLM CLIENT — configuration.

Mirrors `graphrag_neo4j/config.py`: a committed `config/llm.yaml` holds
non-secret defaults, and environment variables take precedence so each
machine supplies its own key without a file.

Env vars:
  DEEPSEEK_API_KEY   the API key (required for real-LLM mode)
  DEEPSEEK_BASE_URL  default https://api.deepseek.com
  DEEPSEEK_MODEL     default deepseek-v4-flash
  LLM_TIMEOUT        seconds per call (default 30)
  LLM_RETRIES        retries on transient errors only (default 1)
  LLM_FORCE_MOCK     1 -> ignore the key, callers use deterministic mocks

Key resolution order: browser-session pasted key (st.session_state,
demo-time) -> env var -> `ds_api.txt` in the repo root -> Streamlit
secrets (DEEPSEEK_API_KEY). Never written to disk by us.
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml

from fraud_agent.paths import ROOT

_CONFIG_PATH = ROOT / "config" / "llm.yaml"


def _load() -> dict:
    if _CONFIG_PATH.exists():
        return yaml.safe_load(_CONFIG_PATH.read_text()) or {}
    return {}


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


def settings() -> dict:
    cfg = _load()
    return {
        "base_url": _env("DEEPSEEK_BASE_URL",
                         cfg.get("base_url", "https://api.deepseek.com")),
        "model": _env("DEEPSEEK_MODEL", cfg.get("model", "deepseek-v4-flash")),
        "temperature": float(_env("LLM_TEMPERATURE",
                                  str(cfg.get("temperature", 0.1)))),
        "timeout": float(_env("LLM_TIMEOUT", str(cfg.get("timeout", 30)))),
        "retries": int(_env("LLM_RETRIES", str(cfg.get("retries", 1)))),
    }


def force_mock() -> bool:
    return _env("LLM_FORCE_MOCK", "0").strip().lower() in ("1", "true", "yes")


def _api_key() -> str | None:
    # 1. pasted at demo time — lives only in the browser session
    #    (st.session_state), never on disk, never in the process env
    try:
        import streamlit as st
        key = st.session_state.get("llm_key")
        if key:
            return str(key).strip()
    except Exception:
        pass
    # 2. env var — the hosting story (Render dashboard stores it
    #    encrypted at rest; `render.yaml` declares it with sync: false)
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if key:
        return key
    try:  # 3. the user's local key file (gitignored)
        key = (ROOT / "ds_api.txt").read_text(encoding="utf-8").strip()
        if key:
            return key
    except Exception:
        pass
    try:  # 4. Streamlit secrets (if running under `streamlit run`)
        import streamlit as st
        key = st.secrets.get("DEEPSEEK_API_KEY")
        if key:
            return str(key).strip()
    except Exception:
        pass
    return None


def available() -> bool:
    """True when a key exists AND mock-forcing is off."""
    return bool(_api_key()) and not force_mock()


def model_id() -> str:
    return settings()["model"]


class mock_mode:
    """Context manager: run a block in deterministic (mock-LLM) mode
    regardless of the environment — the release gate's contract.
    Restores the previous setting afterwards."""

    def __enter__(self):
        self._prev = os.environ.get("LLM_FORCE_MOCK")
        os.environ["LLM_FORCE_MOCK"] = "1"
        return self

    def __exit__(self, *exc):
        if self._prev is None:
            os.environ.pop("LLM_FORCE_MOCK", None)
        else:
            os.environ["LLM_FORCE_MOCK"] = self._prev
        return False

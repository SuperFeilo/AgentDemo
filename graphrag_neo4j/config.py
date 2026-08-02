"""Connection + dataset configuration for the Neo4j GraphRAG layer.

Env vars NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD / NEO4J_DATABASE take
precedence over `config/neo4j.yaml`, so a shared config file can stay
committed while each machine supplies its own credentials.
"""
from __future__ import annotations

import os

import yaml

from fraud_agent.paths import ROOT

_CONFIG_PATH = ROOT / "config" / "neo4j.yaml"


def _load() -> dict:
    if _CONFIG_PATH.exists():
        return yaml.safe_load(_CONFIG_PATH.read_text()) or {}
    return {}


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


def connection() -> dict:
    cfg = _load()
    return {
        "uri": _env("NEO4J_URI", cfg.get("uri", "bolt://localhost:7687")),
        "user": _env("NEO4J_USER", cfg.get("user", "neo4j")),
        "password": _env("NEO4J_PASSWORD", cfg.get("password", "letmein")),
        "database": _env("NEO4J_DATABASE", cfg.get("database", "neo4j")),
    }


def dataset() -> dict:
    cfg = _load()
    return {
        "seed": int(os.environ.get("NEO4J_SEED", cfg.get("seed", 20260801))),
        "dataset_size": os.environ.get("NEO4J_DATASET_SIZE",
                                       cfg.get("dataset_size", "full")),
    }

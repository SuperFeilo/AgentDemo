"""learning_lab — the Learning page's engine.

Three capabilities, all persisted so the demo survives restarts:

  🧠 knowledge ledger  — what the agent believes, where it learned it
                        (data / notes / newsfeed / human / learned)
  🚫 toggle knowledge  — suppress a weight or graph edge (persisted in
                        data/knowledge_toggles_<agent>.json, originals
                        kept for restore)
  ✍️ write knowledge   — feed the agent a new fact: appended to the
                        agent-facing knowledge files (tools re-read them
                        per call → immediate effect) AND upserted into
                        the GraphRAG store (visible on the knowledge map)

  🔁 verify reactivity — baseline run → re-run after changes → before/
                        after diff, recorded to the append-only evidence
                        ledger (data/learning_evidence.jsonl).
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import streamlit as st
import yaml

from fraud_agent.paths import DATA_DIR, ROOT

from app.knowledge_view import prov_kind, source_kind

TOGGLES_DIR = DATA_DIR
EVIDENCE_PATH = DATA_DIR / "learning_evidence.jsonl"


def _toggles_path(agent: str) -> Path:
    return DATA_DIR / f"knowledge_toggles_{agent}.json"


# ═════════════════════════════════════════════════════════════════════
# ITEM INVENTORY — what can be toggled / written
# ═════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=120, show_spinner=False)
def _fraud_recommendations() -> dict:
    try:
        from fraud_agent import learning as fl
        rep = fl.analyze()
        return {p["signal"]: p["precision"] for p in rep["proposals"]}
    except Exception:
        return {}


@st.cache_data(ttl=120, show_spinner=False)
def _graph_recommendations(agent: str) -> dict:
    """driver/signal id -> 'validated' | 'contradicted' from outcomes."""
    try:
        if agent == "cost":
            from cost_agent import learning as cl
            rep = cl.analyze()
            return {p["driver_id"]: (p["proposed_weight"]
                                     >= p["current_weight"])
                    for p in rep["proposals"]}
        from portfolio_agent import learning as pl
        rep = pl.analyze()
        return {p.get("signal_id"): (p["proposed_weight"]
                                     >= p["current_weight"])
                for p in rep["proposals"]}
    except Exception:
        return {}


def _recommendation(agent: str, item_id: str, prec: dict) -> str:
    p = prec.get(item_id)
    if p is None:
        return "seeded knowledge"
    if p < 0.5:
        return f"low precision ({p:.0%}) — consider suppressing"
    return f"fires cleanly ({p:.0%})"


def items(agent: str) -> list[dict]:
    """Normalized knowledge inventory for the ledger."""
    toggles = load_toggles(agent)
    if agent == "fraud":
        return _fraud_items(toggles)
    if agent == "cost":
        return _cost_items(toggles)
    return _portfolio_items(toggles)


def _fraud_items(toggles: dict) -> list[dict]:
    w = yaml.safe_load((ROOT / "config" / "fraud_weights.yaml").read_text())
    scoring = w.get("scoring", {})
    prec = _fraud_recommendations()
    out = []
    for group, signals in scoring.items():
        for sig, val in signals.items():
            if not isinstance(val, (int, float)):
                continue
            if "cap" in sig or "min" in sig:  # thresholds, not additive
                continue
            item_id = f"{group}.{sig}"
            out.append({
                "id": item_id, "name": f"{group} · {sig}",
                "type": "weight", "value": val,
                "active": item_id not in toggles,
                "source_kind": "notes",
                "recommendation": _recommendation("fraud", item_id, prec),
            })
    return out


def _graph_items(agent: str, relation: str) -> list[dict]:
    fname = ("cost_entities.json" if agent == "cost"
             else "portfolio_entities.json")
    payload = json.loads((DATA_DIR / fname).read_text())
    toggles = load_toggles(agent)
    nodes = {n["id"]: n for n in payload["nodes"]}
    validated = _graph_recommendations(agent)
    out = []
    for e in payload["edges"]:
        if e.get("relation") != relation:
            continue
        a, b = e["a"], e["b"]
        item_id = f"{a}→{b}·{e.get('region', 'ALL')}/{e.get('coverage', e.get('class_code', 'ALL'))}"
        src = nodes.get(a, {})
        kind = ("learned" if src.get("learned") else prov_kind(src)
                if src.get("provenance") else "data")
        v = validated.get(a)
        rec = ("validated — keep" if v is True
               else "contradicted — consider suppressing" if v is False
               else "seeded knowledge")
        out.append({
            "id": item_id, "name": f"{a} → {b}",
            "type": relation, "value": e.get("weight"),
            "meta": (f"{e.get('direction', '')} · lag "
                     f"{e.get('lag_quarters', 0)}q · "
                     f"{e.get('region', 'ALL')}/{e.get('coverage', e.get('class_code', 'ALL'))}"),
            "active": item_id not in toggles,
            "source_kind": kind,
            "recommendation": rec,
        })
    return out


def _cost_items(toggles: dict) -> list[dict]:
    return _graph_items("cost", "IMPACTS")


def _portfolio_items(toggles: dict) -> list[dict]:
    return _graph_items("portfolio", "PREDISPOSES")


# ═════════════════════════════════════════════════════════════════════
# TOGGLES — suppress / restore knowledge items (persisted)
# ═════════════════════════════════════════════════════════════════════
def load_toggles(agent: str) -> dict:
    p = _toggles_path(agent)
    return json.loads(p.read_text()) if p.exists() else {}


def toggle(agent: str, item_id: str, enabled: bool, value) -> None:
    toggles = load_toggles(agent)
    if enabled:
        _restore(agent, item_id, toggles)
        toggles.pop(item_id, None)
    else:
        if item_id not in toggles:
            toggles[item_id] = {"active": False, "original": value}
        _suppress(agent, item_id)
    _toggles_path(agent).write_text(json.dumps(toggles, indent=2))
    record_evidence(agent, "toggle", {"item": item_id,
                                      "enabled": enabled, "value": value})


def reset_toggles(agent: str) -> int:
    toggles = load_toggles(agent)
    n = len(toggles)
    for item_id in list(toggles):
        _restore(agent, item_id, toggles)
    _toggles_path(agent).write_text("{}")
    record_evidence(agent, "toggles_reset", {"count": n})
    return n


def _suppress(agent: str, item_id: str) -> None:
    if agent == "fraud":
        group, sig = item_id.split(".", 1)
        _patch_fraud_weight(group, sig, 0)
    elif agent == "cost":
        _patch_cost_edge(item_id, 0.0)
    else:
        _patch_portfolio_edge(item_id, 0.0)


def _restore(agent: str, item_id: str, toggles: dict) -> None:
    orig = toggles.get(item_id, {}).get("original")
    if orig is None:
        return
    if agent == "fraud":
        group, sig = item_id.split(".", 1)
        _patch_fraud_weight(group, sig, orig)
    elif agent == "cost":
        _patch_cost_edge(item_id, orig)
    else:
        _patch_portfolio_edge(item_id, orig)


def _patch_fraud_weight(group: str, sig: str, value) -> None:
    path = ROOT / "config" / "fraud_weights.yaml"
    w = yaml.safe_load(path.read_text())
    if group in w.get("scoring", {}) and sig in w["scoring"][group]:
        w["scoring"][group][sig] = value
        path.write_text(yaml.safe_dump(w, sort_keys=False))
    from app.ui import get_harness
    get_harness.clear()  # brains reload weights on construction


def _edge_by_id(agent: str, item_id: str) -> dict | None:
    payload = json.loads(
        (DATA_DIR / "portfolio_entities.json").read_text()
        if agent == "portfolio" else
        (DATA_DIR / "cost_entities.json").read_text())
    a_b, seg = item_id.rsplit("·", 1)
    a, b = a_b.split("→")
    region, cov = seg.split("/", 1)
    for e in payload["edges"]:
        if (e["a"] == a and e["b"] == b
                and e.get("region", "ALL") == region
                and e.get("coverage", e.get("class_code", "ALL")) == cov):
            return e, payload
    return None


def _patch_cost_edge(item_id: str, value) -> None:
    hit = _edge_by_id("cost", item_id)
    if hit:
        e, payload = hit
        e["weight"] = value
        (DATA_DIR / "cost_entities.json").write_text(
            json.dumps(payload, indent=2))


def _patch_portfolio_edge(item_id: str, value) -> None:
    hit = _edge_by_id("portfolio", item_id)
    if hit:
        e, payload = hit
        e["weight"] = value
        (DATA_DIR / "portfolio_entities.json").write_text(
            json.dumps(payload, indent=2))


# ═════════════════════════════════════════════════════════════════════
# WRITE-IN KNOWLEDGE — feed the agent a new fact (both layers)
# ═════════════════════════════════════════════════════════════════════
def write_knowledge(agent: str, payload: dict) -> dict:
    if agent == "fraud":
        result = _write_fraud(payload)
    elif agent == "cost":
        result = _write_cost(payload)
    else:
        result = _write_portfolio(payload)
    record_evidence(agent, "knowledge_written", payload, result)
    return result


def _write_fraud(p: dict) -> dict:
    claimant = p["claimant"]
    target = p["target"]
    rel = p["relation"]
    payload = json.loads((DATA_DIR / "entities.json").read_text())
    ids = {n["id"] for n in payload["nodes"]}
    if target not in ids:
        payload["nodes"].append({
            "id": target, "type": p["target_type"], "learned": True,
            "source_kind": p["source_kind"], "note": p["note"]})
    payload["edges"].append({
        "a": claimant, "b": target, "relation": rel, "learned": True,
        "strength": p["strength"], "source_kind": p["source_kind"],
        "note": p["note"]})
    (DATA_DIR / "entities.json").write_text(json.dumps(payload, indent=2))
    _graphrag_upsert("fraud", claimant, target, rel, {
        "strength": p["strength"], "note": p["note"],
        "source_kind": p["source_kind"]},
        {target: p["target_type"], claimant: "claimant"})
    return {"claimant": claimant, "target": target, "relation": rel}


def _write_cost(p: dict) -> dict:
    driver, metric = p["driver"], p["metric"]
    payload = json.loads((DATA_DIR / "cost_entities.json").read_text())
    ids = {n["id"] for n in payload["nodes"]}
    if driver not in ids:
        payload["nodes"].append({
            "id": driver, "type": "driver", "name": p["name"],
            "learned": True, "source_kind": p["source_kind"],
            "evidence": p["quote"], "provenance": [
                {"doc_id": p["doc_id"], "title": "Human-written knowledge",
                 "quote": p["quote"]}]})
    payload["edges"].append({
        "a": driver, "b": metric, "relation": "IMPACTS",
        "weight": p["weight"], "direction": p["direction"],
        "lag_quarters": p["lag"], "region": p["region"],
        "coverage": p["coverage"], "learned": True})
    (DATA_DIR / "cost_entities.json").write_text(
        json.dumps(payload, indent=2))
    _graphrag_upsert("cost", driver, metric, "IMPACTS", {
        "weight": p["weight"], "direction": p["direction"],
        "lag_quarters": p["lag"], "region": p["region"],
        "coverage": p["coverage"]},
        {driver: "driver", metric: "metric"})
    return {"driver": driver, "metric": metric, "weight": p["weight"]}


def _write_portfolio(p: dict) -> dict:
    signal, outcome = p["signal"], p["outcome"]
    payload = json.loads((DATA_DIR / "portfolio_entities.json").read_text())
    ids = {n["id"] for n in payload["nodes"]}
    if signal not in ids:
        payload["nodes"].append({
            "id": signal, "type": "signal", "name": p["name"],
            "stage": p["stage"], "learned": True,
            "source_kind": p["source_kind"], "evidence": p["quote"],
            "provenance": [
                {"doc_id": p["doc_id"], "title": "Human-written knowledge",
                 "quote": p["quote"]}]})
    payload["edges"].append({
        "a": signal, "b": outcome, "relation": "PREDISPOSES",
        "weight": p["weight"], "direction": "+", "lag_quarters": 0,
        "region": p["region"], "coverage": p["class_code"],
        "learned": True})
    (DATA_DIR / "portfolio_entities.json").write_text(
        json.dumps(payload, indent=2))
    _graphrag_upsert("portfolio", signal, outcome, "PREDISPOSES", {
        "weight": p["weight"], "region": p["region"],
        "coverage": p["class_code"]},
        {signal: "signal", outcome: "outcome"})
    return {"signal": signal, "outcome": outcome, "weight": p["weight"]}


def _graphrag_upsert(domain: str, a: str, b: str, relation: str,
                     props: dict, node_types: dict) -> None:
    """Both layers: the GraphRAG knowledge map shows written knowledge."""
    try:
        from graphrag_neo4j.store import get_store
        get_store(domain).add_learned_edge(a, b, relation, props,
                                           node_types)
    except Exception:
        pass


# ═════════════════════════════════════════════════════════════════════
# REACTIVITY — verify the agent reacts to updated knowledge
# ═════════════════════════════════════════════════════════════════════
def baseline(agent: str, subject) -> dict:
    from app.ui import get_harness
    run = get_harness(agent).run_auto(subject, autonomy_level="full")
    return {"subject": str(subject), "decision": run.decision,
            "score": run.risk_score}


def verify_reactivity(agent: str, subject,
                      before: dict | None = None) -> dict:
    before = before or baseline(agent, subject)
    after = baseline(agent, subject)
    changed = (before["decision"] != after["decision"]
               or before["score"] != after["score"])
    record_evidence(agent, "verify", {
        "subject": str(subject), "before": before, "after": after,
        "changed": changed})
    return {"before": before, "after": after, "changed": changed}


# ═════════════════════════════════════════════════════════════════════
# EVIDENCE LEDGER — append-only history (survives restarts)
# ═════════════════════════════════════════════════════════════════════
def record_evidence(agent: str, action: str, detail: dict,
                    result=None) -> None:
    try:
        rec = {"ts": datetime.now().isoformat(timespec="seconds"),
               "agent": agent, "action": action, "detail": detail,
               "result": result}
        with EVIDENCE_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
    except Exception:
        pass


def evidence_history(agent: str | None = None) -> list[dict]:
    if not EVIDENCE_PATH.exists():
        return []
    rows = []
    for line in EVIDENCE_PATH.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    if agent:
        rows = [r for r in rows if r.get("agent") == agent]
    rows.sort(key=lambda r: r.get("ts", ""), reverse=True)
    return rows

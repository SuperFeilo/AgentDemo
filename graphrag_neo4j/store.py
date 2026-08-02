"""DUAL-MODE GRAPH STORE — Neo4j when reachable, in-memory otherwise.

The GraphRAG layer answers the same queries two ways:

  Neo4jGraphStore  — the official `neo4j` driver + genuine Cypher from
                     queries.CYPHER. Bulk-loads the synthetic payload
                     with UNWIND/MERGE; curation (approve/reject) is
                     written both to the JSON approval file (the shared
                     single source of truth with the agent tools) and to
                     node properties in the database.
  LocalGraphStore  — the same query API computed in networkx with
                     identical semantics (queries.local), used when no
                     Neo4j server is reachable so the demo, evals, and
                     UI stay fully reproducible offline.

`get_store(domain)` returns whichever is available. Mode is surfaced so
the UI can show "running N Cypher queries" vs "offline fallback".
"""
from __future__ import annotations

import json

import networkx as nx

from fraud_agent.paths import DATA_DIR
from graphrag_neo4j import queries
from graphrag_neo4j.config import connection
from graphrag_neo4j.synthetic import DATA_FILES, LABELS

# approval file per domain — identical paths to the per-agent stores,
# so the agent tools and the Neo4j layer share one curation state.
APPROVAL_PATHS = {
    "fraud": DATA_DIR / "fraud_graph_approval.json",
    "cost": DATA_DIR / "graph_approval.json",
    "portfolio": DATA_DIR / "portfolio_graph_approval.json",
}

# Neo4j Community runs a single database, so all three demo graphs
# share it. These label sets are disjoint across domains (portfolio's
# events use JourneyEvent so they never collide with cost's Event
# causal layer), which lets load_payload clear ONLY its own domain's
# nodes. SourceDoc nodes are shared and never cleared — MERGE is
# idempotent and doc ids are domain-prefixed (SIU-*/M-*/PFM-*).
DOMAIN_LABELS = {
    "fraud": ["Claimant", "Phone", "Address", "RepairShop", "Clinic",
              "Attorney", "ShellCompany", "FraudRing", "ScamPattern",
              "SuspectShop"],
    "cost": ["Metric", "Driver", "Event"],
    "portfolio": ["Stage", "Signal", "Outcome", "Submission", "Bind",
                  "Claim", "Settlement", "JourneyEvent"],
}


def _scalarize(value):
    """Neo4j properties must be scalars or arrays of scalars; maps and
    nested lists are serialized to JSON strings (e.g. `provenance`)."""
    if isinstance(value, dict):
        return json.dumps(value)
    if isinstance(value, (list, tuple)):
        if any(isinstance(v, (dict, list, tuple)) for v in value):
            return json.dumps(value)
        return list(value)
    return value


def _scalarize_props(props: dict) -> dict:
    return {k: _scalarize(v) for k, v in props.items()}


def _safe_rel_type(rel: str) -> str:
    """Keep valid Cypher relationship-type characters (A-Z, 0-9, _)."""
    return "".join(ch for ch in rel.upper() if ch.isalnum() or ch == "_")


class LocalGraphStore:
    """In-memory (networkx) implementation of the query API."""

    mode = "local"

    def __init__(self, domain: str) -> None:
        self.domain = domain
        self.graph = nx.Graph()
        self._loaded = False

    # ── data ─────────────────────────────────────────────────────────
    def load_payload(self, clear: bool = True, payload: dict | None = None,
                     path: str | None = None) -> dict:
        payload = payload or json.loads(
            (DATA_DIR / (path or DATA_FILES[self.domain])).read_text())
        if clear:
            self.graph.clear()
        for node in payload["nodes"]:
            props = {k: v for k, v in node.items() if k != "id"}
            self.graph.add_node(node["id"], **props)
        for e in payload["edges"]:
            # materialise any edge endpoint not declared as a node
            # (e.g. SourceDoc references) as a proper source_doc node
            for endpoint in (e["a"], e["b"]):
                if endpoint not in self.graph:
                    self.graph.add_node(endpoint, type="source_doc",
                                        doc_id=endpoint)
            self.graph.add_edge(e["a"], e["b"],
                                relation=e["relation"], src=e["a"], dst=e["b"],
                                **{k: v for k, v in e.items()
                                   if k not in ("a", "b", "relation")})
        self._loaded = True
        return self.stats()

    # ── curation (approval) ──────────────────────────────────────────
    def load_approval(self) -> dict:
        # no cache: the approval FILE is the single source of truth, and
        # deleting it must restore "everything approved" immediately
        path = APPROVAL_PATHS[self.domain]
        return json.loads(path.read_text()) if path.exists() else {}

    def save_approval(self, state: dict) -> None:
        APPROVAL_PATHS[self.domain].write_text(json.dumps(state, indent=2))

    def set_approval(self, entity_id: str, approved: bool) -> None:
        state = dict(self.load_approval())
        state[entity_id] = approved
        self.save_approval(state)

    def is_citable(self, entity_id: str, node: dict | None = None) -> bool:
        if node is not None and node.get("curated"):
            return True
        return self.load_approval().get(entity_id, True)

    def approved_ids(self) -> list[str]:
        """Every node id except those a human has rejected."""
        rejected = {k for k, v in self.load_approval().items() if not v}
        return [n for n in self.graph.nodes if n not in rejected]

    # ── queries ──────────────────────────────────────────────────────
    def run(self, query_name: str, **params) -> dict:
        if not self._loaded:
            self.load_payload()
        return queries.local(query_name, self.graph, params,
                             set(self.approved_ids()))

    def cypher_for(self, query_name: str, params: dict) -> str:
        """The exact Cypher this query would run on Neo4j."""
        return queries.fill_cypher(query_name, params)

    def upsert_intel(self, candidates: list[dict], kind: str) -> dict:
        """MERGE-style write of extracted candidates (mock-LLM output)
        into the graph — same semantics as the Neo4j MERGE path."""
        count = 0
        for c in candidates:
            if kind == "fraud":
                eid = c["entity_id"]
                label = {"fraud_ring": "FraudRing",
                         "suspect_shop": "SuspectShop",
                         "scam_type": "ScamPattern"}[c["type"]]
                node = self.graph.nodes.get(eid)
                if node is None:
                    self.graph.add_node(eid, type=c["type"],
                                        name=c["name"], approved=True,
                                        curated=False, confidence=c["confidence"],
                                        strength_word=c["strength_word"])
                    node = self.graph.nodes[eid]
                if c["confidence"] > node.get("confidence", 0):
                    node["confidence"] = c["confidence"]
                    node["strength_word"] = c["strength_word"]
                for prov in c["provenance"]:
                    self._touch_source_doc(prov)
                    self.graph.add_edge(eid, prov["doc_id"],
                                        relation="CITED_IN")
                count += 1
            elif kind == "cost":
                did = c["driver_id"]
                node = self.graph.nodes.get(did)
                if node is None:
                    self.graph.add_node(did, type="driver", name=c["name"],
                                        approved=True, curated=False,
                                        evidence=c.get("quote", ""))
                self.graph.add_edge(did, c["metric"], relation="IMPACTS",
                                    coverage=c["coverage"], region=c["region"],
                                    weight=c["weight"],
                                    direction=c["direction"],
                                    lag_quarters=c["lag_quarters"])
                for prov in c["provenance"]:
                    self._touch_source_doc(prov)
                    self.graph.add_edge(did, prov["doc_id"],
                                        relation="CITED_IN")
                count += 1
            elif kind == "portfolio":
                sid = c["signal_id"]
                node = self.graph.nodes.get(sid)
                if node is None:
                    self.graph.add_node(sid, type="signal",
                                        stage=c["stage"], name=c["name"],
                                        approved=True, curated=False,
                                        evidence=c.get("quote", ""))
                self.graph.add_edge(sid, c["outcome"], relation="PREDISPOSES",
                                    coverage=c["class_code"],
                                    region=c["region"], weight=c["weight"],
                                    direction=c["direction"],
                                    lag_quarters=c["lag_quarters"])
                if c["stage"] in self.graph:
                    self.graph.add_edge(sid, c["stage"], relation="PERTAINS_TO")
                for prov in c["provenance"]:
                    self._touch_source_doc(prov)
                    self.graph.add_edge(sid, prov["doc_id"],
                                        relation="CITED_IN")
                count += 1
        return {"upserted": count}

    def _touch_source_doc(self, prov: dict) -> None:
        doc_id = prov["doc_id"]
        if doc_id not in self.graph:
            self.graph.add_node(doc_id, type="source_doc",
                                doc_id=doc_id, title=prov.get("title"),
                                publisher=prov.get("publisher"),
                                date=prov.get("date"))

    def stats(self) -> dict:
        if not self._loaded:
            self.load_payload()
        from collections import Counter
        return {"node_count": self.graph.number_of_nodes(),
                "edge_count": self.graph.number_of_edges(),
                "by_type": dict(Counter(d.get("type") for _n, d
                                        in self.graph.nodes(data=True)))}

    def to_networkx(self) -> nx.Graph:
        if not self._loaded:
            self.load_payload()
        return self.graph

    def add_learned_edge(self, a: str, b: str, relation: str,
                         props: dict | None = None,
                         node_types: dict | None = None) -> None:
        """Human-written knowledge — appears on the knowledge map
        immediately (learned nodes are approved, not curated)."""
        if not self._loaded:
            self.load_payload()
        for nid, ntype in (node_types or {}).items():
            if nid not in self.graph:
                self.graph.add_node(nid, id=nid, type=ntype, approved=True,
                                    curated=False, learned=True)
        if not self.graph.has_edge(a, b):
            self.graph.add_edge(a, b, relation=relation, learned=True,
                                **(props or {}))
        else:
            self.graph.edges[a, b].update(learned=True, **(props or {}))


class Neo4jGraphStore:
    """Live-driver implementation of the query API (real Cypher)."""

    mode = "neo4j"

    def __init__(self, domain: str) -> None:
        self.domain = domain
        self._driver = None
        self._approved_cache: list[str] | None = None

    # ── connection ───────────────────────────────────────────────────
    def connect(self) -> bool:
        from neo4j import GraphDatabase
        cfg = connection()
        try:
            driver = GraphDatabase.driver(cfg["uri"],
                                          auth=(cfg["user"],
                                                cfg["password"]),
                                          connection_timeout=3)
            driver.verify_connectivity()
            self._driver = driver
            self._db = cfg["database"]
            return True
        except Exception:
            if self._driver is not None:
                self._driver.close()
            self._driver = None
            return False

    def _session(self):
        return self._driver.session(database=self._db,
                                    notifications_min_severity="OFF")

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    @property
    def connected(self) -> bool:
        return self._driver is not None

    # ── data ─────────────────────────────────────────────────────────
    def load_payload(self, clear: bool = True, payload: dict | None = None,
                     path: str | None = None) -> dict:
        payload = payload or json.loads(
            (DATA_DIR / (path or DATA_FILES[self.domain])).read_text())
        label_by_type = {t: l for t, l in LABELS.items()}
        if self.domain == "portfolio":
            label_by_type["event"] = "JourneyEvent"
        with self._session() as s:
            if clear:
                s.run(
                    "MATCH (n) "
                    "WHERE any(l IN $labels WHERE l IN labels(n)) "
                    "DETACH DELETE n",
                    labels=DOMAIN_LABELS[self.domain])
            # nodes, grouped by label for one UNWIND-MERGE per label
            by_label: dict[str, list[dict]] = {}
            for node in payload["nodes"]:
                label = label_by_type.get(node["type"], "Node")
                by_label.setdefault(label, []).append(node)
            for label, nodes in by_label.items():
                safe_label = "".join(ch for ch in label if ch.isalnum())
                s.run(
                    f"UNWIND $batch AS n "
                    f"MERGE (x:`{safe_label}` {{id: n.id}}) "
                    f"SET x += n, x.approved = coalesce(n.approved, true)",
                    batch=[{**_scalarize_props(n), "id": n["id"]}
                           for n in nodes])
            # materialise edge endpoints that were never declared as
            # nodes (e.g. SourceDoc references) so every edge can MERGE
            declared = {n["id"] for n in payload["nodes"]}
            endpoints = {e["a"] for e in payload["edges"]} | \
                        {e["b"] for e in payload["edges"]}
            missing = sorted(endpoints - declared)
            if missing:
                s.run(
                    "UNWIND $batch AS n "
                    "MERGE (x:SourceDoc {id: n.id}) "
                    "SET x.doc_id = n.id, x.approved = true",
                    batch=[{"id": i} for i in missing])
            # edges, grouped by relation
            by_rel: dict[str, list[dict]] = {}
            for e in payload["edges"]:
                by_rel.setdefault(e["relation"], []).append(e)
            for rel, edges in by_rel.items():
                safe_rel = _safe_rel_type(rel)
                s.run(
                    f"UNWIND $batch AS e "
                    f"MATCH (a {{id: e.a}}), (b {{id: e.b}}) "
                    f"MERGE (a)-[r:`{safe_rel}`]->(b) "
                    f"SET r += e",
                    batch=[{**_scalarize_props(e), "a": e["a"], "b": e["b"]}
                           for e in edges])
        self._sync_approvals_to_db()
        return self.stats()

    def _sync_approvals_to_db(self) -> None:
        """Push the JSON approval file into node properties so every
        Cypher query sees the human's curation."""
        state = self.load_approval()
        with self._session() as s:
            for entity_id, approved in state.items():
                s.run("MATCH (n {id: $id}) SET n.approved = $approved",
                      id=entity_id, approved=approved)

    # ── curation ─────────────────────────────────────────────────────
    def load_approval(self) -> dict:
        path = APPROVAL_PATHS[self.domain]
        return json.loads(path.read_text()) if path.exists() else {}

    def save_approval(self, state: dict) -> None:
        APPROVAL_PATHS[self.domain].write_text(json.dumps(state, indent=2))
        self._approved_cache = None
        if self.connected:
            self._sync_approvals_to_db()

    def set_approval(self, entity_id: str, approved: bool) -> None:
        state = dict(self.load_approval())
        state[entity_id] = approved
        self.save_approval(state)

    def is_citable(self, entity_id: str, node: dict | None = None) -> bool:
        if node is not None and node.get("curated"):
            return True
        return self.load_approval().get(entity_id, True)

    def approved_ids(self) -> list[str]:
        if self._approved_cache is None:
            rejected = {k for k, v in self.load_approval().items() if not v}
            self._approved_cache = [
                r["id"] for r in self.run_raw(
                    "MATCH (n) WHERE NOT (n.id IN $rejected) "
                    "RETURN n.id AS id ORDER BY id", rejected=list(rejected))["rows"]]
        return self._approved_cache

    def run_raw(self, cypher: str, **params) -> dict:
        with self._session() as s:
            result = s.run(cypher, **params)
            return {"rows": [dict(r) for r in result]}

    # ── queries ──────────────────────────────────────────────────────
    def run(self, query_name: str, **params) -> dict:
        meta = queries.QUERY_META.get(query_name, {})
        for p in meta.get("params", []):
            if p["name"] not in params and "default" in p:
                params[p["name"]] = p["default"]
        cypher = queries.fill_cypher(query_name, params)
        full = {"approved": self.approved_ids(),
                "attr_rels": queries.ATTR_RELS, **params}
        with self._session() as s:
            result = s.run(cypher, **full)
            rows = [dict(r) for r in result]
        adapter = queries.ADAPTERS.get(query_name)
        if adapter is not None:
            return adapter(rows)
        return rows[0] if rows else {}

    def cypher_for(self, query_name: str, params: dict) -> str:
        """The exact Cypher that will execute against the database."""
        return queries.fill_cypher(query_name, params)

    def upsert_intel(self, candidates: list[dict], kind: str) -> dict:
        count = 0
        with self._session() as s:
            for c in candidates:
                if kind == "fraud":
                    label = {"fraud_ring": "FraudRing",
                             "suspect_shop": "SuspectShop",
                             "scam_type": "ScamPattern"}[c["type"]]
                    s.run(
                        f"MERGE (e:`{label}` {{id: $eid}}) "
                        "ON CREATE SET e.confidence = $conf "
                        "ON MATCH SET e.confidence = CASE "
                        "WHEN $conf > e.confidence THEN $conf "
                        "ELSE e.confidence END "
                        "SET e.name = $name, e.approved = true, "
                        "e.type = $type, e.strength_word = $strength",
                        eid=c["entity_id"], name=c["name"],
                        conf=c["confidence"], type=c["type"],
                        strength=c["strength_word"])
                    for prov in c["provenance"]:
                        s.run("MERGE (d:SourceDoc {id: $doc_id}) "
                              "SET d += $props",
                              doc_id=prov["doc_id"], props=prov)
                        s.run("MATCH (e {id: $eid}), (d:SourceDoc {id: $doc}) "
                              "MERGE (e)-[:CITED_IN]->(d)",
                              eid=c["entity_id"], doc=prov["doc_id"])
                elif kind == "cost":
                    s.run("MERGE (d:Driver {id: $did}) "
                          "SET d.name = $name, d.approved = true, "
                          "d.type = 'driver', d.evidence = $evidence",
                          did=c["driver_id"], name=c["name"],
                          evidence=c.get("quote", ""))
                    s.run("MATCH (d:Driver {id: $did}), "
                          "(m:Metric {id: $metric}) "
                          "MERGE (d)-[r:IMPACTS]->(m) "
                          "SET r.coverage = $coverage, r.region = $region, "
                          "r.weight = $weight, r.direction = $direction, "
                          "r.lag_quarters = $lag",
                          did=c["driver_id"], metric=c["metric"],
                          coverage=c["coverage"], region=c["region"],
                          weight=c["weight"], direction=c["direction"],
                          lag=c["lag_quarters"])
                    for prov in c["provenance"]:
                        s.run("MERGE (d:SourceDoc {id: $doc_id}) "
                              "SET d += $props",
                              doc_id=prov["doc_id"], props=prov)
                        s.run("MATCH (x {id: $eid}), (d:SourceDoc {id: $doc}) "
                              "MERGE (x)-[:CITED_IN]->(d)",
                              eid=c["driver_id"], doc=prov["doc_id"])
                elif kind == "portfolio":
                    s.run("MERGE (sig:Signal {id: $sid}) "
                          "SET sig.name = $name, sig.stage = $stage, "
                          "sig.approved = true, sig.type = 'signal', "
                          "sig.evidence = $evidence",
                          sid=c["signal_id"], name=c["name"],
                          stage=c["stage"], evidence=c.get("quote", ""))
                    s.run("MATCH (sig:Signal {id: $sid}), "
                          "(o:Outcome {id: $outcome}) "
                          "MERGE (sig)-[p:PREDISPOSES]->(o) "
                          "SET p.coverage = $coverage, p.region = $region, "
                          "p.weight = $weight, p.direction = $direction, "
                          "p.lag_quarters = $lag",
                          sid=c["signal_id"], outcome=c["outcome"],
                          coverage=c["class_code"], region=c["region"],
                          weight=c["weight"], direction=c["direction"],
                          lag=c["lag_quarters"])
                    s.run("MATCH (sig:Signal {id: $sid}), "
                          "(st:Stage {id: $stage}) "
                          "MERGE (sig)-[:PERTAINS_TO]->(st)",
                          sid=c["signal_id"], stage=c["stage"])
                    for prov in c["provenance"]:
                        s.run("MERGE (d:SourceDoc {id: $doc_id}) "
                              "SET d += $props",
                              doc_id=prov["doc_id"], props=prov)
                        s.run("MATCH (x {id: $eid}), (d:SourceDoc {id: $doc}) "
                              "MERGE (x)-[:CITED_IN]->(d)",
                              eid=c["signal_id"], doc=prov["doc_id"])
                count += 1
        self._approved_cache = None
        return {"upserted": count}

    def stats(self) -> dict:
        return self.run("graph_stats")

    def add_learned_edge(self, a: str, b: str, relation: str,
                         props: dict | None = None,
                         node_types: dict | None = None) -> None:
        """Human-written knowledge — MERGE nodes + edge, learned flag."""
        with self._session() as s:
            for nid, ntype in (node_types or {}).items():
                s.run(f"MERGE (x:{LABELS.get(ntype, 'Entity')} {{id: $id}}) "
                      "SET x.approved = true, x.curated = false, "
                      "x.learned = true",
                      id=nid)
            params = dict(props or {})
            s.run(f"MATCH (a) WHERE a.id = $a "
                  f"MATCH (b) WHERE b.id = $b "
                  f"MERGE (a)-[r:{relation}]->(b) "
                  "SET r.learned = true",
                  a=a, b=b, **params)
        self._approved_cache = None

    def to_networkx(self) -> nx.Graph:
        """Export the whole database as a networkx graph for rendering."""
        rows = self.run_raw(
            "MATCH (n) RETURN n.id AS id, labels(n) AS labels, n AS props")
        g = nx.Graph()
        for r in rows["rows"]:
            g.add_node(r["id"], id=r["id"], type=r["labels"][0] if
                       r["labels"] else "node",
                       **{k: v for k, v in r["props"].items()
                          if k not in ("id",)})
        rels = self.run_raw(
            "MATCH (a)-[r]->(b) RETURN a.id AS a, b.id AS b, type(r) AS rel")
        for r in rels["rows"]:
            g.add_edge(r["a"], r["b"], relation=r["rel"])
        return g


# ── store selection ──────────────────────────────────────────────────

_STORES: dict[str, LocalGraphStore | Neo4jGraphStore] = {}


def get_store(domain: str, prefer_neo4j: bool = True) -> LocalGraphStore | \
        Neo4jGraphStore:
    """Return a cached store for the domain: Neo4j-backed when a server
    is reachable, otherwise the in-memory fallback.

    Cached per (domain, prefer_neo4j) so the agent-facing accessors
    (which must stay file-based and offline) can never shadow the
    GraphRAG tab's live Neo4j connection, and vice versa."""
    key = f"{domain}:{'neo4j' if prefer_neo4j else 'local'}"
    if key in _STORES:
        return _STORES[key]
    store: LocalGraphStore | Neo4jGraphStore = LocalGraphStore(domain)
    if prefer_neo4j:
        candidate = Neo4jGraphStore(domain)
        try:
            if candidate.connect():
                candidate.load_payload()
                store = candidate
        except Exception:
            candidate.close()
    _STORES[key] = store
    return store


def reset_stores() -> None:
    for store in _STORES.values():
        if hasattr(store, "close") and getattr(store, "mode", "") == "neo4j":
            store.close()
    _STORES.clear()

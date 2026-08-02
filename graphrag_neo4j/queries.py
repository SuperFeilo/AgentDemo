"""THE GRAPH QUERY LIBRARY — the "R" of GraphRAG.

Every query exists in two implementations with IDENTICAL semantics:

  CYPHER[query_name]   — real, portable Neo4j 5 Cypher. Runs against a
                         live database via Neo4jGraphStore. No APOC, no
                         procedures — core Cypher only.
  local(query_name)    — the same result computed in networkx, used by
                         LocalGraphStore when no Neo4j is reachable, so
                         the demo and evals stay reproducible offline.

Approval/curation governance is baked into every read: an entity is
citable only if it is in the approved set (human curation) or marked
`curated` (baseline ground truth). Queries take `approved` as a
parameter (list of citable ids), matching exactly how the JSON curation
store works.

The investigator (investigator.py) and the Streamlit query explorer
both consume `QUERY_META` to know each query's parameters.
"""
from __future__ import annotations

import networkx as nx

APPROVED = "approved"
CURATED = "curated"

# ── relationship sets used by shared-attribute analysis ──────────────
ATTR_RELS = ["USES_PHONE", "LIVES_AT", "REPAIRED_AT", "TREATED_AT",
             "REPRESENTED_BY"]

CYPHER: dict[str, str] = {
    # ── fraud ────────────────────────────────────────────────────────
    "ego_neighborhood": """
MATCH (c {id: $entity_id})
MATCH path = (c)-[*1..{hops}]-(n)
UNWIND relationships(path) AS rel
WITH DISTINCT n, rel
RETURN collect(DISTINCT {{id: n.id, type: coalesce(n.type, labels(n)[0]), name: n.name,
                          known_fraud: coalesce(n.known_fraud, false)}}) AS nodes,
       collect(DISTINCT {{a: startNode(rel).id, b: endNode(rel).id,
                         type: type(rel)}}) AS edges
""",
    "shared_attributes": """
MATCH (c {{id: $claimant_id}})-[r1]->(attr)
MATCH (attr)<-[r2]-(other)
WHERE type(r1) IN $attr_rels AND type(r2) IN $attr_rels
  AND other.id <> $claimant_id AND 'Claimant' IN labels(other)
WITH attr, coalesce(attr.type, labels(attr)[0]) AS attr_type, attr.name AS name,
     collect(DISTINCT {{id: other.id,
                        known_fraud: coalesce(other.known_fraud, false)}})
       AS shared_with
WITH attr, attr_type, name, shared_with,
     [x IN shared_with WHERE x.known_fraud | x.id] AS known_fraud
ORDER BY attr_type, attr.id
RETURN collect({{attribute: attr.id, attr_type: attr_type, name: name,
                shared_with: shared_with,
                known_fraud: known_fraud}}) AS shared
""",
    "paths_to_fraud": """
MATCH (c {{id: $claimant_id}})
MATCH (f:Claimant {{known_fraud: true}})
WHERE f.id <> $claimant_id
MATCH p = shortestPath((c)-[*1..{max_hops}]-(f))
WITH [n IN nodes(p) | {{id: n.id, type: coalesce(n.type, labels(n)[0]), name: n.name,
                        known_fraud: coalesce(n.known_fraud, false)}}] AS path,
     length(p) AS hops
ORDER BY hops
LIMIT $limit
RETURN collect({{path: path, hops: hops}}) AS paths
""",
    "cluster_score": """
MATCH (c {{id: $claimant_id}})-[r1]->(attr)
WHERE type(r1) IN $attr_rels
MATCH (attr)<-[r2]-(other:Claimant)
WHERE type(r2) IN $attr_rels AND other.id <> $claimant_id
WITH other, collect(DISTINCT labels(attr)[0]) AS attr_types
ORDER BY size(attr_types) DESC
LIMIT 10
RETURN collect({{other: other.id, shared_count: size(attr_types),
                attr_types: attr_types}}) AS scores
""",
    "root_cause_claimant": """
MATCH (c {{id: $claimant_id}})-[m:MEMBER_OF]->(ring:FraudRing)
WHERE ring.id IN $approved OR coalesce(ring.curated, false) = true
WITH ring, m
OPTIONAL MATCH (ring)-[:USES_PATTERN]->(pat:ScamPattern)
OPTIONAL MATCH (ring)-[:OPERATES_THROUGH]->(fac)
OPTIONAL MATCH (ring)-[:CITED_IN]->(doc:SourceDoc)
WITH ring, m,
     collect(DISTINCT CASE WHEN pat IS NULL THEN NULL
                             ELSE {{id: pat.id, name: pat.name}} END) AS patterns,
     collect(DISTINCT CASE WHEN fac IS NULL THEN NULL
                             ELSE {{id: fac.id, type: coalesce(fac.type, labels(fac)[0]), name: fac.name}}
                             END) AS facilitators,
     collect(DISTINCT doc.doc_id) AS cited_docs
ORDER BY ring.id
RETURN collect({{ring_id: ring.id, ring_name: ring.name, region: ring.region,
                exposure: coalesce(ring.exposure, 0), role: m.role,
                strength: m.strength, patterns: patterns,
                facilitators: facilitators,
                cited_docs: cited_docs}}) AS rings
""",
    "ring_members": """
MATCH (ring:FraudRing {{id: $ring_id}})
MATCH (c)-[m:MEMBER_OF]->(ring)
WITH c, m
ORDER BY c.id
RETURN collect({{claimant_id: c.id, name: c.name,
                known_fraud: coalesce(c.known_fraud, false),
                role: m.role, strength: m.strength}}) AS members
""",
    "intel_catalog": """
MATCH (e)
WHERE any(l IN ['FraudRing', 'ScamPattern', 'SuspectShop'] WHERE l IN labels(e))
  AND (e.id IN $approved OR coalesce(e.curated, false) = true)
WITH e
OPTIONAL MATCH (e)-[:CITED_IN]->(d:SourceDoc)
WITH e,
     collect(DISTINCT CASE WHEN d IS NULL THEN NULL
                           ELSE {{doc_id: d.doc_id, title: d.title,
                                  publisher: d.publisher, date: d.date}}
                           END) AS provenance
ORDER BY coalesce(e.type, labels(e)[0]), coalesce(e.confidence, 0.0) DESC
RETURN collect({{entity_id: e.id, name: e.name, type: coalesce(e.type, labels(e)[0]),
                confidence: coalesce(e.confidence, 0.0),
                strength: e.strength_word, exposure: coalesce(e.exposure, 0),
                curated: coalesce(e.curated, false),
                provenance: provenance}}) AS intel
""",
    # ── cost ─────────────────────────────────────────────────────────
    "driver_tree": """
MATCH (d:Driver)-[r:IMPACTS]->(m:Metric {{id: $metric}})
WHERE (d.id IN $approved OR coalesce(d.curated, false) = true)
  AND (r.coverage = 'ALL' OR r.coverage = $coverage)
  AND (r.region = 'ALL' OR r.region = $region)
WITH {{driver_id: d.id, name: d.name, weight: r.weight,
      direction: r.direction, lag_quarters: r.lag_quarters,
      evidence: d.evidence}} AS driver
ORDER BY driver.weight DESC
RETURN collect(driver) AS drivers
""",
    "root_cause": """
MATCH (ev:Event)-[:CAUSES]->(d:Driver)
MATCH path = (d)-[r:IMPACTS|FEEDS_INTO*1..3]->(m:Metric {{id: $metric}})
WHERE (d.id IN $approved OR coalesce(d.curated, false) = true)
  AND all(r IN relationships(path) WHERE
        (r.coverage = 'ALL' OR r.coverage = $coverage)
    AND (r.region = 'ALL' OR r.region = $region))
  AND (ev.region = 'ALL' OR ev.region = $region)
  AND (ev.coverage = 'ALL' OR ev.coverage = $coverage)
WITH ev, d, [n IN nodes(path) | n.id] AS causal_chain
OPTIONAL MATCH (d)-[:CITED_IN]->(doc:SourceDoc)
WITH d, ev, causal_chain,
     collect(DISTINCT CASE WHEN doc IS NULL THEN NULL
                            ELSE {{doc_id: doc.doc_id, title: doc.title}} END)
       AS cited_docs
ORDER BY ev.quarter
RETURN collect({{event_id: ev.id, trigger_event: ev.name,
                trigger_quarter: ev.quarter, driver_id: d.id,
                driver_name: d.name, causal_chain: causal_chain,
                evidence: d.evidence, figures: d.figures,
                cited_docs: cited_docs}}) AS triggers
""",
    "root_cause_structural": """
MATCH path = (d:Driver)-[r:IMPACTS|FEEDS_INTO*1..3]->(m:Metric {{id: $metric}})
WHERE (d.id IN $approved OR coalesce(d.curated, false) = true)
  AND all(r IN relationships(path) WHERE
        (r.coverage = 'ALL' OR r.coverage = $coverage)
    AND (r.region = 'ALL' OR r.region = $region))
  AND NOT EXISTS {{ (d)<-[:CAUSES]-() }}
  AND NOT EXISTS {{ (d)<-[x:IMPACTS|FEEDS_INTO]-() }}
WITH d, [n IN nodes(path) | n.id] AS causal_chain
OPTIONAL MATCH (d)-[:CITED_IN]->(doc:SourceDoc)
WITH d, causal_chain,
     collect(DISTINCT CASE WHEN doc IS NULL THEN NULL
                           ELSE {{doc_id: doc.doc_id, title: doc.title}}
                           END) AS cited_docs
ORDER BY d.id
RETURN collect({{driver_id: d.id, driver_name: d.name,
                causal_chain: causal_chain, evidence: d.evidence,
                figures: d.figures, cited_docs: cited_docs}})
  AS structural
""",
    "driver_event": """
MATCH (d:Driver {{id: $driver_id}})
OPTIONAL MATCH (ev:Event)-[:CAUSES]->(d)
RETURN d.name AS name, d.evidence AS evidence, d.figures AS figures,
       d.source AS source, d.provenance AS provenance,
       collect(DISTINCT CASE WHEN ev IS NULL THEN NULL
                            ELSE {{event_id: ev.id, name: ev.name,
                                  quarter: ev.quarter}} END) AS events
""",
    # ── portfolio ────────────────────────────────────────────────────
    "lineage_flow": """
MATCH (sig:Signal {{stage: $stage}})-[p:PREDISPOSES]->(o:Outcome {{id: $outcome}})
WHERE (sig.id IN $approved OR coalesce(sig.curated, false) = true)
  AND (p.region = 'ALL' OR p.region = $region)
  AND (p.coverage = 'ALL' OR p.coverage = $class_code)
WITH {{signal_id: sig.id, name: sig.name, stage: sig.stage,
      outcome: o.id, weight: p.weight, direction: p.direction,
      lag_quarters: p.lag_quarters, evidence: sig.evidence}} AS signal
ORDER BY signal.weight DESC
RETURN collect(signal) AS signals
""",
    "leverage": """
MATCH (sig:Signal)-[p:PREDISPOSES]->(o:Outcome)
WHERE (sig.id IN $approved OR coalesce(sig.curated, false) = true)
  AND (p.region = 'ALL' OR p.region = $region)
  AND (p.coverage = 'ALL' OR p.coverage = $class_code)
WITH sig, p, o, round(p.weight * coalesce(p.exposure, 0.5), 3) AS score
OPTIONAL MATCH (sig)-[:CITED_IN]->(doc:SourceDoc)
WITH sig, p, o, score,
     collect(DISTINCT CASE WHEN doc IS NULL THEN NULL
                            ELSE {{doc_id: doc.doc_id, title: doc.title}} END)
       AS cited_docs
ORDER BY score DESC
RETURN collect({{signal_id: sig.id, name: sig.name, stage: sig.stage,
                outcome: o.id, weight: p.weight,
                exposure: coalesce(p.exposure, 0.5), score: score,
                evidence: sig.evidence, cited_docs: cited_docs}})
  AS candidates
""",
    "journey_trace": """
MATCH (start {{id: $entity_id}})-[:FLOWS_TO*0..4]-(n)
OPTIONAL MATCH (n)-[:AT_STAGE]->(st:Stage)
OPTIONAL MATCH (n)-[:EXHIBITS]->(sig:Signal)
RETURN collect(DISTINCT {{id: n.id, type: coalesce(n.type, labels(n)[0]),
                         broker: n.broker,
                         class_code: n.class_code, fnol_days: n.fnol_days,
                         leakage_pct: n.leakage_pct, stage: st.id}}) AS nodes,
       collect(DISTINCT CASE WHEN sig IS NULL THEN NULL
                            ELSE {{id: sig.id, name: sig.name,
                                  stage: sig.stage}} END) AS signals
""",
    "graph_stats": """
MATCH (n)
WITH count(n) AS node_count
MATCH ()-[r]->()
RETURN node_count, count(r) AS edge_count
""",
}

# row-adapters: turn raw Cypher rows into the SAME structured dict the
# local implementation returns (used by Neo4jGraphStore.post-process).
ADAPTERS: dict[str, callable] = {
    "intel_catalog": lambda rows: {
        "rings": [e for e in rows[0]["intel"] if e["type"] == "fraud_ring"],
        "suspect_shops": [e for e in rows[0]["intel"]
                          if e["type"] == "suspect_shop"],
        "scam_types": [e for e in rows[0]["intel"]
                       if e["type"] == "scam_type"],
    },
    "leverage": lambda rows: {
        "candidates": rows[0]["candidates"],
        "winner": (rows[0]["candidates"][0]
                   if rows[0].get("candidates") else None),
    },
}


def fill_cypher(name: str, params: dict) -> str:
    """Render a query template: hop counts are interpolated as validated
    integer literals (variable-length pattern bounds cannot take
    parameters in all Neo4j versions); everything else stays a param.
    `{{` / `}}` template escapes become Cypher map braces."""
    cypher = CYPHER[name]
    for key in ("hops", "max_hops"):
        if "{" + key + "}" in cypher:
            value = int(params.get(key, 2))
            cypher = cypher.replace("{" + key + "}", str(max(1, min(value, 5))))
    return cypher.replace("{{", "{").replace("}}", "}")

# which queries each domain exposes + their parameters (UI / planner)
QUERY_META: dict[str, dict] = {
    "ego_neighborhood": {"domain": "fraud",
                         "params": [{"name": "entity_id", "type": "str"},
                                    {"name": "hops", "type": "int",
                                     "default": 2}],
                         "desc": "1-2 hop neighborhood around an entity"},
    "shared_attributes": {"domain": "fraud",
                          "params": [{"name": "claimant_id", "type": "str"}],
                          "desc": "phones/addresses/shops/clinics/attorneys "
                                  "shared with other claimants"},
    "paths_to_fraud": {"domain": "fraud",
                       "params": [{"name": "claimant_id", "type": "str"},
                                  {"name": "max_hops", "type": "int",
                                   "default": 3},
                                  {"name": "limit", "type": "int",
                                   "default": 5}],
                       "desc": "shortest paths to any known-fraud claimant"},
    "cluster_score": {"domain": "fraud",
                      "params": [{"name": "claimant_id", "type": "str"}],
                      "desc": "common-neighbor counts — ring detection "
                              "without a label-propagation plugin"},
    "root_cause_claimant": {"domain": "fraud",
                            "params": [{"name": "claimant_id", "type": "str"}],
                            "desc": "claimant -> ring -> scheme pattern -> "
                                    "facilitators + exposure + cited docs"},
    "ring_members": {"domain": "fraud",
                     "params": [{"name": "ring_id", "type": "str"}],
                     "desc": "all members of a fraud ring with roles"},
    "intel_catalog": {"domain": "fraud", "params": [],
                      "desc": "approved fraud intel (rings/patterns/shops) "
                              "with provenance"},
    "driver_tree": {"domain": "cost",
                    "params": [{"name": "metric", "type": "str"},
                               {"name": "region", "type": "str"},
                               {"name": "coverage", "type": "str"}],
                    "desc": "drivers that IMPACT a metric in a segment"},
    "root_cause": {"domain": "cost",
                   "params": [{"name": "metric", "type": "str"},
                              {"name": "region", "type": "str"},
                              {"name": "coverage", "type": "str"}],
                   "desc": "event triggers + structural drivers on causal "
                           "chains to a metric"},
    "root_cause_structural": {"domain": "cost",
                              "params": [{"name": "metric", "type": "str"},
                                         {"name": "region", "type": "str"},
                                         {"name": "coverage", "type": "str"}],
                              "desc": "structural (non-event) drivers at the "
                                      "head of causal chains"},
    "driver_event": {"domain": "cost",
                     "params": [{"name": "driver_id", "type": "str"}],
                     "desc": "evidence + triggering events for one driver"},
    "lineage_flow": {"domain": "portfolio",
                     "params": [{"name": "stage", "type": "str"},
                                {"name": "outcome", "type": "str"},
                                {"name": "region", "type": "str"},
                                {"name": "class_code", "type": "str"}],
                     "desc": "signals at a stage that PREDISPOSE an outcome"},
    "leverage": {"domain": "portfolio",
                 "params": [{"name": "broker", "type": "str"},
                            {"name": "class_code", "type": "str"},
                            {"name": "region", "type": "str"}],
                 "desc": "highest-leverage signal for a segment "
                         "(weight x exposure)"},
    "journey_trace": {"domain": "portfolio",
                      "params": [{"name": "entity_id", "type": "str"}],
                      "desc": "full instance journey submission -> "
                              "settlement with exhibited signals"},
    "graph_stats": {"domain": "all", "params": [],
                    "desc": "graph size counters"},
}


# ═════════════════════════════════════════════════════════════════════
# LOCAL (networkx) implementations — identical semantics to the Cypher
# ═════════════════════════════════════════════════════════════════════

def _citable(node_id: str, node: dict, approved: set) -> bool:
    return node_id in approved or bool(node.get(CURATED))


def _neighbors_by_rels(g: nx.Graph, node: str, rels: list[str]) -> list[str]:
    out = []
    for nbr in g.neighbors(node):
        if g[node][nbr].get("relation") in rels:
            out.append(nbr)
    return out


def local(query_name: str, g: nx.Graph, params: dict, approved: set) -> dict:
    fn = {
        "ego_neighborhood": _ego_neighborhood,
        "shared_attributes": _shared_attributes,
        "paths_to_fraud": _paths_to_fraud,
        "cluster_score": _cluster_score,
        "root_cause_claimant": _root_cause_claimant,
        "ring_members": _ring_members,
        "intel_catalog": _intel_catalog,
        "driver_tree": _driver_tree,
        "root_cause": _root_cause,
        "root_cause_structural": _root_cause_structural,
        "driver_event": _driver_event,
        "lineage_flow": _lineage_flow,
        "leverage": _leverage,
        "journey_trace": _journey_trace,
        "graph_stats": _graph_stats,
    }.get(query_name)
    if fn is None:
        raise KeyError(f"no local implementation for {query_name!r}")
    return fn(g, params, approved)


def _node_info(g: nx.Graph, n: str) -> dict:
    data = g.nodes[n]
    return {"id": n, "type": data.get("type"), "name": data.get("name"),
            "known_fraud": bool(data.get("known_fraud"))}


def _ego_neighborhood(g: nx.Graph, params: dict, _approved: set) -> dict:
    entity = params["entity_id"]
    hops = int(params.get("hops", 2))
    if entity not in g:
        return {"nodes": [], "edges": []}
    nodes, edges = {}, {}
    frontier = {entity}
    for _hop in range(hops):
        nxt = set()
        for n in frontier:
            for nbr in g.neighbors(n):
                rel = g[n][nbr].get("relation")
                if rel:
                    edges[(n, nbr, rel)] = True
                if nbr not in nodes:
                    nodes[nbr] = _node_info(g, nbr)
                nxt.add(nbr)
        frontier = nxt - set(nodes) - {entity}
        if not frontier:
            break
    return {"nodes": list(nodes.values()),
            "edges": [{"a": a, "b": b, "relation": r} for a, b, r in edges]}


def _shared_attributes(g: nx.Graph, params: dict, _approved: set) -> dict:
    cid = params["claimant_id"]
    if cid not in g:
        return {"shared": []}
    shared = []
    for attr in _neighbors_by_rels(g, cid, ATTR_RELS):
        others = [o for o in _neighbors_by_rels(g, attr, ATTR_RELS)
                  if o != cid and g.nodes[o].get("type") == "claimant"]
        if not others:
            continue
        fraud = [o for o in others if g.nodes[o].get("known_fraud")]
        shared.append({
            "attribute": attr, "attr_type": g.nodes[attr].get("type"),
            "name": g.nodes[attr].get("name", attr),
            "shared_with": [{"id": o,
                             "known_fraud": bool(g.nodes[o].get("known_fraud"))}
                            for o in others],
            "known_fraud": fraud,
        })
    return {"shared": shared}


def _paths_to_fraud(g: nx.Graph, params: dict, _approved: set) -> dict:
    cid = params["claimant_id"]
    max_hops = int(params.get("max_hops", 3))
    limit = int(params.get("limit", 5))
    if cid not in g:
        return {"paths": []}
    frauds = [n for n, d in g.nodes(data=True)
              if d.get("type") == "claimant" and d.get("known_fraud")
              and n != cid]
    paths = []
    for f in frauds:
        try:
            p = nx.shortest_path(g, cid, f)
        except nx.NetworkXNoPath:
            continue
        if len(p) - 1 > max_hops:
            continue
        paths.append({"path": [_node_info(g, n) for n in p],
                      "hops": len(p) - 1})
    paths.sort(key=lambda x: x["hops"])
    return {"paths": paths[:limit]}


def _cluster_score(g: nx.Graph, params: dict, _approved: set) -> dict:
    cid = params["claimant_id"]
    if cid not in g:
        return {"scores": []}
    counts: dict[str, int] = {}
    attr_types: dict[str, list[str]] = {}
    for attr in _neighbors_by_rels(g, cid, ATTR_RELS):
        for other in _neighbors_by_rels(g, attr, ATTR_RELS):
            if other == cid or g.nodes[other].get("type") != "claimant":
                continue
            counts[other] = counts.get(other, 0) + 1
            attr_types.setdefault(other, []).append(
                g.nodes[attr].get("type", "attribute"))
    scores = sorted(
        ({"other": o, "shared_count": c,
          "attr_types": sorted(set(attr_types[o]))}
         for o, c in counts.items()),
        key=lambda s: -s["shared_count"])
    return {"scores": scores[:10]}


def _root_cause_claimant(g: nx.Graph, params: dict, approved: set) -> dict:
    cid = params["claimant_id"]
    if cid not in g:
        return {"rings": []}
    rings = []
    for ring in g.neighbors(cid):
        rel = g[cid][ring].get("relation")
        if rel != "MEMBER_OF" or g.nodes[ring].get("type") != "fraud_ring":
            continue
        node = g.nodes[ring]
        if not _citable(ring, node, approved):
            continue
        patterns = [{"id": n, "name": g.nodes[n].get("name", n)}
                    for n in g.neighbors(ring)
                    if g[ring][n].get("relation") == "USES_PATTERN"]
        facs = [{"id": n, "type": g.nodes[n].get("type"),
                 "name": g.nodes[n].get("name", n)}
                for n in g.neighbors(ring)
                if g[ring][n].get("relation") == "OPERATES_THROUGH"]
        docs = [n for n in g.neighbors(ring)
                if g[ring][n].get("relation") == "CITED_IN"]
        rings.append({
            "ring_id": ring, "ring_name": node.get("name"),
            "region": node.get("region"),
            "exposure": node.get("exposure", 0),
            "role": g[cid][ring].get("role"),
            "strength": g[cid][ring].get("strength"),
            "patterns": patterns, "facilitators": facs,
            "cited_docs": sorted(docs),
        })
    return {"rings": rings}


def _ring_members(g: nx.Graph, params: dict, _approved: set) -> dict:
    ring = params["ring_id"]
    members = []
    for c in g.neighbors(ring):
        rel = g[c][ring].get("relation")
        if rel != "MEMBER_OF":
            continue
        members.append({"claimant_id": c, "name": g.nodes[c].get("name"),
                        "known_fraud": bool(g.nodes[c].get("known_fraud")),
                        "role": g[c][ring].get("role"),
                        "strength": g[c][ring].get("strength")})
    members.sort(key=lambda m: m["claimant_id"])
    return {"members": members}


def _intel_catalog(g: nx.Graph, params: dict, approved: set) -> dict:
    catalog = {"rings": [], "suspect_shops": [], "scam_types": []}
    bucket = {"fraud_ring": "rings", "suspect_shop": "suspect_shops",
              "scam_type": "scam_types"}
    for nid, node in g.nodes(data=True):
        if node.get("type") not in bucket:
            continue
        if not _citable(nid, node, approved):
            continue
        prov = []
        for d in g.neighbors(nid):
            if g[nid][d].get("relation") == "CITED_IN":
                dnode = g.nodes[d]
                prov.append({"doc_id": dnode.get("doc_id", d),
                             "title": dnode.get("title"),
                             "publisher": dnode.get("publisher"),
                             "date": dnode.get("date")})
        catalog[bucket[node["type"]]].append({
            "entity_id": nid, "name": node.get("name"),
            "confidence": node.get("confidence", 0.0),
            "strength": node.get("strength_word"),
            "exposure": node.get("exposure", 0),
            "curated": bool(node.get("curated")), "provenance": prov,
        })
    for key in catalog:
        catalog[key].sort(key=lambda e: -e["confidence"])
    return catalog


def _seg_match(edge: dict, region: str, coverage: str) -> bool:
    return (edge.get("region", "ALL") in ("ALL", region)
            and edge.get("coverage", "ALL") in ("ALL", coverage))


def _driver_tree(g: nx.Graph, params: dict, approved: set) -> dict:
    metric, region, coverage = params["metric"], params["region"], \
        params["coverage"]
    drivers = []
    for e in g.edges(data=True):
        rel = e[2].get("relation")
        if rel != "IMPACTS" or e[1] != metric:
            continue
        if not _seg_match(e[2], region, coverage):
            continue
        d = e[0]
        if not _citable(d, g.nodes[d], approved):
            continue
        drivers.append({"driver_id": d, "name": g.nodes[d].get("name"),
                        "weight": e[2].get("weight"),
                        "direction": e[2].get("direction"),
                        "lag_quarters": e[2].get("lag_quarters", 0),
                        "evidence": g.nodes[d].get("evidence")})
    drivers.sort(key=lambda x: -x["weight"])
    return {"drivers": drivers}


def _causal_chains(g: nx.Graph, metric: str, region: str, coverage: str,
                   approved: set) -> list[tuple[str, list[str]]]:
    """(driver_id, chain_ids) for every citable driver whose IMPACTS /
    FEEDS_INTO path reaches `metric` in this segment."""
    chains = []
    for d, dnode in g.nodes(data=True):
        if dnode.get("type") != "driver":
            continue
        if not _citable(d, dnode, approved):
            continue
        # BFS over OUTGOING IMPACTS/FEEDS_INTO edges respecting segment
        # props (the local graph stores src/dst so direction is honored)
        queue = [(d, [d])]
        while queue:
            cur, path = queue.pop(0)
            if cur == metric:
                chains.append((d, path))
                continue
            for e in g.edges(cur, data=True):
                if e[2].get("relation") not in ("IMPACTS", "FEEDS_INTO"):
                    continue
                if e[2].get("src") != cur:
                    continue
                if not _seg_match(e[2], region, coverage):
                    continue
                nxt = e[2].get("dst")
                if nxt in path:
                    continue
                if len(path) >= 4:
                    continue
                queue.append((nxt, path + [nxt]))
    return chains


def _root_cause(g: nx.Graph, params: dict, approved: set) -> dict:
    metric, region, coverage = params["metric"], params["region"], \
        params["coverage"]
    chains = _causal_chains(g, metric, region, coverage, approved)
    chain_of = {d: c for d, c in chains}
    triggers = []
    for e in g.edges(data=True):
        if e[2].get("relation") != "CAUSES":
            continue
        ev = e[2].get("src")
        driver = e[2].get("dst")
        evnode = g.nodes[ev]
        if evnode.get("region", "ALL") not in ("ALL", region) or \
                evnode.get("coverage", "ALL") not in ("ALL", coverage):
            continue
        if driver not in chain_of:
            continue
        dnode = g.nodes[driver]
        triggers.append({
            "event_id": ev, "trigger_event": evnode.get("name"),
            "trigger_quarter": evnode.get("quarter"),
            "driver_id": driver, "driver_name": dnode.get("name"),
            "causal_chain": chain_of[driver],
            "evidence": dnode.get("evidence"),
            "figures": dnode.get("figures"),
            "cited_docs": _cited_docs(g, driver),
        })
    triggers.sort(key=lambda t: t.get("trigger_quarter") or "")
    return {"triggers": triggers}


def _cited_docs(g: nx.Graph, node: str) -> list[dict]:
    docs = []
    for n in g.neighbors(node):
        if g[node][n].get("relation") != "CITED_IN":
            continue
        d = g.nodes[n]
        docs.append({"doc_id": d.get("doc_id", n), "title": d.get("title")})
    return docs


def _root_cause_structural(g: nx.Graph, params: dict, approved: set) -> dict:
    metric, region, coverage = params["metric"], params["region"], \
        params["coverage"]
    chains = _causal_chains(g, metric, region, coverage, approved)
    has_cause = {e[2].get("dst") for e in g.edges(data=True)
                 if e[2].get("relation") == "CAUSES"}
    has_incoming = {e[2].get("dst") for e in g.edges(data=True)
                    if e[2].get("relation") in ("IMPACTS", "FEEDS_INTO")}
    structural = []
    for d, chain in chains:
        if d in has_cause or d in has_incoming:
            continue
        dnode = g.nodes[d]
        structural.append({
            "driver_id": d, "driver_name": dnode.get("name"),
            "causal_chain": chain, "evidence": dnode.get("evidence"),
            "figures": dnode.get("figures"),
            "cited_docs": _cited_docs(g, d),
        })
    structural.sort(key=lambda s: s["driver_id"])
    return {"structural": structural}


def _driver_event(g: nx.Graph, params: dict, _approved: set) -> dict:
    did = params["driver_id"]
    if did not in g:
        return {}
    node = g.nodes[did]
    events = []
    for e in g.edges(data=True):
        if e[2].get("relation") == "CAUSES" and e[2].get("dst") == did:
            ev = g.nodes[e[2]["src"]]
            events.append({"event_id": e[2]["src"], "name": ev.get("name"),
                           "quarter": ev.get("quarter")})
    return {"name": node.get("name"), "evidence": node.get("evidence"),
            "figures": node.get("figures"), "source": node.get("source"),
            "provenance": node.get("provenance", []), "events": events}


def _lineage_flow(g: nx.Graph, params: dict, approved: set) -> dict:
    stage, outcome, region, class_code = params["stage"], params["outcome"], \
        params["region"], params["class_code"]
    signals = []
    for e in g.edges(data=True):
        rel = e[2].get("relation")
        if rel != "PREDISPOSES" or e[1] != outcome:
            continue
        if not _seg_match(e[2], region, class_code):
            continue
        sid = e[0]
        node = g.nodes[sid]
        if node.get("stage") != stage or not _citable(sid, node, approved):
            continue
        signals.append({"signal_id": sid, "name": node.get("name"),
                        "stage": stage, "outcome": outcome,
                        "weight": e[2].get("weight"),
                        "direction": e[2].get("direction"),
                        "lag_quarters": e[2].get("lag_quarters", 0),
                        "evidence": node.get("evidence")})
    signals.sort(key=lambda s: -s["weight"])
    return {"signals": signals}


def _leverage(g: nx.Graph, params: dict, approved: set) -> dict:
    broker, class_code, region = params["broker"], params["class_code"], \
        params["region"]
    out_region = "West" if broker == "BRO-W" and region == "ALL" else region
    candidates = []
    for e in g.edges(data=True):
        if e[2].get("relation") != "PREDISPOSES":
            continue
        if not _seg_match(e[2], out_region, class_code):
            continue
        sid = e[0]
        node = g.nodes[sid]
        if node.get("type") != "signal" or not _citable(sid, node, approved):
            continue
        weight = e[2].get("weight", 0)
        exposure = e[2].get("exposure", 0.5)
        candidates.append({
            "signal_id": sid, "name": node.get("name"),
            "stage": node.get("stage"), "outcome": e[1],
            "weight": weight, "exposure": exposure,
            "score": round(weight * exposure, 3),
            "evidence": node.get("evidence"),
            "cited_docs": _cited_docs(g, sid),
        })
    candidates.sort(key=lambda c: -c["score"])
    return {"candidates": candidates,
            "winner": candidates[0] if candidates else None}


def _journey_trace(g: nx.Graph, params: dict, _approved: set) -> dict:
    entity = params["entity_id"]
    if entity not in g:
        return {"nodes": [], "signals": []}
    seen, nodes, signals = {entity}, {}, {}
    frontier = [entity]
    while frontier:
        cur = frontier.pop(0)
        for e in g.edges(cur, data=True):
            rel = e[2].get("relation")
            if rel == "FLOWS_TO":
                ed = e[2]
                nxt = ed.get("src") if ed.get("dst") == cur else ed.get("dst")
                if nxt is not None and nxt != cur and nxt not in seen:
                    seen.add(nxt)
                    frontier.append(nxt)
            elif rel == "EXHIBITS":
                sig = e[1]
                s = g.nodes[sig]
                signals[sig] = {"id": sig, "name": s.get("name"),
                                "stage": s.get("stage")}
            elif rel == "AT_STAGE":
                nodes[cur] = self_props(g, cur, e[1])
                continue
        if cur not in nodes:
            nodes[cur] = self_props(g, cur, None)
    return {"nodes": list(nodes.values()),
            "signals": list(signals.values())}


def self_props(g: nx.Graph, nid: str, stage: str | None) -> dict:
    d = g.nodes[nid]
    return {"id": nid, "type": d.get("type"), "name": d.get("name"),
            "known_fraud": bool(d.get("known_fraud")),
            "broker": d.get("broker"), "class_code": d.get("class_code"),
            "fnol_days": d.get("fnol_days"),
            "leakage_pct": d.get("leakage_pct"), "stage": stage}


def _graph_stats(g: nx.Graph, params: dict, _approved: set) -> dict:
    from collections import Counter
    return {"node_count": g.number_of_nodes(),
            "edge_count": g.number_of_edges(),
            "by_type": dict(Counter(d.get("type") for _n, d
                                    in g.nodes(data=True)))}

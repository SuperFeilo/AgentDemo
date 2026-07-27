"""ANATOMY COMPONENT: GRAPH KNOWLEDGE

Fraud is relational: rings share phones, addresses and repair shops.
A flat table cannot express "claimant A shares a phone with known
fraudster B" — a graph can, and traversing it is one hop of
`nx.ego_graph`. This module is the agent's structured long-term
knowledge; the `fraud_ring_network` tool is how the agent queries it.
"""
from __future__ import annotations

import json

import networkx as nx

from fraud_agent.paths import DATA_DIR


class KnowledgeGraph:
    def __init__(self, path=None) -> None:
        payload = json.loads((path or DATA_DIR / "entities.json").read_text())
        self.g = nx.Graph()
        for node in payload["nodes"]:
            self.g.add_node(node["id"], **{k: v for k, v in node.items() if k != "id"})
        for edge in payload["edges"]:
            self.g.add_edge(edge["a"], edge["b"], relation=edge["relation"])

    def neighborhood(self, claimant_id: str, hops: int = 2) -> dict:
        """Return the claimant's ego subgraph plus fraud-relevant findings."""
        if claimant_id not in self.g:
            return {"nodes": [], "edges": [], "fraud_links": [], "shared_attributes": []}

        sub = nx.ego_graph(self.g, claimant_id, radius=hops)
        fraud_links, shared = [], []

        # attributes (phone/address/shop) this claimant shares with others
        for attr in self.g.neighbors(claimant_id):
            attr_type = self.g.nodes[attr].get("type")
            if attr_type == "claimant":
                continue
            others = [n for n in self.g.neighbors(attr)
                      if n != claimant_id and self.g.nodes[n].get("type") == "claimant"]
            if others:
                shared.append({
                    "attribute": attr, "type": attr_type,
                    "name": self.g.nodes[attr].get("name", attr),
                    "shared_with": others,
                    "known_fraud": [o for o in others
                                    if self.g.nodes[o].get("known_fraud")],
                })
                for o in others:
                    if self.g.nodes[o].get("known_fraud"):
                        fraud_links.append({
                            "via": attr, "via_type": attr_type,
                            "entity": o,
                        })

        return {
            "nodes": [{"id": n, **sub.nodes[n]} for n in sub.nodes],
            "edges": [{"a": a, "b": b, **sub.edges[a, b]} for a, b in sub.edges],
            "fraud_links": fraud_links,
            "shared_attributes": shared,
        }

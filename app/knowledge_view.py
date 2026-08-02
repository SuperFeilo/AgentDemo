"""GraphRAG visual kit — make the agent's knowledge visible.

The GraphRAG tab's intuition layer: the knowledge map (what the agent
knows, drawn as the graph it actually is), shape-aware result rendering
(graphs / causal chains / ranked candidates / tables), provenance
chips, and the extract → curate → cite write path with visible graph
growth. The exact Cypher + raw JSON remain the teaching layer, shown in
expanders beneath these visuals.
"""
from __future__ import annotations

import pandas as pd
import networkx as nx
import streamlit as st

from app.components import (INTEL_TYPES, SOURCE_COLORS, knowledge_map_figure,
                            ranked_bar_figure)

# ── source kinds: where the knowledge came from ──────────────────────
SOURCE_LABELS = {"data": "📊 data", "notes": "📝 notes",
                 "newsfeed": "📰 newsfeed", "human": "🧑‍🎓 human",
                 "learned": "🧪 learned"}
SOURCE_ORDER = ("data", "notes", "newsfeed", "human", "learned")


def source_kind(doc_id: str = "", publisher: str = "") -> str:
    """External bulletins (NICB, media monitoring, news services) are a
    newsfeed; internal memos are notes; anything else is data."""
    d = (doc_id or "").upper()
    p = (publisher or "").upper()
    if (d.startswith(("NB-", "MEDIA-")) or "NEWS" in p or "MEDIA" in p
            or "BUREAU" in p or "MONITOR" in p):
        return "newsfeed"
    return "notes"


def _first_prov(node: dict) -> dict:
    prov = node.get("provenance") or []
    if isinstance(prov, dict):
        prov = [prov]
    for p in prov:
        if isinstance(p, dict):
            return p
    return {}


def prov_kind(node: dict) -> str:
    """Source kind from ALL provenance entries: any external bulletin
    makes the item newsfeed-grounded; otherwise the first internal doc
    (notes); no provenance = structured data."""
    prov = node.get("provenance") or []
    if isinstance(prov, dict):
        prov = [prov]
    kinds = [source_kind(p.get("doc_id", ""), p.get("publisher", ""))
             for p in prov if isinstance(p, dict)]
    if not kinds:
        return "data"
    return "newsfeed" if "newsfeed" in kinds else kinds[0]


def knowledge_items(store) -> list[dict]:
    """Normalized inventory of what the agent knows: id, name, type,
    source kind, admitted (citable) status and strength metadata."""
    g = store.to_networkx()
    rejected = rejected_ids(store)
    items = []
    for nid, d in g.nodes(data=True):
        if d.get("type") == "source_doc":
            continue
        prov = _first_prov(d)
        kind = ("human" if d.get("learned") and d.get("source_kind") == "human"
                else "learned" if d.get("learned")
                else prov_kind(d))
        items.append({
            "id": nid, "name": d.get("name") or nid,
            "type": d.get("type", "node"), "source_kind": kind,
            "admitted": nid not in rejected,
            "confidence": d.get("confidence"), "weight": d.get("weight"),
            "strength": d.get("strength_word") or d.get("strength"),
            "exposure": d.get("exposure"),
            "known_fraud": bool(d.get("known_fraud")),
            "provenance": [prov] if prov else [],
        })
    return items


def source_map(store) -> dict[str, str]:
    """id -> source kind, for coloring the knowledge map by source."""
    return {i["id"]: i["source_kind"] for i in knowledge_items(store)}


def render_source_ribbon(items: list[dict],
                         admitted_only: bool = True) -> None:
    """'What we know, where we learned it' — cards + grouped bar."""
    def _ok(i):
        return i.get("admitted", i.get("active", True))
    pool = [i for i in items if _ok(i)] if admitted_only else items
    by: dict[str, list[dict]] = {}
    for i in pool:
        by.setdefault(i["source_kind"], []).append(i)
    order = [k for k in SOURCE_ORDER if k in by]
    if not order:
        st.caption("No admitted knowledge yet.")
        return
    cols = st.columns(len(order))
    for col, kind in zip(cols, order):
        group = by[kind]
        n_intel = sum(1 for i in group if i["type"] in INTEL_TYPES)
        with col:
            st.markdown(
                f'<div class="sticky st-cat-hypotheses" style="border-top-color:'
                f'{SOURCE_COLORS.get(kind, "#94a3b8")}">'
                f'<div class="sttitle">{SOURCE_LABELS[kind]} · {len(group)}</div>'
                f'<div style="font-size:.8rem">{len(group)} admitted '
                f'item(s){f" · {n_intel} intel" if n_intel else ""}</div>'
                f'</div>', unsafe_allow_html=True)
    st.plotly_chart(
        ranked_bar_figure(
            [{"id": k, "name": SOURCE_LABELS[k], "score": len(v)}
             for k, v in by.items()], "score", top=6),
        use_container_width=True)


def render_by_source(items: list[dict], toggler=None) -> None:
    """Per-source ledger; optional toggler(item) renders a widget per
    row (e.g. use/suppress) and handles the change itself."""
    by: dict[str, list[dict]] = {}
    for i in items:
        by.setdefault(i["source_kind"], []).append(i)
    for kind in SOURCE_ORDER:
        group = by.get(kind)
        if not group:
            continue
        with st.expander(f"{SOURCE_LABELS[kind]} — {len(group)} item(s)",
                         expanded=(kind in ("newsfeed", "human", "learned"))):
            for it in group[:50]:
                ok = it.get("active", it.get("admitted", True))
                mark = "✅" if ok else "🚫"
                meta = [f"`{it['type']}`"]
                if it.get("value") is not None:
                    meta.append(f"value {it['value']}")
                if it.get("meta"):
                    meta.append(str(it["meta"]))
                if it.get("strength"):
                    meta.append(str(it["strength"]))
                if it.get("known_fraud"):
                    meta.append("🚨")
                row = (f"{mark} **{it['name']}** (`{it['id']}`) — "
                       f"{' · '.join(meta)}"
                       + (f"<br><span class='boardtag'>rec</span> "
                          f"{it['recommendation']}"
                          if it.get("recommendation") else ""))
                if toggler:
                    c1, c2 = st.columns([6, 1])
                    with c1:
                        st.markdown(row, unsafe_allow_html=True)
                        if it.get("provenance"):
                            render_provenance(it["provenance"][:2],
                                              label="grounded in")
                    with c2:
                        toggler(it)
                else:
                    st.markdown(row, unsafe_allow_html=True)
                    if it.get("provenance"):
                        render_provenance(it["provenance"][:2],
                                          label="grounded in")

KVCSS = """
<style>
.kvchain {margin: 8px 0;}
.kvchaintitle {font-size:.72rem; font-weight:700; letter-spacing:.04em;
               text-transform:uppercase; color:#8ea0bd; margin-bottom:4px;}
.kvrow {display:flex; align-items:center; gap:6px; flex-wrap:wrap;}
.kvnode {border-radius:8px; padding:6px 10px; border:1px solid #22314f;
         background:rgba(20,29,51,.85); color:#e6ebf4; font-size:.78rem;
         max-width:340px;}
.kvnode .kvname {font-weight:700;}
.kvnode .kvsub {font-size:.68rem; opacity:.72;}
.kvnode .kvbranch {font-size:.68rem; color:#a5b4cf;}
.kvchip {display:inline-block; font-size:.64rem; border-radius:8px;
         padding:0 7px; margin:2px 3px 0 0; background:#22314f;
         color:#c7d2e8;}
.kvchip.hot {background:rgba(239,68,68,.2); color:#fca5a5;}
.kvchip.ok {background:rgba(34,197,94,.18); color:#4ade80;}
.kvchip.gold {background:rgba(245,158,11,.18); color:#fbbf24;}
.kvarrow {color:#3d4d6f; font-weight:800;}
</style>
"""


# ── knowledge state ──────────────────────────────────────────────────
def rejected_ids(store) -> set[str]:
    """Entity ids a human has rejected (approval file = source of truth)."""
    try:
        approval = store.load_approval() or {}
    except Exception:
        return set()
    return {k for k, v in approval.items() if v is False}


def knowledge_stats(store) -> dict:
    g = store.to_networkx()
    return {
        "entities": g.number_of_nodes(),
        "relationships": g.number_of_edges(),
        "source_docs": sum(1 for _, d in g.nodes(data=True)
                           if d.get("type") == "source_doc"),
        "intel": sum(1 for _, d in g.nodes(data=True)
                     if d.get("type") in INTEL_TYPES),
        "rejected": len(rejected_ids(store)),
    }


def intel_subset(g: nx.Graph) -> set[str]:
    """Intel entities + source memos + their direct neighbors."""
    keep = set()
    for nid, d in g.nodes(data=True):
        t = d.get("type")
        if t in INTEL_TYPES:
            keep.add(nid)
            keep |= set(g.neighbors(nid))
        elif t == "source_doc":
            keep.add(nid)
    return keep


def render_knowledge_map(store, highlight: set[str] | None = None,
                         show_full: bool = False,
                         color_mode: str = "type",
                         source_map: dict | None = None) -> None:
    g = store.to_networkx()
    rejected = rejected_ids(store)
    if show_full:
        subset, limit = None, 420
    else:
        subset, limit = intel_subset(g), 170
    st.plotly_chart(
        knowledge_map_figure(g, rejected=rejected, highlight=highlight,
                             subset_ids=subset, limit=limit,
                             color_mode=color_mode,
                             source_map=source_map),
        use_container_width=True)
    n = g.number_of_nodes()
    shown = len(subset) if subset is not None else min(n, limit)
    if color_mode == "source":
        legend = "color = provenance source (📊 data · 📝 notes · 📰 newsfeed)"
    else:
        legend = "color = entity type"
    st.caption(f"{'Everything' if show_full else 'Intel layer'} — showing "
               f"{shown} of {n:,} entities · {legend} · size = knowledge "
               f"importance · ghost = human-rejected ({len(rejected)}) · "
               f"hover for details.")


def render_entity_detail(store, eid: str) -> None:
    g = store.to_networkx()
    if eid not in g:
        st.info(f"`{eid}` is not in the knowledge graph.")
        return
    d = g.nodes[eid]
    st.markdown(f"**{eid}** — `{d.get('type', '?')}`"
                + (" · 🚨 **known fraud**" if d.get("known_fraud") else "")
                + (f" · {d.get('strength_word', '')}" if d.get("strength_word")
                   else ""))
    rows = [{"property": k, "value": str(v)}
            for k, v in d.items()
            if k not in ("type",) and not isinstance(v, (dict, list))]
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True,
                     use_container_width=True)
    prov = d.get("provenance") or []
    if isinstance(prov, dict):
        prov = [prov]
    render_provenance([p for p in prov if isinstance(p, dict)]
                      or prov, label="provenance")
    nbrs = [f"{nb} ({g.edges[eid, nb].get('relation', '?')})"
            for nb in g.neighbors(eid)]
    if nbrs:
        st.caption("neighbors: " + ", ".join(nbrs[:14])
                   + (" …" if len(nbrs) > 14 else ""))


# ── provenance ───────────────────────────────────────────────────────
def render_provenance(items, label: str = "cited docs") -> None:
    items = items or []
    if not items:
        return
    chips = []
    for p in items:
        if isinstance(p, str):
            chips.append(p)
        else:
            chips.append(f"{p.get('doc_id', '?')} · "
                         f"{str(p.get('title', ''))[:44]} · "
                         f"{p.get('publisher', '')} · {p.get('date', '')}")
    st.markdown(f"<span class='boardtag'>{label}</span> " +
                " ".join(f"<span class='postchip'>{c}</span>"
                         for c in chips[:8]),
                unsafe_allow_html=True)


# ── causal-chain flows ───────────────────────────────────────────────
def chain_html(title: str, chain: list[dict]) -> str:
    """Horizontal flow row: node → node → node, with chips."""
    parts = [KVCSS,
             f'<div class="kvchain"><div class="kvchaintitle">{title}</div>'
             '<div class="kvrow">']
    for i, node in enumerate(chain):
        if i:
            parts.append('<span class="kvarrow">→</span>')
        chips = "".join(f'<span class="kvchip {cls}">{c}</span>'
                        for c, cls in node.get("chips", []))
        sub = (f'<div class="kvsub">{node["sub"]}</div>'
               if node.get("sub") else "")
        parts.append(f'<div class="kvnode"><div class="kvname">'
                     f'{node["label"]}</div>{sub}{chips}</div>')
    parts.append("</div></div>")
    return "".join(parts)


def _doc_chips(docs) -> list[tuple[str, str]]:
    out = []
    for d in docs or []:
        if isinstance(d, str):
            out.append((d, ""))
        else:
            out.append((d.get("doc_id", "?"), "ok"))
    return out


def _fig_chips(figs) -> list[tuple[str, str]]:
    return [(f, "gold") for f in (figs or [])]


# ── shape-aware result rendering ─────────────────────────────────────
def render_result_visual(domain: str, qname: str, result) -> None:
    """Render one query result by its shape: graph / chain / ranked /
    table. The exact Cypher + raw JSON live in an expander above this."""
    if not result:
        st.caption("no result")
        return

    # ── graph-shaped ────────────────────────────────────────────────
    if qname in ("ego_neighborhood", "journey_trace"):
        nodes, edges = result.get("nodes", []), result.get("edges", [])
        if not nodes:
            st.caption("empty subgraph")
            return
        g = nx.Graph()
        for nd in nodes:
            g.add_node(nd["id"],
                       **{k: v for k, v in nd.items() if k != "id"})
        for e in edges:
            g.add_edge(e["a"], e["b"], relation=e.get("relation"))
        st.plotly_chart(
            knowledge_map_figure(g, highlight=set(g.nodes), limit=170),
            use_container_width=True)
        return

    # ── causal chains (cost) ────────────────────────────────────────
    if qname == "root_cause":
        for tr in result.get("triggers", []):
            chain = [
                {"label": tr.get("trigger_event", "?"),
                 "sub": f"trigger · {tr.get('trigger_quarter', '')}",
                 "chips": []},
                {"label": tr.get("driver_name", tr.get("driver_id", "?")),
                 "sub": str(tr.get("evidence", ""))[:130],
                 "chips": _fig_chips(tr.get("figures"))
                          + _doc_chips(tr.get("cited_docs"))},
                {"label": f"{tr.get('metric', '?')} · "
                          f"{tr.get('region', '?')}",
                 "chips": []},
            ]
            st.markdown(
                chain_html(f"Trigger {tr.get('trigger_event', '?')} — "
                           f"{tr.get('trigger_quarter', '')}", chain),
                unsafe_allow_html=True)
        return

    if qname == "root_cause_structural":
        for s in result.get("structural", []):
            chain = [
                {"label": s.get("driver_name", s.get("driver_id", "?")),
                 "sub": str(s.get("evidence", ""))[:130],
                 "chips": _fig_chips(s.get("figures"))
                          + _doc_chips(s.get("cited_docs"))},
                {"label": "structural driver", "chips": []},
            ]
            st.markdown(chain_html("Structural driver", chain),
                        unsafe_allow_html=True)
        return

    # ── chains (fraud) ──────────────────────────────────────────────
    if qname == "root_cause_claimant":
        for r in result.get("rings", []):
            fac = [f.get("name", f.get("id", "?"))
                   for f in r.get("facilitators", [])]
            chain = [
                {"label": "claimant",
                 "chips": [(f"role {r.get('role', '?')}", "hot"),
                           (r.get("strength", ""), "")]},
                {"label": r.get("ring_name", r.get("ring_id", "?")),
                 "sub": r.get("region", ""),
                 "chips": [(f"${r.get('exposure', 0):,} exposure", "hot")]
                          + _doc_chips(r.get("cited_docs"))},
                {"label": "facilitators",
                 "chips": [(f, "") for f in fac]},
            ]
            st.markdown(
                chain_html(f"Ring {r['ring_id']} — why this claimant is "
                           f"risky", chain), unsafe_allow_html=True)
        return

    if qname == "paths_to_fraud":
        for p in result.get("paths", []):
            chain = [
                {"label": nd.get("id", "?"),
                 "chips": [("🚨 fraud", "hot") if nd.get("known_fraud")
                           else (nd.get("type", ""), "")]}
                for nd in p.get("path", [])]
            st.markdown(chain_html(
                f"Path to fraud · {p.get('hops', '?')} hops", chain),
                unsafe_allow_html=True)
        return

    # ── ranked candidates ───────────────────────────────────────────
    if qname == "leverage":
        items = result.get("candidates") or []
        if not items:
            st.caption("no candidates")
            return
        winner = (result.get("winner") or {}).get("id")
        st.plotly_chart(ranked_bar_figure(items, "score",
                                          winner_id=winner),
                        use_container_width=True)
        w = result.get("winner") or {}
        if w:
            st.markdown(f"**Winner:** {w.get('name', w.get('id', '?'))} — "
                        f"score {w.get('score', 0):.2f} (weight "
                        f"{w.get('weight', 0)} × exposure "
                        f"{w.get('exposure', 0)})")
            render_provenance(w.get("cited_docs"),
                              label="winner provenance")
        return

    if qname == "driver_tree":
        items = result.get("drivers") or []
        if items:
            st.plotly_chart(ranked_bar_figure(items, "weight"),
                            use_container_width=True)
            for d in items[:4]:
                st.markdown(f"**{d.get('name', d.get('driver_id', '?'))}** "
                            f"(w={d['weight']}, {d.get('direction', '')}, "
                            f"lag {d.get('lag_quarters', 0)}q) — "
                            f"{str(d.get('evidence', ''))[:110]}")
        return

    if qname == "intel_catalog":
        items = (result.get("rings", []) + result.get("suspect_shops", [])
                 + result.get("scam_types", []))
        if items:
            st.plotly_chart(ranked_bar_figure(items, "confidence",
                                              winner_id=None, top=12),
                            use_container_width=True)
            for it in items[:6]:
                prov = it.get("provenance") or []
                st.markdown(f"**{it.get('name', it.get('entity_id', '?'))}**"
                            f" — {it.get('strength', it.get('strength_word', ''))}"
                            f" · confidence {it.get('confidence', 0):.2f}"
                            + (f" · ${it.get('exposure', 0):,}" if it.get("exposure") else ""))
                render_provenance(prov)
        return

    # ── detail cards ────────────────────────────────────────────────
    if qname == "driver_event":
        st.markdown(f"**{result.get('name', result.get('driver_id', '?'))}**"
                    f" — {result.get('source', '')}")
        st.markdown(result.get("evidence", ""))
        st.caption("figures: " + ", ".join(result.get("figures", [])))
        render_provenance(result.get("provenance"))
        if result.get("events"):
            st.markdown("linked events: " + ", ".join(
                f"{e.get('name', '?')} ({e.get('quarter', '')})"
                for e in result["events"]))
        return

    # ── tables ──────────────────────────────────────────────────────
    rows = result
    if isinstance(result, dict):
        lists = [v for v in result.values() if isinstance(v, list)]
        if len(lists) == 1:
            rows = lists[0]
    if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        st.dataframe(pd.DataFrame(rows), hide_index=True,
                     use_container_width=True)
    else:
        st.json(result)

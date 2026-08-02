"""THE GRAPHRAG READER — turns investigative assignments into cited answers.

`investigate()` is a deterministic stand-in for an LLM agent: it takes a
natural-language-style assignment, decomposes it into a *plan* of graph
queries (each with its Cypher), executes them against the active store,
and composes a root-cause / investigation / leverage report where every
claim carries PROVENANCE back to a source document.

The report shape is stable — `plan`, `steps` (query + cypher + result),
`findings`, `verdict`, `citations` — so the Streamlit tab, the headless
demo, and the test suite all consume the same object.

SEAM FOR A REAL LLM ────────────────────────────────────────────────
The intent→plan mapping below (`_PLANS`) is the LLM seam. Replace
`investigate()`'s dispatch with:

    SYSTEM: You are an insurance-fraud / actuarial investigator with a
    Neo4j graph. Given this assignment, return JSON:
    {"plan": [{"query": "<query name from the library>",
               "params": {...}}], "synthesis": "..."}

    Queries available: {list from QUERY_META}
    Always answer from the query results; cite every quantitative
    claim with its source document.
─────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import json

from fraud_agent.paths import DATA_DIR
from graphrag_neo4j.queries import QUERY_META, fill_cypher
from graphrag_neo4j.store import get_store

GROUND_TRUTH_PATH = DATA_DIR / "neo4j_ground_truth.json"


class AssignmentReport:
    """One investigated assignment: plan, executed steps, findings."""

    def __init__(self, domain: str, title: str, subject: dict) -> None:
        self.domain = domain
        self.title = title
        self.subject = subject
        self.steps: list[dict] = []
        self.findings: list[str] = []
        self.verdict: str | None = None
        self.citations: list[dict] = []
        self.mode = "local"

    def step(self, query: str, params: dict, result: dict) -> None:
        self.steps.append({
            "query": query,
            "params": params,
            "cypher": fill_cypher(query, params),
            "result": result,
        })

    def to_dict(self) -> dict:
        return {
            "domain": self.domain, "title": self.title,
            "subject": self.subject, "steps": self.steps,
            "findings": self.findings, "verdict": self.verdict,
            "citations": self.citations, "mode": self.mode,
        }


def _store(domain: str, prefer_neo4j: bool = True):
    store = get_store(domain, prefer_neo4j=prefer_neo4j)
    return store


def investigate(domain: str, assignment: str, params: dict | None = None,
                prefer_neo4j: bool = True) -> AssignmentReport:
    """Run one of the built-in assignment archetypes.

    `assignment` — one of the keys in _PLANS ("fraud_root_cause",
    "fraud_plan_investigation", "cost_root_cause",
    "portfolio_leverage", "portfolio_journey").
    `params`    — subject overrides, e.g. {"claimant_id": "CL-345"}.
    """
    plan = _PLANS.get(assignment)
    if plan is None:
        raise KeyError(f"unknown assignment {assignment!r}; "
                       f"available: {sorted(_PLANS)}")
    store = _store(domain, prefer_neo4j=prefer_neo4j)
    report = AssignmentReport(domain, plan["title"], params or {})
    report.mode = store.mode
    plan_fn = plan["fn"]

    for query_name, param_fn in plan["steps"]:
        qparams = param_fn(params or {})
        result = store.run(query_name, **qparams)
        report.step(query_name, qparams, result)

    plan_fn(report, params or {}, store)
    return report


# ── fraud ────────────────────────────────────────────────────────────

def _fraud_root_cause(report: AssignmentReport, params: dict,
                      store) -> None:
    cid = params.get("claimant_id", "CL-201")
    rings = report.steps[0]["result"].get("rings", [])
    if not rings:
        report.findings.append(
            f"{cid} has no membership in any approved fraud ring.")
        report.verdict = "NO RING AFFILIATION — no scheme-level root cause"
        return
    ring = rings[0]
    patterns = ", ".join(p.get("name", p) if isinstance(p, dict) else p
                         for p in ring.get("patterns", []))
    facs = ", ".join(f"{f['name']} ({f['type']})"
                     for f in ring.get("facilitators", []))
    exposure = ring.get("exposure", 0)
    docs = ring.get("cited_docs", [])
    report.findings.extend([
        f"Root ring: {ring['ring_name']} ({ring['ring_id']}, "
        f"{ring['region']}) — member role: {ring.get('role')}.",
        f"Scheme pattern: {patterns}.",
        f"Facilitators: {facs}.",
        f"Estimated exposure: ${exposure:,.0f} across the ring.",
        f"Cited in: {', '.join(docs)}.",
    ])
    report.verdict = (
        f"ROOT CAUSE: {ring['ring_name']} — an organized "
        f"{patterns.split(',')[0].lower()} operation run through "
        f"{facs.split(',')[0].split('(')[0].strip()} with ~"
        f"${exposure:,.0f} exposure.")
    report.citations = [{"doc_id": d} for d in docs]


def _fraud_plan_investigation(report: AssignmentReport, params: dict,
                              store) -> None:
    cid = params.get("claimant_id", "CL-345")
    shared = report.steps[0]["result"].get("shared", [])
    paths = report.steps[1]["result"].get("paths", [])
    rings = report.steps[2]["result"].get("rings", [])
    report.findings.append(
        f"Subject {cid} shares {len(shared)} attribute(s) with other "
        f"claimants; {len(paths)} path(s) to known-fraud entities; "
        f"{len(rings)} ring affiliation(s).")
    plan_steps = [
        ("1. Verify identity & policy", "claims DB + policy timing"),
        ("2. Map shared attributes", f"{len(shared)} shared "
         f"phone/address/shop links to enumerate the cluster"),
        ("3. Confirm fraud linkage",
         f"{len(paths)} shortest path(s) to known-fraud claimants"),
        ("4. Escalate to ring level",
         f"root-cause walk: {rings[0]['ring_name']} via "
         f"{rings[0]['ring_id']}" if rings else "no ring — stop"),
    ]
    for line in plan_steps:
        report.findings.append(f"• {line[0]}: {line[1]}")
    ring = rings[0] if rings else None
    report.verdict = (
        f"INVESTIGATION PLAN for {cid}: run identity + policy checks, "
        f"enumerate {len(shared)} shared attributes, confirm "
        f"{len(paths)} fraud paths, then " +
        (f"open ring-level file on {ring['ring_name']} "
         f"(exposure ${ring.get('exposure', 0):,.0f})."
         if ring else "close with no ring-level referral."))
    if ring:
        report.citations = [{"doc_id": d} for d in ring.get("cited_docs", [])]


# ── cost ─────────────────────────────────────────────────────────────

def _cost_root_cause(report: AssignmentReport, params: dict, store) -> None:
    segment = params.get("segment", {})
    metric = segment.get("metric", "frequency")
    region = segment.get("region", "South")
    coverage = segment.get("coverage", "auto_pd")
    triggers = report.steps[0]["result"].get("triggers", [])
    structural = report.steps[1]["result"].get("structural", [])
    primary = triggers[0] if triggers else None
    if primary:
        report.findings.append(
            f"Triggering event: {primary['trigger_event']} "
            f"({primary['trigger_quarter']}) CAUSES {primary['driver_name']} "
            f"→ causal chain {' → '.join(primary['causal_chain'])}.")
    if structural:
        names = [f"{s['driver_name']} ({s['causal_chain'][0]})"
                 for s in structural[:3]]
        report.findings.append(
            f"Structural drivers compounding the trend: {', '.join(names)}.")
    docs = {d["doc_id"] for t in triggers for d in t.get("cited_docs", [])}
    report.citations = [{"doc_id": d} for d in sorted(docs)]
    if primary:
        report.verdict = (
            f"ROOT CAUSE ({metric}/{region}/{coverage}): the "
            f"{primary['trigger_event']} in {primary['trigger_quarter']} "
            f"triggered {primary['driver_name']}, flowing through "
            f"{' → '.join(primary['causal_chain'])}. "
            + (f"Compounded by {structural[0]['driver_name']}." if structural
               else ""))
    else:
        report.verdict = (
            f"NO EPISODIC TRIGGER ({metric}/{region}/{coverage}) — "
            f"trend is structural. Leading driver: "
            f"{structural[0]['driver_name']}." if structural else
            "NO CAUSAL EXPLANATION FOUND.")


# ── portfolio ────────────────────────────────────────────────────────

def _portfolio_leverage(report: AssignmentReport, params: dict,
                        store) -> None:
    segment = params.get("segment", {})
    winner = report.steps[0]["result"].get("winner")
    if not winner:
        report.verdict = "NO LEVERAGE SIGNAL FOUND for this segment."
        return
    report.findings.append(
        f"Segment {segment.get('broker', 'ALL')} / "
        f"{segment.get('class_code', 'ALL')} / {segment.get('region', 'ALL')}: "
        f"top lever is {winner['name']} at the {winner['stage']} stage "
        f"(PREDISPOSES {winner['outcome']}, weight {winner['weight']} × "
        f"exposure {winner['exposure']} = score {winner['score']}).")
    report.findings.append(
        f"Evidence: {winner.get('evidence')}.")
    docs = [d["doc_id"] for d in winner.get("cited_docs", [])]
    report.citations = [{"doc_id": d} for d in docs if d]
    report.verdict = (
        f"HIGHEST-LEVERAGE LEVER: {winner['name']} ({winner['stage']} "
        f"stage → {winner['outcome']}), score {winner['score']}.")


def _portfolio_journey(report: AssignmentReport, params: dict, store) -> None:
    cid = params.get("claim_id", "CLM-015")
    nodes = report.steps[0]["result"].get("nodes", [])
    signals = report.steps[0]["result"].get("signals", [])
    ordered = sorted(nodes, key=lambda n: {
        "submission": 0, "bind": 1, "claim": 2, "settlement": 3,
    }.get(n.get("type"), 4))
    chain = " → ".join(f"{n['id']} ({n.get('stage') or n.get('type')})"
                       for n in ordered)
    report.findings.append(f"Journey: {chain}.")
    report.findings.append(
        f"Signals exhibited: {', '.join(s['name'] for s in signals) or 'none'}.")
    report.verdict = (
        f"JOURNEY TRACE {cid}: {chain}. "
        f"Exhibits {len(signals)} signal(s): "
        f"{', '.join(s['name'] for s in signals) or 'none'}.")


# ── plan registry (the intent→plan LLM seam) ─────────────────────────

_PLANS: dict[str, dict] = {
    "fraud_root_cause": {
        "title": "Root-cause analysis — why is this claimant risky?",
        "steps": [
            ("root_cause_claimant",
             lambda p: {"claimant_id": p.get("claimant_id", "CL-201")}),
        ],
        "fn": _fraud_root_cause,
    },
    "fraud_plan_investigation": {
        "title": "Deep planning — investigate a new claimant",
        "steps": [
            ("shared_attributes",
             lambda p: {"claimant_id": p.get("claimant_id", "CL-345")}),
            ("paths_to_fraud",
             lambda p: {"claimant_id": p.get("claimant_id", "CL-345")}),
            ("root_cause_claimant",
             lambda p: {"claimant_id": p.get("claimant_id", "CL-345")}),
        ],
        "fn": _fraud_plan_investigation,
    },
    "cost_root_cause": {
        "title": "Root-cause analysis — why did this metric move?",
        "steps": [
            ("root_cause",
             lambda p: {**p.get("segment", {"metric": "frequency",
                                            "region": "South",
                                            "coverage": "auto_pd"})}),
            ("root_cause_structural",
             lambda p: {**p.get("segment", {"metric": "frequency",
                                            "region": "South",
                                            "coverage": "auto_pd"})}),
        ],
        "fn": _cost_root_cause,
    },
    "portfolio_leverage": {
        "title": "Deep planning — where is the high-leverage margin lever?",
        "steps": [
            ("leverage",
             lambda p: {**p.get("segment", {"broker": "BRO-W",
                                            "class_code": "ALL",
                                            "region": "ALL"})}),
        ],
        "fn": _portfolio_leverage,
    },
    "portfolio_journey": {
        "title": "Investigative trace — one claim's full journey",
        "steps": [
            ("journey_trace",
             lambda p: {"entity_id": p.get("claim_id", "CLM-015")}),
        ],
        "fn": _portfolio_journey,
    },
}

# which assignments each agent tab offers, with example subjects
OFFERINGS: dict[str, list[dict]] = {
    "fraud": [
        {"id": "fraud_root_cause", "label": "Root cause — CL-201",
         "params": {"claimant_id": "CL-201"}},
        {"id": "fraud_plan_investigation", "label": "Plan investigation — "
         "CL-345 (new ring member)", "params": {"claimant_id": "CL-345"}},
        {"id": "fraud_plan_investigation", "label": "Plan investigation — "
         "CL-701 (clean distractor)", "params": {"claimant_id": "CL-701"}},
    ],
    "cost": [
        {"id": "cost_root_cause",
         "label": "Root cause — why did South auto-pd frequency spike?",
         "params": {"segment": {"metric": "frequency", "region": "South",
                                "coverage": "auto_pd"}}},
        {"id": "cost_root_cause",
         "label": "Root cause — why did loss_ratio rise nationally?",
         "params": {"segment": {"metric": "loss_ratio", "region": "ALL",
                                "coverage": "auto_pd"}}},
    ],
    "portfolio": [
        {"id": "portfolio_leverage",
         "label": "Leverage — BRO-W / ALL / ALL",
         "params": {"segment": {"broker": "BRO-W", "class_code": "ALL",
                                "region": "ALL"}}},
        {"id": "portfolio_leverage",
         "label": "Leverage — ALL / 5437 / ALL",
         "params": {"segment": {"broker": "ALL", "class_code": "5437",
                                "region": "ALL"}}},
        {"id": "portfolio_journey", "label": "Journey trace — CLM-015",
         "params": {"claim_id": "CLM-015"}},
    ],
}


def load_ground_truth() -> dict:
    return json.loads(GROUND_TRUTH_PATH.read_text())


def assignment_cypher(assignment: str, params: dict | None = None) -> list:
    """The Cypher an assignment will run (shown in the UI before run)."""
    plan = _PLANS[assignment]
    return [{"query": q, "params": f(params or {}),
             "cypher": fill_cypher(q, f(params or {}))}
            for q, f in plan["steps"]]

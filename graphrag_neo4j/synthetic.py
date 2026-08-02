"""SEEDED SYNTHETIC DATA — the Neo4j GraphRAG demo graphs.

Generates realistic-volume graphs for all three agents, with planted
ground truth (known rings, causal events, leverage levers), realistic
distractors (innocent shared households, episodic weather events), and
source memos whose text "grounds" the intel with provenance — exactly
the way the real graph would be built.

Deterministic: every graph is a pure function of `seed`, so headless
evals and the demo are reproducible. Run via:

    python scripts/generate_neo4j_demo_data.py

Outputs (all committed under data/):
    neo4j_fraud.json / neo4j_cost.json / neo4j_portfolio.json
    neo4j_fraud_memos.json / neo4j_cost_memos.json / neo4j_portfolio_memos.json
    neo4j_ground_truth.json        (expected answers for the demo)
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from fraud_agent.paths import DATA_DIR

# ── label mapping: payload "type" -> Neo4j label ─────────────────────
LABELS = {
    # fraud
    "claimant": "Claimant", "phone": "Phone", "address": "Address",
    "repair_shop": "RepairShop", "clinic": "Clinic", "attorney": "Attorney",
    "shell_company": "ShellCompany", "fraud_ring": "FraudRing",
    "scam_type": "ScamPattern", "suspect_shop": "SuspectShop",
    "source_doc": "SourceDoc",
    # cost
    "metric": "Metric", "driver": "Driver", "event": "Event",
    # portfolio
    "stage": "Stage", "signal": "Signal", "outcome": "Outcome",
    "submission": "Submission", "bind": "Bind", "claim": "Claim",
    "settlement": "Settlement",
}


class Graph:
    def __init__(self, rng: random.Random) -> None:
        self.rng = rng
        self.nodes: dict[str, dict] = {}
        self.edges: list[dict] = []

    def node(self, id_: str, type_: str, **props) -> dict:
        props = {"id": id_, "type": type_, "approved": True, **props}
        self.nodes[id_] = props
        return props

    def edge(self, a: str, b: str, relation: str, **props) -> None:
        self.edges.append({"a": a, "b": b, "relation": relation, **props})

    def payload(self) -> dict:
        return {"nodes": list(self.nodes.values()), "edges": self.edges}


# ═════════════════════════════════════════════════════════════════════
# FRAUD — claimant network with planted rings, facilitators, distractors
# ═════════════════════════════════════════════════════════════════════

_ANCHOR_MEMOS = json.loads((DATA_DIR / "fraud_memos.json").read_text())

RINGS = [
    # id, name, region, confidence, strength, exposure, curated,
    # patterns, through, member ids
    ("RING-SOUTH-1", "South Texas staged-accident ring", "South", 0.85,
     "confirmed", 687000, True,
     ["PATTERN-STAGING-1", "PATTERN-ID-1", "PATTERN-PIP-1"],
     [("SHOP-77", "billing nexus"), ("CLIN-01", "medical mill"),
      ("ATTY-01", "retainer solicitor"), ("SHELL-01", "fee laundering")],
     ["CL-201", "CL-202", "CL-203", "CL-207"]),
    ("RING-MIDWEST-1", "Midwest medical-mill ring", "Midwest", 0.70,
     "strongly_suspected", 412000, True,
     ["PATTERN-PIP-1"],
     [("CLIN-02", "treatment mill"), ("ATTY-02", "referral attorney"),
      ("SHELL-02", "billing shell")],
     ["CL-106", "CL-111"]),
    ("RING-NORTHEAST-1", "Northeast premium-diversion ring", "Northeast",
     0.85, "confirmed", 540000, True,
     ["PATTERN-ID-1"],
     [("ATTY-03", "straw agent"), ("SHELL-03", "fake agency")],
     []),
    ("RING-SE-1", "Southeast tow-steering ring", "Southeast", 0.55,
     "suspected", 296000, False,
     ["PATTERN-TOW-1"],
     [("SHOP-12", "tow-yard nexus"), ("ATTY-04", "ambulance chaser"),
      ("SHELL-04", "towing fee shell")],
     []),
    ("RING-WEST-1", "West ghost-repair ring", "West", 0.55, "suspected",
     348000, False,
     ["PATTERN-GHOST-1"],
     [("SHOP-45", "ghost-repair bay"), ("CLIN-04", "referral clinic"),
      ("SHELL-05", "parts vendor shell")],
     []),
    ("RING-DFW-1", "DFW swoop-and-squat cell", "South", 0.40, "possible",
     187000, False,
     ["PATTERN-STAGING-1"],
     [("SHOP-88", "phantom repair shop"), ("ATTY-05", "runner attorney")],
     []),
    ("RING-PHX-1", "Phoenix rental-receipt ring", "West", 0.40,
     "possible", 143000, False,
     ["PATTERN-RENTAL-1"],
     [("ATTY-06", "receipt fabricator"), ("SHELL-06", "rental billing shell")],
     []),
    ("RING-MW-2", "Indianapolis chiro-referral cell", "Midwest", 0.55,
     "suspected", 231000, False,
     ["PATTERN-PIP-1"],
     [("CLIN-03", "chiro referral mill"), ("SHELL-07", "admin fee shell")],
     []),
]

PATTERNS = [
    ("PATTERN-STAGING-1", "Staged accidents — swoop-and-squat & jump-ins",
     0.85, "confirmed", True, ["SIU-01", "SIU-04", "SIU-10"]),
    ("PATTERN-PIP-1", "PIP abuse — inflated soft-tissue treatment", 0.70,
     "strongly_suspected", True, ["SIU-02", "NB-001"]),
    ("PATTERN-ID-1", "Identity manipulation — synthetic claimants", 0.85,
     "confirmed", True, ["SIU-03", "NB-002"]),
    ("PATTERN-TOW-1", "Tow steering — referral kickbacks", 0.55,
     "suspected", False, ["NB-001", "SIU-07"]),
    ("PATTERN-GHOST-1", "Ghost repairs — parts never installed", 0.55,
     "suspected", False, ["AUD-001", "AUD-005", "SIU-08"]),
    ("PATTERN-RENTAL-1", "Rental-reimbursement inflation", 0.40,
     "possible", False, ["NB-004", "SIU-09"]),
]

SHOPS = {
    "SHOP-77": ("QuickFix Auto", "South", True, "SHOP-COLLUSION-1"),
    "SHOP-12": ("Certified Auto Care", "Southeast", True, "SHOP-COLLUSION-2"),
    "SHOP-45": ("Ace Collision & Paint", "West", True, "SHOP-COLLUSION-3"),
    "SHOP-88": ("Metro Body DFW", "South", True, "SHOP-COLLUSION-4"),
    "SHOP-201": ("Lone Star Collision", "South", False, None),
    "SHOP-202": ("Hilltop Auto Body", "Midwest", False, None),
    "SHOP-203": ("Beacon Street Repair", "Northeast", False, None),
    "SHOP-204": ("Peachtree Frame & Body", "Southeast", False, None),
    "SHOP-205": ("Pacific Auto Craft", "West", False, None),
    "SHOP-206": ("Trinity Valley Collision", "South", False, None),
    "SHOP-207": ("Fox River Body Shop", "Midwest", False, None),
    "SHOP-208": ("Hudson Auto Works", "Northeast", False, None),
    "SHOP-209": ("Magnolia Repair Center", "Southeast", False, None),
    "SHOP-210": ("Desert Sky Collision", "West", False, None),
}

CLINICS = {
    "CLIN-01": ("South Houston Spine & Rehab", True),
    "CLIN-02": ("Midwest Injury Centers", True),
    "CLIN-03": ("Circle City Chiro Clinic", True),
    "CLIN-04": ("Valley Rehab Partners", True),
    "CLIN-51": ("FirstCare Family Medicine", False),
    "CLIN-52": ("Riverbend Orthopedics", False),
    "CLIN-53": ("Northgate Physical Therapy", False),
    "CLIN-54": ("Summit Chiropractic Care", False),
    "CLIN-55": ("Bayview Health Clinic", False),
}

ATTORNEYS = {
    "ATTY-01": ("Marcus Devereaux", True), "ATTY-02": ("Neil Prescott", True),
    "ATTY-03": ("Howard Castellano", True), "ATTY-04": ("Ralph Berman", True),
    "ATTY-05": ("Lyle Drummond", True), "ATTY-06": ("Victor Salazar", True),
    "ATTY-51": ("Amanda Whitfield", False), "ATTY-52": ("George Kim", False),
    "ATTY-53": ("Priya Raman", False), "ATTY-54": ("Daniel Ochoa", False),
    "ATTY-55": ("Susan Marsh", False),
}

SHELLS = {
    "SHELL-01": "Gulf Coast Logistics LLC",
    "SHELL-02": "Hoosier Billing Services LLC",
    "SHELL-03": "Liberty Square Insurance Group",
    "SHELL-04": "Peachtree Towing Admin LLC",
    "SHELL-05": "West Coast Parts Supply LLC",
    "SHELL-06": "Sunset Valley Rentals LLC",
    "SHELL-07": "Circle City Admin Services LLC",
}


def _member_blocks(rng: random.Random, per_ring: int) -> dict[str, list[str]]:
    """Ring id -> member claimant ids (CL-301+ blocks)."""
    blocks, start = {}, 301
    for ring_id, *_rest, members in RINGS:
        existing = [m for m in members if m.startswith("CL-")]
        need = per_ring - len(existing)
        new = [f"CL-{start + i}" for i in range(need)]
        blocks[ring_id] = existing + new
        start += need
    return blocks


def generate_fraud(seed: int, size: str = "full") -> dict:
    rng = random.Random(seed)
    g = Graph(rng)

    member_blocks = _member_blocks(rng, 16 if size == "full" else 10)
    ring_members: dict[str, list[str]] = {}

    # ── intel layer first: rings, patterns, suspect shops, facilitators ──
    for ring_id, name, region, conf, strength, exposure, curated, \
            pattern_ids, through, anchor_members in RINGS:
        prov = _ring_provenance(ring_id)
        g.node(ring_id, "fraud_ring", name=name, region=region,
               confidence=conf, strength_word=strength, exposure=exposure,
               curated=curated, provenance=prov)
        ring_members[ring_id] = member_blocks[ring_id]
        for pid in pattern_ids:
            g.edge(ring_id, pid, "USES_PATTERN")
        for ent, role in through:
            g.edge(ring_id, ent, "OPERATES_THROUGH", role=role)
        for doc in prov:
            g.edge(ring_id, doc["doc_id"], "CITED_IN")

    for pid, name, conf, strength, curated, docs in PATTERNS:
        g.node(pid, "scam_type", name=name, confidence=conf,
               strength_word=strength, curated=curated,
               provenance=[{"doc_id": d} for d in docs])
        for d in docs:
            g.edge(pid, d, "CITED_IN")

    for shop_id, (name, region, suspect, intel_id) in SHOPS.items():
        g.node(shop_id, "repair_shop", name=name, region=region,
               suspect=suspect)
        if intel_id:
            g.node(intel_id, "suspect_shop",
                   name=f"{name} — suspected billing fraud",
                   confidence=0.55 if suspect else 0.40,
                   strength_word="suspected" if suspect else "possible",
                   curated=suspect, refers_to=shop_id)
            g.edge(intel_id, shop_id, "REFERS_TO")

    for clin_id, (name, suspect) in CLINICS.items():
        g.node(clin_id, "clinic", name=name, suspicious=suspect)
    for atty_id, (name, suspect) in ATTORNEYS.items():
        g.node(atty_id, "attorney", name=name, suspicious=suspect)
    for shell_id, name in SHELLS.items():
        g.node(shell_id, "shell_company", name=name)

    # kickback edges: suspect shop -> shell (PAID_VIA)
    for shop_id, (_n, _r, suspect, _i) in SHOPS.items():
        if not suspect:
            continue
        shell = _shell_for_shop(shop_id)
        g.edge(shop_id, shell, "PAID_VIA",
               amount=rng.choice([78400, 61200, 93300, 118400, 54700]))

    # ── claimants: anchors + ring members + clean population ──
    _anchor_claimants(g)
    for ring_id, members in ring_members.items():
        for m in members:
            if m in g.nodes:      # anchor claimant already created
                continue
            g.node(m, "claimant", known_fraud=True,
                   risk_flags=["member_of_ring"])
    for ring_id, members in ring_members.items():
        _ring_edges(g, ring_id, members)

    clean_count = 300 - len(g.nodes)
    _clean_claimants(g, clean_count)

    return g.payload()


def _anchor_claimants(g: Graph) -> None:
    for i in range(101, 115):
        g.node(f"CL-{i}", "claimant", known_fraud=False, risk_flags=[])
    for cid, known in [("CL-201", True), ("CL-202", True), ("CL-203", True),
                       ("CL-207", True)]:
        g.node(cid, "claimant", known_fraud=known, risk_flags=[])
    # baseline attribute links (identical to data/entities.json)
    for i in range(101, 115):
        g.edge(f"CL-{i}", f"PH-{i}", "USES_PHONE")
        g.edge(f"CL-{i}", f"ADDR-{i}", "LIVES_AT")
    g.node("PH-900", "phone", number="(713) 555-0190")
    g.node("ADDR-550", "address", zip="77017", street="4102 Bellfort St")
    g.edge("CL-106", "PH-900", "USES_PHONE")
    g.edge("CL-201", "PH-900", "USES_PHONE")
    g.edge("CL-202", "PH-900", "USES_PHONE")
    g.edge("CL-201", "ADDR-550", "LIVES_AT")
    g.edge("CL-202", "ADDR-550", "LIVES_AT")
    g.edge("CL-203", "ADDR-550", "LIVES_AT")
    g.edge("CL-111", "ADDR-550", "LIVES_AT")
    for cid in ("CL-106", "CL-111", "CL-201", "CL-202", "CL-203"):
        g.edge(cid, "SHOP-77", "REPAIRED_AT")
    for cid in ("CL-101", "CL-104"):
        g.edge(cid, "SHOP-12", "REPAIRED_AT")
    for i in range(101, 115):
        g.node(f"PH-{i}", "phone", number=f"(555) 01{i % 100:02d}-{i}")
        g.node(f"ADDR-{i}", "address", zip=str(77000 + i),
               street=f"{100 + i} Anchor St")


def _ring_edges(g: Graph, ring_id: str, members: list[str]) -> None:
    rng = g.rng
    phone = f"PH-9{rng.randint(1, 4)}"
    addr = f"ADDR-9{rng.randint(1, 4)}"
    if phone not in g.nodes:
        g.node(phone, "phone", number=f"(800) 555-9{rng.randint(100, 999)}")
    if addr not in g.nodes:
        g.node(addr, "address", zip=str(rng.randint(30000, 90000)),
               street=f"{rng.randint(100, 9999)} Ring Rd")
    shop = _shop_of_ring(ring_id)
    clinic = _clinic_of_ring(ring_id)
    atty = _atty_of_ring(ring_id)
    roles = ["driver", "organizer", "straw_policy", "claimant", "claimant",
             "claimant", "spotter", "claimant"]
    for m in members:
        role = rng.choice(roles)
        g.edge(m, ring_id, "MEMBER_OF", role=role,
               strength=rng.choice(["confirmed", "strongly_suspected",
                                    "suspected"]))
        g.edge(m, phone, "USES_PHONE")
        g.edge(m, addr, "LIVES_AT")
        if shop:
            g.edge(m, shop, "REPAIRED_AT",
                   days_before=rng.randint(3, 60))
        if clinic and rng.random() < 0.8:
            g.edge(m, clinic, "TREATED_AT")
        if atty and rng.random() < 0.5:
            g.edge(m, atty, "REPRESENTED_BY")


def _clean_claimants(g: Graph, count: int) -> None:
    rng = g.rng
    start = 701
    clean_shops = [s for s, (_n, _r, sus, _i) in SHOPS.items() if not sus]
    clean_clinics = [c for c, (_n, sus) in CLINICS.items() if not sus]
    clean_attys = [a for a, (_n, sus) in ATTORNEYS.items() if not sus]
    for k in range(count):
        cid = f"CL-{start + k}"
        g.node(cid, "claimant", known_fraud=False, risk_flags=[])
        g.node(f"PH-{start + k}", "phone",
               number=f"({rng.randint(200, 999)}) 555-{rng.randint(1000, 9999)}")
        g.node(f"ADDR-{start + k}", "address",
               zip=str(rng.randint(10000, 99999)),
               street=f"{rng.randint(10, 9999)} {rng.choice(['Oak', 'Main', 'Elm', 'Cedar', 'Maple', 'Pine'])} {rng.choice(['St', 'Ave', 'Dr', 'Ln'])}")
        g.edge(cid, f"PH-{start + k}", "USES_PHONE")
        g.edge(cid, f"ADDR-{start + k}", "LIVES_AT")
        if rng.random() < 0.55:
            g.edge(cid, rng.choice(clean_shops), "REPAIRED_AT",
                   days_before=rng.randint(1, 300))
        if rng.random() < 0.2:
            g.edge(cid, rng.choice(clean_clinics), "TREATED_AT")
        if rng.random() < 0.1:
            g.edge(cid, rng.choice(clean_attys), "REPRESENTED_BY")
    # innocent shared households (distractor: shared attributes, no fraud)
    for k in range(0, count - 1, 31):
        c1, c2 = f"CL-{start + k}", f"CL-{start + k + 1}"
        shared_phone = f"PH-{start + k}"
        g.edge(c2, shared_phone, "USES_PHONE")


def _ring_provenance(ring_id: str) -> list[dict]:
    docs = {
        "RING-SOUTH-1": [("SIU-01", "SIU Investigation: Staged Rear-Ends "
                          "in South Houston", "Special Investigations Unit "
                          "— Region 3", "2026-03-10"),
                         ("AUD-001", "Post-Payment Audit: QuickFix Auto — "
                          "Ghost Repairs", "Claims Audit & Recovery — "
                          "Region 3", "2026-04-01"),
                         ("SIU-05", "SIU Closing Memo: Ring-South-1 "
                          "Prosecution Referral", "Special Investigations "
                          "Unit — Region 3", "2026-05-01")],
        "RING-MIDWEST-1": [("SIU-02", "Medical-Mill Investigation: Midwest "
                            "PIP Abuse Pattern", "Special Investigations "
                            "Unit — Region 2", "2026-01-22")],
        "RING-NORTHEAST-1": [("SIU-03", "SIU Alert: Northeast Premium "
                              "Diversion Ring", "Special Investigations "
                              "Unit — Region 1", "2026-03-28")],
        "RING-SE-1": [("SIU-07", "SIU Report: Tow-Steering Corridor on "
                       "I-285", "Special Investigations Unit — Region 4",
                       "2026-02-27")],
        "RING-WEST-1": [("SIU-08", "SIU Investigation: Ghost Repairs in "
                         "the San Gabriel Valley", "Special Investigations "
                         "Unit — Region 5", "2026-03-05")],
        "RING-DFW-1": [("SIU-10", "SIU Alert: Swoop-and-Squat Cell on "
                        "FM-635", "Special Investigations Unit — Region 3",
                        "2026-03-19")],
        "RING-PHX-1": [("SIU-09", "SIU Report: Rental-Receipt Inflation in "
                        "Maricopa County", "Special Investigations Unit — "
                        "Region 5", "2026-02-11")],
        "RING-MW-2": [("SIU-12", "SIU Investigation: Chiro-Referral Cell in "
                       "Indianapolis", "Special Investigations Unit — "
                       "Region 2", "2026-04-09")],
    }
    return [{"doc_id": d, "title": t, "publisher": p, "date": dt}
            for d, t, p, dt in docs.get(ring_id, [])]


def _shop_of_ring(ring_id: str) -> str | None:
    for rid, _n, _r, _c, _s, _e, _cu, _p, through, _m in RINGS:
        if rid == ring_id:
            shops = [e for e, _role in through if e.startswith("SHOP")]
            return shops[0] if shops else None
    return None


def _clinic_of_ring(ring_id: str) -> str | None:
    for rid, _n, _r, _c, _s, _e, _cu, _p, through, _m in RINGS:
        if rid == ring_id:
            clinics = [e for e, _role in through if e.startswith("CLIN")]
            return clinics[0] if clinics else None
    return None


def _atty_of_ring(ring_id: str) -> str | None:
    for rid, _n, _r, _c, _s, _e, _cu, _p, through, _m in RINGS:
        if rid == ring_id:
            attys = [e for e, _role in through if e.startswith("ATTY")]
            return attys[0] if attys else None
    return None


def _shell_for_shop(shop_id: str) -> str:
    return {"SHOP-77": "SHELL-01", "SHOP-12": "SHELL-04",
            "SHOP-45": "SHELL-05", "SHOP-88": "SHELL-04"}.get(shop_id,
                                                              "SHELL-01")


# ── fraud memos ──────────────────────────────────────────────────────

def generate_fraud_memos(seed: int) -> list[dict]:
    rng = random.Random(seed)
    memos = {m["doc_id"]: m for m in _ANCHOR_MEMOS}
    new = [
        ("SIU-06", "SIU Report: Premium Diversion — Policy Leakage Review",
         "2026-04-15", "Special Investigations Unit — Region 1",
         "An unlicensed agent redirected premiums from 32 small businesses "
         "into a personal account; none reached the carrier. Straw policies "
         "were issued 14 days before losses on multiple claims. The fake "
         "agency operated from a virtual office with no physical presence. "
         "SIU confirmed 6 of these policies generated claims totalling "
         "$540,000, none of which were validly insured. Premium diversion "
         "is confirmed as an organized enterprise with synthetic identities "
         "involved — the same compromised SSN patterns as NB-002."),
        ("SIU-07", "SIU Report: Tow-Steering Corridor on I-285",
         "2026-02-27", "Special Investigations Unit — Region 4",
         "Runners steer towed vehicles from I-285 accident scenes to "
         "Certified Auto Care. Suspected tow-referral kickbacks of "
         "$500-$1,200 per vehicle are paid through fictitious towing "
         "administration fees. 48 towed vehicles in 6 months all came from "
         "the same 4-mile stretch. Ambulance chaser attorneys sign retainers "
         "within hours of each incident. This tow steering pattern is "
         "suspected to involve at least 12 claimants and an estimated "
         "$296,000 in inflated payouts."),
        ("SIU-08", "SIU Investigation: Ghost Repairs in the San Gabriel "
         "Valley", "2026-03-05", "Special Investigations Unit — Region 5",
         "Ace Collision & Paint submits ghost-repair invoices: parts billed "
         "as replaced OEM were never installed — vehicles examined after "
         "repair show original parts painted over. Ghost repairs account for "
         "an estimated 31% of sampled invoices, roughly $348,000 in "
         "exposure. A parts vendor with no physical inventory supplied the "
         "invoices. 12 claimants are suspected members of an organized "
         "ghost-repair ring."),
        ("SIU-09", "SIU Report: Rental-Receipt Inflation in Maricopa County",
         "2026-02-11", "Special Investigations Unit — Region 5",
         "Claimants submitted rental-car receipts for vehicles never "
         "rented. Rental reimbursement claims average $3,100 vs a market "
         "median of $1,150. Receipts are fabricated by a single vendor and "
         "billed through a shell company. The rental-reimbursement inflation "
         "pattern is possible organized fraud involving 10 claimants and "
         "estimated exposure of $143,000."),
        ("SIU-10", "SIU Alert: Swoop-and-Squat Cell on FM-635",
         "2026-03-19", "Special Investigations Unit — Region 3",
         "A swoop-and-squat cell stages low-speed collisions on FM-635 in "
         "Dallas. Phantom vehicle damage and jump-in passengers inflate "
         "bodily-injury demands. 10 claimants are linked to Metro Body DFW, "
         "which produces phantom repair estimates. Estimated exposure "
         "$187,000. The staged accident pattern mirrors Ring-South-1 with "
         "possible links to the same attorney network."),
        ("SIU-11", "SIU Bulletin: Cross-Ring Facilitator Overlap",
         "2026-04-22", "Special Investigations Unit — National",
         "Link analysis confirms facilitator overlap between rings: the "
         "South Texas ring, the DFW cell, and the Southeast corridor share "
         "attorney networks and shell-company administrators. Phantom "
         "vehicle claims, inflated medical billing, and tow referral "
         "kickbacks appear together in the worst clusters. Suspected total "
         "cross-ring exposure exceeds $1.4 million."),
        ("SIU-12", "SIU Investigation: Chiro-Referral Cell in Indianapolis",
         "2026-04-09", "Special Investigations Unit — Region 2",
         "A chiropractic referral cell steers claimants to Circle City "
         "Chiro Clinic within 24 hours of each incident. Pre-existing "
         "injury conditions are not disclosed at policy inception. "
         "Excessive treatment billing shows 35+ visits per claim vs a "
         "median of 12. The medical-mill pattern matches the Midwest ring; "
         "10 claimants, estimated exposure $231,000, paid as fictitious "
         "administrative fees through a shell company."),
        ("NB-003", "NICB Advisory: Ghost Repair Networks in Urban Corridors",
         "2026-03-25", "National Insurance Crime Bureau (NICB)",
         "NICB is tracking ghost-repair networks where parts billed as "
         "replaced OEM are never installed. Photographic evidence from "
         "social media shows no evidence of bumper replacement. Parts "
         "invoices trace to vendors with no physical inventory. The ghost "
         "repairs pattern is suspected nationwide, with the heaviest "
         "concentration on the West Coast."),
        ("NB-004", "NICB Advisory: Rental Reimbursement Schemes",
         "2026-04-03", "National Insurance Crime Bureau (NICB)",
         "Rental reimbursement inflation is a possible emerging scheme: "
         "claimants bill for rental vehicles never rented, using fabricated "
         "receipts from a common vendor. Average claim $3,100 vs $1,150 "
         "market median. NICB recommends verifying rental vendor invoices "
         "directly and flagging repeated vendor ids."),
        ("NB-005", "NICB Bulletin: Attorney Solicitation Rings",
         "2026-03-08", "National Insurance Crime Bureau (NICB)",
         "Suspected ambulance chaser attorneys solicit signed retainers "
         "within hours of incidents, often through runners at tow yards. "
         "These attorneys are linked to medical mills and shell-company "
         "billing in prior NICB bulletins. Retainer-solicitation is a "
         "strongly suspected enabler of staged collision and PIP abuse."),
        ("AUD-002", "Post-Payment Audit: Certified Auto Care — Steering "
         "Fees", "2026-04-18", "Claims Audit & Recovery — Region 4",
         "Audit of Certified Auto Care reveals 'towing administration "
         "fees' totalling $61,200 paid to Peachtree Towing Admin LLC, a "
         "shell with no employees. 48 towed vehicles in 6 months came from "
         "one I-285 corridor. Tow referral kickbacks are suspected; the "
         "shop shows unusual claim frequency for the region."),
        ("AUD-003", "Post-Payment Audit: Ace Collision — Vendor Chain",
         "2026-05-02", "Claims Audit & Recovery — Region 5",
         "Parts invoices from West Coast Parts Supply LLC resolve to a "
         "residential mailbox store. 31% of sampled invoices billed "
         "replacement parts that were never installed. Ghost repairs are "
         "confirmed on 9 of 29 sampled claims. Exposure $348,000."),
        ("AUD-004", "Audit Referral: South Houston Medical Billing",
         "2026-05-12", "Medical Bill Review — Region 3",
         "South Houston Spine & Rehab bills 40+ visits per soft-tissue "
         "claim vs a market median of 12. MRI costs average $4,200 vs "
         "$1,800 market. Chiropractic mill referrals processed the same "
         "claimants within 24 hours of each staged incident. Inflated "
         "medical billing is suspected across the ring's 16 members."),
        ("AUD-005", "Audit Report: Shell Company Fee Flows",
         "2026-05-20", "Financial Crimes Unit",
         "Fee flows through four shell companies — Gulf Coast Logistics, "
         "Peachtree Towing Admin, West Coast Parts Supply, and Circle City "
         "Admin Services — total $312,000 over 12 months. All four share a "
         "registered agent and resolve to mailbox storefronts. Ghost "
         "repairs and tow referral kickbacks are funded through these "
         "shells."),
        ("LEG-001", "Legal Bulletin: Retainer Solicitation — Region 4",
         "2026-03-30", "Legal Operations",
         "Attorney R. Berman signed retainers for 48 I-285 towed-vehicle "
         "claimants within 48 hours of each loss. Represented claims settle "
         "roughly 25% higher than unrepresented ones. Ambulance chaser "
         "activity is a primary enabler of the tow-steering corridor."),
    ]
    for doc in new:
        memos[doc[0]] = {"doc_id": doc[0], "title": doc[1], "date": doc[2],
                         "publisher": doc[3], "text": doc[4]}
    return [memos[k] for k in sorted(memos)]


# ═════════════════════════════════════════════════════════════════════
# COST — driver tree + causal event layer
# ═════════════════════════════════════════════════════════════════════

_COST_BASE = json.loads((DATA_DIR / "cost_entities.json").read_text())
_COST_MEMOS = json.loads((DATA_DIR / "memos.json").read_text())

NEW_COST_DRIVERS = [
    ("rental_costs", "Rental cost inflation",
     "Rental-reimbursement rates rose +11% in 2024 as rental fleets shrank; "
     "rental duration on repair claims grew from 9.1 to 12.4 days.",
     ["+11% rates", "9.1 -> 12.4 days"], "rental fleet analytics",
     [("M-10", "Rental & Towing Cost Review",
       "Rental reimbursement rates rose +11% in 2024 and average rental "
       "duration grew from 9.1 to 12.4 days per repair claim")],
     "severity", "auto_pd", "ALL", 0.35, "+", 1, False),
    ("labor_rates", "Body-shop labor rates",
     "Dealer labor rates rose +7.8% in 2024Q4 alone; labor now accounts for "
     "41% of the average collision repair ticket.",
     ["+7.8% 2024Q4", "41% of ticket"], "repair-order analytics",
     [("M-11", "Repair Labor Rate Survey",
       "Dealer labor rates rose +7.8% in 2024Q4 and labor now accounts for "
       "41% of the average collision repair ticket")],
     "severity", "auto_pd", "ALL", 0.40, "+", 1, False),
    ("used_car_values", "Used-car market volatility",
     "Used-car values fell -12% through 2025, making total-loss payouts "
     "less volatile but raising claims frequency on financed vehicles.",
     ["-12% values"], "valuation analytics",
     [("M-12", "Valuation Trends Memo",
       "Used-car values fell -12% through 2025, modestly easing total-loss "
       "severity while frequency on financed vehicles edged up")],
     "frequency", "auto_pd", "ALL", 0.25, "+", 2, False),
    ("hail_corridor", "Southwest hail season (recurrent)",
     "The 2025Q3 hail season struck the Southwest corridor twice — a "
     "significant spike in auto-pd frequency of +9% for one quarter.",
     ["+9% 2025Q3"], "cat event reports",
     [("M-13", "Catastrophe Event Report — 2025Q3 Hail",
       "The 2025Q3 hail season hit the Southwest corridor twice, lifting "
       "auto-pd frequency about +9% for one quarter")],
     "frequency", "auto_pd", "Southwest", 0.45, "+", 0, False),
    ("telehealth_billing", "Telehealth billing abuse",
     "Telehealth-based PT billing grew 4x since 2024; 18% of billed "
     "telehealth sessions on BI claims lack a supporting clinical note.",
     ["4x growth", "18% unsubstantiated"], "medical bill review",
     [("M-14", "Medical Bill Review Quarterly",
       "Telehealth-based PT billing grew 4x since 2024 and 18% of billed "
       "sessions on BI claims lack a supporting clinical note")],
     "severity", "auto_bi", "ALL", 0.30, "+", 1, False),
    ("attorney_advertising", "Attorney advertising intensity",
     "Attorney ad spend on BI claims rose +26% YoY in the Northeast; "
     "represented-claim share reached 61% there.",
     ["+26% ad spend", "61% represented"], "media monitoring",
     [("M-15", "Legal Media Monitor",
       "Attorney advertising spend on BI claims rose +26% year over year; "
       "Northeast represented-claim share reached 61%")],
     "severity", "auto_bi", "Northeast", 0.35, "+", 1, False),
]

COST_EVENTS = [
    ("EVT-01", "Hurricane landfall — South", "2024Q3", "South", "auto_pd",
     "cat_weather", 0.70),
    ("EVT-02", "Polar vortex — Midwest", "2025Q1", "Midwest", "auto_pd",
     "winter_weather", 0.60),
    ("EVT-03", "OEM parts supply disruption", "2024Q2", "ALL", "auto_pd",
     "supply_chain", 0.55),
    ("EVT-04", "Northeast lawsuit spike", "2025Q2", "Northeast", "auto_bi",
     "litigation_climate", 0.55),
    ("EVT-05", "Southwest hail season", "2025Q3", "Southwest", "auto_pd",
     "hail_corridor", 0.60),
]


def generate_cost(seed: int, size: str = "full") -> dict:
    g = Graph(random.Random(seed))
    for n in _COST_BASE["nodes"]:
        g.node(n["id"], n["type"], **{k: v for k, v in n.items()
                                      if k not in ("id", "type")})
    for e in _COST_BASE["edges"]:
        g.edge(e["a"], e["b"], e["relation"],
               **{k: v for k, v in e.items() if k not in ("a", "b",
                                                          "relation")})
    for did, name, evidence, figures, source, prov, metric, cov, region, \
            weight, direction, lag, curated in NEW_COST_DRIVERS:
        prov_dicts = [{"doc_id": d, "title": t, "quote": q} for d, t, q
                      in prov]
        g.node(did, "driver", name=name, evidence=evidence, figures=figures,
               source=source, provenance=prov_dicts, curated=curated)
        g.edge(did, metric, "IMPACTS", coverage=cov, region=region,
               weight=weight, direction=direction, lag_quarters=lag)
        for p in prov_dicts:
            g.edge(did, p["doc_id"], "CITED_IN")
    for ev_id, name, quarter, region, cov, driver, weight in COST_EVENTS:
        g.node(ev_id, "event", name=name, quarter=quarter, region=region,
               coverage=cov)
        g.edge(ev_id, driver, "CAUSES", weight=weight)
    # CITED_IN for the baseline drivers too
    for n in _COST_BASE["nodes"]:
        for p in n.get("provenance", []):
            g.edge(n["id"], p["doc_id"], "CITED_IN")
    # newsfeed grounding: two baseline drivers cited by external bulletins
    for did, doc, title, quote in [
        ("parts_inflation", "MEDIA-01", "Market Bulletin — OEM Parts Pricing",
         "OEM parts prices remain the primary contributor to repair "
         "severity, with the average parts ticket up +6.1% year over year "
         "as of Q4."),
        ("litigation_climate", "MEDIA-02",
         "Market Watch — Northeast BI Litigation",
         "Represented-claim share in the Northeast reached 61%; litigation "
         "remains a significant regional driver of bodily-injury "
         "severity."),
    ]:
        if did in g.nodes:
            g.nodes[did].setdefault("provenance", []).append(
                {"doc_id": doc, "title": title, "quote": quote})
            g.edge(did, doc, "CITED_IN")
    return g.payload()


def generate_cost_memos(seed: int) -> list[dict]:
    rng = random.Random(seed)
    memos = {m["doc_id"]: m for m in _COST_MEMOS}
    for m in [
        ("M-09", "Quarterly Severity Attribution — Q4",
         "2026-04-20", "Pricing actuarial",
         "Average repair ticket grew +6.1% in Q4. OEM parts prices remain "
         "the primary contributor, with dealer labor rates a major "
         "secondary factor at +7.8%. Rental duration lengthened again — "
         "a significant, persistent cost."),
        ("M-10", "Rental & Towing Cost Review", "2026-05-01",
         "Rental fleet analytics",
         "Rental reimbursement rates rose +11% in 2024 as rental fleets "
         "shrank, a moderate contributor to severity. Rental duration on "
         "repair claims grew from 9.1 to 12.4 days."),
        ("M-11", "Repair Labor Rate Survey", "2026-05-08",
         "Repair-network analytics",
         "Dealer labor rates rose +7.8% in 2024Q4 alone — a major driver of "
         "auto-pd severity. Labor now accounts for 41% of the average "
         "collision repair ticket."),
        ("M-12", "Valuation Trends Memo", "2026-05-15",
         "Valuation analytics",
         "Used-car values fell -12% through 2025, a mild factor: total-loss "
         "severity eased while frequency on financed vehicles edged up."),
        ("M-13", "Catastrophe Event Report — 2025Q3 Hail", "2026-05-20",
         "Cat event reports",
         "The 2025Q3 hail season hit the Southwest corridor twice, lifting "
         "auto-pd frequency about +9% for one quarter — significant but "
         "episodic."),
        ("M-14", "Medical Bill Review Quarterly", "2026-05-25",
         "Medical bill review",
         "Telehealth-based PT billing grew 4x since 2024, a moderate "
         "contributor to BI severity. 18% of billed sessions lack a "
         "supporting clinical note."),
        ("M-15", "Legal Media Monitor", "2026-06-01",
         "Media monitoring",
         "Attorney advertising spend on BI claims rose +26% year over "
         "year; Northeast represented-claim share reached 61%. Litigation "
         "climate remains a significant regional driver."),
        ("M-16", "Actuarial Trend Selection Memo — Q2", "2026-06-05",
         "Pricing actuarial",
         "Medical care CPI continues to outpace general inflation; medical "
         "inflation remains the dominant driver of BI severity "
         "countrywide. Litigation climate is major in the Northeast."),
        ("M-17", "Supply Chain & Cycle Time Review", "2026-06-10",
         "Cycle-time analytics",
         "Parts delivery delays peaked at 9.1 days in 2024Q2 and remain at "
         "6.3 days. Supplement handling adds roughly $180 per claim — a "
         "significant, persistent contributor to auto-pd severity."),
        ("MEDIA-01", "Market Bulletin — OEM Parts Pricing", "2026-06-15",
         "Market bulletin — external newsfeed",
         "Tier-one suppliers announced another quarterly increase: OEM "
         "parts prices remain the primary contributor to repair severity, "
         "with the average parts ticket up +6.1% year over year as of "
         "Q4. Analysts expect the pass-through to persist into 2026."),
        ("MEDIA-02", "Market Watch — Northeast BI Litigation", "2026-06-18",
         "Market watch — external newsfeed",
         "Represented-claim share in the Northeast reached 61%, and "
         "attorney advertising spend keeps rising. Litigation remains a "
         "significant regional driver of bodily-injury severity — "
         "insurers should price the corridor accordingly."),
    ]:
        memos[m[0]] = {"doc_id": m[0], "title": m[1], "date": m[2],
                       "publisher": m[3], "text": m[4]}
    return [memos[k] for k in sorted(memos)]


# ═════════════════════════════════════════════════════════════════════
# PORTFOLIO — lineage graph + instance journey layer
# ═════════════════════════════════════════════════════════════════════

_PF_BASE = json.loads((DATA_DIR / "portfolio_entities.json").read_text())
_PF_MEMOS = json.loads((DATA_DIR / "portfolio_memos.json").read_text())

NEW_PF_SIGNALS = [
    # id, name, stage, curated, evidence, figures, source
    ("submission_velocity", "Rush submission surge", "submission", False,
     "Rush quotes rose 3.1x in 2024Q4 as brokers raced year-end renewals",
     ["3.1x Q4 rush quotes"], "warehouse: submission rollup"),
    ("broker_latency", "Broker response latency", "submission", False,
     "Average broker response time grew from 6 to 11 days after the "
     "consolidation wave", ["6 -> 11 days"], "warehouse: cycle time"),
    ("uw_staffing", "UW capacity strain", "underwriting", False,
     "Note volume per UW rose 40% while staffing was frozen in 2024Q4",
     ["40% note volume per UW"], "UW workforce report"),
    ("score_drift", "Model score drift", "risk_scoring", False,
     "Post-refresh score drift reached 0.7% of book between model versions",
     ["0.7% drift"], "model governance log"),
    ("deductible_gaming", "Deductible gaming at bind", "bind", False,
     "Deductible-lowering endorsements doubled in Q1 2025 for mid-tier "
     "accounts", ["2x deductible endorsements"], "warehouse: bind rollup"),
    ("premium_override", "Premium override frequency", "bind", False,
     "Downward premium overrides rose 2.2x after the rate filing approval",
     ["2.2x overrides"], "warehouse: bind rollup"),
    ("reserve_cycles", "Reserve cycle manipulation", "claim", False,
     "Reserve increase frequency fell 28% while settlement leakage stayed "
     "flat — signs of reserve suppression", ["-28% reserve increases"],
     "warehouse: reserve history"),
    ("attorney_engagement", "Attorney engagement at settlement",
     "settlement", False,
     "Claimant attorney representation at settlement rose from 22% to 31%",
     ["22% -> 31% represented"], "warehouse: settlement rollup"),
    ("audit_findings", "Internal audit findings rate", "settlement", False,
     "Audit exception rate on settlement payments reached 9.4% in 2025Q2",
     ["9.4% exceptions"], "internal audit"),
    ("inspection_quality", "Inspection report quality", "site_inspection",
     False,
     "Inspection reports flagged incomplete in 18% of sampled files",
     ["18% incomplete reports"], "inspection QA sample"),
]

PF_EVENTS = [
    ("EVT-P1", "Gulf hurricane exposure spike", "2024Q3",
     "late_fnol", 0.60),
    ("EVT-P2", "UW staffing freeze", "2024Q4", "uw_staffing", 0.65),
    ("EVT-P3", "Broker consolidation wave", "2025Q1", "broker_latency", 0.55),
    ("EVT-P4", "Risk model refresh", "2025Q2", "score_drift", 0.55),
    ("EVT-P5", "Rate filing approval", "2025Q3", "premium_override", 0.60),
]

# leverage ground truth: (segment, winning signal, weight, exposure)
LEVERAGE_TRUTH = [
    ({"broker": "BRO-W", "class_code": "ALL", "region": "ALL"},
     "reserve_adequacy", 0.65, 0.85),
    ({"broker": "ALL", "class_code": "5437", "region": "ALL"},
     "risk_score_override", 0.72, 0.95),
]


def generate_portfolio(seed: int, size: str = "full") -> dict:
    rng = random.Random(seed)
    g = Graph(rng)
    for n in _PF_BASE["nodes"]:
        g.node(n["id"], n["type"], **{k: v for k, v in n.items()
                                      if k not in ("id", "type")})
    for e in _PF_BASE["edges"]:
        g.edge(e["a"], e["b"], e["relation"],
               **{k: v for k, v in e.items() if k not in ("a", "b",
                                                          "relation")})
    for n in _PF_BASE["nodes"]:
        for p in n.get("provenance", []):
            g.edge(n["id"], p["doc_id"], "CITED_IN")
    # newsfeed grounding: two baseline signals cited by industry bulletins
    for sid, doc, title, quote in [
        ("reserve_adequacy", "MEDIA-01",
         "Industry News — Reserve Adequacy Watch",
         "Regulators flagged reserve adequacy as the top watch item; "
         "carriers with low reserve adequacy are seeing settlement "
         "leakage of up to 12% of reserves."),
        ("risk_score_override", "MEDIA-02",
         "Industry News — Risk-Model Override Coverage",
         "Downward risk-score overrides near 2.2x the portfolio average "
         "on class 5437 correlate with loss-ratio spikes one to two "
         "quarters later."),
    ]:
        if sid in g.nodes:
            g.nodes[sid].setdefault("provenance", []).append(
                {"doc_id": doc, "title": title, "quote": quote})
            g.edge(sid, doc, "CITED_IN")

    for sid, name, stage, curated, evidence, figures, source in NEW_PF_SIGNALS:
        g.node(sid, "signal", stage=stage, name=name, curated=curated,
               evidence=evidence, figures=figures, source=source)
        g.edge(sid, stage, "PERTAINS_TO")

    for ev_id, name, quarter, signal, weight in PF_EVENTS:
        g.node(ev_id, "event", name=name, quarter=quarter)
        g.edge(ev_id, signal, "CAUSES", weight=weight)

    # PREDISPOSES edges for the new signals (with exposure props)
    new_predisposes = [
        ("submission_velocity", "bind_conversion", "ALL", "West", 0.30, "-",
         0, 0.35, "PFM-104"),
        ("broker_latency", "bind_conversion", "ALL", "ALL", 0.32, "-", 1,
         0.40, "PFM-105"),
        ("uw_staffing", "pricing_inadequacy", "ALL", "ALL", 0.38, "+", 0,
         0.45, "PFM-106"),
        ("score_drift", "loss_ratio", "5437", "ALL", 0.40, "+", 1, 0.50,
         "PFM-107"),
        ("deductible_gaming", "margin_contribution", "ALL", "ALL", 0.34,
         "-", 1, 0.42, "PFM-108"),
        ("premium_override", "margin_contribution", "ALL", "ALL", 0.36, "-",
         1, 0.60, "PFM-109"),
        ("reserve_cycles", "leakage_pct", "ALL", "ALL", 0.38, "+", 1, 0.55,
         "PFM-110"),
        ("attorney_engagement", "leakage_pct", "ALL", "ALL", 0.42, "+", 0,
         0.58, "PFM-111"),
        ("audit_findings", "leakage_pct", "ALL", "ALL", 0.40, "+", 0, 0.50,
         "PFM-112"),
        ("inspection_quality", "pricing_inadequacy", "ALL", "ALL", 0.30,
         "+", 1, 0.33, "PFM-113"),
    ]
    for sid, outcome, cov, region, weight, direction, lag, exposure, doc \
            in new_predisposes:
        g.edge(sid, outcome, "PREDISPOSES", coverage=cov, region=region,
               weight=weight, direction=direction, lag_quarters=lag,
               exposure=exposure, stage=region_to_stage(sid),
               provenance=[{"doc_id": doc}])
        g.edge(sid, doc, "CITED_IN")

    # raise the winning levers so ground truth holds for every segment
    _tune_levers(g, "reserve_adequacy", "leakage_pct", 0.65, 0.85,
                 "ALL", "ALL")
    _tune_levers(g, "risk_score_override", "loss_ratio", 0.72, 0.95,
                 "ALL", "5437")

    # instance journey layer
    _instance_layer(g, "full" if size == "full" else "small")
    return g.payload()


def region_to_stage(sid: str) -> str:
    stage = next((n["stage"] for n in _PF_BASE["nodes"]
                  if n["id"] == sid), None)
    return stage or "submission"


def _tune_levers(g: Graph, signal: str, outcome: str, weight: float,
                 exposure: float, region: str, cov: str) -> None:
    for e in g.edges:
        if e["relation"] == "PREDISPOSES" and e["a"] == signal \
                and e["b"] == outcome:
            e["weight"] = max(e.get("weight", 0), weight)
            e["exposure"] = max(e.get("exposure", 0), exposure)
            e["region"] = region
            e["coverage"] = cov


def _instance_layer(g: Graph, size: str) -> None:
    rng = g.rng
    n_sub = 30 if size == "full" else 12
    brokers = ["BRO-W", "BRO-A", "BRO-M", "BRO-C"]
    classes = ["5437", "5438", "5602", "5620"]
    regions = ["West", "Midwest", "Northeast", "Southeast"]
    stage_ids = ["submission", "underwriting", "risk_scoring",
                 "site_inspection", "bind", "claim", "settlement"]

    subs = []
    for i in range(1, n_sub + 1):
        sid = f"SUB-{i:03d}"
        broker = brokers[i % len(brokers)]
        cls = classes[i % len(classes)]
        region = regions[i % len(regions)]
        g.node(sid, "submission", broker=broker, class_code=cls,
               region=region)
        g.edge(sid, "submission", "AT_STAGE")
        subs.append((sid, broker, cls, region))
        incomplete = (broker == "BRO-W" and i % 2 == 0)
        if incomplete:
            g.edge(sid, "exposure_completeness", "EXHIBITS")
        if i % 5 == 0:
            g.edge(sid, "submission_velocity", "EXHIBITS")
        if i % 7 == 0:
            g.edge(sid, "broker_latency", "EXHIBITS")

    binds = []
    for i, (sid, broker, cls, region) in enumerate(subs):
        if i % 6 == 0:           # ~83% bind conversion
            continue
        bid = f"BIND-{i + 1:03d}"
        g.node(bid, "bind", broker=broker, class_code=cls, region=region)
        g.edge(sid, bid, "FLOWS_TO")
        g.edge(bid, "bind", "AT_STAGE")
        binds.append((bid, broker, cls, region, sid))
        if cls == "5437" and i % 3 == 0:
            g.edge(bid, "risk_score_override", "EXHIBITS")
        if i % 9 == 0:
            g.edge(bid, "deductible_gaming", "EXHIBITS")

    claims = []
    for i, (bid, broker, cls, region, sid) in enumerate(binds):
        if i % 5 == 0:
            continue
        cid = f"CLM-{i + 1:03d}"
        g.node(cid, "claim", broker=broker, class_code=cls, region=region,
               fnol_days=rng.choice([1, 2, 3, 9, 14, 21]))
        g.edge(bid, cid, "FLOWS_TO")
        g.edge(cid, "claim", "AT_STAGE")
        claims.append((cid, broker, cls, region))
        late = cid == "CLM-015" or (cls == "5437" and cid.endswith(("08",
                                                                     "18")))
        if late or g.nodes[cid]["fnol_days"] >= 9:
            g.edge(cid, "late_fnol", "EXHIBITS")
        if cid == "CLM-015":        # planted: the demo journey claim
            g.edge(cid, "reserve_adequacy", "EXHIBITS")
        elif i % 4 == 0:
            g.edge(cid, "reserve_adequacy", "EXHIBITS")
        if i % 6 == 0:
            g.edge(cid, "reserve_cycles", "EXHIBITS")

    for i, (cid, broker, cls, region) in enumerate(claims):
        if i % 4 == 0:
            continue
        stid = f"SETT-{i + 1:03d}"
        g.node(stid, "settlement", broker=broker, class_code=cls,
               region=region, leakage_pct=round(rng.uniform(2, 19), 1))
        g.edge(cid, stid, "FLOWS_TO")
        g.edge(stid, "settlement", "AT_STAGE")
        if g.nodes[stid]["leakage_pct"] >= 10:
            g.edge(stid, "settlement_slowness", "EXHIBITS")
        if i % 5 == 0:
            g.edge(stid, "attorney_engagement", "EXHIBITS")
        if i % 7 == 0:
            g.edge(stid, "audit_findings", "EXHIBITS")


def generate_portfolio_memos(seed: int) -> list[dict]:
    memos = {m["doc_id"]: m for m in _PF_MEMOS}
    for m in [
        ("PFM-104", "Q4 Submission Rush Analysis", "2024-Q4",
         "Distribution analytics",
         "Rush quotes rose 3.1x in 2024Q4 as brokers raced year-end "
         "renewals. Rush submissions convert at 41% vs 68% for the "
         "portfolio — a significant drag on bind_conversion."),
        ("PFM-105", "Broker Response Latency Review", "2025-Q1",
         "Operations",
         "Average broker response time grew from 6 to 11 days after the "
         "consolidation wave. Longer latency shows a moderate negative "
         "relationship with bind conversion across all regions."),
        ("PFM-106", "UW Capacity & Note Volume Report", "2025-Q1",
         "Underwriting leadership",
         "Note volume per UW rose 40% while staffing was frozen in "
         "2024Q4. Hedging phrasing in UW notes is a primary signal of "
         "pricing inadequacy under capacity strain."),
        ("PFM-107", "Model Governance — Drift Log", "2025-Q2",
         "Model risk management",
         "Post-refresh score drift reached 0.7% of book between model "
         "versions. Drift concentrates in class 5437 where overrides "
         "are most frequent."),
        ("PFM-108", "Bind Endorsement Analysis", "2025-Q1",
         "Pricing actuarial",
         "Deductible-lowering endorsements doubled in Q1 2025 for "
         "mid-tier accounts, a meaningful negative contribution to "
         "margin_contribution."),
        ("PFM-109", "Premium Override Post-Filing Review", "2025-Q3",
         "Pricing actuarial",
         "Downward premium overrides rose 2.2x after the rate filing "
         "approval. Overrides are a significant drag on "
         "margin_contribution with a one-quarter lag."),
        ("PFM-110", "Reserve History Deep Dive", "2025-Q2",
         "Actuarial reserving",
         "Reserve increase frequency fell 28% while settlement leakage "
         "stayed flat — signs of reserve suppression that later shows up "
         "as leakage_pct."),
        ("PFM-111", "Settlement Attorney Engagement Review", "2025-Q2",
         "Claims legal ops",
         "Claimant attorney representation at settlement rose from 22% "
         "to 31%. Represented settlements leak a major share of reserve."),
        ("PFM-112", "Internal Audit — Payment Exceptions", "2025-Q2",
         "Internal audit",
         "Audit exception rate on settlement payments reached 9.4% in "
         "2025Q2 — a significant indicator of settlement-stage leakage."),
        ("PFM-113", "Inspection QA Sample", "2025-Q1", "Field operations",
         "Inspection reports flagged incomplete in 18% of sampled files, "
         "a modest contributor to pricing inadequacy where waived "
         "inspection flags also appear."),
        ("PFM-114", "Broker BRO-W Margin Attribution", "2025-Q3",
         "Portfolio analytics",
         "BRO-W's margin shortfall traces to the claim stage: low "
         "reserve adequacy combined with slow settlements converts "
         "adequate pricing into leakage. The claim-stage lever "
         "dominates the margin thesis."),
        ("PFM-115", "Class 5437 Override Post-Mortem", "2025-Q3",
         "Portfolio analytics",
         "5437's loss-ratio spike traces to systematic risk-score "
         "overrides at binding, compounded by late FNOL reporting. "
         "The override lever dominates for this class."),
        ("MEDIA-01", "Industry News — Reserve Adequacy Watch", "2025-Q4",
         "Industry news service — external newsfeed",
         "Regulators flagged reserve adequacy as the top watch item: "
         "carriers with low reserve adequacy on legacy books are seeing "
         "settlement leakage of up to 12% of reserves. The market "
         "expects the claim-stage reserve lever to dominate margin "
         "debates into next year."),
        ("MEDIA-02", "Industry News — Risk-Model Override Coverage",
         "2025-Q4", "Industry news service — external newsfeed",
         "Audit firms spotlighted downward risk-score overrides in "
         "high-frequency classes: override rates near 2.2x the "
         "portfolio average on class 5437 correlate with loss-ratio "
         "spikes one to two quarters later."),
    ]:
        memos[m[0]] = {"doc_id": m[0], "title": m[1], "date": m[2],
                       "publisher": m[3], "text": m[4]}
    return [memos[k] for k in sorted(memos)]


# ═════════════════════════════════════════════════════════════════════
# GROUND TRUTH manifest
# ═════════════════════════════════════════════════════════════════════

def generate_ground_truth(payloads: dict, seed: int, size: str) -> dict:
    fraud = payloads["fraud"]
    nodes = {n["id"]: n for n in fraud["nodes"]}
    ring_members: dict[str, list[str]] = {}
    for e in fraud["edges"]:
        if e["relation"] == "MEMBER_OF":
            ring_members.setdefault(e["b"], []).append(e["a"])
    se_members = sorted(m for m in ring_members.get("RING-SE-1", [])
                        if m.startswith("CL-3"))
    clean_subjects = sorted(n for n in nodes
                            if n.startswith("CL-70"))
    cost = payloads["cost"]
    pf = payloads["portfolio"]

    gt = {
        "fraud": {
            "rings": {
                "RING-SOUTH-1": {
                    "members": ring_members.get("RING-SOUTH-1", []),
                    "exposure": 687000, "root_pattern": "PATTERN-STAGING-1",
                    "facilitators": ["SHOP-77", "CLIN-01", "ATTY-01",
                                     "SHELL-01"],
                    "cited_docs": ["SIU-01", "AUD-001", "SIU-05"],
                },
                "RING-MIDWEST-1": {"members": ring_members.get("RING-MIDWEST-1", []),
                                   "exposure": 412000,
                                   "root_pattern": "PATTERN-PIP-1",
                                   "facilitators": ["CLIN-02", "ATTY-02",
                                                    "SHELL-02"]},
                "RING-NORTHEAST-1": {"members": ring_members.get("RING-NORTHEAST-1", []),
                                     "exposure": 540000,
                                     "root_pattern": "PATTERN-ID-1",
                                     "facilitators": ["ATTY-03",
                                                      "SHELL-03"]},
            },
            "assignments": {
                "root_cause_cl201": {
                    "subject": "CL-201", "ring": "RING-SOUTH-1",
                    "root_pattern": "PATTERN-STAGING-1",
                    "facilitators": ["SHOP-77", "CLIN-01", "ATTY-01",
                                     "SHELL-01"],
                    "exposure": 687000,
                    "cited_docs": ["SIU-01", "AUD-001"],
                },
                "plan_ring_member": {
                    "subject": se_members[0] if se_members else "CL-343",
                    "ring": "RING-SE-1",
                    "root_pattern": "PATTERN-TOW-1",
                    "facilitators": ["SHOP-12", "ATTY-04", "SHELL-04"],
                    "steps": ["ego_neighborhood", "shared_attributes",
                              "paths_to_fraud", "root_cause_claimant"],
                },
                "distractor_clean": {
                    "subject": clean_subjects[0] if clean_subjects else "CL-501",
                    "expected_ring": None, "known_fraud_links": 0,
                },
            },
        },
        "cost": {
            "assignments": {
                "root_cause_south_frequency": {
                    "metric": "frequency", "region": "South",
                    "coverage": "auto_pd",
                    "trigger_event": "EVT-01",
                    "primary_driver": "cat_weather",
                    "secondary_drivers": ["vmt_mileage"],
                    "excluded": ["winter_weather"],
                    "cited_docs": ["M-04"],
                },
            },
        },
        "portfolio": {
            "assignments": {
                "leverage_bro_w": {
                    "segment": {"broker": "BRO-W", "class_code": "ALL",
                                "region": "ALL"},
                    "lever": "reserve_adequacy", "stage": "claim",
                    "outcome": "leakage_pct",
                    "cited_docs": ["PFM-114"],
                },
                "leverage_5437": {
                    "segment": {"broker": "ALL", "class_code": "5437",
                                "region": "ALL"},
                    "lever": "risk_score_override", "stage": "risk_scoring",
                    "outcome": "loss_ratio",
                    "cited_docs": ["PFM-115"],
                },
                "journey_clm015": {
                    "claim": "CLM-015",
                    "signals": ["late_fnol", "reserve_adequacy"],
                },
            },
        },
        "meta": {
            "seed": seed, "dataset_size": size,
            "counts": {d: {"nodes": len(json.loads(
                payload)["nodes"]) if isinstance(payload, str) else
                len(payload["nodes"])}
                for d, payload in payloads.items()},
        },
    }
    return gt


# ── public entry ─────────────────────────────────────────────────────

DATA_FILES = {
    "fraud": "neo4j_fraud.json",
    "cost": "neo4j_cost.json",
    "portfolio": "neo4j_portfolio.json",
}
MEMO_FILES = {
    "fraud": "neo4j_fraud_memos.json",
    "cost": "neo4j_cost_memos.json",
    "portfolio": "neo4j_portfolio_memos.json",
}
GROUND_TRUTH_FILE = "neo4j_ground_truth.json"

GENERATORS = {
    "fraud": (generate_fraud, generate_fraud_memos),
    "cost": (generate_cost, generate_cost_memos),
    "portfolio": (generate_portfolio, generate_portfolio_memos),
}


def generate_all(seed: int, size: str = "full",
                 out_dir: Path = DATA_DIR) -> dict[str, Path]:
    """Generate every graph + memo set + ground truth; return file paths."""
    payloads, paths = {}, {}
    for domain, (graph_fn, memo_fn) in GENERATORS.items():
        payload = graph_fn(seed, size)
        payloads[domain] = payload
        path = out_dir / DATA_FILES[domain]
        path.write_text(json.dumps(payload, indent=1))
        paths[domain] = path
        memo_path = out_dir / MEMO_FILES[domain]
        memo_path.write_text(json.dumps(memo_fn(seed), indent=1))
        paths[f"{domain}_memos"] = memo_path
    gt_path = out_dir / GROUND_TRUTH_FILE
    gt_path.write_text(json.dumps(generate_ground_truth(payloads, seed,
                                                        size), indent=1))
    paths["ground_truth"] = gt_path
    return paths


if __name__ == "__main__":
    files = generate_all(20260801, "full")
    for name, path in files.items():
        print(f"{name:16s} {path.name}  {path.stat().st_size:>8,} bytes")

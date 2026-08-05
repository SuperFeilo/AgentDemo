"""ANATOMY COMPONENT: GRAPHRAG WRITE PATH — fraud investigator edition.

Reads SIU memos, fraud bulletins, and post-payment audit reports and
extracts *candidate* knowledge-graph content: fraud rings, suspect shops,
scam patterns, and their links to claimants/entities. Every claim carries
PROVENANCE: exactly which sentence in which document it came from.

Deterministic heuristics stand in for an LLM so the demo runs offline.

SEAM FOR A REAL LLM ────────────────────────────────────────────────
Replace `extract()` with an LLM call per document:

    SYSTEM: You build insurance-fraud knowledge graphs. From this SIU
    memo or fraud bulletin, extract fraud-intel entities as JSON:
    {"entities": [{"entity_id", "name", "type": "ring|shop|scam_type|
                   high_risk_zip|suspect_claimant",
                   "evidence_quote", "linked_entities": ["CL-xxx", ...],
                   "strength": "confirmed|strongly_suspected|suspected|
                   possible|unsubstantiated"}]}
    Always quote the exact source sentence; never infer beyond the text.

Strength words then map to confidence weights exactly as below — that
part stays deterministic even with a real LLM, because confidence is
policy, not prose.
─────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import re

# strength phrase -> confidence weight (curation POLICY, not model output)
STRENGTH_WEIGHTS = {
    "confirmed": 0.85, "strongly_suspected": 0.70, "suspected": 0.55,
    "probable": 0.50, "possible": 0.40, "unsubstantiated": 0.25,
}

# fraud-intel signatures: what the mock extractor is 'trained' to recognise
SIGNATURES = [
    {
        "entity_id": "RING-SOUTH-1",
        "name": "South Texas staged-accident ring",
        "type": "fraud_ring",
        "keywords": ["staged accident", "rear-end", "phantom vehicle",
                     "staged collision", "swoop-and-squat"],
        "linked": ["CL-201", "CL-202", "CL-203", "SHOP-77"],
    },
    {
        "entity_id": "RING-MIDWEST-1",
        "name": "Midwest medical-mill ring",
        "type": "fraud_ring",
        "keywords": ["medical mill", "chiropractic mill", "excessive treatment",
                     "pre-existing injury"],
        "linked": ["CL-106", "CL-111"],
    },
    {
        "entity_id": "SHOP-COLLUSION-1",
        "name": "QuickFix Auto — suspected billing fraud",
        "type": "suspect_shop",
        "keywords": ["quickfix", "billing irregularity", "inflated estimate",
                     "parts not replaced", "ghost repairs"],
        "linked": ["SHOP-77"],
    },
    {
        "entity_id": "PATTERN-PIP-1",
        "name": "PIP abuse — inflated soft-tissue claims",
        "type": "scam_type",
        "keywords": ["pip", "personal injury protection", "soft tissue",
                     "mri", "inflated medical"],
        "linked": ["CL-108", "CL-111"],
    },
    {
        "entity_id": "PATTERN-ID-1",
        "name": "Identity manipulation — synthetic claimants",
        "type": "scam_type",
        "keywords": ["synthetic identity", "stolen identity", "identity fraud",
                     "fake id", "nonexistent policyholder"],
        "linked": ["CL-203"],
    },
    {
        "entity_id": "RING-NORTHEAST-1",
        "name": "Northeast premium-diversion ring",
        "type": "fraud_ring",
        "keywords": ["premium diversion", "straw policy", "fake agency",
                     "unlicensed agent"],
        "linked": ["CL-201", "CL-207"],
    },
    {
        "entity_id": "SHOP-COLLUSION-2",
        "name": "Certified Auto Care — tow-referral kickback",
        "type": "suspect_shop",
        "keywords": ["tow referral", "kickback", "steering", "runner",
                     "ambulance chaser"],
        "linked": ["SHOP-12"],
    },
    {
        "entity_id": "PATTERN-STAGING-1",
        "name": "Jump-in fraud — passengers added after loss",
        "type": "scam_type",
        "keywords": ["jump-in", "phantom passenger", "added occupant",
                     "late-reported injury"],
        "linked": ["CL-105"],
    },
    {
        "entity_id": "RING-SE-1",
        "name": "Southeast tow-steering ring",
        "type": "fraud_ring",
        "keywords": ["i-285", "tow steering", "towing administration"],
        "linked": ["SHOP-12"],
    },
    {
        "entity_id": "RING-WEST-1",
        "name": "West ghost-repair ring",
        "type": "fraud_ring",
        "keywords": ["san gabriel", "ace collision"],
        "linked": ["SHOP-45"],
    },
    {
        "entity_id": "RING-DFW-1",
        "name": "DFW swoop-and-squat cell",
        "type": "fraud_ring",
        "keywords": ["fm-635", "dallas", "phantom repair"],
        "linked": ["SHOP-88"],
    },
    {
        "entity_id": "RING-PHX-1",
        "name": "Phoenix rental-receipt ring",
        "type": "fraud_ring",
        "keywords": ["maricopa", "rental reimbursement", "rental-receipt"],
        "linked": ["ATTY-06"],
    },
    {
        "entity_id": "RING-MW-2",
        "name": "Indianapolis chiro-referral cell",
        "type": "fraud_ring",
        "keywords": ["circle city", "chiro-referral",
                     "chiropractic referral"],
        "linked": ["CLIN-03"],
    },
    {
        "entity_id": "PATTERN-TOW-1",
        "name": "Tow steering — referral kickbacks",
        "type": "scam_type",
        "keywords": ["tow steering", "towing administration"],
        "linked": ["SHOP-12"],
    },
    {
        "entity_id": "PATTERN-GHOST-1",
        "name": "Ghost repairs — parts never installed",
        "type": "scam_type",
        "keywords": ["ghost repairs", "never installed"],
        "linked": ["SHOP-45"],
    },
    {
        "entity_id": "PATTERN-RENTAL-1",
        "name": "Rental reimbursement inflation",
        "type": "scam_type",
        "keywords": ["rental reimbursement", "fabricated receipts"],
        "linked": ["ATTY-06"],
    },
    {
        "entity_id": "SHOP-COLLUSION-3",
        "name": "Ace Collision — suspected ghost repairs",
        "type": "suspect_shop",
        "keywords": ["ace collision"],
        "linked": ["SHOP-45"],
    },
    {
        "entity_id": "SHOP-COLLUSION-4",
        "name": "Metro Body DFW — phantom repair estimates",
        "type": "suspect_shop",
        "keywords": ["metro body"],
        "linked": ["SHOP-88"],
    },
]

_FIGURE_RE = re.compile(
    r"[+\-≈~]?\$?\d+(?:\.\d+)?%|(?:\d+\s*claims?)"
    r"|\$\d+(?:,\d{3})*(?:\.\d+)?|\d+\s*(?:claimants?|cases?)"
)

# strength word -> weight, best-first (shared pick_strength order)
_STRENGTHS_ORDERED = sorted(STRENGTH_WEIGHTS.items(),
                            key=lambda x: -x[1])


class MockLLMFraudGraphExtractor:
    """Deterministic stand-in for LLM document->fraud-graph extraction."""

    def extract(self, memos: list[dict]) -> list[dict]:
        """Return candidate intel entities, one per (signature, document)
        mention, with provenance. Callers dedupe/merge by entity_id."""
        from llm_client.extract import best_sentence, pick_strength
        candidates = []
        for memo in memos:
            text = memo["text"]
            lowered = text.lower()
            for sig in SIGNATURES:
                if not any(k in lowered for k in sig["keywords"]):
                    continue
                quote = best_sentence(text, sig["keywords"], _FIGURE_RE)
                weight, strength = pick_strength(quote.lower(),
                                                 _STRENGTHS_ORDERED)
                if strength == "(default)":
                    weight, strength = pick_strength(lowered,
                                                     _STRENGTHS_ORDERED)
                candidates.append({
                    "entity_id": sig["entity_id"],
                    "name": sig["name"],
                    "type": sig["type"],
                    "linked_entities": sig["linked"],
                    "strength_word": strength,
                    "confidence": weight,
                    "quote": quote,
                    "figures": _FIGURE_RE.findall(quote) or
                               _FIGURE_RE.findall(text),
                    "provenance": {
                        "doc_id": memo["doc_id"],
                        "title": memo["title"],
                        "publisher": memo["publisher"],
                        "date": memo["date"],
                    },
                })
        return candidates


_FRAUD_LLM_SYSTEM = """You build insurance-fraud knowledge graphs. From this SIU
memo or fraud bulletin, extract fraud-intel entities. Return ONLY JSON:
{"entities": [{"entity_id": str, "name": str,
 "type": "ring|shop|scam_type|high_risk_zip|suspect_claimant",
 "evidence_quote": str, "linked_entities": [str],
 "strength": "confirmed|strongly_suspected|suspected|probable|possible|
              unsubstantiated"}]}

Rules:
- entity_id must be a stable slug like RING-SOUTH-1, SHOP-COLLUSION-1,
  PATTERN-PIP-1 (no spaces).
- Always quote the exact source sentence in evidence_quote; never infer
  beyond the text. Empty result is valid: {"entities": []}."""

_VALID_FRAUD_TYPES = {"ring", "shop", "scam_type", "high_risk_zip",
                      "suspect_claimant"}


class LLMFraudGraphExtractor:
    """Real DeepSeek document->fraud-graph extraction. Same candidate
    contract as the mock; strength->confidence stays policy (the
    STRENGTH_WEIGHTS map above), figures stay regex-extracted."""

    def extract(self, memos: list[dict]) -> list[dict]:
        from llm_client.extract import extract_documents
        return extract_documents(memos, _FRAUD_LLM_SYSTEM,
                                 self._normalize, "entities",
                                 tag="extract:fraud")

    @staticmethod
    def _normalize(item: dict, memo: dict) -> dict | None:
        eid = str(item.get("entity_id", "")).strip()
        itype = item.get("type", "")
        if not eid or itype not in _VALID_FRAUD_TYPES:
            return None
        strength = str(item.get("strength", ""))
        weight = STRENGTH_WEIGHTS.get(strength, 0.40)
        quote = str(item.get("evidence_quote") or item.get("quote") or "")
        return {
            "entity_id": eid,
            "name": str(item.get("name") or eid),
            "type": itype,
            "linked_entities": [str(x) for x in
                                (item.get("linked_entities") or [])],
            "strength_word": strength if strength in STRENGTH_WEIGHTS
                             else "(default)",
            "confidence": weight,
            "quote": quote,
            "figures": _FIGURE_RE.findall(quote) or
                       _FIGURE_RE.findall(memo["text"]),
            "provenance": {
                "doc_id": memo["doc_id"], "title": memo["title"],
                "publisher": memo["publisher"], "date": memo["date"],
            },
        }


def merge_candidates(candidates: list[dict]) -> dict[str, dict]:
    """Merge per-document candidates into one entry per entity, keeping
    the strongest confidence and ALL provenance docs."""
    from llm_client.extract import merge_candidates as _shared
    return _shared(candidates, "entity_id")

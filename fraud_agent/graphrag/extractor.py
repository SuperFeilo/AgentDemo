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
]

_FIGURE_RE = re.compile(
    r"[+\-≈~]?\$?\d+(?:\.\d+)?%|(?:\d+\s*claims?)"
    r"|\$\d+(?:,\d{3})*(?:\.\d+)?|\d+\s*(?:claimants?|cases?)"
)


class MockLLMFraudGraphExtractor:
    """Deterministic stand-in for LLM document->fraud-graph extraction."""

    def extract(self, memos: list[dict]) -> list[dict]:
        """Return candidate intel entities, one per (signature, document)
        mention, with provenance. Callers dedupe/merge by entity_id."""
        candidates = []
        for memo in memos:
            text = memo["text"]
            lowered = text.lower()
            for sig in SIGNATURES:
                if not any(k in lowered for k in sig["keywords"]):
                    continue
                quote = self._best_sentence(text, sig["keywords"])
                weight, strength = self._strength(quote.lower())
                if strength == "(default)":
                    weight, strength = self._strength(lowered)
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

    @staticmethod
    def _strength(lowered_text: str) -> tuple[float, str]:
        for word, weight in sorted(
                STRENGTH_WEIGHTS.items(), key=lambda x: -x[1]):
            if word in lowered_text:
                return weight, word
        return 0.40, "(default)"

    @staticmethod
    def _best_sentence(text: str, keywords: list[str]) -> str:
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text)]
        for s in sentences:
            if any(k in s.lower() for k in keywords) and \
                    (_FIGURE_RE.search(s)):
                return s
        for s in sentences:
            if any(k in s.lower() for k in keywords):
                return s
        return sentences[0] if sentences else ""


def merge_candidates(candidates: list[dict]) -> dict[str, dict]:
    """Merge per-document candidates into one entry per entity, keeping
    the strongest confidence and ALL provenance docs."""
    merged: dict[str, dict] = {}
    for c in candidates:
        eid = c["entity_id"]
        if eid not in merged:
            merged[eid] = {**c, "provenance": [c["provenance"]]}
        else:
            m = merged[eid]
            m["provenance"].append(c["provenance"])
            m["linked_entities"] = list(
                set(m["linked_entities"]) | set(c["linked_entities"]))
            if c["confidence"] > m["confidence"]:
                m["confidence"] = c["confidence"]
                m["strength_word"] = c["strength_word"]
    return merged

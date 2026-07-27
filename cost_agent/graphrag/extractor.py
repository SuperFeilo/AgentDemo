"""ANATOMY COMPONENT: GRAPHRAG WRITE PATH (mock-LLM extraction)

Reads raw source documents (actuarial memos, bulletins, event reports)
and extracts *candidate* knowledge-graph content: driver nodes, their
IMPACTS edges (with inferred weight/scope/direction), and — most
importantly — PROVENANCE: exactly which sentence in which document each
claim came from.

Deterministic heuristics stand in for an LLM so the demo runs offline.

SEAM FOR A REAL LLM ────────────────────────────────────────────────
Replace `extract()` with an LLM call per document:

    SYSTEM: You build insurance cost-driver knowledge graphs. From this
    document, extract any cost drivers as JSON:
    {"drivers": [{"driver_id", "name", "evidence_quote", "figures",
                  "impacts": [{"metric", "coverage", "region",
                               "strength": "overwhelming|dominant|primary|
                               major|significant|moderate|modest|mild|minor",
                               "direction": "+|-", "lag_quarters"}]}]}
    Always quote the exact source sentence; never infer beyond the text.

Strength words then map to edge weights exactly as below — that part
stays deterministic even with a real LLM, because weights are policy,
not prose.
─────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import re

# strength phrase -> edge weight (curation POLICY, applied to extraction)
STRENGTH_WEIGHTS = {
    "overwhelmingly": 0.70, "dominant": 0.60, "primary": 0.55,
    "major": 0.50, "significant": 0.45, "moderate": 0.40,
    "modest": 0.35, "minor": 0.35, "mild": 0.30,
}

# driver signatures: what the mock extractor is 'trained' to recognise
SIGNATURES = [
    {"driver_id": "parts_inflation", "name": "OEM parts inflation",
     "keywords": ["oem", "parts prices", "parts cost"],
     "metric": "severity", "coverage": "auto_pd", "region": "ALL"},
    {"driver_id": "medical_inflation", "name": "Medical cost inflation",
     "keywords": ["medical care cpi", "medical inflation"],
     "metric": "severity", "coverage": "auto_bi", "region": "ALL"},
    {"driver_id": "litigation_climate", "name": "Litigation climate (Northeast)",
     "keywords": ["attorney", "litigation", "represented claims"],
     "metric": "severity", "coverage": "auto_bi", "region": "Northeast"},
    {"driver_id": "cat_weather", "name": "Catastrophe weather event",
     "keywords": ["hurricane", "landfall"],
     "metric": "frequency", "coverage": "auto_pd", "region": "South"},
    {"driver_id": "adas_complexity", "name": "ADAS repair complexity",
     "keywords": ["adas"],
     "metric": "severity", "coverage": "auto_pd", "region": "ALL"},
    {"driver_id": "supply_chain", "name": "Parts supply-chain friction",
     "keywords": ["supply-chain", "supply chain", "delivery delay",
                  "supplement"],
     "metric": "severity", "coverage": "auto_pd", "region": "ALL"},
    {"driver_id": "vmt_mileage", "name": "Miles driven (VMT)",
     "keywords": ["vehicle-miles", "vmt", "mileage"],
     "metric": "frequency", "coverage": "auto_pd", "region": "ALL"},
    {"driver_id": "winter_weather", "name": "Winter storm (episodic)",
     "keywords": ["polar vortex", "winter storm"],
     "metric": "frequency", "coverage": "auto_pd", "region": "Midwest"},
]

_FIGURE_RE = re.compile(r"[+\-≈~]?\$?\d+(?:\.\d+)?%|(?:\d+(?:\.\d+)?\s*days)|"
                        r"\+\$\d+(?:\.\d+)?\s*per claim|\$\d+")


class MockLLMGraphExtractor:
    """Deterministic stand-in for LLM document->graph extraction."""

    def extract(self, memos: list[dict]) -> list[dict]:
        """Return candidate edges, one per (driver, document) mention,
        with provenance. Callers dedupe/merge by driver_id."""
        candidates = []
        for memo in memos:
            text = memo["text"]
            lowered = text.lower()
            for sig in SIGNATURES:
                if not any(k in lowered for k in sig["keywords"]):
                    continue
                quote = self._best_sentence(text, sig["keywords"])
                # attribute the strength word from the driver's own sentence
                # first (a memo may grade several drivers differently)
                weight, strength = self._strength(quote.lower())
                if strength == "(default)":
                    weight, strength = self._strength(lowered)
                candidates.append({
                    "driver_id": sig["driver_id"], "name": sig["name"],
                    "metric": sig["metric"], "coverage": sig["coverage"],
                    "region": sig["region"],
                    "weight": weight, "strength_word": strength,
                    "direction": "+", "lag_quarters": 0,
                    "quote": quote,
                    "figures": _FIGURE_RE.findall(quote) or
                               _FIGURE_RE.findall(text),
                    "provenance": {"doc_id": memo["doc_id"],
                                   "title": memo["title"],
                                   "publisher": memo["publisher"],
                                   "date": memo["date"]},
                })
        return candidates

    @staticmethod
    def _strength(lowered_text: str) -> tuple[float, str]:
        for word, weight in STRENGTH_WEIGHTS.items():
            if word in lowered_text:
                return weight, word
        return 0.40, "(default)"

    @staticmethod
    def _best_sentence(text: str, keywords: list[str]) -> str:
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text)]
        for s in sentences:
            if any(k in s.lower() for k in keywords) and \
                    (_FIGURE_RE.search(s) or "%" in s):
                return s
        for s in sentences:
            if any(k in s.lower() for k in keywords):
                return s
        return sentences[0]


def merge_candidates(candidates: list[dict]) -> dict[str, dict]:
    """Merge per-document candidates into one entry per driver, keeping
    the strongest weight and ALL provenance docs."""
    merged: dict[str, dict] = {}
    for c in candidates:
        did = c["driver_id"]
        if did not in merged:
            merged[did] = {**c, "provenance": [c["provenance"]]}
        else:
            m = merged[did]
            m["provenance"].append(c["provenance"])
            if c["weight"] > m["weight"]:
                m["weight"], m["strength_word"] = c["weight"], c["strength_word"]
    return merged

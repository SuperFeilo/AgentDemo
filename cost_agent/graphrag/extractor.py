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
    {"driver_id": "rental_costs", "name": "Rental cost inflation",
     "keywords": ["rental reimbursement rates", "rental duration"],
     "metric": "severity", "coverage": "auto_pd", "region": "ALL"},
    {"driver_id": "labor_rates", "name": "Body-shop labor rates",
     "keywords": ["dealer labor rates", "labor rates"],
     "metric": "severity", "coverage": "auto_pd", "region": "ALL"},
    {"driver_id": "used_car_values", "name": "Used-car market volatility",
     "keywords": ["used-car values", "valuation trends"],
     "metric": "frequency", "coverage": "auto_pd", "region": "ALL"},
    {"driver_id": "hail_corridor", "name": "Southwest hail season (recurrent)",
     "keywords": ["hail season", "southwest corridor"],
     "metric": "frequency", "coverage": "auto_pd", "region": "Southwest"},
    {"driver_id": "telehealth_billing", "name": "Telehealth billing abuse",
     "keywords": ["telehealth"],
     "metric": "severity", "coverage": "auto_bi", "region": "ALL"},
    {"driver_id": "attorney_advertising",
     "name": "Attorney advertising intensity",
     "keywords": ["attorney advertising"],
     "metric": "severity", "coverage": "auto_bi", "region": "Northeast"},
]

_FIGURE_RE = re.compile(r"[+\-≈~]?\$?\d+(?:\.\d+)?%|(?:\d+(?:\.\d+)?\s*days)|"
                        r"\+\$\d+(?:\.\d+)?\s*per claim|\$\d+")

# strength word -> edge weight, dict order (shared pick_strength order)
_STRENGTHS_ORDERED = list(STRENGTH_WEIGHTS.items())


class MockLLMGraphExtractor:
    """Deterministic stand-in for LLM document->graph extraction."""

    def extract(self, memos: list[dict]) -> list[dict]:
        """Return candidate edges, one per (driver, document) mention,
        with provenance. Callers dedupe/merge by driver_id."""
        from llm_client.extract import best_sentence, pick_strength
        candidates = []
        for memo in memos:
            text = memo["text"]
            lowered = text.lower()
            for sig in SIGNATURES:
                if not any(k in lowered for k in sig["keywords"]):
                    continue
                quote = best_sentence(text, sig["keywords"], _FIGURE_RE,
                                      prefer_pct=True)
                # attribute the strength word from the driver's own sentence
                # first (a memo may grade several drivers differently)
                weight, strength = pick_strength(quote.lower(),
                                                 _STRENGTHS_ORDERED)
                if strength == "(default)":
                    weight, strength = pick_strength(lowered,
                                                     _STRENGTHS_ORDERED)
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


_COST_LLM_SYSTEM = """You build insurance cost-driver knowledge graphs. From this
document, extract any cost drivers. Return ONLY JSON:
{"drivers": [{"driver_id": str, "name": str, "evidence_quote": str,
 "impacts": [{"metric": str, "coverage": str, "region": str,
              "strength": "overwhelmingly|dominant|primary|major|
                           significant|moderate|modest|minor|mild",
              "direction": "+|-", "lag_quarters": int}]}]}

Rules:
- driver_id must be a stable slug like parts_inflation, supply_chain
  (no spaces).
- metrics/coverages/regions should use the project's vocabulary
  (metric: severity|frequency|loss_ratio; coverage: auto_pd|auto_bi|home;
  region: ALL|Northeast|South|Midwest|Southwest|West).
- Always quote the exact source sentence in evidence_quote; never infer
  beyond the text. Empty result is valid: {"drivers": []}."""


class LLMGraphExtractor:
    """Real DeepSeek document->cost-graph extraction. Same candidate
    contract as the mock; strength->weight stays policy (STRENGTH_WEIGHTS
    above), figures stay regex-extracted."""

    def extract(self, memos: list[dict]) -> list[dict]:
        from llm_client.extract import extract_documents
        return extract_documents(memos, _COST_LLM_SYSTEM,
                                 self._normalize, "drivers",
                                 tag="extract:cost")

    @staticmethod
    def _normalize(item: dict, memo: dict) -> dict | None:
        did = str(item.get("driver_id", "")).strip()
        if not did:
            return None
        quote = str(item.get("evidence_quote") or item.get("quote") or "")
        name = str(item.get("name") or did)
        out = []
        for imp in item.get("impacts") or []:
            if not isinstance(imp, dict):
                continue
            strength = str(imp.get("strength", ""))
            weight = STRENGTH_WEIGHTS.get(strength, 0.40)
            out.append({
                "driver_id": did, "name": name,
                "metric": str(imp.get("metric", "")),
                "coverage": str(imp.get("coverage", "ALL")),
                "region": str(imp.get("region", "ALL")),
                "weight": weight,
                "strength_word": strength if strength in STRENGTH_WEIGHTS
                                 else "(default)",
                "direction": str(imp.get("direction", "+")),
                "lag_quarters": int(imp.get("lag_quarters", 0) or 0),
                "quote": quote,
                "figures": _FIGURE_RE.findall(quote) or
                           _FIGURE_RE.findall(memo["text"]),
                "provenance": {
                    "doc_id": memo["doc_id"], "title": memo["title"],
                    "publisher": memo["publisher"], "date": memo["date"],
                },
            })
        return out or None


def merge_candidates(candidates: list[dict]) -> dict[str, dict]:
    """Merge per-document candidates into one entry per driver, keeping
    the strongest weight and ALL provenance docs."""
    from llm_client.extract import merge_candidates as _shared
    return _shared(candidates, "driver_id")

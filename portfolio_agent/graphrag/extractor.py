"""ANATOMY COMPONENT: GRAPHRAG WRITE PATH (mock-LLM signal extraction)

Reads the raw source documents in `data/portfolio_memos.json` (UW
committee memos, inspection reports, claims narratives) and extracts
*candidate* lineage content: signal nodes + their PREDISPOSES edges
with inferred weight/direction/scope, and PROVENANCE to the exact
document and sentence the claim came from.

Deterministic heuristics stand in for an LLM, mirroring the cost agent's
MockLLMGraphExtractor.

SEAM FOR A REAL LLM ────────────────────────────────────────────────
Replace `extract()` with an LLM call per document:

    SYSTEM: You build portfolio-journey knowledge graphs. From this
    document, extract any risk signals relevant to the commercial-lines
    submission→bind→claim→settlement journey as JSON:
    {"signals": [{"signal_id", "name", "evidence_quote", "figures",
                  "stage": "submission|underwriting|risk_scoring|
                          site_inspection|bind|claim|settlement",
                  "predisposes": [{"outcome", "class_code": "ALL|...",
                                   "region": "ALL|...",
                                   "strength": "...",
                                   "direction": "+|-",
                                   "lag_quarters"}]}]}
    Always quote the exact source sentence; never infer beyond the text.

Strength words then map to edge weights exactly as below — that part
stays deterministic even with a real LLM.
"""
from __future__ import annotations

import re

STRENGTH_WEIGHTS = {
    "dominant": 0.65, "primary": 0.60, "major": 0.55,
    "significant": 0.50, "moderate": 0.42, "meaningful": 0.40,
    "modest": 0.32, "minor": 0.28, "mild": 0.25,
}
# 'significant' first to win the substring race for ambiguous phrases
_STRENGTHS_ORDERED = sorted(STRENGTH_WEIGHTS.items(), key=lambda kv: -len(kv[0]))

# signal signatures: what the mock extractor is 'trained' to recognise
SIGNATURES = [
    {"signal_id": "exposure_completeness",
     "name": "Exposure detail completeness", "stage": "submission",
     "keywords": ["exposure detail", "incomplete ", "completeness"],
     "outcome": "bind_conversion", "class_code": "ALL", "region": "West"},
    {"signal_id": "broker_pattern",
     "name": "Broker submission pattern", "stage": "submission",
     "keywords": ["bro-w", "broker"],
     "outcome": "loss_ratio", "class_code": "ALL", "region": "West"},
    {"signal_id": "uw_note_hedging",
     "name": "UW hedging phrasing", "stage": "underwriting",
     "keywords": ["hedging phrasing", "hedging", "hedged"],
     "outcome": "pricing_inadequacy", "class_code": "ALL", "region": "ALL"},
    {"signal_id": "risk_score_override",
     "name": "Risk-score override (downward)", "stage": "risk_scoring",
     "keywords": ["override", "risk-score override", "downward override"],
     "outcome": "loss_ratio", "class_code": "5437", "region": "ALL"},
    {"signal_id": "inspection_flag_ignored",
     "name": "Inspection flag waived at bind", "stage": "site_inspection",
     "keywords": ["inspection", "waived", "flag", "ignored at bind"],
     "outcome": "claim_frequency", "class_code": "ALL", "region": "ALL"},
    {"signal_id": "pricing_inadequacy",
     "name": "Premium vs expected loss", "stage": "bind",
     "keywords": ["premium", "pricing adequacy", "pricing", "under-priced"],
     "outcome": "margin_contribution", "class_code": "5437", "region": "ALL"},
    {"signal_id": "late_fnol",
     "name": "Late FNOL on class 5437", "stage": "claim",
     "keywords": ["fnol", "fnol lag", "first-notice", "late fnol"],
     "outcome": "loss_ratio", "class_code": "5437", "region": "ALL"},
    {"signal_id": "reserve_adequacy",
     "name": "Reserve adequacy", "stage": "claim",
     "keywords": ["reserve", "reserving", "low reserve", "adequacy"],
     "outcome": "leakage_pct", "class_code": "ALL", "region": "ALL"},
    {"signal_id": "settlement_slowness",
     "name": "Settlement slowness", "stage": "settlement",
     "keywords": ["settlement slowness", "days-to-settle", "cycle time",
                   "long tail", "180 days"],
     "outcome": "leakage_pct", "class_code": "ALL", "region": "ALL"},
    {"signal_id": "submission_velocity",
     "name": "Rush submission surge", "stage": "submission",
     "keywords": ["rush quotes", "rush submissions"],
     "outcome": "bind_conversion", "class_code": "ALL", "region": "ALL"},
    {"signal_id": "broker_latency",
     "name": "Broker response latency", "stage": "submission",
     "keywords": ["response latency", "response time grew", "consolidation"],
     "outcome": "bind_conversion", "class_code": "ALL", "region": "ALL"},
    {"signal_id": "uw_staffing",
     "name": "UW capacity strain", "stage": "underwriting",
     "keywords": ["note volume per uw", "staffing was frozen",
                  "capacity strain"],
     "outcome": "pricing_inadequacy", "class_code": "ALL", "region": "ALL"},
    {"signal_id": "score_drift",
     "name": "Model score drift", "stage": "risk_scoring",
     "keywords": ["score drift", "model refresh"],
     "outcome": "loss_ratio", "class_code": "5437", "region": "ALL"},
    {"signal_id": "deductible_gaming",
     "name": "Deductible gaming at bind", "stage": "bind",
     "keywords": ["deductible-lowering"],
     "outcome": "margin_contribution", "class_code": "ALL", "region": "ALL"},
    {"signal_id": "premium_override",
     "name": "Premium override frequency", "stage": "bind",
     "keywords": ["premium overrides"],
     "outcome": "margin_contribution", "class_code": "ALL", "region": "ALL"},
    {"signal_id": "reserve_cycles",
     "name": "Reserve cycle manipulation", "stage": "claim",
     "keywords": ["reserve increase frequency", "reserve suppression",
                  "reserve history"],
     "outcome": "leakage_pct", "class_code": "ALL", "region": "ALL"},
    {"signal_id": "attorney_engagement",
     "name": "Attorney engagement at settlement", "stage": "settlement",
     "keywords": ["attorney representation at settlement",
                  "represented settlements"],
     "outcome": "leakage_pct", "class_code": "ALL", "region": "ALL"},
    {"signal_id": "audit_findings",
     "name": "Internal audit findings rate", "stage": "settlement",
     "keywords": ["audit exception rate", "audit findings"],
     "outcome": "leakage_pct", "class_code": "ALL", "region": "ALL"},
    {"signal_id": "inspection_quality",
     "name": "Inspection report quality", "stage": "site_inspection",
     "keywords": ["inspection reports flagged incomplete"],
     "outcome": "pricing_inadequacy", "class_code": "ALL", "region": "ALL"},
]

_FIGURE_RE = re.compile(
    r"[+\-≈~]?\d+(?:\.\d+)?%|"
    r"\$\d+(?:,\d{3})*(?:\.\d+)?|"
    r"\d+(?:\.\d+)?\s*days|"
    r"\d+(?:\.\d+)?\s*points")


class MockLLMPortfolioGraphExtractor:
    """Deterministic stand-in for LLM document->graph extraction for the
    portfolio journey segment."""

    def extract(self, memos: list[dict]) -> list[dict]:
        candidates = []
        for memo in memos:
            text = memo["text"]
            lowered = text.lower()
            for sig in SIGNATURES:
                if not any(k.lower() in lowered for k in sig["keywords"]):
                    continue
                quote = self._best_sentence(text, sig["keywords"])
                weight, strength = self._strength(quote.lower())
                if strength == "(default)":
                    weight, strength = self._strength(lowered)
                candidates.append({
                    "signal_id": sig["signal_id"], "name": sig["name"],
                    "stage": sig["stage"], "outcome": sig["outcome"],
                    "class_code": sig["class_code"], "region": sig["region"],
                    "weight": weight, "strength_word": strength,
                    "direction": "+", "lag_quarters": 0,
                    "quote": quote,
                    "figures": _FIGURE_RE.findall(quote)
                              or _FIGURE_RE.findall(text),
                    "provenance": {"doc_id": memo["doc_id"],
                                    "title": memo["title"],
                                    "publisher": memo["publisher"],
                                    "date": memo["date"]},
                })
        return candidates

    @staticmethod
    def _strength(lowered_text: str) -> tuple[float, str]:
        for word, weight in _STRENGTHS_ORDERED:
            if word in lowered_text:
                return weight, word
        return 0.40, "(default)"

    @staticmethod
    def _best_sentence(text: str, keywords: list[str]) -> str:
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text)]
        for s in sentences:
            if any(k.lower() in s.lower() for k in keywords) and \
                    (_FIGURE_RE.search(s) or "%" in s):
                return s
        for s in sentences:
            if any(k.lower() in s.lower() for k in keywords):
                return s
        return sentences[0]


def merge_candidates(candidates: list[dict]) -> dict[str, dict]:
    """Merge per-document candidates into one entry per signal, keeping
    the strongest weight and ALL provenance docs."""
    merged: dict[str, dict] = {}
    for c in candidates:
        sid = c["signal_id"]
        if sid not in merged:
            merged[sid] = {**c, "provenance": [c["provenance"]]}
        else:
            m = merged[sid]
            m["provenance"].append(c["provenance"])
            if c["weight"] > m["weight"]:
                m["weight"], m["strength_word"] = c["weight"], c["strength_word"]
    return merged
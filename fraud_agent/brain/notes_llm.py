"""ANATOMY COMPONENT: MODEL-BASED BRAIN (mock LLM)

`MockLLMNotesAnalyzer` plays the role a real LLM would play in
production: reading messy free-text adjuster notes and returning
*typed, quoted* inconsistencies. It is implemented with deterministic
heuristics so the project runs offline and evals are reproducible.

SEAM FOR A REAL LLM ────────────────────────────────────────────────
To swap in a real model, reimplement `analyze()` with an API call
using a prompt like:

    SYSTEM: You are an insurance fraud analyst. Read the adjuster notes
    and return JSON: {"inconsistencies": [{"type", "detail", "quotes"}],
    "hedging_count": int}. Types: date_contradiction,
    time_contradiction, location_contradiction, injury_contradiction,
    story_revision.

The rest of the agent (loop, harness, eval) does not change — that is
the point of isolating brains behind a stable contract.
─────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import re

_MONTHS = ("January|February|March|April|May|June|July|August|"
           "September|October|November|December")
_DATE_RE = re.compile(rf"\b(?:{_MONTHS})\s+\d{{1,2}}\b")
_TIME_RE = re.compile(r"\b\d{1,2}\s?(?:AM|PM)\b", re.IGNORECASE)
_ROAD_RE = re.compile(
    r"\b(I-\d+(?:\s+\w+bound)?|Route\s+\d+|Hwy\.?\s+\d+|"
    r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Rd|St|Ave)\.?|"
    r"\d+(?:st|nd|rd|th)\s+and\s+[A-Z][a-z]+)\b"
)
_INCIDENT_WORDS = re.compile(
    r"accident|crash|collision|occurred|happened|strike|theft|burglary|"
    r"fire|rear-ended|sideswipe|hail|storm|dent|pipe|hit-and-run|loss",
    re.IGNORECASE,
)
_HEDGING_RE = re.compile(
    r"i think|maybe|not sure|approximately|can'?t recall|cannot recall|confused",
    re.IGNORECASE,
)
_NO_INJURY_RE = re.compile(r"no injur|declined ambulance|declined medical", re.IGNORECASE)
_INJURY_CLAIM_RE = re.compile(
    r"whiplash|severe|treatment|therapy|medical records|surgery|rehab", re.IGNORECASE)
_REVISION_RE = re.compile(r"now says|changed (?:his|her|their) story", re.IGNORECASE)


class MockLLMNotesAnalyzer:
    """Deterministic stand-in for an LLM inconsistency-detection call."""

    def analyze(self, notes: list[str]) -> dict:
        # strip the "YYYY-MM-DD | " adjuster timestamp prefixes
        bodies = [re.sub(r"^\d{4}-\d{2}-\d{2}\s*\|\s*", "", n) for n in notes]
        sentences = [s.strip() for b in bodies for s in re.split(r"(?<=[.!?])\s+", b) if s.strip()]

        findings: list[dict] = []
        findings += self._contradiction(
            sentences, _DATE_RE, "date_contradiction",
            "Conflicting incident dates across statements")
        findings += self._contradiction(
            sentences, _TIME_RE, "time_contradiction",
            "Conflicting times of day across statements")
        findings += self._locations(sentences)
        findings += self._injury(bodies)
        findings += self._revisions(sentences)

        hedging = sum(len(_HEDGING_RE.findall(s)) for s in sentences)
        return {
            "notes_read": len(notes),
            "inconsistencies": findings,
            "hedging_count": hedging,
        }

    # ── detectors ───────────────────────────────────────────────────
    @staticmethod
    def _contradiction(sentences, pattern, kind, detail) -> list[dict]:
        hits = {}  # value -> quote
        for s in sentences:
            if not _INCIDENT_WORDS.search(s):
                continue
            for value in pattern.findall(s):
                hits.setdefault(value if isinstance(value, str) else value[0], s)
        if len(hits) >= 2:
            return [{"type": kind, "detail": f"{detail}: "
                     f"{', '.join(sorted(hits))}", "quotes": sorted(set(hits.values()))}]
        return []

    @staticmethod
    def _locations(sentences) -> list[dict]:
        hits = {}
        for s in sentences:
            if not (_INCIDENT_WORDS.search(s) or re.search(r"\bon\b|\bat\b", s)):
                continue
            for value in _ROAD_RE.findall(s):
                hits.setdefault(value if isinstance(value, str) else value[0], s)
            if "parked" in s.lower():  # parked on the street vs. in a garage
                for place in ("street", "garage", "driveway"):
                    if place in s.lower():
                        hits.setdefault(place, s)
        if len(hits) >= 2:
            return [{"type": "location_contradiction",
                     "detail": f"Conflicting locations: {', '.join(sorted(hits))}",
                     "quotes": sorted(set(hits.values()))}]
        return []

    @staticmethod
    def _injury(bodies) -> list[dict]:
        denial = next((i for i, b in enumerate(bodies) if _NO_INJURY_RE.search(b)), None)
        if denial is None:
            return []
        later = [b for b in bodies[denial + 1:] if _INJURY_CLAIM_RE.search(b)]
        if later:
            return [{"type": "injury_contradiction",
                     "detail": "No injury reported at scene, but treatment "
                               "claimed later",
                     "quotes": [bodies[denial], later[0]]}]
        return []

    @staticmethod
    def _revisions(sentences) -> list[dict]:
        hits = [s for s in sentences if _REVISION_RE.search(s)]
        if hits:
            return [{"type": "story_revision",
                     "detail": "Claimant revised their account between statements",
                     "quotes": hits[:2]}]
        return []

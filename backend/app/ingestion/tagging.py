"""Tie free-text signals to the digital twin (corridors, countries) + score them.

Keyword-driven, deterministic, and cheap — this is the clustering/entity step
that turns raw articles into structured events before any LLM is involved.
"""

from __future__ import annotations

import hashlib

# corridor_id -> trigger keywords
CORRIDOR_KEYWORDS: dict[str, list[str]] = {
    "hormuz": ["hormuz", "persian gulf", "strait of hormuz", "iran", "iranian",
               "gulf tanker", "irgc"],
    "red_sea": ["red sea", "bab-el-mandeb", "bab el mandeb", "houthi", "yemen",
                "suez", "gulf of aden"],
    "cape": ["cape of good hope", "cape route"],
    "malacca": ["malacca", "singapore strait"],
}

COUNTRY_KEYWORDS: dict[str, list[str]] = {
    "Iran": ["iran", "iranian", "tehran", "irgc"],
    "Saudi Arabia": ["saudi", "aramco", "riyadh"],
    "Russia": ["russia", "russian", "urals", "moscow"],
    "Iraq": ["iraq", "basra", "baghdad"],
    "UAE": ["uae", "emirates", "abu dhabi", "murban"],
    "Yemen": ["houthi", "yemen", "sanaa"],
    "United States": ["u.s.", "united states", "washington", "opec+"],
    "Israel": ["israel", "israeli", "idf"],
    "Venezuela": ["venezuela", "pdvsa"],
}

# escalation keywords -> severity weight
_HIGH = ["closure", "closed", "blockade", "attack", "strike", "seized", "missile",
         "explosion", "war", "sanction", "halt", "suspend", "escalat", "military"]
_MED = ["threat", "tension", "warning", "risk", "disrupt", "delay", "premium",
        "cut", "reduce", "concern", "protest"]


def make_id(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:12]


def match_corridors(text: str) -> list[str]:
    t = text.lower()
    return [cid for cid, kws in CORRIDOR_KEYWORDS.items() if any(k in t for k in kws)]


def match_countries(text: str) -> list[str]:
    t = text.lower()
    return [c for c, kws in COUNTRY_KEYWORDS.items() if any(k in t for k in kws)]


def score_text(text: str) -> tuple[str, float, float]:
    """Return (severity, confidence, risk_score) from keyword intensity."""
    t = text.lower()
    high = sum(1 for k in _HIGH if k in t)
    med = sum(1 for k in _MED if k in t)
    raw = high * 22 + med * 9

    corridor_boost = 15 if match_corridors(t) else 0
    risk = min(98, 25 + raw + corridor_boost)

    if risk >= 75:
        sev = "critical"
    elif risk >= 55:
        sev = "high"
    elif risk >= 35:
        sev = "elevated"
    else:
        sev = "nominal"

    # confidence rises with corroborating signal density
    confidence = min(95, 45 + high * 8 + med * 4 + corridor_boost)
    return sev, float(confidence), float(risk)


def estimate_duration(severity: str) -> int:
    return {"critical": 21, "high": 12, "elevated": 6, "nominal": 3}.get(severity, 5)

"""GDELT adapter — keyless global geopolitical event stream.

Pulls recent English coverage on energy-relevant disruption, then clusters &
scores it into normalized IntelEvents. Falls back to a realistic synthetic set
when GDELT is unreachable.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from app.core.logging import get_logger
from app.ingestion.cache import cache_get, cache_set
from app.ingestion.models import (
    Evidence,
    IntelEvent,
    SignalCategory,
    SourceKind,
)
from app.ingestion.tagging import (
    estimate_duration,
    make_id,
    match_corridors,
    match_countries,
    score_text,
)

log = get_logger("ingestion.gdelt")

_GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
_QUERY = (
    '("Strait of Hormuz" OR "Red Sea shipping" OR "tanker attack" OR '
    '"oil sanctions" OR "OPEC production" OR "crude oil supply" OR "Houthi")'
)
_CACHE_KEY = "gdelt:events"
_TTL = 600  # 10 min


def _parse_seendate(s: str) -> datetime:
    try:
        return datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except Exception:  # noqa: BLE001
        return datetime.now(timezone.utc)


def _event_from_article(art: dict) -> IntelEvent | None:
    title = (art.get("title") or "").strip()
    if not title:
        return None
    domain = art.get("domain", "")
    text = f"{title} {domain}"
    corridors = match_corridors(text)
    countries = match_countries(text)
    sev, conf, risk = score_text(text)
    return IntelEvent(
        id=make_id("gdelt", art.get("url", title)),
        title=title[:180],
        summary=f"Reported by {domain or 'source'} — {art.get('sourcecountry', '')}".strip(" —"),
        category=SignalCategory.GEOPOLITICAL,
        severity=sev,
        confidence=conf,
        risk_score=risk,
        affected_countries=countries,
        affected_corridors=corridors,
        estimated_duration_days=estimate_duration(sev),
        source=domain or "GDELT",
        source_kind=SourceKind.LIVE,
        published_at=_parse_seendate(art.get("seendate", "")),
        evidence=[Evidence(label="Source article", detail=domain, url=art.get("url"))],
    )


async def fetch_gdelt_events(limit: int = 24) -> list[IntelEvent]:
    cached = await cache_get(_CACHE_KEY)
    if cached:
        return [IntelEvent(**{**e, "source_kind": SourceKind.CACHED}) for e in cached]

    params = {
        "query": _QUERY,
        "mode": "artlist",
        "maxrecords": str(limit * 2),
        "format": "json",
        "sort": "datedesc",
        "timespan": "3d",
    }
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            resp = await client.get(_GDELT_URL, params=params,
                                    headers={"User-Agent": "CHANAKYA/0.1"})
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        log.warning("gdelt.fetch_failed", error=str(exc))
        return _fallback_events()

    events: list[IntelEvent] = []
    seen: set[str] = set()
    for art in data.get("articles", []):
        ev = _event_from_article(art)
        if not ev:
            continue
        key = ev.title.lower()[:60]
        if key in seen:
            continue
        seen.add(key)
        events.append(ev)
        if len(events) >= limit:
            break

    if not events:
        return _fallback_events()

    events.sort(key=lambda e: e.risk_score, reverse=True)
    await cache_set(_CACHE_KEY, [e.model_dump(mode="json") for e in events], _TTL)
    return events


def _fallback_events() -> list[IntelEvent]:
    now = datetime.now(timezone.utc)
    seeds = [
        ("Naval build-up reported near Strait of Hormuz",
         "Multiple outlets report increased military presence around the Strait of Hormuz.",
         "critical", 84, 82, ["Iran", "United States"], ["hormuz"]),
        ("Houthi drones target Red Sea shipping lane",
         "Renewed attacks on commercial vessels raise Red Sea transit risk.",
         "high", 79, 71, ["Yemen"], ["red_sea"]),
        ("OPEC+ signals possible emergency production review",
         "Ministers weigh output adjustments amid market volatility.",
         "elevated", 66, 48, ["Saudi Arabia", "Russia"], []),
        ("Fresh sanctions pressure on Iranian crude exports",
         "New secondary-sanctions guidance targets Iranian oil buyers.",
         "high", 72, 63, ["Iran", "United States"], ["hormuz"]),
    ]
    return [
        IntelEvent(
            id=make_id("fallback", t),
            title=t, summary=s, category=SignalCategory.GEOPOLITICAL,
            severity=sev, confidence=conf, risk_score=risk,
            affected_countries=countries, affected_corridors=corr,
            estimated_duration_days=estimate_duration(sev),
            source="synthetic-baseline", source_kind=SourceKind.FALLBACK,
            published_at=now,
        )
        for (t, s, sev, conf, risk, countries, corr) in seeds
    ]

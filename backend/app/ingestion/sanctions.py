"""Sanctions adapter — energy-relevant OFAC / OpenSanctions signals.

Attempts a live OpenSanctions search (keyless, rate-limited) for energy/vessel
designations; falls back to a curated set of standing energy-sector programs.
"""

from __future__ import annotations

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.ingestion.cache import cache_get, cache_set
from app.ingestion.models import SanctionSignal, SourceKind
from app.ingestion.tagging import make_id

log = get_logger("ingestion.sanctions")

_OS_URL = "https://api.opensanctions.org/search/default"
_TTL = 21600  # 6h


async def fetch_sanctions(limit: int = 8) -> list[SanctionSignal]:
    cached = await cache_get("sanctions:signals")
    if cached:
        return [SanctionSignal(**{**s, "source_kind": SourceKind.CACHED}) for s in cached]

    # OpenSanctions moved to authenticated access; only attempt live with a key.
    if not settings.opensanctions_api_key:
        return _fallback()

    signals: list[SanctionSignal] = []
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(_OS_URL, params={
                "q": "crude oil tanker", "limit": limit,
                "schema": "Vessel", "countries": "ir,ru,ve",
            }, headers={
                "User-Agent": "CHANAKYA/0.1",
                "Authorization": f"ApiKey {settings.opensanctions_api_key}",
            })
            if r.status_code == 200:
                for res in r.json().get("results", []):
                    props = res.get("properties", {})
                    signals.append(SanctionSignal(
                        id=make_id("os", res.get("id", "")),
                        program=(props.get("program", ["OFAC/EU"])[0]
                                 if props.get("program") else "Designated"),
                        target=res.get("caption", "Unknown"),
                        target_type="vessel",
                        description="Designated vessel linked to sanctioned oil trade.",
                        affected_countries=[c.upper() for c in res.get("countries", [])],
                        source="OpenSanctions", source_kind=SourceKind.LIVE,
                    ))
    except Exception as exc:  # noqa: BLE001
        log.debug("sanctions.fetch_failed", error=str(exc))

    if not signals:
        return _fallback()
    await cache_set("sanctions:signals", [s.model_dump(mode="json") for s in signals], _TTL)
    return signals


def _fallback() -> list[SanctionSignal]:
    seeds = [
        ("Iran Crude Exports", "Iranian NIOC-linked shipping network", "entity",
         "Secondary sanctions targeting Iranian crude export facilitation.", ["Iran"]),
        ("Russia Oil Price Cap", "Shadow-fleet tankers moving Urals above cap", "vessel",
         "Vessels flagged for breaching the G7 price cap on Russian crude.", ["Russia"]),
        ("Venezuela PdVSA", "PdVSA affiliated intermediaries", "entity",
         "Restrictions on Venezuelan state oil company counterparties.", ["Venezuela"]),
    ]
    return [
        SanctionSignal(
            id=make_id("fallback-sanction", t), program=t, target=tgt,
            target_type=tt, description=d, affected_countries=ac,
            source="curated-baseline", source_kind=SourceKind.FALLBACK,
        )
        for (t, tgt, tt, d, ac) in seeds
    ]

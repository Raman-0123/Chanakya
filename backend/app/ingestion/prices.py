"""Commodity price adapter — Brent & WTI via Alpha Vantage (free key).

Falls back to the domain baseline market state when no key / unreachable, so
downstream never sees an empty price.
"""

from __future__ import annotations

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.ingestion.cache import cache_get, cache_set
from app.ingestion.models import PriceQuote, SourceKind

log = get_logger("ingestion.prices")

_URL = "https://www.alphavantage.co/query"
_TTL = 3600
_BASELINE = {"BRENT": 82.0, "WTI": 78.2}


async def _one(client: httpx.AsyncClient, symbol: str) -> PriceQuote:
    r = await client.get(_URL, params={
        "function": symbol, "interval": "daily", "apikey": settings.alpha_vantage_api_key,
    })
    data = r.json().get("data", [])
    if len(data) < 2:
        raise ValueError("insufficient price data")
    latest = float(data[0]["value"])
    prev = float(data[1]["value"]) or latest
    change = round((latest - prev) / prev * 100, 2) if prev else 0.0
    return PriceQuote(symbol=symbol, price_usd=round(latest, 2), change_pct=change,
                      source="AlphaVantage", source_kind=SourceKind.LIVE)


async def fetch_prices() -> list[PriceQuote]:
    cached = await cache_get("prices:quotes")
    if cached:
        return [PriceQuote(**{**q, "source_kind": SourceKind.CACHED}) for q in cached]

    # Prefer the authoritative EIA series when configured. Import lazily to
    # avoid a module cycle with the supplemental adapter's fallback contract.
    if settings.eia_api_key:
        from app.ingestion.supplemental import fetch_eia_prices
        eia = await fetch_eia_prices()
        if eia:
            await cache_set("prices:quotes", [q.model_dump(mode="json") for q in eia], _TTL)
            return eia

    if not settings.alpha_vantage_api_key:
        return _fallback()

    quotes: list[PriceQuote] = []
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            for sym in ("BRENT", "WTI"):
                try:
                    quotes.append(await _one(client, sym))
                except Exception as exc:  # noqa: BLE001
                    log.debug("prices.symbol_failed", symbol=sym, error=str(exc))
    except Exception as exc:  # noqa: BLE001
        log.warning("prices.fetch_failed", error=str(exc))

    if not quotes:
        return _fallback()
    await cache_set("prices:quotes", [q.model_dump(mode="json") for q in quotes], _TTL)
    return quotes


def _fallback() -> list[PriceQuote]:
    return [
        PriceQuote(symbol=s, price_usd=p, change_pct=0.0,
                   source="baseline", source_kind=SourceKind.FALLBACK)
        for s, p in _BASELINE.items()
    ]

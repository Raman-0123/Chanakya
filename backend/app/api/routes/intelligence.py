"""Global Intelligence Room endpoints — the live, fused situational feed."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from app.domain import build_energy_network
from app.domain.risk_scoring import assess_disruption_risk
from app.ingestion import get_intelligence_service

router = APIRouter(prefix="/intelligence", tags=["intelligence"])

_network = build_energy_network()


def _event_payload(event) -> dict:
    row = event.model_dump(mode="json")
    freshness = max(0, int((datetime.now(timezone.utc) - event.published_at).total_seconds()))
    return {**row, "schema_version": "1.0", "provenance": event.source_kind.value,
            "freshness_seconds": freshness, "stale": freshness > 3600}


@router.get("/feed")
async def get_feed() -> dict:
    """Everything, fused: risk-ranked events + prices + weather + vessels + sanctions."""
    feed = await get_intelligence_service().feed()
    return {
        "summary": feed.summary(),
        "schema_version": "1.0",
        "events": [_event_payload(e) for e in feed.events],
        "prices": [p.model_dump(mode="json") for p in feed.prices],
        "weather": [w.model_dump(mode="json") for w in feed.weather],
        "vessels": [v.model_dump(mode="json") for v in feed.vessels],
        "sanctions": [s.model_dump(mode="json") for s in feed.sanctions],
        "detections": [d.model_dump(mode="json") for d in feed.detections],
    }


@router.get("/events")
async def get_events() -> dict:
    feed = await get_intelligence_service().feed()
    return {
        "summary": feed.summary(),
        "schema_version": "1.0",
        "events": [_event_payload(e) for e in feed.events],
    }


@router.get("/summary")
async def get_summary() -> dict:
    feed = await get_intelligence_service().feed()
    return feed.summary()


@router.get("/risk")
async def get_disruption_risk() -> dict:
    """Live disruption-probability score per corridor and supplier.

    Continuously recomputed from the fused feed: each corridor/supplier carries a
    0–100 probability, a detection lead-time (how long we've been flagging it),
    and a confidence-weighted accuracy proxy.
    """
    feed = await get_intelligence_service().feed()
    assessment = assess_disruption_risk(_network, feed.events)
    return assessment.model_dump(mode="json")


def _feature(geometry_type: str, coords, props: dict) -> dict:
    return {"type": "Feature",
            "geometry": {"type": geometry_type, "coordinates": coords},
            "properties": props}


@router.get("/geo")
async def get_geospatial_layer() -> dict:
    """Unified GeoJSON evidence layer for the digital twin map.

    Corridors (with chokepoints), ports, refineries, strategic reserves, live
    vessel positions + wake tracks, geolocated intel events and satellite
    thermal detections — one FeatureCollection the map can render directly.
    """
    feed = await get_intelligence_service().feed()
    risk = {c.corridor_id: c for c in assess_disruption_risk(_network, feed.events).corridors}
    features: list[dict] = []

    for corr in _network.corridors:
        if corr.path:
            cr = risk.get(corr.id)
            features.append(_feature(
                "LineString", [[p.lon, p.lat] for p in corr.path],
                {"kind": "corridor", "id": corr.id, "name": corr.name,
                 "chokepoint": corr.chokepoint, "import_share": corr.import_share,
                 "status": corr.status.value,
                 "disruption_probability": cr.disruption_probability if cr else None,
                 "band": cr.band if cr else None},
            ))
        if corr.chokepoint_coords:
            features.append(_feature(
                "Point", [corr.chokepoint_coords.lon, corr.chokepoint_coords.lat],
                {"kind": "chokepoint", "id": corr.id, "name": corr.chokepoint},
            ))
    for port in _network.ports:
        features.append(_feature(
            "Point", [port.coords.lon, port.coords.lat],
            {"kind": "port", "id": port.id, "name": port.name,
             "coast": port.coast.value, "crude_capacity_kbpd": port.crude_capacity_kbpd},
        ))
    for r in _network.refineries:
        features.append(_feature(
            "Point", [r.coords.lon, r.coords.lat],
            {"kind": "refinery", "id": r.id, "name": r.name, "operator": r.operator,
             "nameplate_kbpd": r.nameplate_kbpd, "utilization": r.utilization},
        ))
    for res in _network.reserves:
        features.append(_feature(
            "Point", [res.coords.lon, res.coords.lat],
            {"kind": "reserve", "id": res.id, "name": res.name,
             "stored_mmt": res.stored_mmt, "fill_pct": res.fill_pct},
        ))
    for v in feed.vessels:
        features.append(_feature(
            "Point", [v.lon, v.lat],
            {"kind": "vessel", "id": v.id, "name": v.name, "corridor_id": v.corridor_id,
             "speed_kn": v.speed_kn, "provenance": v.source_kind.value,
             "track": v.track},
        ))
    for e in feed.events:
        if e.lat is not None and e.lon is not None:
            features.append(_feature(
                "Point", [e.lon, e.lat],
                {"kind": "event", "id": e.id, "title": e.title, "severity": e.severity,
                 "category": e.category.value, "risk_score": e.risk_score,
                 "provenance": e.source_kind.value},
            ))
    for d in feed.detections:
        features.append(_feature(
            "Point", [d.lon, d.lat],
            {"kind": "satellite", "id": d.id, "brightness_k": d.brightness_k,
             "confidence": d.confidence, "near_asset": d.near_asset,
             "provenance": d.source_kind.value},
        ))

    counts: dict[str, int] = {}
    for f in features:
        k = f["properties"]["kind"]
        counts[k] = counts.get(k, 0) + 1
    return {"type": "FeatureCollection", "features": features,
            "schema_version": "1.0", "counts": counts}

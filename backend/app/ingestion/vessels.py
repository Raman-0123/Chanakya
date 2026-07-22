"""Vessel adapter — crude-tanker positions for the digital twin.

Live AIS via aisstream.io is a persistent websocket (populated by a background
collector when AISSTREAM_API_KEY is set). Until then this derives realistic
tanker positions along each corridor from the domain model so the map is alive.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import json
import math
import random

import websockets

from app.core.config import settings
from app.core.logging import get_logger
from app.domain import build_energy_network
from app.ingestion.models import SourceKind, Vessel

_net = build_energy_network()
log = get_logger("ingestion.vessels")

_TANKER_NAMES = [
    "New Diamond", "Sea Pioneer", "Kutch Pride", "Deccan Voyager", "Gulf Sentinel",
    "Bay Mariner", "Konkan Star", "Vindhya Spirit", "Sagar Kanya", "Aravalli",
    "Malabar Dawn", "Coromandel", "Sindhu Prabha", "Kaveri Trader", "Nilgiri",
]

# Focus the paid/live firehose on the actual energy network instead of treating
# every ship from Cape Town to Suez as an Indian crude tanker.
_MONITORED_BOXES = [
    [[22.0, 52.0], [31.5, 61.5]],      # Persian Gulf / Hormuz
    [[8.0, 30.0], [32.5, 46.0]],       # Suez / Red Sea / Bab-el-Mandeb
    [[-38.0, 12.0], [-25.0, 28.0]],    # Cape of Good Hope
    [[5.0, 66.0], [24.0, 90.0]],       # Arabian Sea + Indian crude terminals
    [[-12.0, 45.0], [16.0, 76.0]],     # western Indian Ocean approach
]


def _ship_kind(type_code: int | None) -> str:
    if type_code is None:
        return "unknown"
    if 80 <= type_code <= 89:
        return "tanker"
    if 70 <= type_code <= 79:
        return "cargo"
    if 60 <= type_code <= 69:
        return "passenger"
    if 30 <= type_code <= 39:
        return "special"
    return "other"


def _point_segment_distance(lat: float, lon: float, a, b) -> float:
    """Approximate point-to-route distance in degrees for a local geofence."""
    mean_lat = math.radians((a.lat + b.lat + lat) / 3)
    x, y = lon * math.cos(mean_lat), lat
    ax, ay = a.lon * math.cos(mean_lat), a.lat
    bx, by = b.lon * math.cos(mean_lat), b.lat
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(x - ax, y - ay)
    t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(x - (ax + t * dx), y - (ay + t * dy))


def assign_corridor(lat: float, lon: float, threshold_deg: float = 3.2) -> str | None:
    best: tuple[float, str] | None = None
    for corridor in _net.corridors:
        for a, b in zip(corridor.path, corridor.path[1:]):
            distance = _point_segment_distance(lat, lon, a, b)
            if best is None or distance < best[0]:
                best = (distance, corridor.id)
    return best[1] if best and best[0] <= threshold_deg else None


def _interp(a: dict, b: dict, t: float) -> tuple[float, float]:
    return (a["lat"] + (b["lat"] - a["lat"]) * t,
            a["lon"] + (b["lon"] - a["lon"]) * t)


def _trailing_track(path: list[dict], seg: int, t: float,
                    jlat: float, jlon: float, points: int = 5) -> list[list[float]]:
    """Recent breadcrumb positions behind the vessel, oldest→newest.

    Walks backwards along the corridor path from the vessel's current position so
    the map can draw a realistic wake trail toward India.
    """
    trail: list[list[float]] = []
    step = 0.16  # fraction of a segment between breadcrumbs
    for i in range(points, 0, -1):
        back = i * step
        s, tt = seg, t - back
        while tt < 0 and s > 0:  # roll back into the previous segment
            s -= 1
            tt += 1.0
        tt = max(0.0, tt)
        lat, lon = _interp(path[s], path[s + 1], tt)
        trail.append([round(lat + jlat, 3), round(lon + jlon, 3)])
    return trail


def synthetic_vessels(per_corridor: int = 4, seed: int = 7) -> list[Vessel]:
    rng = random.Random(seed)
    vessels: list[Vessel] = []
    n = 0
    for corr in _net.corridors:
        path = [p.model_dump() for p in corr.path]
        if len(path) < 2:
            continue
        suppliers = [s for s in _net.suppliers if s.corridor_id == corr.id]
        origin = suppliers[0].country if suppliers else "Global"
        count = max(2, int(per_corridor * (0.5 + corr.import_share)))
        for _ in range(count):
            seg = rng.randint(0, len(path) - 2)
            t = rng.random()
            lat, lon = _interp(path[seg], path[seg + 1], t)
            jitter_lat, jitter_lon = rng.uniform(-0.4, 0.4), rng.uniform(-0.4, 0.4)
            lat += jitter_lat
            lon += jitter_lon
            disrupted = corr.status.value != "operational"
            track = _trailing_track(path, seg, t, jitter_lat, jitter_lon)
            vessels.append(Vessel(
                id=f"v{n:03d}",
                name=rng.choice(_TANKER_NAMES),
                lat=round(lat, 3), lon=round(lon, 3),
                heading=round(rng.uniform(40, 110), 0),
                speed_kn=0.0 if disrupted else round(rng.uniform(9, 15), 1),
                corridor_id=corr.id, origin=origin, destination="India (west coast)",
                cargo_kbbl=round(rng.uniform(600, 2000), 0), kind="crude_tanker",
                track=track,
                source_kind=SourceKind.REPLAY,
            ))
            n += 1
    return vessels


async def fetch_vessels() -> list[Vessel]:
    live = ais_collector.snapshot()
    if live:
        return live
    return synthetic_vessels()


class AISCollector:
    """Persistent aisstream.io collector; replay remains explicit when absent."""

    def __init__(self) -> None:
        self._vessels: dict[str, Vessel] = {}
        self._static: dict[str, dict] = {}
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    def snapshot(self) -> list[Vessel]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        stale = [mmsi for mmsi, vessel in self._vessels.items()
                 if vessel.last_seen_at < cutoff]
        for mmsi in stale:
            self._vessels.pop(mmsi, None)
        # Energy operations prioritise identified tankers; retain unknowns only
        # as low-trust situational context and never use them for capacity math.
        rows = sorted(self._vessels.values(),
                      key=lambda v: ("tanker" not in v.kind, -v.last_seen_at.timestamp()))
        return rows[:150]

    async def _loop(self) -> None:
        delay = 2
        while not self._stop.is_set() and settings.aisstream_api_key:
            try:
                async with websockets.connect("wss://stream.aisstream.io/v0/stream",
                                              ping_interval=20, ping_timeout=20) as socket:
                    await socket.send(json.dumps({
                        "APIKey": settings.aisstream_api_key,
                        "BoundingBoxes": _MONITORED_BOXES,
                        "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
                    }))
                    delay = 2
                    async for raw in socket:
                        if self._stop.is_set():
                            break
                        payload = json.loads(raw)
                        message_type = payload.get("MessageType")
                        message = payload.get("Message", {})
                        meta = payload.get("MetaData", {})
                        if message_type == "ShipStaticData":
                            static = message.get("ShipStaticData", {})
                            mmsi = str(meta.get("MMSI") or static.get("UserID") or "")
                            if mmsi:
                                self._static[mmsi] = {
                                    "name": (static.get("Name") or meta.get("ShipName") or "").strip(" @"),
                                    "type": static.get("Type"),
                                    "imo": static.get("ImoNumber") or None,
                                    "destination": (static.get("Destination") or "").strip(" @") or None,
                                }
                                existing = self._vessels.get(mmsi)
                                if existing:
                                    info = self._static[mmsi]
                                    existing.kind = _ship_kind(info.get("type"))
                                    existing.ship_type_code = info.get("type")
                                    existing.imo = info.get("imo")
                                    existing.destination_reported = info.get("destination")
                                    if info.get("name"):
                                        existing.name = info["name"]
                            continue
                        if message_type != "PositionReport":
                            continue
                        report = message.get("PositionReport", {})
                        mmsi = str(meta.get("MMSI") or report.get("UserID") or "")
                        lat, lon = report.get("Latitude"), report.get("Longitude")
                        if not mmsi or lat is None or lon is None:
                            continue
                        lat, lon = float(lat), float(lon)
                        speed = float(report.get("Sog") or 0)
                        if not (-90 <= lat <= 90 and -180 <= lon <= 180 and 0 <= speed <= 45):
                            continue
                        now = datetime.now(timezone.utc)
                        existing = self._vessels.get(mmsi)
                        track = list(existing.track[-11:]) if existing else []
                        track.append([round(lat, 5), round(lon, 5)])
                        info = self._static.get(mmsi, {})
                        heading = float(report.get("TrueHeading") or report.get("Cog") or 0)
                        if heading > 360:
                            heading = float(report.get("Cog") or 0)
                        self._vessels[mmsi] = Vessel(
                            id=mmsi,
                            name=(info.get("name") or meta.get("ShipName") or f"AIS {mmsi}").strip(),
                            kind=_ship_kind(info.get("type")), lat=lat, lon=lon,
                            heading=heading, speed_kn=speed,
                            corridor_id=assign_corridor(lat, lon), track=track,
                            imo=info.get("imo"), ship_type_code=info.get("type"),
                            destination_reported=info.get("destination"), last_seen_at=now,
                            source_kind=SourceKind.LIVE,
                        )
            except Exception as exc:  # noqa: BLE001
                log.warning("aisstream.disconnected", error=str(exc), retry_seconds=delay)
                await asyncio.sleep(delay)
                delay = min(60, delay * 2)

    def start(self) -> None:
        if settings.aisstream_api_key and not self._task:
            self._task = asyncio.create_task(self._loop(), name="chanakya-ais")

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None


ais_collector = AISCollector()

"""Vessel adapter — crude-tanker positions for the digital twin.

Live AIS via aisstream.io is a persistent websocket (populated by a background
collector when AISSTREAM_API_KEY is set). Until then this derives realistic
tanker positions along each corridor from the domain model so the map is alive.
"""

from __future__ import annotations

import asyncio
import json
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
                cargo_kbbl=round(rng.uniform(600, 2000), 0),
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
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    def snapshot(self) -> list[Vessel]:
        return list(self._vessels.values())[:150]

    async def _loop(self) -> None:
        delay = 2
        while not self._stop.is_set() and settings.aisstream_api_key:
            try:
                async with websockets.connect("wss://stream.aisstream.io/v0/stream",
                                              ping_interval=20, ping_timeout=20) as socket:
                    await socket.send(json.dumps({
                        "APIKey": settings.aisstream_api_key,
                        "BoundingBoxes": [[[-40.0, 15.0], [32.0, 90.0]]],
                        "FilterMessageTypes": ["PositionReport"],
                    }))
                    delay = 2
                    async for raw in socket:
                        if self._stop.is_set():
                            break
                        payload = json.loads(raw)
                        report = payload.get("Message", {}).get("PositionReport", {})
                        meta = payload.get("MetaData", {})
                        mmsi = str(meta.get("MMSI") or report.get("UserID") or "")
                        lat, lon = report.get("Latitude"), report.get("Longitude")
                        if not mmsi or lat is None or lon is None:
                            continue
                        self._vessels[mmsi] = Vessel(
                            id=mmsi, name=(meta.get("ShipName") or f"AIS {mmsi}").strip(),
                            lat=float(lat), lon=float(lon),
                            heading=float(report.get("TrueHeading") or report.get("Cog") or 0),
                            speed_kn=float(report.get("Sog") or 0),
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

"""Typed entities for India's energy supply-chain digital twin.

Numbers are order-of-magnitude realistic (public 2024–2026 figures) and are
treated as explicit, tunable assumptions — not ground truth. Units are stated
on every field so the simulation stays auditable.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
#  Enumerations
# ---------------------------------------------------------------------------
class CrudeGrade(str, Enum):
    LIGHT_SWEET = "light_sweet"
    MEDIUM_SOUR = "medium_sour"
    HEAVY_SOUR = "heavy_sour"


class Coast(str, Enum):
    WEST = "west"
    EAST = "east"


class InfraStatus(str, Enum):
    OPERATIONAL = "operational"
    STRAINED = "strained"
    DISRUPTED = "disrupted"
    OFFLINE = "offline"


class GeoPoint(BaseModel):
    lat: float
    lon: float


# ---------------------------------------------------------------------------
#  Supply side
# ---------------------------------------------------------------------------
class ShippingCorridor(BaseModel):
    """A maritime route India's crude transits, with its chokepoint risk."""

    id: str
    name: str
    chokepoint: str
    # share of India's total crude imports transiting this corridor (0–1)
    import_share: float = Field(ge=0, le=1)
    base_transit_days: float
    # if this corridor closes, the fallback route and its penalty
    reroute_corridor_id: str | None = None
    reroute_added_days: float = 0.0
    reroute_cost_premium_pct: float = 0.0  # % added freight cost when rerouting
    status: InfraStatus = InfraStatus.OPERATIONAL
    path: list[GeoPoint] = Field(default_factory=list)
    # precise chokepoint location for the geospatial layer (map marker + FIRMS)
    chokepoint_coords: GeoPoint | None = None


class Supplier(BaseModel):
    """A crude-exporting nation India sources from."""

    id: str
    country: str
    # share of India's crude imports from this supplier (0–1)
    import_share: float = Field(ge=0, le=1)
    grade: CrudeGrade
    corridor_id: str
    # 0–100: geopolitical/contractual reliability (higher = more dependable)
    reliability: float = Field(ge=0, le=100)
    # spare export capacity this supplier could add on short notice, kbpd
    spare_capacity_kbpd: float = 0.0
    # spot premium over baseline if India buys extra on short notice, $/bbl
    spot_premium_usd: float = 0.0
    sanctioned: bool = False
    coords: GeoPoint


# ---------------------------------------------------------------------------
#  Domestic infrastructure
# ---------------------------------------------------------------------------
class Port(BaseModel):
    id: str
    name: str
    coast: Coast
    coords: GeoPoint
    crude_capacity_kbpd: float
    status: InfraStatus = InfraStatus.OPERATIONAL


class Refinery(BaseModel):
    id: str
    name: str
    operator: str
    coords: GeoPoint
    coast: Coast
    nameplate_kbpd: float          # design capacity, thousand bbl/day
    throughput_kbpd: float         # current processing rate
    preferred_grade: CrudeGrade
    # ports this refinery draws imported crude from
    port_ids: list[str]
    # days of crude inventory currently on hand
    inventory_days: float
    status: InfraStatus = InfraStatus.OPERATIONAL

    @property
    def utilization(self) -> float:
        if self.nameplate_kbpd == 0:
            return 0.0
        return round(100 * self.throughput_kbpd / self.nameplate_kbpd, 1)


class StrategicReserveSite(BaseModel):
    id: str
    name: str
    coords: GeoPoint
    capacity_mmt: float            # million metric tonnes
    fill_pct: float = Field(ge=0, le=100)

    @property
    def stored_mmt(self) -> float:
        return round(self.capacity_mmt * self.fill_pct / 100, 3)


class DemandCenter(BaseModel):
    """Downstream product-demand hub supplied by one or more refineries."""

    id: str
    name: str
    region: str
    coords: GeoPoint
    demand_share: float = Field(ge=0, le=1)
    sector_mix: dict[str, float] = Field(default_factory=dict)
    supplying_refinery_ids: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
#  Market + macro baseline
# ---------------------------------------------------------------------------
class MarketState(BaseModel):
    brent_usd: float = 82.0
    inr_usd: float = 83.4
    retail_diesel_inr_per_l: float = 89.6
    retail_petrol_inr_per_l: float = 96.7


class DemandProfile(BaseModel):
    # national refinery crude demand, thousand bbl/day
    refinery_demand_kbpd: float
    import_dependence_pct: float = 88.0
    # tonnes -> barrels conversion for crude (~7.33 bbl per tonne)
    bbl_per_tonne: float = 7.33


# ---------------------------------------------------------------------------
#  Aggregate network (the digital twin)
# ---------------------------------------------------------------------------
class EnergyNetwork(BaseModel):
    suppliers: list[Supplier]
    corridors: list[ShippingCorridor]
    ports: list[Port]
    refineries: list[Refinery]
    reserves: list[StrategicReserveSite]
    demand_centers: list[DemandCenter] = Field(default_factory=list)
    market: MarketState
    demand: DemandProfile

    # ---- convenience aggregates ----
    @property
    def total_refining_capacity_kbpd(self) -> float:
        return sum(r.nameplate_kbpd for r in self.refineries)

    @property
    def total_throughput_kbpd(self) -> float:
        return sum(r.throughput_kbpd for r in self.refineries)

    @property
    def daily_crude_imports_kbpd(self) -> float:
        return self.demand.refinery_demand_kbpd * self.demand.import_dependence_pct / 100

    @property
    def spr_total_mmt(self) -> float:
        return sum(s.stored_mmt for s in self.reserves)

    def spr_coverage_days(self) -> float:
        """How many days national refinery demand the SPR can cover."""
        stored_bbl = self.spr_total_mmt * 1_000_000 * self.demand.bbl_per_tonne
        daily_bbl = self.demand.refinery_demand_kbpd * 1000
        return round(stored_bbl / daily_bbl, 1) if daily_bbl else 0.0

    def supplier_hhi(self) -> float:
        """Herfindahl-Hirschman index of supplier concentration (0–10000)."""
        return round(sum((s.import_share * 100) ** 2 for s in self.suppliers), 1)

    def corridor(self, corridor_id: str) -> ShippingCorridor | None:
        return next((c for c in self.corridors if c.id == corridor_id), None)

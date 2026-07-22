"""National Energy Security Index (NESI).

A single 0–100 resilience score (higher = more secure) built as a transparent
weighted composite of seven components. Nothing is hidden: the breakdown and
weights are returned so the UI can explain exactly why the number moved.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.domain.entities import EnergyNetwork


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


class NesiComponent(BaseModel):
    key: str
    label: str
    score: float          # 0–100 (higher = better)
    weight: float         # 0–1
    detail: str


class NesiResult(BaseModel):
    value: float
    band: str
    components: list[NesiComponent]


WEIGHTS = {
    "supply": 0.24,
    "shipping": 0.16,
    "geopolitical": 0.14,
    "reserve": 0.14,
    "diversification": 0.12,
    "market": 0.10,
    "refinery": 0.10,
}


class NesiSignals(BaseModel):
    """Optional post-scenario overrides. When absent, baseline is derived."""

    supply_availability: float | None = None
    shipping_stability: float | None = None
    geopolitical_tension: float | None = None   # 0–100, higher = MORE tension
    market_volatility: float | None = None      # 0–100, higher = MORE volatile


def _band(value: float) -> str:
    if value >= 75:
        return "Secure"
    if value >= 60:
        return "Elevated Exposure"
    if value >= 40:
        return "High Exposure"
    return "Critical Exposure"


def compute_nesi(
    network: EnergyNetwork, signals: NesiSignals | None = None
) -> NesiResult:
    signals = signals or NesiSignals()

    # ---- reserve health: SPR coverage vs a 30-day resilience target ----
    days = network.spr_coverage_days()
    reserve = _clamp(days / 30 * 100)

    # ---- supplier diversification: from HHI concentration ----
    hhi = network.supplier_hhi()
    diversification = _clamp(100 * (4000 - hhi) / 3000)

    # ---- refinery health: national utilisation (collapse = danger) ----
    cap = network.total_refining_capacity_kbpd
    util = 100 * network.total_throughput_kbpd / cap if cap else 0
    refinery = _clamp(util)

    # ---- structural / signal-driven components ----
    supply = signals.supply_availability if signals.supply_availability is not None else 92.0
    shipping = signals.shipping_stability if signals.shipping_stability is not None else 70.0
    geo_tension = (
        signals.geopolitical_tension if signals.geopolitical_tension is not None else 52.0
    )
    volatility = (
        signals.market_volatility if signals.market_volatility is not None else 42.0
    )
    geopolitical = _clamp(100 - geo_tension)   # invert: tension lowers security
    market = _clamp(100 - volatility)

    components = [
        NesiComponent(key="supply", label="Supply Availability",
                      score=round(supply, 1), weight=WEIGHTS["supply"],
                      detail="Crude reaching refineries vs. baseline demand."),
        NesiComponent(key="shipping", label="Shipping Stability",
                      score=round(shipping, 1), weight=WEIGHTS["shipping"],
                      detail="Health of import corridors and chokepoint exposure."),
        NesiComponent(key="geopolitical", label="Geopolitical Calm",
                      score=round(geopolitical, 1), weight=WEIGHTS["geopolitical"],
                      detail=f"Inverse of active geopolitical tension ({geo_tension:.0f}/100)."),
        NesiComponent(key="reserve", label="Reserve Health",
                      score=round(reserve, 1), weight=WEIGHTS["reserve"],
                      detail=f"SPR covers ~{days:.1f} days of national demand."),
        NesiComponent(key="diversification", label="Supplier Diversification",
                      score=round(diversification, 1), weight=WEIGHTS["diversification"],
                      detail=f"Concentration HHI {hhi:.0f} (lower is safer)."),
        NesiComponent(key="market", label="Market Stability",
                      score=round(market, 1), weight=WEIGHTS["market"],
                      detail="Inverse of crude-price volatility."),
        NesiComponent(key="refinery", label="Refinery Utilisation",
                      score=round(refinery, 1), weight=WEIGHTS["refinery"],
                      detail=f"National run rate {util:.0f}% of nameplate."),
    ]

    value = round(sum(c.score * c.weight for c in components), 1)
    return NesiResult(value=value, band=_band(value), components=components)

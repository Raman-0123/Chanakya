"""Disruption scenario catalog + response levers.

A scenario defines the *shock* (what breaks in the world). Response levers are
the *decision variables* an operator tunes (how much SPR to release, whether to
reroute, whether to buy spot). Separating the two is what makes counterfactual
analysis possible: fix the shock, vary the response, compare outcomes.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ScenarioCategory(str, Enum):
    CHOKEPOINT = "chokepoint"
    MARKET = "market"
    SANCTIONS = "sanctions"
    WEATHER = "weather"
    DEMAND = "demand"


class ScenarioShock(BaseModel):
    """The disruption applied to the baseline network."""

    corridor_id: str | None = None
    block_fraction: float = Field(default=0.0, ge=0, le=1)
    duration_days: int = 14
    sanctioned_supplier_ids: list[str] = Field(default_factory=list)
    opec_cut_kbpd: float = 0.0
    demand_surge_pct: float = 0.0
    ports_offline: list[str] = Field(default_factory=list)
    # baseline Brent shock fraction this scenario type induces at full severity
    market_shock_base: float = 0.0


class ResponseLevers(BaseModel):
    """Operator decision variables layered on top of a shock."""

    spr_release_pct: float = Field(default=0.0, ge=0, le=100)
    enable_reroute: bool = True
    enable_spot: bool = True


class ScenarioSpec(BaseModel):
    id: str
    name: str
    category: ScenarioCategory
    description: str
    shock: ScenarioShock
    default_levers: ResponseLevers = Field(default_factory=ResponseLevers)


# ---------------------------------------------------------------------------
#  Catalog — the crises operators can trigger / explore
# ---------------------------------------------------------------------------
SCENARIO_CATALOG: list[ScenarioSpec] = [
    ScenarioSpec(
        id="hormuz_closure",
        name="Strait of Hormuz Closure",
        category=ScenarioCategory.CHOKEPOINT,
        description=(
            "Military escalation halts tanker traffic through the Strait of "
            "Hormuz. ~46% of India's crude imports transit here and Gulf crude "
            "has no maritime bypass — blocked volume must be replaced, not "
            "merely rerouted."
        ),
        shock=ScenarioShock(
            corridor_id="hormuz", block_fraction=0.9, duration_days=21,
            market_shock_base=0.22,
        ),
        default_levers=ResponseLevers(spr_release_pct=45),
    ),
    ScenarioSpec(
        id="red_sea_disruption",
        name="Red Sea Shipping Suspension",
        category=ScenarioCategory.CHOKEPOINT,
        description=(
            "Escalating attacks force suspension of the Red Sea / Suez corridor. "
            "Cargoes reroute around the Cape of Good Hope — supply survives but "
            "arrives ~14 days later at sharply higher freight cost."
        ),
        shock=ScenarioShock(
            corridor_id="red_sea", block_fraction=0.85, duration_days=30,
            market_shock_base=0.09,
        ),
        default_levers=ResponseLevers(spr_release_pct=15),
    ),
    ScenarioSpec(
        id="opec_cut",
        name="OPEC+ Emergency Production Cut",
        category=ScenarioCategory.MARKET,
        description=(
            "OPEC+ announces a coordinated emergency output cut, tightening the "
            "global market and erasing spare capacity India relies on for spot "
            "replacement."
        ),
        shock=ScenarioShock(
            opec_cut_kbpd=2000, duration_days=60, market_shock_base=0.14,
        ),
        default_levers=ResponseLevers(spr_release_pct=20),
    ),
    ScenarioSpec(
        id="supplier_sanctions",
        name="Sanctions on Primary Supplier",
        category=ScenarioCategory.SANCTIONS,
        description=(
            "Secondary sanctions make continued purchases from India's largest "
            "supplier untenable, forcing rapid diversification to costlier "
            "alternative grades."
        ),
        shock=ScenarioShock(
            sanctioned_supplier_ids=["russia"], duration_days=45,
            market_shock_base=0.07,
        ),
        default_levers=ResponseLevers(spr_release_pct=25),
    ),
    ScenarioSpec(
        id="west_coast_cyclone",
        name="Cyclone — Western Ports",
        category=ScenarioCategory.WEATHER,
        description=(
            "A severe cyclonic storm forces closure of Gujarat's crude terminals "
            "(Vadinar/Sikka), choking intake to Jamnagar and Vadinar refineries "
            "for several days."
        ),
        shock=ScenarioShock(
            ports_offline=["vadinar"], duration_days=5, market_shock_base=0.02,
        ),
        default_levers=ResponseLevers(spr_release_pct=10),
    ),
    ScenarioSpec(
        id="demand_surge",
        name="Seasonal Demand Surge",
        category=ScenarioCategory.DEMAND,
        description=(
            "A sharp seasonal / industrial demand surge lifts national fuel "
            "consumption faster than procurement can adjust."
        ),
        shock=ScenarioShock(
            demand_surge_pct=12, duration_days=30, market_shock_base=0.04,
        ),
        default_levers=ResponseLevers(spr_release_pct=15),
    ),
]

SCENARIO_BY_ID: dict[str, ScenarioSpec] = {s.id: s for s in SCENARIO_CATALOG}


def get_scenario(scenario_id: str) -> ScenarioSpec | None:
    return SCENARIO_BY_ID.get(scenario_id)

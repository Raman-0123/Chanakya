"""Scenario simulation endpoints — the deterministic what-if engine.

Pure compute, no LLM in the path, so responses are effectively instant and the
Simulation Lab / Counterfactual comparisons feel real-time.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.domain import SimulationEngine, build_energy_network
from app.domain.scenarios import (
    SCENARIO_CATALOG,
    ResponseLevers,
    ScenarioShock,
    ScenarioSpec,
    ScenarioCategory,
    get_scenario,
)

router = APIRouter(prefix="/simulation", tags=["simulation"])

_network = build_energy_network()
_engine = SimulationEngine(_network)


class RunRequest(BaseModel):
    scenario_id: str
    levers: ResponseLevers | None = None


class CustomRunRequest(BaseModel):
    """Ad-hoc scenario for the Scenario Lab's free-form builder."""

    name: str = "Custom Scenario"
    category: ScenarioCategory = ScenarioCategory.CHOKEPOINT
    shock: ScenarioShock
    levers: ResponseLevers | None = None


@router.get("/scenarios")
async def list_scenarios() -> list[dict]:
    """Catalog of triggerable / explorable crises."""
    return [s.model_dump() for s in SCENARIO_CATALOG]


@router.post("/run")
async def run_scenario(req: RunRequest) -> dict:
    spec = get_scenario(req.scenario_id)
    if not spec:
        raise HTTPException(404, f"Unknown scenario '{req.scenario_id}'")
    result = _engine.run(spec, req.levers)
    return result.model_dump()


@router.post("/run-custom")
async def run_custom(req: CustomRunRequest) -> dict:
    spec = ScenarioSpec(
        id="custom",
        name=req.name,
        category=req.category,
        description="Operator-defined scenario.",
        shock=req.shock,
        default_levers=req.levers or ResponseLevers(),
    )
    return _engine.run(spec, req.levers).model_dump()

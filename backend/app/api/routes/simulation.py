"""Scenario simulation endpoints — the deterministic what-if engine.

Pure compute, no LLM in the path, so responses are effectively instant and the
Simulation Lab / Counterfactual comparisons feel real-time.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.domain import SimulationEngine, build_energy_network
from app.domain.assumptions import assumptions_report
from app.domain.scenarios import (
    SCENARIO_CATALOG,
    ResponseLevers,
    ScenarioShock,
    ScenarioSpec,
    ScenarioCategory,
    get_scenario,
)
from app.operations import get_operational_service

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
    snapshot = await get_operational_service().current()
    return [snapshot.active_scenario.model_dump(mode="json")] + [
        s.model_dump(mode="json") for s in SCENARIO_CATALOG
    ]


@router.get("/assumptions")
async def model_assumptions() -> dict:
    """Explicit, testable model-fidelity assumptions with a live self-audit.

    Every structural and calibration assumption behind the scenario engine,
    each checked against the running model right now (PASS/FAIL).
    """
    return assumptions_report(_network)


@router.post("/run")
async def run_scenario(req: RunRequest) -> dict:
    operational = await get_operational_service().current()
    spec = (operational.active_scenario if req.scenario_id == "auto_live"
            else get_scenario(req.scenario_id))
    if not spec:
        raise HTTPException(404, f"Unknown scenario '{req.scenario_id}'")
    result = _engine.run(spec, req.levers, operational)
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
    operational = await get_operational_service().current()
    return _engine.run(spec, req.levers, operational).model_dump()

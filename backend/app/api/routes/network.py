"""Digital-twin network endpoints — the baseline energy supply chain + NESI."""

from __future__ import annotations

from fastapi import APIRouter

from app.domain import build_energy_network, compute_nesi

router = APIRouter(prefix="/network", tags=["network"])

# The baseline twin is process-wide and immutable; build once.
_network = build_energy_network()


@router.get("")
async def get_network() -> dict:
    """Full digital twin plus derived aggregates for the map + inspectors."""
    net = _network
    return {
        "suppliers": [s.model_dump() for s in net.suppliers],
        "corridors": [c.model_dump() for c in net.corridors],
        "ports": [p.model_dump() for p in net.ports],
        "refineries": [
            {**r.model_dump(), "utilization": r.utilization} for r in net.refineries
        ],
        "reserves": [
            {**r.model_dump(), "stored_mmt": r.stored_mmt} for r in net.reserves
        ],
        "demand_centers": [center.model_dump() for center in net.demand_centers],
        "market": net.market.model_dump(),
        "demand": net.demand.model_dump(),
        "aggregates": {
            "total_refining_capacity_kbpd": net.total_refining_capacity_kbpd,
            "total_throughput_kbpd": net.total_throughput_kbpd,
            "daily_crude_imports_kbpd": round(net.daily_crude_imports_kbpd, 1),
            "spr_total_mmt": net.spr_total_mmt,
            "spr_coverage_days": net.spr_coverage_days(),
            "supplier_hhi": net.supplier_hhi(),
        },
    }


@router.get("/nesi")
async def get_nesi() -> dict:
    """Current baseline National Energy Security Index with full breakdown."""
    return compute_nesi(_network).model_dump()

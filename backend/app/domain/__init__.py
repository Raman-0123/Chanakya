"""CHANAKYA domain core.

A deterministic, explainable model of India's crude-oil supply chain and the
scenario engine that simulates disruption. This package is the single source of
truth every downstream module (agents, decision engine, simulation lab, NESI)
reads from — it holds ZERO black boxes: every impact carries its assumptions.
"""

__all__ = ["build_energy_network", "SimulationEngine", "compute_nesi"]


def __getattr__(name: str):
    """Load domain entry points lazily to keep type-only dependencies acyclic."""
    if name == "build_energy_network":
        from app.domain.seed import build_energy_network
        return build_energy_network
    if name == "SimulationEngine":
        from app.domain.engine import SimulationEngine
        return SimulationEngine
    if name == "compute_nesi":
        from app.domain.nesi import compute_nesi
        return compute_nesi
    raise AttributeError(name)

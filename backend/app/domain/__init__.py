"""CHANAKYA domain core.

A deterministic, explainable model of India's crude-oil supply chain and the
scenario engine that simulates disruption. This package is the single source of
truth every downstream module (agents, decision engine, simulation lab, NESI)
reads from — it holds ZERO black boxes: every impact carries its assumptions.
"""

from app.domain.seed import build_energy_network
from app.domain.engine import SimulationEngine
from app.domain.nesi import compute_nesi

__all__ = ["build_energy_network", "SimulationEngine", "compute_nesi"]

"""Aggregate API router — mounts every route module under /api."""

from fastapi import APIRouter

from app.api.routes import (
    council, events, graph, health, intelligence, missions, network,
    ontology, operations, realtime, satellite, simulation, sources, workflows,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(network.router)
api_router.include_router(simulation.router)
api_router.include_router(intelligence.router)
api_router.include_router(council.router)
api_router.include_router(graph.router)
api_router.include_router(ontology.router)
api_router.include_router(events.router)
api_router.include_router(sources.router)
api_router.include_router(workflows.router)
api_router.include_router(missions.router)
api_router.include_router(realtime.router)
api_router.include_router(satellite.router)
api_router.include_router(operations.router)

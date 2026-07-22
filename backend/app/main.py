"""CHANAKYA backend — FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db import get_datastores, get_repositories
from app.ingestion.pipeline import pipeline
from app.events import stream_consumer
from app.ingestion.vessels import ais_collector
from app.rag import evidence_store
from app.llm.router import get_llm_router

configure_logging()
log = get_logger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("app.starting", version=__version__, env=settings.environment)
    await get_datastores().connect()
    repositories = get_repositories()
    repositories.bind(get_datastores())
    await repositories.initialize()
    await evidence_store.ensure_corpus()
    router = get_llm_router()
    if not router.available:
        log.warning(
            "app.no_llm_provider",
            hint="Set at least one *_API_KEY in .env to enable the agent council.",
        )
    log.info("app.ready")
    if settings.process_role in {"all", "worker"}:
        pipeline.start()
        stream_consumer.start()
        ais_collector.start()
    yield
    if settings.process_role in {"all", "worker"}:
        await pipeline.stop()
        await stream_consumer.stop()
        await ais_collector.stop()
    await get_datastores().disconnect()
    log.info("app.stopped")


app = FastAPI(
    title="CHANAKYA — Energy Crisis Operating System",
    description="AI-native operational intelligence for national energy resilience.",
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    # accept any localhost / 127.0.0.1 port in dev so a port change never breaks CORS
    allow_origin_regex=(None if settings.is_production else
                        r"https?://(localhost|127\.0\.0\.1):\d+"),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.middleware("http")
async def operational_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid4().hex
    # Lightweight distributed guard suitable for the public demo. Failure of
    # Redis never makes the API unavailable.
    redis = get_datastores().redis
    if redis is not None and request.url.path.startswith("/api/"):
        try:
            minute = int(__import__("time").time() // 60)
            key = f"rate:{request.client.host if request.client else 'unknown'}:{minute}"
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, 70)
            if count > 300:
                return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429,
                                    headers={"x-request-id": request_id})
        except Exception:  # noqa: BLE001
            pass
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    response.headers["x-content-type-options"] = "nosniff"
    return response


@app.get("/", tags=["system"])
async def root() -> dict:
    return {
        "name": "CHANAKYA",
        "tagline": "AI-Powered Energy Crisis Operating System",
        "version": __version__,
        "docs": "/docs",
        "health": "/api/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=not settings.is_production,
    )

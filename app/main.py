"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Response, status
from redis.asyncio import Redis

from app import __version__
from app.config import get_settings
from app.db import get_engine, ping_database
from app.web.routes import demo
from app.webhooks import forms


async def ping_redis() -> bool:
    client: Redis = Redis.from_url(get_settings().redis_url)
    try:
        return bool(await client.ping())
    except Exception:
        return False
    finally:
        await client.aclose()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await get_engine().dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="AdmissionPilot", version=__version__, lifespan=lifespan)

    @app.get("/health")
    async def health() -> dict[str, Any]:
        """Liveness: the process is up. No dependencies checked."""
        settings = get_settings()
        return {"status": "ok", "version": __version__, "dry_run": settings.dry_run}

    @app.get("/health/ready")
    async def ready(response: Response) -> dict[str, Any]:
        """Readiness: database and Redis reachable."""
        checks = {"database": await ping_database(), "redis": await ping_redis()}
        healthy = all(checks.values())
        if not healthy:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "ok" if healthy else "degraded", "checks": checks}

    app.include_router(demo.router)
    app.include_router(forms.router)
    return app


app = create_app()

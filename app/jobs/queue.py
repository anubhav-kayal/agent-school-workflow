"""Enqueue background jobs. Webhooks depend on the `Enqueuer` protocol, not on arq."""

from __future__ import annotations

from typing import Any, Protocol

from arq import ArqRedis, create_pool
from arq.connections import RedisSettings

from app.config import get_settings


class Enqueuer(Protocol):
    async def __call__(self, job: str, *, job_id: str | None = None, **kwargs: Any) -> None: ...


class ArqEnqueuer:
    def __init__(self) -> None:
        self._pool: ArqRedis | None = None

    async def __call__(self, job: str, *, job_id: str | None = None, **kwargs: Any) -> None:
        if self._pool is None:
            self._pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
        # arq ignores a job whose id is already queued/running: cheap idempotency.
        await self._pool.enqueue_job(job, _job_id=job_id, **kwargs)


_enqueuer = ArqEnqueuer()


def get_enqueuer() -> Enqueuer:
    return _enqueuer

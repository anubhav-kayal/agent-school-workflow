from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.jobs.queue import get_enqueuer
from app.main import create_app


class RecordingEnqueuer:
    def __init__(self) -> None:
        self.jobs: list[tuple[str, str | None, dict[str, Any]]] = []

    async def __call__(self, job: str, *, job_id: str | None = None, **kwargs: Any) -> None:
        self.jobs.append((job, job_id, kwargs))


@pytest.fixture
def enqueuer() -> RecordingEnqueuer:
    return RecordingEnqueuer()


@pytest.fixture
async def client(db: AsyncSession, enqueuer: RecordingEnqueuer) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app()

    async def session() -> AsyncIterator[AsyncSession]:
        yield db

    app.dependency_overrides[get_session] = session
    app.dependency_overrides[get_enqueuer] = lambda: enqueuer
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        yield c

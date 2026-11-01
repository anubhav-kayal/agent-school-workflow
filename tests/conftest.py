"""Shared fixtures.

DB tests use the docker-compose test database (`make up`). The schema is created once
per session from model metadata; each test runs inside a transaction that is rolled back.
"""

from __future__ import annotations

import ipaddress
import os
import socket
from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from app.models import Base

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://admissionpilot:admissionpilot@localhost:5433/admissionpilot_test",
)


_real_connect = socket.socket.connect


def _guarded_connect(self: socket.socket, address: Any) -> Any:
    """Tests may only reach loopback (Postgres/Redis). External APIs must be faked."""
    if self.family in (socket.AF_INET, socket.AF_INET6):
        host = address[0]
        if not ipaddress.ip_address(host).is_loopback:
            raise RuntimeError(f"test tried to reach the network: {address!r}")
    return _real_connect(self, address)


@pytest.fixture(autouse=True, scope="session")
def block_external_network() -> Iterator[None]:
    socket.socket.connect = _guarded_connect  # type: ignore[method-assign]
    yield
    socket.socket.connect = _real_connect  # type: ignore[method-assign]


@pytest.fixture(scope="session")
async def db_engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db(db_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with db_engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(
            bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()

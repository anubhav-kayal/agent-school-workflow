from collections.abc import AsyncIterator

import httpx
import pytest

from app import main
from app.main import create_app


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_health_reports_dry_run(client: httpx.AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["dry_run"] is True


async def test_ready_ok_when_dependencies_up(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def up() -> bool:
        return True

    monkeypatch.setattr(main, "ping_database", up)
    monkeypatch.setattr(main, "ping_redis", up)
    resp = await client.get("/health/ready")
    assert resp.status_code == 200
    assert resp.json()["checks"] == {"database": True, "redis": True}


async def test_ready_degraded_when_database_down(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def up() -> bool:
        return True

    async def down() -> bool:
        return False

    monkeypatch.setattr(main, "ping_database", down)
    monkeypatch.setattr(main, "ping_redis", up)
    resp = await client.get("/health/ready")
    assert resp.status_code == 503
    assert resp.json()["status"] == "degraded"

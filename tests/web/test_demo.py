from collections.abc import AsyncIterator
from datetime import date

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.llm.fake import ScriptedProvider, text_turn, tool_turn
from app.config import Settings, get_settings
from app.db import get_session
from app.main import create_app
from app.seed import seed
from app.web.routes import demo


def client_for(db: AsyncSession, demo_mode: bool, provider: object = None) -> httpx.AsyncClient:
    app = create_app()

    async def session() -> AsyncIterator[AsyncSession]:
        yield db

    app.dependency_overrides[get_session] = session
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, demo_mode=demo_mode)  # type: ignore[call-arg]
    app.dependency_overrides[demo.provider_or_none] = lambda: provider
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_demo_hidden_unless_demo_mode(db: AsyncSession) -> None:
    async with client_for(db, demo_mode=False) as c:
        assert (await c.get("/demo/chat")).status_code == 404


async def test_demo_flow_template_then_assistant_with_slot_buttons(db: AsyncSession) -> None:
    await seed(db, today=date(2026, 11, 2))
    demo.TRANSPORT.sent.clear()
    provider = ScriptedProvider(
        [
            tool_turn("get_visit_slots", from_date=None, to_date=None),
            text_turn("Please pick a time below."),
        ]
    )
    async with client_for(db, demo_mode=True, provider=provider) as c:
        page = await c.get("/demo/chat")
        assert "Demo — sample school data" in page.text
        started = await c.post("/demo/start", data={"parent_name": "Priya", "grade": "Class 1"})
        assert started.status_code == 303
        chat = (await c.get("/demo/partials/chat")).text
        assert "Template · no AI" in chat and "Hello Priya" in chat
        assert provider.requests == []  # first message used no LLM
        chat = (await c.post("/demo/send", data={"text": "Can we visit the campus?"})).text
        assert "Please pick a time below." in chat
        assert 'hx-vals=\'{"button_id": "slot:' in chat
        side = (await c.get("/demo/partials/side")).text
        assert "gpt-6-luna" in side and "get_visit_slots" in side
    assert all(p["to"].startswith("9199999") for p in demo.TRANSPORT.sent)  # fake numbers only


async def test_send_without_api_key_explains(db: AsyncSession) -> None:
    await seed(db, today=date(2026, 11, 2))
    async with client_for(db, demo_mode=True, provider=None) as c:
        await c.post("/demo/start", data={"parent_name": "Ravi", "grade": "Nursery"})
        resp = await c.post("/demo/send", data={"text": "fees?"})
        assert resp.status_code == 200  # htmx only swaps 2xx; show the notice in the chat
        assert "OPENAI_API_KEY is not set" in resp.text


@pytest.mark.parametrize("event", ["visited", "admitted"])
async def test_counselor_buttons_update_status(db: AsyncSession, event: str) -> None:
    await seed(db, today=date(2026, 11, 2))
    async with client_for(db, demo_mode=True) as c:
        await c.post("/demo/start", data={"parent_name": "Asha", "grade": "Class 5"})
        side = (await c.post(f"/demo/counselor/{event}")).text
        assert event.replace("_", " ") in side

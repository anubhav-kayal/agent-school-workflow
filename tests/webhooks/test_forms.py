from datetime import date

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.seed import SLUG, seed
from tests.webhooks.conftest import RecordingEnqueuer

FORM = {
    "parent_name": "Priya",
    "phone": "99999 00030",
    "grade_interest": "Nursery",
    "consent": True,
}


async def test_form_creates_lead_and_enqueues_first_response(
    db: AsyncSession, client: httpx.AsyncClient, enqueuer: RecordingEnqueuer
) -> None:
    await seed(db, today=date(2026, 11, 2))
    resp = await client.post(f"/webhooks/forms/{SLUG}", json=FORM)
    assert resp.status_code == 202
    lead_id = resp.json()["lead_id"]
    assert enqueuer.jobs == [("send_first_response", f"first:{lead_id}", {"lead_id": lead_id})]


async def test_form_rejects_missing_consent_and_bad_phone(
    db: AsyncSession, client: httpx.AsyncClient
) -> None:
    await seed(db, today=date(2026, 11, 2))
    assert (
        await client.post(f"/webhooks/forms/{SLUG}", json={**FORM, "consent": False})
    ).status_code == 422
    assert (
        await client.post(f"/webhooks/forms/{SLUG}", json={**FORM, "phone": "12345"})
    ).status_code == 422
    assert (await client.post("/webhooks/forms/nope", json=FORM)).status_code == 404

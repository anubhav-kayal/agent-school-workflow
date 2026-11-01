"""Meta Lead Ads webhook: subscription challenge + signed leadgen notifications."""

from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from app.adapters.meta_leads import parse_leadgen_webhook, verify_signature
from app.config import Settings, get_settings
from app.jobs.queue import Enqueuer, get_enqueuer

router = APIRouter(prefix="/webhooks/meta", tags=["webhooks"])
SettingsDep = Annotated[Settings, Depends(get_settings)]


def verify_challenge(
    mode: str | None, token: str | None, challenge: str | None, expected: str | None
) -> PlainTextResponse:
    if mode == "subscribe" and expected and token == expected and challenge:
        return PlainTextResponse(challenge)
    raise HTTPException(403, "verification failed")


@router.get("/leads", response_class=PlainTextResponse)
async def subscribe(
    settings: SettingsDep,
    mode: Annotated[str | None, Query(alias="hub.mode")] = None,
    token: Annotated[str | None, Query(alias="hub.verify_token")] = None,
    challenge: Annotated[str | None, Query(alias="hub.challenge")] = None,
) -> PlainTextResponse:
    expected = settings.meta_verify_token.get_secret_value() if settings.meta_verify_token else None
    return verify_challenge(mode, token, challenge, expected)


@router.post("/leads")
async def leadgen(
    request: Request, settings: SettingsDep, enqueue: Annotated[Enqueuer, Depends(get_enqueuer)]
) -> dict[str, Any]:
    body = await request.body()
    secret = settings.meta_app_secret.get_secret_value() if settings.meta_app_secret else ""
    if not secret or not verify_signature(secret, body, request.headers.get("x-hub-signature-256")):
        raise HTTPException(401, "bad signature")
    events = parse_leadgen_webhook(json.loads(body))
    for e in events:
        await enqueue(
            "process_meta_lead",
            job_id=f"metalead:{e.leadgen_id}",
            leadgen_id=e.leadgen_id,
            page_id=e.page_id,
        )
    return {"queued": len(events)}

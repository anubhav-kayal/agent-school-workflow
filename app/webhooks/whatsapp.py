"""WhatsApp Cloud API webhook: challenge, signature, statuses inline, messages queued."""

from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.meta_leads import verify_signature
from app.adapters.whatsapp_inbound import parse_whatsapp_webhook
from app.config import Settings, get_settings
from app.db import get_session
from app.jobs.queue import Enqueuer, get_enqueuer
from app.services.inbound_whatsapp import apply_status
from app.webhooks.meta_leads import verify_challenge

router = APIRouter(prefix="/webhooks/whatsapp", tags=["webhooks"])
SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.get("", response_class=PlainTextResponse)
async def subscribe(
    settings: SettingsDep,
    mode: Annotated[str | None, Query(alias="hub.mode")] = None,
    token: Annotated[str | None, Query(alias="hub.verify_token")] = None,
    challenge: Annotated[str | None, Query(alias="hub.challenge")] = None,
) -> PlainTextResponse:
    expected = settings.meta_verify_token.get_secret_value() if settings.meta_verify_token else None
    return verify_challenge(mode, token, challenge, expected)


@router.post("")
async def receive(
    request: Request,
    settings: SettingsDep,
    db: Annotated[AsyncSession, Depends(get_session)],
    enqueue: Annotated[Enqueuer, Depends(get_enqueuer)],
) -> dict[str, Any]:
    body = await request.body()
    secret = settings.whatsapp_app_secret or settings.meta_app_secret
    key = secret.get_secret_value() if secret else ""
    if not key or not verify_signature(key, body, request.headers.get("x-hub-signature-256")):
        raise HTTPException(401, "bad signature")
    messages, statuses = parse_whatsapp_webhook(json.loads(body))
    for status in statuses:
        await apply_status(db, status)
    await db.commit()
    for m in messages:
        await enqueue(
            "process_whatsapp_message",
            job_id=f"wa:{m.wa_message_id}",
            phone_number_id=m.phone_number_id,
            sender=m.sender,
            wa_message_id=m.wa_message_id,
            sent_at=m.sent_at.isoformat(),
            text=m.text,
            button_id=m.button_id,
        )
    return {"messages": len(messages), "statuses": len(statuses)}

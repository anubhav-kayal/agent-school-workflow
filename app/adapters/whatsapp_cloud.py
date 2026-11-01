"""WhatsApp Cloud API transport (httpx). Only used when DRY_RUN is off and DEMO_MODE is off."""

from __future__ import annotations

from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.adapters.whatsapp import OutsideServiceWindowError

GRAPH_BASE = "https://graph.facebook.com"
# TO VERIFY: Cloud API error code for messages outside the customer service window.
REENGAGEMENT_ERROR_CODE = 131047


class WhatsAppApiError(Exception):
    def __init__(self, status: int, code: int | None, message: str) -> None:
        super().__init__(f"WhatsApp API {status} (code={code}): {message}")
        self.status = status
        self.code = code


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    return isinstance(exc, WhatsAppApiError) and (exc.status == 429 or exc.status >= 500)


class CloudApiTransport:
    def __init__(
        self,
        client: httpx.AsyncClient,
        token: str,
        phone_number_id: str,
        graph_version: str,
        max_attempts: int = 4,
    ) -> None:
        self._client = client
        self._url = f"{GRAPH_BASE}/{graph_version}/{phone_number_id}/messages"
        self._headers = {"Authorization": f"Bearer {token}"}
        self._max_attempts = max_attempts

    async def send(self, payload: dict[str, Any]) -> str:
        async for attempt in AsyncRetrying(
            retry=retry_if_exception(_retryable),
            stop=stop_after_attempt(self._max_attempts),
            wait=wait_exponential_jitter(multiplier=0.5, max=8),
            reraise=True,
        ):
            with attempt:
                return await self._post(payload)
        raise AssertionError("unreachable")

    async def _post(self, payload: dict[str, Any]) -> str:
        resp = await self._client.post(self._url, json=payload, headers=self._headers, timeout=10)
        if resp.status_code >= 400:
            error = resp.json().get("error", {}) if resp.content else {}
            code = error.get("code")
            if code == REENGAGEMENT_ERROR_CODE:
                raise OutsideServiceWindowError(error.get("message", "outside window"))
            raise WhatsAppApiError(resp.status_code, code, error.get("message", resp.text))
        return str(resp.json()["messages"][0]["id"])

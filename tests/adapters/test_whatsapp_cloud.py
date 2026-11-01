import httpx
import pytest
import respx

from app.adapters.whatsapp import OutsideServiceWindowError
from app.adapters.whatsapp_cloud import CloudApiTransport, WhatsAppApiError

URL = "https://graph.facebook.com/v24.0/PHONE_ID/messages"
PAYLOAD = {
    "messaging_product": "whatsapp",
    "to": "919999900001",
    "type": "text",
    "text": {"body": "hi"},
}


def transport(client: httpx.AsyncClient) -> CloudApiTransport:
    return CloudApiTransport(client, "FAKE_TOKEN", "PHONE_ID", "v24.0", max_attempts=3)


@respx.mock
async def test_send_returns_message_id_and_sends_bearer() -> None:
    route = respx.post(URL).respond(200, json={"messages": [{"id": "wamid.ABC"}]})
    async with httpx.AsyncClient() as client:
        assert await transport(client).send(PAYLOAD) == "wamid.ABC"
    assert route.calls[0].request.headers["Authorization"] == "Bearer FAKE_TOKEN"


@respx.mock
async def test_retries_on_throttling_then_succeeds() -> None:
    respx.post(URL).mock(
        side_effect=[
            httpx.Response(429, json={"error": {"code": 130429, "message": "throttled"}}),
            httpx.Response(200, json={"messages": [{"id": "wamid.OK"}]}),
        ]
    )
    async with httpx.AsyncClient() as client:
        assert await transport(client).send(PAYLOAD) == "wamid.OK"


@respx.mock
async def test_client_error_not_retried() -> None:
    route = respx.post(URL).respond(400, json={"error": {"code": 100, "message": "bad param"}})
    async with httpx.AsyncClient() as client:
        with pytest.raises(WhatsAppApiError):
            await transport(client).send(PAYLOAD)
    assert route.call_count == 1


@respx.mock
async def test_reengagement_error_maps_to_window_error() -> None:
    respx.post(URL).respond(400, json={"error": {"code": 131047, "message": "re-engage"}})
    async with httpx.AsyncClient() as client:
        with pytest.raises(OutsideServiceWindowError):
            await transport(client).send(PAYLOAD)

import hashlib
import hmac
import json

import httpx
import respx

from app.adapters.meta_leads import GraphLeadClient, parse_leadgen_webhook, verify_signature

SECRET = "fake-app-secret"
# Shape of Meta's documented leadgen webhook example (ids are fake).
WEBHOOK = {
    "object": "page",
    "entry": [
        {
            "id": "000000000000001",
            "time": 1762000000,
            "changes": [
                {
                    "field": "leadgen",
                    "value": {
                        "leadgen_id": "444444444",
                        "page_id": "000000000000001",
                        "form_id": "555",
                        "ad_id": "666",
                        "created_time": 1762000000,
                    },
                },
                {"field": "feed", "value": {"item": "status"}},
            ],
        }
    ],
}
GRAPH_LEAD = {
    "id": "444444444",
    "created_time": "2026-11-02T04:00:00+0000",
    "ad_id": "666",
    "adset_id": "777",
    "campaign_id": "888",
    "form_id": "555",
    "field_data": [
        {"name": "full_name", "values": ["Test Parent"]},
        {"name": "phone_number", "values": ["+919999900040"]},
        {"name": "which_class_are_you_seeking_admission_for?", "values": ["Class 1"]},
    ],
}


def sign(body: bytes) -> str:
    return "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()


def test_signature_valid_and_tampered() -> None:
    body = json.dumps(WEBHOOK).encode()
    assert verify_signature(SECRET, body, sign(body))
    assert not verify_signature(SECRET, body + b" ", sign(body))
    assert not verify_signature(SECRET, body, None)
    assert not verify_signature(SECRET, body, "sha1=abc")


def test_parse_only_leadgen_changes() -> None:
    [event] = parse_leadgen_webhook(WEBHOOK)
    assert (event.leadgen_id, event.page_id, event.form_id, event.ad_id) == (
        "444444444",
        "000000000000001",
        "555",
        "666",
    )
    assert parse_leadgen_webhook({"object": "instagram", "entry": []}) == []


@respx.mock
async def test_fetch_lead_flattens_fields() -> None:
    route = respx.get("https://graph.facebook.com/v24.0/444444444").respond(200, json=GRAPH_LEAD)
    async with httpx.AsyncClient() as http:
        lead = await GraphLeadClient(http, "FAKE_TOKEN", "v24.0").fetch_lead("444444444")
    assert lead.fields["full_name"] == "Test Parent"
    assert lead.first("class", "grade") == "Class 1"
    assert (lead.adset_id, lead.campaign_id) == ("777", "888")
    request = route.calls[0].request
    assert "access_token" not in str(request.url)  # token never in URLs/logs
    assert request.headers["Authorization"] == "Bearer FAKE_TOKEN"

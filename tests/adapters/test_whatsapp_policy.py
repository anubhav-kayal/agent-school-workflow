from datetime import UTC, datetime, timedelta

import pytest

from app.adapters.fakes.whatsapp import FakeWhatsAppTransport
from app.adapters.whatsapp import (
    Button,
    OptedOutError,
    OutsideServiceWindowError,
    Recipient,
    TemplateNotApprovedError,
    WhatsAppAdapter,
)

NOW = datetime(2026, 11, 2, 6, 0, tzinfo=UTC)
PHONE = "+919999900001"


def adapter() -> tuple[WhatsAppAdapter, FakeWhatsAppTransport]:
    transport = FakeWhatsAppTransport()
    wa = WhatsAppAdapter(transport, {("enquiry_first_response", "en")}, clock=lambda: NOW)
    return wa, transport


def parent(hours_since_inbound: float | None, opted_out: bool = False) -> Recipient:
    last = None if hours_since_inbound is None else NOW - timedelta(hours=hours_since_inbound)
    return Recipient(PHONE, last_inbound_at=last, opted_out_at=NOW if opted_out else None)


async def test_free_form_inside_window() -> None:
    wa, transport = adapter()
    msg_id = await wa.send_text(parent(23.9), "Hello")
    assert msg_id.startswith("wamid.")
    assert transport.sent[0]["text"] == {"body": "Hello"}
    assert transport.sent[0]["to"] == "919999900001"


@pytest.mark.parametrize("hours", [None, 24, 30])
async def test_free_form_blocked_outside_window(hours: float | None) -> None:
    wa, transport = adapter()
    with pytest.raises(OutsideServiceWindowError):
        await wa.send_text(parent(hours), "Hello")
    with pytest.raises(OutsideServiceWindowError):
        await wa.send_buttons(parent(hours), "Pick", [Button("a", "A")])
    assert transport.sent == []


async def test_template_allowed_outside_window() -> None:
    wa, transport = adapter()
    await wa.send_template(parent(None), "enquiry_first_response", "en", ["Priya", "Demo"])
    params = transport.sent[0]["template"]["components"][0]["parameters"]
    assert [p["text"] for p in params] == ["Priya", "Demo"]


async def test_unapproved_template_blocked() -> None:
    wa, _ = adapter()
    with pytest.raises(TemplateNotApprovedError):
        await wa.send_template(parent(None), "enquiry_first_response", "hi", [])


async def test_opted_out_blocks_every_kind_of_send() -> None:
    wa, transport = adapter()
    gone = parent(1, opted_out=True)
    with pytest.raises(OptedOutError):
        await wa.send_text(gone, "Hi")
    with pytest.raises(OptedOutError):
        await wa.send_template(gone, "enquiry_first_response", "en", ["x"])
    with pytest.raises(OptedOutError):
        await wa.send_list(gone, "Pick", "Slots", [Button("s1", "Sat 10:00")])
    assert transport.sent == []


async def test_button_limits_and_title_truncation() -> None:
    wa, transport = adapter()
    with pytest.raises(ValueError):
        await wa.send_buttons(parent(1), "Pick", [Button(str(i), "x") for i in range(4)])
    await wa.send_buttons(parent(1), "Pick", [Button("slot:1", "Saturday 7 November 10:00 AM")])
    reply = transport.sent[0]["interactive"]["action"]["buttons"][0]["reply"]
    assert reply == {"id": "slot:1", "title": "Saturday 7 November"}

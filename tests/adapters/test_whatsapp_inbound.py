from app.adapters.whatsapp_inbound import parse_whatsapp_webhook


def envelope(value: dict) -> dict:  # type: ignore[type-arg]
    value = {
        "messaging_product": "whatsapp",
        "metadata": {"display_phone_number": "910000000000", "phone_number_id": "000000000000002"},
        **value,
    }
    return {
        "object": "whatsapp_business_account",
        "entry": [{"id": "WABA_FAKE", "changes": [{"field": "messages", "value": value}]}],
    }


TEXT = envelope(
    {
        "contacts": [{"wa_id": "919999900050", "profile": {"name": "Test"}}],
        "messages": [
            {
                "from": "919999900050",
                "id": "wamid.T1",
                "timestamp": "1762056000",
                "type": "text",
                "text": {"body": "fees kitni hai?"},
            }
        ],
    }
)
BUTTON = envelope(
    {
        "messages": [
            {
                "from": "919999900050",
                "id": "wamid.B1",
                "timestamp": "1762056000",
                "type": "interactive",
                "interactive": {
                    "type": "button_reply",
                    "button_reply": {"id": "slot:12", "title": "Sat 7 Nov, 10:00 AM"},
                },
            }
        ]
    }
)
QUICK = envelope(
    {
        "messages": [
            {
                "from": "919999900102",
                "id": "wamid.Q1",
                "timestamp": "1762056000",
                "type": "button",
                "button": {"payload": "lead:5:visited", "text": "Visited"},
            }
        ]
    }
)
STATUS = envelope(
    {
        "statuses": [
            {
                "id": "wamid.OUT1",
                "status": "read",
                "timestamp": "1762056000",
                "recipient_id": "919999900050",
            }
        ]
    }
)


def test_text_message() -> None:
    [m], _ = parse_whatsapp_webhook(TEXT)
    assert (m.sender, m.text, m.button_id, m.phone_number_id) == (
        "+919999900050",
        "fees kitni hai?",
        None,
        "000000000000002",
    )


def test_interactive_and_template_buttons() -> None:
    [m], _ = parse_whatsapp_webhook(BUTTON)
    assert (m.button_id, m.text) == ("slot:12", "Sat 7 Nov, 10:00 AM")
    [q], _ = parse_whatsapp_webhook(QUICK)
    assert q.button_id == "lead:5:visited"


def test_statuses_and_unknown_types() -> None:
    _, [s] = parse_whatsapp_webhook(STATUS)
    assert (s.wa_message_id, s.status) == ("wamid.OUT1", "read")
    image = envelope({"messages": [{"from": "1", "id": "w", "timestamp": "0", "type": "image"}]})
    assert parse_whatsapp_webhook(image) == ([], [])

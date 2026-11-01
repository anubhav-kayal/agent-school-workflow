import pytest

from app.models.enums import LeadEventType
from app.services.routing import Route, route_inbound


@pytest.mark.parametrize(
    "text",
    ["STOP", "stop.", " Stop messages ", "Unsubscribe", "बंद करो", "मैसेज बंद करें।", "band karo"],
)
def test_stop_phrases_opt_out(text: str) -> None:
    assert route_inbound(text, None).route is Route.OPT_OUT


@pytest.mark.parametrize(
    "text",
    ["please don't stop sending updates", "bus stop near school?", "fees kya hai"],
)
def test_sentences_containing_stop_go_to_llm(text: str) -> None:
    assert route_inbound(text, None).route is Route.LLM


def test_opt_out_button() -> None:
    assert route_inbound("Stop messages", "optout").route is Route.OPT_OUT


def test_slot_button() -> None:
    d = route_inbound("Sat 7 Nov, 10:00 AM", "slot:42")
    assert (d.route, d.slot_id) == (Route.BOOK_SLOT, 42)


def test_counselor_button() -> None:
    d = route_inbound("Visited", "lead:17:visited")
    assert (d.route, d.lead_id, d.event) == (Route.COUNSELOR_STATUS, 17, LeadEventType.VISITED)


@pytest.mark.parametrize("button", ["slot:abc", "lead:x:visited", "lead:1:hacked", "other"])
def test_malformed_buttons_fall_back_to_llm(button: str) -> None:
    assert route_inbound("hello", button).route is Route.LLM

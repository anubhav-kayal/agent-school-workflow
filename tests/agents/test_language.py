import pytest

from app.agents.language import detect_language


@pytest.mark.parametrize(
    ("text", "lang"),
    [
        ("What are the fees for class 1?", "en"),
        ("कक्षा 1 की फीस कितनी है?", "hi"),
        ("class 1 ki fees kitni hai?", "hinglish"),
        ("Bus facility milegi kya Baner se?", "hinglish"),
        ("नर्सरी की tuition fees ₹65,000 per year है, जो 4 instalments में payable है।", "hi"),
    ],
)
def test_detect_language(text: str, lang: str) -> None:
    assert detect_language(text) == lang

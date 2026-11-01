import pytest

from app.agents.language import detect_language


@pytest.mark.parametrize(
    ("text", "lang"),
    [
        ("What are the fees for class 1?", "en"),
        ("कक्षा 1 की फीस कितनी है?", "hi"),
        ("class 1 ki fees kitni hai?", "hinglish"),
        ("Bus facility milegi kya Baner se?", "hinglish"),
    ],
)
def test_detect_language(text: str, lang: str) -> None:
    assert detect_language(text) == lang

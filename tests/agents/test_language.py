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


def test_purity_metrics() -> None:
    from app.agents.language import devanagari_share, hindi_word_share

    good_hi = "कक्षा 1 की फीस ₹85,000 प्रति वर्ष है, जिसे 4 किस्तों में दिया जा सकता है।"
    mixed_hi = "नर्सरी की tuition fees ₹65,000 per year है, जो 4 instalments में payable है।"
    assert devanagari_share(good_hi) > 0.95 > 0.6 > devanagari_share(mixed_hi)
    assert devanagari_share("CBSE बोर्ड", frozenset({"cbse"})) == 1.0
    good = "Class 1 ki fees ₹85,000 saal ki hai, aur aap ise 4 kishton mein de sakte hain."
    bad = "Class 1 fees are ₹85,000 per year hai."
    assert hindi_word_share(good) >= 0.4 > 0.3 > hindi_word_share(bad)

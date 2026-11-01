"""Cheap language hint for the parent's latest message (en | hi | hinglish)."""

from __future__ import annotations

import re

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_LATIN = re.compile(r"[A-Za-z]")
_HINGLISH_MARKERS = {
    "hai",
    "hain",
    "kya",
    "kitna",
    "kitni",
    "kitne",
    "nahi",
    "nahin",
    "mujhe",
    "aap",
    "aapka",
    "aapke",
    "chahiye",
    "kab",
    "kaise",
    "kahan",
    "haan",
    "ji",
    "bacche",
    "baccha",
    "beti",
    "beta",
    "karna",
    "karo",
    "milega",
    "hoga",
    "wala",
    "wali",
    "mein",
    "bhi",
    "batao",
    "bataiye",
    *[
        "ki",
        "ka",
        "ke",
        "ko",
        "se",
        "aur",
        "sakte",
        "sakti",
        "sakta",
        "ise",
        "isko",
        "yeh",
        "ye",
        "woh",
        "wo",
        "abhi",
        "neeche",
        "diye",
        "gaye",
        "liye",
    ],
    *[
        "kar",
        "karein",
        "kijiye",
        "saal",
        "theek",
        "dhanyavaad",
        "zaroor",
        "jaldi",
        "hum",
        "humare",
        "aapki",
        "apne",
        "koi",
        "kuch",
    ],
    *["de", "dena", "milegi", "milenge", "kishton", "kisht"],
    *["milti", "milta", "iski", "iska", "iske", "mahine", "mahina", "ek", "baar"],
    *["lijiye", "chun", "samay", "dekhne", "aa"],
}


def detect_language(text: str) -> str:
    deva = len(_DEVANAGARI.findall(text))
    latin = len(_LATIN.findall(text))
    # Hindi replies often keep English school words ("fees", "admission"); a third of the
    # letters in Devanagari is already a Hindi message.
    if deva and deva >= 0.3 * (deva + latin):
        return "hi"
    words = set(re.findall(r"[a-z]+", text.lower()))
    if words & _HINGLISH_MARKERS:
        return "hinglish"
    return "en"


def devanagari_share(text: str, keep_english: frozenset[str] = frozenset()) -> float:
    """Share of letters in Devanagari, ignoring allowed English words (names, CBSE)."""
    words = [w for w in re.findall(r"[A-Za-z]+", text) if w.lower() not in keep_english]
    latin = sum(len(w) for w in words)
    deva = len(_DEVANAGARI.findall(text))
    return deva / (deva + latin) if deva + latin else 0.0


def hindi_word_share(text: str, ignore: frozenset[str] = frozenset()) -> float:
    """For Hinglish: share of Roman-script words that are Hindi words (names ignored)."""
    words = [w for w in re.findall(r"[a-z]+", text.lower()) if w not in ignore]
    return sum(w in _HINGLISH_MARKERS for w in words) / len(words) if words else 0.0

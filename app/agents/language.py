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
}


def detect_language(text: str) -> str:
    deva = len(_DEVANAGARI.findall(text))
    latin = len(_LATIN.findall(text))
    if deva and deva >= latin:
        return "hi"
    words = set(re.findall(r"[a-z]+", text.lower()))
    if words & _HINGLISH_MARKERS:
        return "hinglish"
    return "en"

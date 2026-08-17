"""Bodhi language ids -> Sarvam BCP-47 codes, and the Tanglish special case.

Pure functions, no network. The one place that knows Tanglish is not a language
Sarvam has ever heard of — it is Tamil wearing a Latin alphabet, and both the
speech-to-text and text-to-speech sides need to be told so differently.
"""

from __future__ import annotations

# Sarvam speaks all six of Bodhi's languages. Tanglish rides on the Tamil voice.
_CODES = {
    "tanglish": "ta-IN",
    "tamil": "ta-IN",
    "english": "en-IN",
    "hindi": "hi-IN",
    "telugu": "te-IN",
    "malayalam": "ml-IN",
}

_FALLBACK = "en-IN"


def bcp47(language: str) -> str:
    """Sarvam language code for a Bodhi language id."""
    return _CODES.get((language or "").lower(), _FALLBACK)


def stt_mode(language: str) -> str:
    """Sarvam transcription mode.

    `translit` returns romanised output, which is exactly the format the rest of
    the app expects for Tanglish — a student speaks Tamil and the textarea fills
    with Latin script, no conversion needed. Everything else wants native script.
    """
    return "translit" if (language or "").lower() == "tanglish" else "transcribe"


def needs_transliteration(language: str) -> bool:
    """True when the on-screen text is romanised and the voice needs native script.

    Only Tanglish. An English TTS voice mangles the Tamil words and a Tamil voice
    cannot parse Latin letters, so the text is converted before it is spoken —
    audio only, the display stays romanised.
    """
    return (language or "").lower() == "tanglish"

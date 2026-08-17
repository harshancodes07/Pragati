"""Task-shaped voice operations. Sits above the provider the way llm/service.py
sits above llm/provider.py — routes call these and never see a model id.

Both directions are cached on content hash. That is worth more here than
anywhere else in the app: replaying the same answer during a demo becomes
instant and keeps working if the venue wifi dies mid-presentation.
"""

from __future__ import annotations

from backend import cache
from backend.config import settings
from backend.speech.langs import bcp47, needs_transliteration
from backend.speech.provider import SpeechError, get_speech_provider
from backend.speech.text import split_for_tts


def transcribe_audio(
    audio: bytes, *, filename: str, mime: str, language: str
) -> dict[str, str]:
    """Recording -> text, in the script the rest of the app expects."""
    if not audio:
        raise SpeechError("That recording was empty.")
    return get_speech_provider().transcribe(
        audio, filename=filename, mime=mime, language=language
    )


def _transliterated(text: str, language: str) -> str:
    """Cache-first romanised -> native script."""
    key = cache.content_hash(text, salt=f"translit:{bcp47(language)}")
    if (hit := cache.get("translit", key)) is not None:
        return hit
    native = get_speech_provider().transliterate(text, language=language)
    cache.put("translit", key, native)
    return native


def speak(text: str, language: str) -> dict:
    """Text -> a list of base64 mp3 clips, played back in order.

    Tanglish is converted to Tamil script first so the Tamil voice can actually
    read it. That conversion is audio-only — what the student sees never changes.
    """
    text = (text or "").strip()
    if not text:
        raise SpeechError("There is nothing to read out.")

    spoken = _transliterated(text, language) if needs_transliteration(language) else text

    provider = get_speech_provider()
    clips: list[str] = []
    for chunk in split_for_tts(spoken):
        key = cache.content_hash(
            chunk,
            salt=f"{bcp47(language)}:{settings.sarvam_tts_model}:{settings.sarvam_tts_speaker}",
        )
        if (hit := cache.get("tts", key)) is not None:
            clips.append(hit)
            continue
        clip = provider.synthesize(chunk, language=language)
        cache.put("tts", key, clip)
        clips.append(clip)

    if not clips:
        raise SpeechError("There is nothing to read out.")

    return {
        "clips": clips,
        "spoken_language": bcp47(language),
        "transliterated": spoken != text,
    }

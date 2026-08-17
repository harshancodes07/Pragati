"""Sarvam AI provider.

The only place in the codebase that talks to Sarvam. Deliberately shaped like
backend/llm/provider.py: task-shaped methods, a lazy singleton, raw httpx (Sarvam
is not OpenAI-shaped, so the SDK is no help here), and a hard failure rather than
a silent bad result.

Counters live in a *separate* UsageStats from the NIM one on purpose. Judge mode
advertises `nim_calls` as the number of LLM calls, and scripts/demo_check.py
asserts a refusal spends zero of them — speaking an answer must not move that
number.
"""

from __future__ import annotations

import time

import httpx

from backend.config import settings
from backend.llm.provider import UsageStats
from backend.speech.langs import bcp47, stt_mode

# Speech calls are counted apart from NIM calls; same dataclass, own instance.
speech_stats = UsageStats()

_TIMEOUT = 90.0


class SpeechError(RuntimeError):
    """Raised when Sarvam is unreachable or returns something unusable."""


class SarvamProvider:
    def __init__(self) -> None:
        if not settings.sarvam_api_key:
            raise SpeechError(
                "SARVAM_API_KEY is not set. Add it to .env to enable voice."
            )
        self._headers = {"api-subscription-key": settings.sarvam_api_key}

    # ------------------------------------------------------------------ plumbing

    def _post(self, path: str, *, task: str, **kwargs) -> dict:
        started = time.perf_counter()
        try:
            resp = httpx.post(
                f"{settings.sarvam_base_url}{path}",
                headers=self._headers,
                timeout=_TIMEOUT,
                **kwargs,
            )
        except httpx.HTTPError as exc:
            speech_stats.record_failure()
            raise SpeechError(f"Sarvam unreachable for '{task}': {exc}") from exc

        if resp.status_code >= 400:
            speech_stats.record_failure()
            raise SpeechError(f"Sarvam {task} failed ({resp.status_code}): {resp.text[:300]}")

        speech_stats.record(task, (time.perf_counter() - started) * 1000, None)
        try:
            return resp.json()
        except ValueError as exc:
            speech_stats.record_failure()
            raise SpeechError(f"Sarvam {task} returned a non-JSON body.") from exc

    # ----------------------------------------------------------- speech to text

    def transcribe(
        self, audio: bytes, *, filename: str, mime: str, language: str
    ) -> dict[str, str]:
        """Transcribe a recording.

        For Tanglish this asks for `translit` mode, so a student speaking Tamil
        gets romanised text back — the format every other layer already expects.
        """
        data = self._post(
            "/speech-to-text",
            task="stt",
            files={"file": (filename or "recording.wav", audio, mime or "audio/wav")},
            data={
                "model": settings.sarvam_stt_model,
                "language_code": bcp47(language),
                "mode": stt_mode(language),
            },
        )
        return {
            "text": (data.get("transcript") or "").strip(),
            "detected_language": data.get("language_code") or "",
        }

    # ----------------------------------------------------------- text to speech

    def synthesize(self, text: str, *, language: str) -> str:
        """Synthesise one already-chunked piece of text. Returns base64 audio."""
        data = self._post(
            "/text-to-speech",
            task="tts",
            json={
                "text": text,
                "language_code": bcp47(language),
                "model": settings.sarvam_tts_model,
                "speaker": settings.sarvam_tts_speaker,
                "output_audio_codec": "mp3",
            },
        )
        audios = data.get("audios") or []
        if not audios:
            raise SpeechError("Sarvam returned no audio for that text.")
        return audios[0]

    # --------------------------------------------------------- transliteration

    def transliterate(self, text: str, *, language: str) -> str:
        """Romanised text -> native script, so a native voice can read it.

        Source is en-IN because the *script* is Latin; the target language is
        what the words actually are.
        """
        data = self._post(
            "/transliterate",
            task="translit",
            json={
                "input": text,
                "source_language_code": "en-IN",
                "target_language_code": bcp47(language),
                "numerals_format": "international",
            },
        )
        return (data.get("transliterated_text") or "").strip() or text


_provider: SarvamProvider | None = None


def get_speech_provider() -> SarvamProvider:
    global _provider
    if _provider is None:
        _provider = SarvamProvider()
    return _provider

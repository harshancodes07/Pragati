"""Pure text preparation for speech synthesis. No network, no config.

Kept separate from the provider so the interesting logic — where to cut a long
answer — is unit-testable without an API key.
"""

from __future__ import annotations

import re

# Sarvam's bulbul:v3 accepts 2500 characters. We cut well below that: shorter
# requests come back faster, and a sentence boundary is a natural place for the
# tiny gap between two clips to land.
TTS_CHAR_LIMIT = 1200

# Markdown the tutor sometimes emits. Spoken aloud, "asterisk asterisk" is worse
# than useless, so it is stripped before synthesis (the screen still renders it).
_BOLD_ITALIC = re.compile(r"[*_]{1,3}(?=\S)(.+?)(?<=\S)[*_]{1,3}", re.DOTALL)
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+", re.MULTILINE)
_BULLET = re.compile(r"^\s{0,3}[-*+]\s+", re.MULTILINE)
_CODE_FENCE = re.compile(r"```[\w-]*\n?")
_INLINE_CODE = re.compile(r"`([^`]+)`")
_BLANK_RUN = re.compile(r"\n{3,}")

# Devanagari danda included — Hindi answers end sentences with it, not a period.
_SENTENCE_END = re.compile(r"(?<=[.!?।])\s+|\n+")


def strip_markup(text: str) -> str:
    """Remove markdown so the voice reads words, not punctuation."""
    if not text:
        return ""
    text = _CODE_FENCE.sub("", text)
    text = _INLINE_CODE.sub(r"\1", text)
    text = _HEADING.sub("", text)
    text = _BULLET.sub("", text)
    text = _BOLD_ITALIC.sub(r"\1", text)
    text = _BLANK_RUN.sub("\n\n", text)
    return text.strip()


def _hard_split(sentence: str, limit: int) -> list[str]:
    """Last resort for a single sentence longer than the limit.

    Breaks on whitespace so a word is never cut in half — a spliced word sounds
    like a glitch, a spliced clause just sounds like a pause.
    """
    words, chunks, current = sentence.split(), [], ""
    for word in words:
        if current and len(current) + 1 + len(word) > limit:
            chunks.append(current)
            current = word
        else:
            current = f"{current} {word}" if current else word
        # A single word longer than the limit (a URL, say) still has to go.
        while len(current) > limit:
            chunks.append(current[:limit])
            current = current[limit:]
    if current:
        chunks.append(current)
    return chunks


def split_for_tts(text: str, limit: int = TTS_CHAR_LIMIT) -> list[str]:
    """Split text into synthesis-sized chunks on sentence boundaries.

    A normal tutor answer comes back as a single chunk. Only long ones are cut,
    and always between sentences unless one sentence alone exceeds the limit.
    """
    text = strip_markup(text)
    if not text:
        return []
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current = ""
    for sentence in (s.strip() for s in _SENTENCE_END.split(text)):
        if not sentence:
            continue
        if len(sentence) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_hard_split(sentence, limit))
        elif not current:
            current = sentence
        elif len(current) + 1 + len(sentence) <= limit:
            current = f"{current} {sentence}"
        else:
            chunks.append(current)
            current = sentence

    if current:
        chunks.append(current)
    return chunks

"""Tolerant JSON extraction.

NIM model support for `response_format={"type":"json_schema"}` varies per model,
so we never bet on it. Instead we instruct the model to emit JSON and parse
defensively: strip prose, strip code fences, and scan for the first balanced
object. The caller handles the repair retry.
"""

import json
import re
from typing import Any

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def _balanced_span(text: str) -> str | None:
    """Return the first balanced {...} span, ignoring braces inside strings."""
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False

    for i in range(start, len(text)):
        ch = text[i]
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def extract_json(text: str) -> dict[str, Any] | None:
    """Best-effort parse of a JSON object out of a model response."""
    if not text:
        return None

    candidates: list[str] = []
    if fenced := _FENCE.search(text):
        candidates.append(fenced.group(1).strip())
    candidates.append(text.strip())

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        if span := _balanced_span(candidate):
            try:
                parsed = json.loads(span)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                # Trailing commas are the most common model slip; try once more.
                repaired = re.sub(r",(\s*[}\]])", r"\1", span)
                try:
                    parsed = json.loads(repaired)
                    if isinstance(parsed, dict):
                        return parsed
                except json.JSONDecodeError:
                    pass

    return None

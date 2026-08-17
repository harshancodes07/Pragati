"""NVIDIA NIM provider.

The only place in the codebase that talks to NVIDIA. Everything above this layer
calls task-shaped functions and never sees a model ID, an endpoint, or the key.
Also the single point where we count calls, tokens and latency for judge mode.
"""

from __future__ import annotations

import base64
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Iterator

import httpx
from openai import OpenAI

from backend.config import settings


@dataclass
class UsageStats:
    """Live counters surfaced by /api/stats. Every NIM call must have a reason."""

    calls: int = 0
    failures: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_latency_ms: float = 0.0
    by_task: dict[str, int] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record(self, task: str, latency_ms: float, usage: Any | None) -> None:
        with self._lock:
            self.calls += 1
            self.total_latency_ms += latency_ms
            self.by_task[task] = self.by_task.get(task, 0) + 1
            if usage is not None:
                self.prompt_tokens += getattr(usage, "prompt_tokens", 0) or 0
                self.completion_tokens += getattr(usage, "completion_tokens", 0) or 0

    def record_failure(self) -> None:
        with self._lock:
            self.failures += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            avg = self.total_latency_ms / self.calls if self.calls else 0.0
            return {
                "nim_calls": self.calls,
                "failures": self.failures,
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "avg_latency_ms": round(avg, 1),
                "by_task": dict(self.by_task),
            }


stats = UsageStats()


class NIMError(RuntimeError):
    """Raised when NIM is unreachable or returns an error we cannot recover from."""


# Several NIM models (the Nemotron-3 family among them) are reasoning models.
# Left alone they emit a chain of thought, and if max_tokens is hit mid-thought
# that raw reasoning lands in `content` — i.e. on screen, in front of a judge.
# Disabling thinking also cuts latency and output tokens, which we want anyway.
_NO_THINK_BODY = {"chat_template_kwargs": {"thinking": False}}

# Defensive second line: strip any thinking block that still slips through.
_THINK_BLOCK = re.compile(r"<(think|thinking|reasoning)>.*?</\1>", re.DOTALL | re.IGNORECASE)
_ORPHAN_OPEN = re.compile(r"<(think|thinking|reasoning)>.*\Z", re.DOTALL | re.IGNORECASE)


def _is_bad_request(exc: Exception) -> bool:
    """True when the server rejected the request shape (not a transient fault)."""
    status = getattr(exc, "status_code", None) or getattr(
        getattr(exc, "response", None), "status_code", None
    )
    return status in (400, 415, 422)


def _clean_content(text: str) -> str:
    """Remove leaked reasoning from a completion."""
    if not text:
        return ""
    text = _THINK_BLOCK.sub("", text)
    # An unclosed tag means the response was truncated mid-thought — drop the tail.
    text = _ORPHAN_OPEN.sub("", text)
    return text.strip()


class NIMProvider:
    def __init__(self) -> None:
        if not settings.nvidia_api_key:
            raise NIMError("NVIDIA_API_KEY is not set. Copy .env.example to .env.")
        self._client = OpenAI(
            api_key=settings.nvidia_api_key,
            base_url=settings.nvidia_base_url,
            timeout=90.0,
            max_retries=0,  # we handle retry/fallback ourselves so stats stay honest
        )
        # Per-model memo of whether the thinking-disable body is accepted.
        self._supports_no_think: dict[str, bool] = {}

    # ---------------------------------------------------------------- catalog

    def list_models(self) -> list[str]:
        """Enumerate what this key can actually reach. Never guess a model ID."""
        resp = httpx.get(
            f"{settings.nvidia_base_url}/models",
            headers={"Authorization": f"Bearer {settings.nvidia_api_key}"},
            timeout=30.0,
        )
        resp.raise_for_status()
        return sorted(m["id"] for m in resp.json().get("data", []))

    # ------------------------------------------------------------ completions

    def _create(self, model: str, messages, temperature: float, max_tokens: int,
                stream: bool = False):
        """Create a completion with thinking disabled.

        Not every model accepts `chat_template_kwargs`, so a rejection falls
        back to a plain call rather than failing the request.
        """
        kwargs = dict(model=model, messages=messages, temperature=temperature,
                      max_tokens=max_tokens, stream=stream)
        if self._supports_no_think.get(model, True):
            try:
                return self._client.chat.completions.create(
                    **kwargs, extra_body=_NO_THINK_BODY
                )
            except Exception as exc:  # noqa: BLE001
                # Only treat a request-shape rejection as "unsupported"; a
                # timeout or server error must still propagate to the caller.
                if not _is_bad_request(exc):
                    raise
                self._supports_no_think[model] = False

        return self._client.chat.completions.create(**kwargs)

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        task: str,
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 1200,
    ) -> str:
        """Single completion. Falls back to the backup model on failure."""
        primary = model or settings.nvidia_model
        if not primary:
            raise NIMError("No NVIDIA_MODEL configured. Run scripts/benchmark_nim.py.")

        attempts = [primary]
        if settings.nvidia_model_backup and settings.nvidia_model_backup != primary:
            attempts.append(settings.nvidia_model_backup)

        last_error: Exception | None = None
        for candidate in attempts:
            started = time.perf_counter()
            try:
                resp = self._create(candidate, messages, temperature, max_tokens)
            except Exception as exc:  # noqa: BLE001 — any failure means try backup
                stats.record_failure()
                last_error = exc
                continue

            latency = (time.perf_counter() - started) * 1000
            stats.record(task, latency, getattr(resp, "usage", None))
            return _clean_content(resp.choices[0].message.content or "")

        raise NIMError(f"NIM call failed for task '{task}': {last_error}") from last_error

    def stream(
        self,
        messages: list[dict[str, Any]],
        *,
        task: str,
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 1200,
    ) -> Iterator[str]:
        """Streaming completion. Used only for the tutor answer, where the
        perceived-latency win is real."""
        candidate = model or settings.nvidia_model
        started = time.perf_counter()
        try:
            stream = self._create(candidate, messages, temperature, max_tokens, stream=True)
            in_think = False
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                # Reasoning arrives on its own field when the model supports it;
                # never forward that to the student.
                if getattr(delta, "reasoning_content", None):
                    continue
                if not (text := delta.content):
                    continue
                # Suppress an inline thinking block across chunk boundaries.
                if in_think:
                    if "</" in text:
                        in_think = False
                    continue
                if "<think" in text.lower():
                    in_think = True
                    continue
                yield text
        except Exception as exc:  # noqa: BLE001
            stats.record_failure()
            raise NIMError(f"NIM stream failed for task '{task}': {exc}") from exc
        finally:
            stats.record(task, (time.perf_counter() - started) * 1000, None)

    # -------------------------------------------------------------- embedding

    def embed(self, texts: list[str], *, input_type: str) -> list[list[float]]:
        """Embed a batch.

        `input_type` must be "query" or "passage". NeMo Retriever models are
        asymmetric — using the wrong side silently halves retrieval quality,
        which is the failure mode most likely to sink the grounding score.
        """
        if input_type not in ("query", "passage"):
            raise ValueError("input_type must be 'query' or 'passage'")
        if not texts:
            return []

        vectors: list[list[float]] = []
        batch_size = 32
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            started = time.perf_counter()
            resp = httpx.post(
                f"{settings.nvidia_base_url}/embeddings",
                headers={
                    "Authorization": f"Bearer {settings.nvidia_api_key}",
                    "Accept": "application/json",
                },
                json={
                    "input": batch,
                    "model": settings.nvidia_embed_model,
                    "input_type": input_type,
                    "encoding_format": "float",
                    "truncate": "END",
                },
                timeout=90.0,
            )
            if resp.status_code >= 400:
                stats.record_failure()
                raise NIMError(f"Embedding failed ({resp.status_code}): {resp.text[:300]}")

            stats.record("embed", (time.perf_counter() - started) * 1000, None)
            data = sorted(resp.json()["data"], key=lambda d: d["index"])
            vectors.extend(d["embedding"] for d in data)

        return vectors

    # ----------------------------------------------------------------- vision

    def ocr_image(self, image_bytes: bytes, mime: str = "image/png") -> str:
        """Read a textbook page photo with a NIM vision model."""
        b64 = base64.b64encode(image_bytes).decode()
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Transcribe ALL text from this textbook page exactly as "
                            "printed. Preserve headings, paragraph breaks, lists and "
                            "numbering. Describe any diagram in one bracketed line, "
                            "e.g. [Diagram: cross-section of a leaf]. Output only the "
                            "transcription — no commentary, no preamble."
                        ),
                    },
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                ],
            }
        ]
        return self.chat(
            messages,
            task="ocr",
            model=settings.vision_model,
            temperature=0.0,
            max_tokens=2500,
        )


_provider: NIMProvider | None = None


def get_provider() -> NIMProvider:
    global _provider
    if _provider is None:
        _provider = NIMProvider()
    return _provider

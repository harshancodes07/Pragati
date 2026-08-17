"""Embedding helpers.

NeMo Retriever models are ASYMMETRIC: a question must be embedded as a "query"
and a textbook chunk as a "passage". Mixing them up silently halves retrieval
quality — no error, just worse answers — so the two calls are named separately
here rather than exposing a flag that is easy to get wrong at the call site.
"""

from __future__ import annotations

from backend import cache
from backend.config import settings
from backend.llm.provider import get_provider


def embed_passages(texts: list[str]) -> list[list[float]]:
    """Embed textbook chunks for indexing."""
    return get_provider().embed(texts, input_type="passage")


def embed_query(text: str, *, use_cache: bool = True) -> list[float]:
    """Embed a student question for retrieval.

    Cached: during a demo the same question gets asked repeatedly, and this
    removes a network round-trip from the critical path.
    """
    key = cache.content_hash(text, salt=f"q-{settings.nvidia_embed_model}")
    if use_cache and (hit := cache.get("embed_query", key)) is not None:
        return hit

    vector = get_provider().embed([text], input_type="query")[0]
    if use_cache:
        cache.put("embed_query", key, vector)
    return vector

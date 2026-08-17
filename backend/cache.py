"""Content-hashed disk cache for expensive, deterministic work.

OCR and embeddings cost real latency and real NIM calls. During a demo the same
textbook gets processed repeatedly — caching on content hash means the second
run is instant and, critically, works even if the venue wifi dies.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from backend.config import settings


def content_hash(data: bytes | str, *, salt: str = "") -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    h = hashlib.sha256()
    if salt:
        h.update(salt.encode("utf-8"))
        h.update(b"\x00")
    h.update(data)
    return h.hexdigest()[:32]


def _path(namespace: str, key: str) -> Path:
    d = settings.cache_dir / namespace
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{key}.json"


def get(namespace: str, key: str) -> Any | None:
    p = _path(namespace, key)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))["value"]
    except (json.JSONDecodeError, KeyError, OSError):
        return None  # a corrupt cache entry should never break a request


def put(namespace: str, key: str, value: Any) -> None:
    try:
        _path(namespace, key).write_text(
            json.dumps({"value": value}, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        pass  # caching is an optimisation, never a hard dependency

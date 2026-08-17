"""Vector store.

A single textbook is a few hundred chunks. Exact cosine over a numpy matrix is
sub-millisecond at that scale, so FAISS's approximate index would solve a
problem we do not have, and Chroma would add a server process to babysit during
a live demo. Everything goes through the VectorStore interface, so swapping in
FAISS later is a contained change.
"""

from __future__ import annotations

import pickle
import threading
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from backend.config import settings


class VectorStore(Protocol):
    def add(self, chunks: list[dict[str, Any]], vectors: list[list[float]]) -> None: ...
    def search(self, query_vector: list[float], top_k: int, document_id: str | None) -> list[dict]: ...


class NumpyVectorStore:
    """Exact cosine similarity over an L2-normalised matrix."""

    def __init__(self) -> None:
        self._matrix: np.ndarray | None = None
        self._chunks: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ write

    def add(self, chunks: list[dict[str, Any]], vectors: list[list[float]]) -> None:
        if not chunks:
            return
        if len(chunks) != len(vectors):
            raise ValueError(f"chunk/vector count mismatch: {len(chunks)} vs {len(vectors)}")

        arr = np.asarray(vectors, dtype=np.float32)
        # Normalise once at write time so search is a plain dot product.
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        arr = arr / np.maximum(norms, 1e-10)

        with self._lock:
            self._matrix = arr if self._matrix is None else np.vstack([self._matrix, arr])
            self._chunks.extend(chunks)

    # ----------------------------------------------------------------- search

    def search(
        self, query_vector: list[float], top_k: int = 5, document_id: str | None = None
    ) -> list[dict[str, Any]]:
        with self._lock:
            if self._matrix is None or not self._chunks:
                return []
            matrix, chunks = self._matrix, list(self._chunks)

        q = np.asarray(query_vector, dtype=np.float32)
        q = q / max(float(np.linalg.norm(q)), 1e-10)

        if q.shape[0] != matrix.shape[1]:
            raise ValueError(
                f"Query dim {q.shape[0]} != index dim {matrix.shape[1]}. "
                "The embedding model changed — re-index the document."
            )

        scores = matrix @ q  # cosine, since both sides are unit-normalised

        if document_id is not None:
            mask = np.array([c["document_id"] == document_id for c in chunks])
            if not mask.any():
                return []
            scores = np.where(mask, scores, -np.inf)

        k = min(top_k, int(np.isfinite(scores).sum()))
        if k <= 0:
            return []

        # argpartition avoids a full sort; we only need the top k.
        top_idx = np.argpartition(-scores, k - 1)[:k]
        top_idx = top_idx[np.argsort(-scores[top_idx])]

        return [{**chunks[i], "score": float(scores[i])} for i in top_idx]

    # ------------------------------------------------------------- lifecycle

    def has_document(self, document_id: str) -> bool:
        with self._lock:
            return any(c["document_id"] == document_id for c in self._chunks)

    def __len__(self) -> int:
        return len(self._chunks)

    def save(self, path: Path | None = None) -> None:
        target = path or (settings.index_dir / "index.pkl")
        with self._lock:
            payload = {
                "matrix": self._matrix,
                "chunks": self._chunks,
                "embed_model": settings.nvidia_embed_model,
            }
        tmp = target.with_suffix(".tmp")
        tmp.write_bytes(pickle.dumps(payload))
        tmp.replace(target)  # atomic — never leave a half-written index

    def load(self, path: Path | None = None) -> bool:
        target = path or (settings.index_dir / "index.pkl")
        if not target.exists():
            return False
        try:
            payload = pickle.loads(target.read_bytes())
        except Exception:  # noqa: BLE001
            return False

        # Vectors from a different embedding model are meaningless here.
        if payload.get("embed_model") != settings.nvidia_embed_model:
            return False

        with self._lock:
            self._matrix = payload["matrix"]
            self._chunks = payload["chunks"]
        return True


_store: NumpyVectorStore | None = None


def get_store() -> NumpyVectorStore:
    global _store
    if _store is None:
        _store = NumpyVectorStore()
        _store.load()
    return _store

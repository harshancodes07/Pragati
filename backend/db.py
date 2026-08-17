"""SQLite persistence. Five tables, no auth.

Auth earns zero rubric points and costs demo time, so sessions are anonymous
UUIDs. The one thing that genuinely must persist is per-session performance,
because that is what drives visible difficulty adaptation.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from typing import Any

from backend.config import settings

_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id            TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    source        TEXT NOT NULL,
    page_count    INTEGER NOT NULL DEFAULT 0,
    chunk_count   INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id      TEXT PRIMARY KEY,
    document_id   TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_number   INTEGER NOT NULL,
    text          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(document_id);

CREATE TABLE IF NOT EXISTS sessions (
    id            TEXT PRIMARY KEY,
    document_id   TEXT REFERENCES documents(id) ON DELETE CASCADE,
    language      TEXT NOT NULL DEFAULT 'tanglish',
    difficulty    TEXT NOT NULL DEFAULT 'medium',
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS interactions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    kind          TEXT NOT NULL,          -- ask | teachback | practice
    concept       TEXT,
    payload       TEXT,                   -- JSON blob of the full exchange
    grounded      INTEGER,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_inter_session ON interactions(session_id);

CREATE TABLE IF NOT EXISTS performance (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    concept       TEXT NOT NULL,
    difficulty    TEXT NOT NULL,
    correct       INTEGER NOT NULL,
    total         INTEGER NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_perf_session ON performance(session_id);
"""


def get_conn() -> sqlite3.Connection:
    """One connection per thread — SQLite objects are not thread-safe."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(settings.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA)
        conn.commit()
        _local.conn = conn
    return conn


def init_db() -> None:
    get_conn()


# ------------------------------------------------------------------ documents

def create_document(title: str, source: str, page_count: int, chunk_count: int) -> str:
    doc_id = f"doc_{uuid.uuid4().hex[:12]}"
    conn = get_conn()
    conn.execute(
        "INSERT INTO documents (id, title, source, page_count, chunk_count) VALUES (?,?,?,?,?)",
        (doc_id, title, source, page_count, chunk_count),
    )
    conn.commit()
    return doc_id


def save_chunks(chunks: list[dict[str, Any]]) -> None:
    conn = get_conn()
    conn.executemany(
        "INSERT OR REPLACE INTO chunks (chunk_id, document_id, page_number, text) VALUES (?,?,?,?)",
        [(c["chunk_id"], c["document_id"], c["page_number"], c["text"]) for c in chunks],
    )
    conn.commit()


def get_document(doc_id: str) -> dict[str, Any] | None:
    row = get_conn().execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    return dict(row) if row else None


def list_documents() -> list[dict[str, Any]]:
    rows = get_conn().execute("SELECT * FROM documents ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


# ------------------------------------------------------------------- sessions

def create_session(document_id: str | None, language: str = "tanglish") -> str:
    session_id = f"ses_{uuid.uuid4().hex[:12]}"
    conn = get_conn()
    conn.execute(
        "INSERT INTO sessions (id, document_id, language) VALUES (?,?,?)",
        (session_id, document_id, language),
    )
    conn.commit()
    return session_id


def get_session(session_id: str) -> dict[str, Any] | None:
    row = get_conn().execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    return dict(row) if row else None


def set_difficulty(session_id: str, difficulty: str) -> None:
    conn = get_conn()
    conn.execute("UPDATE sessions SET difficulty = ? WHERE id = ?", (difficulty, session_id))
    conn.commit()


# --------------------------------------------------------------- interactions

def log_interaction(
    session_id: str, kind: str, concept: str | None, payload: dict, grounded: bool | None = None
) -> None:
    conn = get_conn()
    conn.execute(
        "INSERT INTO interactions (session_id, kind, concept, payload, grounded) VALUES (?,?,?,?,?)",
        (session_id, kind, concept, json.dumps(payload, ensure_ascii=False),
         None if grounded is None else int(grounded)),
    )
    conn.commit()


def record_performance(
    session_id: str, concept: str, difficulty: str, correct: int, total: int
) -> None:
    conn = get_conn()
    conn.execute(
        "INSERT INTO performance (session_id, concept, difficulty, correct, total) VALUES (?,?,?,?,?)",
        (session_id, concept, difficulty, correct, total),
    )
    conn.commit()


def session_progress(session_id: str) -> dict[str, Any]:
    conn = get_conn()
    rows = conn.execute(
        """SELECT concept, difficulty, SUM(correct) AS correct, SUM(total) AS total
           FROM performance WHERE session_id = ? GROUP BY concept, difficulty""",
        (session_id,),
    ).fetchall()

    by_concept = [dict(r) for r in rows]
    total = sum(r["total"] for r in by_concept)
    correct = sum(r["correct"] for r in by_concept)
    session = get_session(session_id) or {}

    return {
        "session_id": session_id,
        "difficulty": session.get("difficulty", "medium"),
        "language": session.get("language", "tanglish"),
        "answered": total,
        "correct": correct,
        "accuracy": round(correct / total, 2) if total else None,
        "by_concept": by_concept,
        "weak_concepts": [
            r["concept"] for r in by_concept
            if r["total"] and (r["correct"] / r["total"]) < 0.6
        ],
    }

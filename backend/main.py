"""Pragati FastAPI app.

Every NIM call happens here or below. The frontend never sees the API key.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend import adaptive, db
from backend.config import settings
from backend.ingest.chunk import chunk_pages
from backend.ingest.extract import ExtractionError, extract
from backend.llm import prompts, service
from backend.llm.provider import NIMError, get_provider, stats
from backend.rag.embeddings import embed_passages
from backend.rag.retrieve import out_of_scope_message, retrieve
from backend.rag.store import get_store
from backend.speech import service as speech_service
from backend.speech.provider import SpeechError, speech_stats

def _elapsed_ms(started: float) -> float:
    return (time.perf_counter() - started) * 1000


app = FastAPI(title="Pragati", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory cache of generated practice sets, so /practice/submit can grade
# without a second NIM call and without trusting answers sent by the client.
_practice_sets: dict[str, list[dict[str, Any]]] = {}


@app.on_event("startup")
def _startup() -> None:
    db.init_db()
    get_store()  # loads a persisted index if one matches the current embed model


# ------------------------------------------------------------------- schemas

class AskRequest(BaseModel):
    document_id: str | None = None
    session_id: str | None = None
    question: str = Field(min_length=1, max_length=2000)
    language: str = "tanglish"
    stream: bool = False


class TeachBackRequest(BaseModel):
    document_id: str | None = None
    session_id: str
    concept: str = Field(min_length=1, max_length=500)
    explanation: str = Field(min_length=1, max_length=4000)
    language: str = "tanglish"
    mode: str = "simple"  # simple | exam | friend — changes the rubric, not just the tone


class PracticeRequest(BaseModel):
    document_id: str | None = None
    session_id: str
    concept: str = Field(min_length=1, max_length=500)
    language: str = "tanglish"
    difficulty: str | None = None


class SubmitRequest(BaseModel):
    session_id: str
    set_id: str
    answers: dict[str, str]
    concept: str = ""


class DoubtMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class DoubtRequest(BaseModel):
    document_id: str | None = None
    session_id: str
    chat_id: str | None = None  # continues a saved chat; omitted starts a new one
    concept: str = Field(default="", max_length=500)
    explanation: str = Field(min_length=1, max_length=6000)
    language: str = "tanglish"
    # The whole thread, ending with the student's latest doubt. The popup owns
    # history in-memory; the server persists it under chat_id for Recent Chats.
    messages: list[DoubtMessage] = Field(default_factory=list, max_length=20)


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=6000)
    language: str = "tanglish"


# -------------------------------------------------------------------- health

@app.get("/api/health")
def health() -> dict[str, Any]:
    configured = bool(settings.nvidia_api_key)
    reachable, detail = False, "NVIDIA_API_KEY not set"

    if configured:
        try:
            models = get_provider().list_models()
            reachable = True
            detail = f"{len(models)} models reachable"
        except Exception as exc:  # noqa: BLE001
            detail = str(exc)[:200]

    return {
        "status": "ok" if reachable else "degraded",
        "nim": {
            "configured": configured,
            "reachable": reachable,
            "detail": detail,
            "model": settings.nvidia_model or None,
            "tutor_model": settings.tutor_model or None,
            "structured_model": settings.structured_model or None,
            "embed_model": settings.nvidia_embed_model,
        },
        "index": {"chunks": len(get_store())},
        "grounding_threshold": settings.grounding_threshold,
        # The frontend hides every mic and speaker button when this is false, so
        # a missing key degrades to exactly the app we had before voice existed.
        "speech": {
            "configured": bool(settings.sarvam_api_key),
            "detail": (
                f"{settings.sarvam_stt_model} / {settings.sarvam_tts_model}"
                if settings.sarvam_api_key
                else "SARVAM_API_KEY not set"
            ),
        },
    }


# -------------------------------------------------------------------- upload

# A hard cap keeps a mis-click from turning into a multi-minute OCR bill; the
# bounded concurrency below keeps a legitimate batch from hammering NIM with
# every page's vision call at once.
_MAX_UPLOAD_FILES = 8
_MAX_CONCURRENT_EXTRACTIONS = 3


async def _extract_one(f: UploadFile, semaphore: asyncio.Semaphore) -> tuple[list[str], dict[str, Any]]:
    data = await f.read()
    if not data:
        raise HTTPException(400, f"'{f.filename}' is empty.")

    async with semaphore:
        try:
            # extract() makes blocking network calls (OCR); to_thread keeps
            # the event loop free so other files' extractions can proceed
            # concurrently instead of queueing behind this one.
            return await asyncio.to_thread(extract, data=data, filename=f.filename or "")
        except ExtractionError as exc:
            raise HTTPException(400, f"'{f.filename}': {exc}") from exc
        except NIMError as exc:
            raise HTTPException(503, f"Couldn't process '{f.filename}': {exc}") from exc


@app.post("/api/upload")
async def upload(
    files: list[UploadFile] | None = File(default=None),
    text: str | None = Form(default=None),
    title: str | None = Form(default=None),
    language: str = Form(default="tanglish"),
) -> dict[str, Any]:
    # Timed per stage so a slow upload can be diagnosed from the response alone
    # — OCR, embedding and file transfer all live on wildly different budgets,
    # and guessing which one is slow from the outside wastes a support cycle.
    timing_ms: dict[str, float] = {}
    started = time.perf_counter()

    uploaded = [f for f in (files or []) if f.filename]
    if len(uploaded) > _MAX_UPLOAD_FILES:
        raise HTTPException(400, f"Upload at most {_MAX_UPLOAD_FILES} files at once.")

    if uploaded:
        t = time.perf_counter()
        semaphore = asyncio.Semaphore(_MAX_CONCURRENT_EXTRACTIONS)
        results = await asyncio.gather(*(_extract_one(f, semaphore) for f in uploaded))
        timing_ms["extract"] = _elapsed_ms(t)

        # Multiple files become one logical document — a flat, continuous page
        # list. Nothing downstream (chunking, retrieval, citations) needs to
        # know a page boundary was also a file boundary.
        pages: list[str] = []
        sources: list[str] = []
        ocr_pages_total = 0
        cached_all = True
        for file_pages, file_meta in results:
            pages.extend(file_pages)
            sources.append(file_meta.get("source", "unknown"))
            ocr_pages_total += file_meta.get("ocr_pages", 0)
            cached_all = cached_all and file_meta.get("cached", False)
        meta = {
            "source": "+".join(dict.fromkeys(sources)),
            "ocr_pages": ocr_pages_total,
            "cached": cached_all,
        }

        names = [f.filename or "Untitled" for f in uploaded]
        doc_title = title or (
            names[0] if len(names) == 1 else f"{names[0]} + {len(names) - 1} more"
        )
    else:
        try:
            t = time.perf_counter()
            pages, meta = extract(text=text or "")
            timing_ms["extract"] = _elapsed_ms(t)
        except ExtractionError as exc:
            raise HTTPException(400, str(exc)) from exc
        doc_title = title or "Pasted text"

    t = time.perf_counter()
    doc_id = db.create_document(doc_title, meta.get("source", "unknown"), len(pages), 0)
    chunks = chunk_pages(pages, doc_id)
    if not chunks:
        raise HTTPException(400, "Couldn't find any teachable content in that upload.")
    timing_ms["chunk"] = _elapsed_ms(t)

    t = time.perf_counter()
    try:
        vectors = embed_passages([c["text"] for c in chunks])
    except NIMError as exc:
        raise HTTPException(503, f"Couldn't index that document: {exc}") from exc
    timing_ms["embed"] = _elapsed_ms(t)

    t = time.perf_counter()
    store = get_store()
    store.add(chunks, vectors)
    store.save()
    db.save_chunks(chunks)
    db.get_conn().execute(
        "UPDATE documents SET chunk_count = ? WHERE id = ?", (len(chunks), doc_id)
    )
    db.get_conn().commit()
    session_id = db.create_session(doc_id, language)
    timing_ms["store"] = _elapsed_ms(t)
    timing_ms["total"] = _elapsed_ms(started)

    return {
        "document_id": doc_id,
        "session_id": session_id,
        "title": doc_title,
        "pages": len(pages),
        "chunk_count": len(chunks),
        "ocr_pages": meta.get("ocr_pages", 0),
        "cached": meta.get("cached", False),
        "preview": chunks[0]["text"][:400],
        "timing_ms": {k: round(v) for k, v in timing_ms.items()},
        "file_count": len(uploaded) or (1 if text and text.strip() else 0),
    }


# ------------------------------------------------------------------- speech

def _require_voice() -> None:
    if not settings.sarvam_api_key:
        raise HTTPException(503, "Voice is not configured. Set SARVAM_API_KEY in .env.")


@app.post("/api/stt")
async def speech_to_text(
    file: UploadFile = File(...),
    language: str = Form(default="tanglish"),
) -> dict[str, Any]:
    """Recording -> text. Tanglish comes back romanised, ready for the textarea."""
    _require_voice()
    audio = await file.read()
    if not audio:
        raise HTTPException(400, "That recording was empty.")

    try:
        return speech_service.transcribe_audio(
            audio,
            filename=file.filename or "recording.wav",
            mime=file.content_type or "audio/wav",
            language=language,
        )
    except SpeechError as exc:
        raise HTTPException(503, f"Couldn't hear that: {exc}") from exc


@app.post("/api/tts")
def text_to_speech(req: TTSRequest) -> dict[str, Any]:
    """Text -> ordered base64 mp3 clips for the browser to play in sequence."""
    _require_voice()
    try:
        return speech_service.speak(req.text, req.language)
    except SpeechError as exc:
        raise HTTPException(503, f"Couldn't read that out: {exc}") from exc


# ----------------------------------------------------------------------- ask

@app.post("/api/ask")
def ask(req: AskRequest) -> Any:
    result = retrieve(req.question, document_id=req.document_id)

    # The refusal happens here, on retrieval scores — no NIM call is spent.
    if not result.grounded:
        payload = {
            "answer": out_of_scope_message(req.language),
            "grounded": False,
            "sources": [],
            "retrieval": {
                "max_score": round(result.max_score, 3),
                "threshold": result.threshold,
                "reason": result.reason,
            },
        }
        if req.session_id:
            db.log_interaction(req.session_id, "ask", req.question, payload, grounded=False)
        return payload

    if req.stream:
        def generate():
            collected = []
            try:
                for token in service.stream_tutor_response(
                    req.question, result.chunks, req.language
                ):
                    collected.append(token)
                    yield f"data: {json.dumps({'token': token})}\n\n"
            except NIMError as exc:
                yield f"data: {json.dumps({'error': str(exc)})}\n\n"
                return

            done = {
                "done": True,
                "grounded": True,
                "sources": result.to_sources(),
                "retrieval": {
                    "max_score": round(result.max_score, 3),
                    "threshold": result.threshold,
                    "reason": result.reason,
                },
            }
            if req.session_id:
                db.log_interaction(
                    req.session_id, "ask", req.question,
                    {"answer": "".join(collected), **done}, grounded=True,
                )
            yield f"data: {json.dumps(done)}\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

    try:
        answer = service.generate_tutor_response(req.question, result.chunks, req.language)
    except NIMError as exc:
        raise HTTPException(503, "Something went wrong while generating your explanation. "
                                 "Try again.") from exc

    payload = {
        "answer": answer,
        "grounded": True,
        "sources": result.to_sources(),
        "retrieval": {
            "max_score": round(result.max_score, 3),
            "mean_score": round(result.mean_score, 3),
            "threshold": result.threshold,
            "reason": result.reason,
        },
    }
    if req.session_id:
        db.log_interaction(req.session_id, "ask", req.question, payload, grounded=True)
    return payload


# ---------------------------------------------------------------- teach-back

@app.post("/api/teachback")
def teach_back(req: TeachBackRequest) -> dict[str, Any]:
    session = db.get_session(req.session_id)
    if session is None:
        raise HTTPException(404, "Session not found.")

    # Retrieve on the concept plus the student's own words, so the evidence
    # covers whatever they actually claimed — including the wrong parts.
    result = retrieve(
        f"{req.concept}. {req.explanation}",
        document_id=req.document_id or session.get("document_id"),
        threshold=0.0,  # we grade against best-available evidence, never refuse here
    )

    mode = req.mode if req.mode in prompts.TEACH_BACK_MODES else "simple"

    try:
        evaluation = service.evaluate_teach_back(
            req.concept, req.explanation, result.chunks, req.language, mode
        )
    except NIMError as exc:
        raise HTTPException(503, "Couldn't evaluate that answer. Try again.") from exc

    current = session.get("difficulty", "medium")
    new_difficulty, reason = adaptive.next_difficulty_from_teach_back(
        current, evaluation["understanding"]
    )
    if new_difficulty != current:
        db.set_difficulty(req.session_id, new_difficulty)

    payload = {
        **evaluation,
        "mode": mode,
        # Derived, not asked of the model: a 5-mark equivalent has to agree with
        # the overall score the student is looking at, and arithmetic guarantees
        # that where a second model judgement would not.
        "marks_out_of_5": round(evaluation["scores"]["overall"] / 20, 1),
        "sources": result.to_sources(2),
        "difficulty": {
            "previous": current, "current": new_difficulty,
            "changed": new_difficulty != current, "reason": reason,
        },
    }
    db.log_interaction(req.session_id, "teachback", req.concept, payload)
    return payload


# ---------------------------------------------------------------------- doubt

@app.post("/api/doubt")
def doubt(req: DoubtRequest) -> dict[str, Any]:
    """Follow-up chat anchored to one already-generated explanation."""
    session = db.get_session(req.session_id)
    if session is None:
        raise HTTPException(404, "Session not found.")
    if not req.messages or req.messages[-1].role != "user":
        raise HTTPException(400, "The last message must be the student's doubt.")

    latest = req.messages[-1].content
    # Never refuse here — a doubt about content already taught should always
    # get the best-available evidence, the way teachback grades on it too.
    result = retrieve(
        f"{req.concept}. {latest}",
        document_id=req.document_id or session.get("document_id"),
        threshold=0.0,
    )

    try:
        answer = service.answer_doubt(
            req.explanation,
            req.concept,
            result.chunks,
            req.language,
            [m.model_dump() for m in req.messages],
        )
    except NIMError as exc:
        raise HTTPException(503, "Couldn't answer that. Try again.") from exc

    full_messages = [m.model_dump() for m in req.messages] + [
        {"role": "assistant", "content": answer}
    ]
    doc_id = req.document_id or session.get("document_id")
    if req.chat_id and db.get_chat(req.chat_id):
        db.update_chat_messages(req.chat_id, full_messages)
        chat_id = req.chat_id
    else:
        chat_id = db.create_chat(
            req.session_id, doc_id, req.concept, req.explanation, req.language, full_messages
        )

    return {"answer": answer, "sources": result.to_sources(2), "chat_id": chat_id}


# ----------------------------------------------------------------- chats

@app.get("/api/chats")
def chats(session_id: str | None = None) -> dict[str, Any]:
    """Recent Chats sidebar: newest-first, title + language + timestamp only."""
    rows = db.list_chats(session_id)
    return {
        "chats": [
            {
                "id": c["id"],
                "title": c["title"],
                "language": c["language"],
                "concept": c["concept"],
                "created_at": c["created_at"],
                "updated_at": c["updated_at"],
                "message_count": len(c["messages"]),
            }
            for c in rows
        ]
    }


@app.get("/api/chats/{chat_id}")
def get_chat(chat_id: str) -> dict[str, Any]:
    """Full chat, used to restore the thread and its grounding context."""
    chat = db.get_chat(chat_id)
    if chat is None:
        raise HTTPException(404, "Chat not found.")
    return chat


# ------------------------------------------------------------------ practice

@app.post("/api/practice")
def practice(req: PracticeRequest) -> dict[str, Any]:
    session = db.get_session(req.session_id)
    if session is None:
        raise HTTPException(404, "Session not found.")

    difficulty = req.difficulty or session.get("difficulty", "medium")
    result = retrieve(
        req.concept,
        document_id=req.document_id or session.get("document_id"),
        top_k=6, threshold=0.0,
    )
    if not result.chunks:
        raise HTTPException(400, "Couldn't find enough information in your textbook.")

    try:
        questions = service.generate_practice(
            req.concept, result.chunks, req.language, difficulty
        )
    except NIMError as exc:
        raise HTTPException(503, str(exc)) from exc

    if not questions:
        raise HTTPException(503, "Couldn't generate usable questions. Try again.")

    set_id = f"set_{req.session_id}_{len(_practice_sets)}"
    _practice_sets[set_id] = questions

    # Answers are withheld until submission so they cannot be read off the wire.
    return {
        "set_id": set_id,
        "difficulty": difficulty,
        "concept": req.concept,
        "questions": [
            {k: v for k, v in q.items() if k not in ("correct_answer", "explanation")}
            for q in questions
        ],
        "counts": {
            "mcq": sum(q["type"] == "mcq" for q in questions),
            "short_answer": sum(q["type"] == "short_answer" for q in questions),
        },
    }


@app.post("/api/practice/submit")
def submit_practice(req: SubmitRequest) -> dict[str, Any]:
    questions = _practice_sets.get(req.set_id)
    if questions is None:
        raise HTTPException(404, "That practice set has expired. Generate a new one.")

    session = db.get_session(req.session_id)
    if session is None:
        raise HTTPException(404, "Session not found.")

    graded = adaptive.grade_answers(questions, req.answers)
    current = session.get("difficulty", "medium")
    new_difficulty, reason = adaptive.next_difficulty_from_score(
        current, graded["correct"], graded["total"]
    )
    if new_difficulty != current:
        db.set_difficulty(req.session_id, new_difficulty)

    concept = req.concept or (questions[0].get("concept") or "general")
    db.record_performance(
        req.session_id, concept, current, graded["correct"], graded["total"]
    )

    payload = {
        **graded,
        "difficulty": {
            "previous": current, "current": new_difficulty,
            "changed": new_difficulty != current, "reason": reason,
        },
    }
    db.log_interaction(req.session_id, "practice", concept, payload)
    return payload


# ------------------------------------------------------------------ progress

@app.get("/api/progress/{session_id}")
def progress(session_id: str) -> dict[str, Any]:
    if db.get_session(session_id) is None:
        raise HTTPException(404, "Session not found.")
    return db.session_progress(session_id)


@app.get("/api/documents")
def documents() -> dict[str, Any]:
    return {"documents": db.list_documents()}


@app.get("/api/stats")
def get_stats() -> dict[str, Any]:
    """Judge mode: proves the out-of-scope refusal spends no NIM call."""
    speech = speech_stats.snapshot()
    return {
        **stats.snapshot(),
        # Counted separately: nim_calls must keep meaning "LLM calls", or the
        # refusal-spends-nothing proof stops proving anything.
        "speech_calls": speech["nim_calls"],
        "speech_by_task": speech["by_task"],
        "indexed_chunks": len(get_store()),
        "grounding_threshold": settings.grounding_threshold,
        "models": {
            "tutor": settings.tutor_model or None,
            "structured": settings.structured_model or None,
            "vision": settings.vision_model or None,
            "embed": settings.nvidia_embed_model,
        },
    }

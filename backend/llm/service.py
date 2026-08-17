"""Task-shaped LLM interface.

Routes above this call generate_tutor_response / evaluate_teach_back /
generate_practice and never see a model ID, a prompt, or a JSON quirk. Swapping
the NIM model is an .env change, not a code change.

Structured tasks use a repair retry: if the model returns unparseable JSON we
send the broken output back once and ask for JSON only. If that also fails we
degrade to a usable default rather than showing an error to a judge.
"""

from __future__ import annotations

import re
from typing import Any, Iterator

from backend.config import settings
from backend.llm import prompts
from backend.llm.json_utils import extract_json
from backend.llm.provider import NIMError, get_provider

_REPAIR = (
    "Your previous reply was not valid JSON. Reply again with ONLY the JSON "
    "object — no explanation, no markdown fences, nothing before or after it."
)


def _structured_call(
    system: str, user: str, *, task: str, max_tokens: int = 1600
) -> dict[str, Any] | None:
    """One call, plus one repair retry. Returns None if both fail to parse."""
    provider = get_provider()
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]

    raw = provider.chat(
        messages, task=task, model=settings.structured_model,
        temperature=0.2, max_tokens=max_tokens,
    )
    if (parsed := extract_json(raw)) is not None:
        return parsed

    messages += [{"role": "assistant", "content": raw}, {"role": "user", "content": _REPAIR}]
    raw = provider.chat(
        messages, task=f"{task}:repair", model=settings.structured_model,
        temperature=0.0, max_tokens=max_tokens,
    )
    return extract_json(raw)


# ---------------------------------------------------------------- 1. teaching

def _tutor_messages(question: str, chunks: list[dict], language: str) -> list[dict]:
    return [
        {"role": "system", "content": prompts.tutor_system_prompt(language)},
        {
            "role": "user",
            "content": (
                f"{prompts.build_context_block(chunks)}\n\n"
                f"Student's question: {question}\n\n"
                "Teach them the answer using only the textbook context above.\n"
                f"{prompts.language_reminder(language)}"
            ),
        },
    ]


def generate_tutor_response(question: str, chunks: list[dict], language: str) -> str:
    return get_provider().chat(
        _tutor_messages(question, chunks, language),
        task="tutor", model=settings.tutor_model, temperature=0.5, max_tokens=900,
    )


def stream_tutor_response(question: str, chunks: list[dict], language: str) -> Iterator[str]:
    return get_provider().stream(
        _tutor_messages(question, chunks, language),
        task="tutor", model=settings.tutor_model, temperature=0.5, max_tokens=900,
    )


# -------------------------------------------------------------- 2. teach-back

_VALID_UNDERSTANDING = {"correct", "partial", "misconception", "incorrect"}
_VALID_NEXT = {"reteach", "reinforce", "advance"}

_SCORE_KEYS = ("overall", "concept", "clarity", "completeness", "examples")

# Fallback when the model returns a label but no usable numbers. Keeps the
# dashboard honest rather than showing a confident-looking zero.
_UNDERSTANDING_TO_SCORE = {
    "correct": 85, "partial": 60, "misconception": 40, "incorrect": 25,
}


def _clamp_score(value: Any, default: int) -> int:
    """0-100 int, tolerating the '82/100', '82%' and 0.82 shapes models emit."""
    if isinstance(value, str):
        value = value.strip().rstrip("%").split("/")[0].strip()
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    # A model that answers 0.82 meant 82 — but a real 1/100 is vanishingly rare.
    if 0 < number <= 1:
        number *= 100
    return max(0, min(100, round(number)))


def _normalise_scores(raw: Any, understanding: str) -> dict[str, int]:
    fallback = _UNDERSTANDING_TO_SCORE.get(understanding, 50)
    if not isinstance(raw, dict):
        raw = {}

    scores = {k: _clamp_score(raw.get(k), fallback) for k in _SCORE_KEYS}

    # If the model skipped "overall" specifically, average the parts it did give
    # rather than inheriting a label-derived guess that ignores its own detail.
    if raw.get("overall") is None:
        parts = [scores[k] for k in _SCORE_KEYS if k != "overall"]
        scores["overall"] = round(sum(parts) / len(parts))

    return scores


def evaluate_teach_back(
    concept: str,
    explanation: str,
    chunks: list[dict],
    language: str,
    mode: str = prompts.DEFAULT_TEACH_BACK_MODE,
) -> dict[str, Any]:
    audience = prompts.TEACH_BACK_MODES.get(
        mode, prompts.TEACH_BACK_MODES[prompts.DEFAULT_TEACH_BACK_MODE]
    )["goal"]

    user = (
        f"{prompts.build_context_block(chunks)}\n\n"
        f"Concept being tested: {concept}\n\n"
        f"The student was asked to {audience}.\n\n"
        f"They explained it in their own words:\n\"\"\"\n{explanation}\n\"\"\"\n\n"
        "Evaluate their conceptual understanding against that audience. Ignore "
        "grammar, spelling, script and language mixing entirely."
    )

    parsed = _structured_call(
        prompts.teach_back_system_prompt(language, mode), user,
        task="teachback", max_tokens=1800,
    )

    if parsed is None:
        # Never hard-fail in front of a judge — ask them to try again.
        return {
            "understanding": "partial",
            "scores": {k: 0 for k in _SCORE_KEYS},
            "correct_points": [],
            "did_well": [],
            "improve": [],
            "misconceptions": [],
            "feedback": "I couldn't evaluate that properly. Try explaining it once more.",
            "improved_explanation": "",
            "next_action": "reinforce",
            "degraded": True,
        }

    return _normalise_teach_back(parsed)


def _normalise_teach_back(parsed: dict[str, Any]) -> dict[str, Any]:
    """Coerce model output into the exact shape the frontend expects."""
    understanding = str(parsed.get("understanding", "")).strip().lower()
    if understanding not in _VALID_UNDERSTANDING:
        understanding = "partial"

    misconceptions = []
    for m in parsed.get("misconceptions") or []:
        if isinstance(m, dict):
            misconceptions.append({
                "student_claim": str(m.get("student_claim", "")).strip(),
                "problem": str(m.get("problem", "")).strip(),
                "correct_concept": str(m.get("correct_concept", "")).strip(),
            })
        elif isinstance(m, str) and m.strip():
            misconceptions.append({"student_claim": m.strip(), "problem": "", "correct_concept": ""})

    # A model that names misconceptions but grades "correct" is contradicting
    # itself; trust the specific finding over the summary label.
    if misconceptions and understanding == "correct":
        understanding = "misconception"

    next_action = str(parsed.get("next_action", "")).strip().lower()
    if next_action not in _VALID_NEXT:
        next_action = {"correct": "advance", "partial": "reinforce"}.get(understanding, "reteach")

    def _points(key: str, limit: int = 4) -> list[str]:
        return [str(p).strip() for p in (parsed.get(key) or []) if str(p).strip()][:limit]

    points = _points("correct_points")
    scores = _normalise_scores(parsed.get("scores"), understanding)

    # A named misconception must be visible in the number, not just the prose —
    # an 88 sitting next to "misconception detected" reads as a broken grader.
    if misconceptions:
        scores["overall"] = min(scores["overall"], 65)

    return {
        "understanding": understanding,
        "scores": scores,
        "correct_points": points,
        # Fall back to correct_points so the "what you did well" panel is never
        # empty just because the model used the older field name.
        "did_well": _points("did_well") or points,
        "improve": _points("improve"),
        "misconceptions": misconceptions,
        "feedback": str(parsed.get("feedback", "")).strip(),
        "improved_explanation": str(parsed.get("improved_explanation", "")).strip(),
        "next_action": next_action,
        "degraded": False,
    }


# ---------------------------------------------------------------- 3. practice

_VALID_DIFFICULTY = ("easy", "medium", "hard")


def generate_practice(
    concept: str, chunks: list[dict], language: str, difficulty: str
) -> list[dict[str, Any]]:
    if difficulty not in _VALID_DIFFICULTY:
        difficulty = "medium"

    user = (
        f"{prompts.build_context_block(chunks)}\n\n"
        f"Concept: {concept}\n\n"
        f"Write 5 MCQs and 2 short-answer questions at {difficulty} difficulty, "
        "answerable entirely from the textbook context above."
    )

    parsed = _structured_call(
        prompts.practice_system_prompt(language, difficulty), user,
        task="practice", max_tokens=2600,
    )
    if parsed is None:
        raise NIMError("Couldn't generate practice questions. Try again.")

    return _normalise_practice(parsed.get("questions") or [], difficulty)


_OPTION_PREFIX = re.compile(r"^\s*(?:option\s*)?([A-D])\s*[\).:\-]?\s*$", re.IGNORECASE)


def _resolve_option(answer: str, options: list[str]) -> str | None:
    """Map a model's `correct_answer` onto the exact option text.

    Models answer inconsistently: the option text, a bare letter, "Option B",
    "C)". Anything we cannot resolve confidently returns None so the caller
    drops the question — a mis-mapped answer would mark a right student wrong,
    which is far worse than one fewer question.
    """
    stripped = answer.strip()

    for option in options:
        if option.strip().lower() == stripped.lower():
            return option

    # A bare letter, with or without an "Option"/punctuation wrapper.
    if m := _OPTION_PREFIX.match(stripped):
        idx = ord(m.group(1).upper()) - 65
        if 0 <= idx < len(options):
            return options[idx]

    # The model prefixed the real option text, e.g. "B) Soil".
    for option in options:
        text = option.strip().lower()
        if text and stripped.lower().endswith(text):
            return option

    return None


def _normalise_practice(raw: list, difficulty: str) -> list[dict[str, Any]]:
    """Validate and repair questions; drop any that are structurally unusable."""
    out: list[dict[str, Any]] = []

    for i, q in enumerate(raw):
        if not isinstance(q, dict):
            continue
        question = str(q.get("question", "")).strip()
        if not question:
            continue

        qtype = str(q.get("type", "")).strip().lower()
        options = [str(o).strip() for o in (q.get("options") or []) if str(o).strip()]
        answer = str(q.get("correct_answer", "")).strip()
        # Infer the type when the model omits or mislabels it.
        qtype = "mcq" if (qtype == "mcq" or len(options) >= 2) else "short_answer"

        if qtype == "mcq":
            if len(options) < 2 or not answer:
                continue
            if answer not in options:
                match = _resolve_option(answer, options)
                if match is None:
                    continue  # unanswerable — better to drop than to mis-grade
                answer = match

        out.append({
            "id": f"q{i}",
            "type": qtype,
            "question": question,
            "options": options if qtype == "mcq" else [],
            "correct_answer": answer,
            "explanation": str(q.get("explanation", "")).strip(),
            "difficulty": (str(q.get("difficulty", "")).strip().lower()
                           if str(q.get("difficulty", "")).strip().lower() in _VALID_DIFFICULTY
                           else difficulty),
            "concept": str(q.get("concept", "")).strip(),
        })

    return out

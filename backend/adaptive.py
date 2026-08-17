"""Rule-based adaptive difficulty.

Deliberately transparent rather than ML-based: the judge must be able to see
*why* the difficulty changed, and a rule can be explained in one sentence on
stage. Complexity here would cost hours and win nothing.
"""

from __future__ import annotations

from typing import Any

LEVELS = ["easy", "medium", "hard"]


def _shift(difficulty: str, step: int) -> str:
    idx = LEVELS.index(difficulty) if difficulty in LEVELS else 1
    return LEVELS[max(0, min(len(LEVELS) - 1, idx + step))]


def next_difficulty_from_teach_back(current: str, understanding: str) -> tuple[str, str]:
    """Teach-back outcome moves difficulty. Returns (new_difficulty, reason)."""
    if understanding == "correct":
        new = _shift(current, +1)
        return new, ("Concept explained correctly — moving up." if new != current
                     else "Concept explained correctly — already at the hardest level.")
    if understanding == "partial":
        return current, "Partly right — staying here to reinforce."
    return _shift(current, -1), "Misconception found — easing off to rebuild the basics."


def next_difficulty_from_score(current: str, correct: int, total: int) -> tuple[str, str]:
    """Practice results move difficulty. Returns (new_difficulty, reason)."""
    if total == 0:
        return current, "No questions answered."

    accuracy = correct / total
    if accuracy >= 0.8:
        new = _shift(current, +1)
        return new, (f"Scored {correct}/{total} — moving up to {new}." if new != current
                     else f"Scored {correct}/{total} — already at the hardest level.")
    if accuracy >= 0.5:
        return current, f"Scored {correct}/{total} — staying at {current} for more practice."

    new = _shift(current, -1)
    return new, (f"Scored {correct}/{total} — dropping to {new} to rebuild." if new != current
                 else f"Scored {correct}/{total} — already at the easiest level; let's review.")


def grade_answers(questions: list[dict[str, Any]], answers: dict[str, str]) -> dict[str, Any]:
    """Grade a submitted practice set.

    MCQs are graded exactly. Short answers are NOT auto-graded — keyword
    matching would punish correct Tanglish phrasing, which is precisely the
    mistake this product exists to avoid. They are returned for self-review.
    """
    results = []
    correct_count = 0
    graded_total = 0

    for q in questions:
        given = (answers.get(q["id"]) or "").strip()

        if q["type"] == "mcq":
            is_correct = given.lower() == q["correct_answer"].strip().lower()
            graded_total += 1
            correct_count += int(is_correct)
            results.append({
                "id": q["id"], "type": "mcq", "given": given,
                "correct": is_correct, "correct_answer": q["correct_answer"],
                "explanation": q.get("explanation", ""),
            })
        else:
            results.append({
                "id": q["id"], "type": "short_answer", "given": given,
                "correct": None,  # self-reviewed against the model answer
                "correct_answer": q.get("correct_answer", ""),
                "explanation": q.get("explanation", ""),
            })

    return {
        "results": results,
        "correct": correct_count,
        "total": graded_total,
        "accuracy": round(correct_count / graded_total, 2) if graded_total else None,
    }

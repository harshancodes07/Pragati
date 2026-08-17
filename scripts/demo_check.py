"""End-to-end demo rehearsal — Block 8's verification, automated.

Runs the exact judge sequence against a live backend and prints a pass/fail
line for each step, so the demo can be re-verified in seconds before going on
stage.

    python -m scripts.demo_check              # needs the backend running on :8000
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE = "http://127.0.0.1:8000/api"
DEMO_FILE = Path(__file__).resolve().parent.parent / "demo" / "photosynthesis.txt"

PASS, FAIL = "\033[92m✓\033[0m", "\033[91m✗\033[0m"
_failures = 0


def check(label: str, ok: bool, detail: str = "") -> bool:
    global _failures
    if not ok:
        _failures += 1
    print(f"  {PASS if ok else FAIL} {label}" + (f"  — {detail}" if detail else ""))
    return ok


def main() -> int:
    client = httpx.Client(timeout=180.0)

    print("\n1. Health")
    h = client.get(f"{BASE}/health").json()
    check("NIM reachable", h["nim"]["reachable"], h["nim"]["detail"])
    check("model configured", bool(h["nim"]["model"]), h["nim"]["model"] or "NOT SET")
    if not h["nim"]["reachable"]:
        print("\nBackend cannot reach NIM. Fix .env before rehearsing.\n")
        return 1

    before = client.get(f"{BASE}/stats").json()["nim_calls"]

    print("\n2. Upload textbook")
    r = client.post(
        f"{BASE}/upload",
        files={"file": ("photosynthesis.txt", DEMO_FILE.read_bytes(), "text/plain")},
        data={"language": "tanglish"},
    )
    check("upload accepted", r.status_code == 200, r.text[:120])
    if r.status_code != 200:
        return 1
    doc = r.json()
    check("chunks indexed", doc["chunk_count"] > 0, f"{doc['chunk_count']} chunks")

    ids = {"document_id": doc["document_id"], "session_id": doc["session_id"]}

    print("\n3. In-scope Tanglish question")
    r = client.post(f"{BASE}/ask", json={**ids, "question": "Photosynthesis-na enna?",
                                         "language": "tanglish"}).json()
    check("grounded", r["grounded"], f"score {r['retrieval']['max_score']}")
    check("has page citation", bool(r["sources"]) and r["sources"][0]["page"] is not None)
    print(f"      \033[2m{r['answer'][:180]}…\033[0m")

    print("\n4. Out-of-scope question")
    calls_before = client.get(f"{BASE}/stats").json()["nim_calls"]
    r = client.post(f"{BASE}/ask", json={**ids, "question": "Who is the current Prime Minister of India?",
                                         "language": "tanglish"}).json()
    calls_after = client.get(f"{BASE}/stats").json()["nim_calls"]
    check("refused", not r["grounded"], r["retrieval"]["reason"])
    # The headline claim: refusal costs zero generation calls.
    check("spent no LLM call", calls_after == calls_before + 1,
          f"{calls_after - calls_before} call(s) — embedding only")

    print("\n5. Teach-back — correct answer in informal Tanglish")
    r = client.post(f"{BASE}/teachback", json={
        **ids, "concept": "photosynthesis", "language": "tanglish",
        "explanation": "Plant sunlight ah use panni, water and carbon dioxide vechi food make pannum.",
    }).json()
    check("graded correct despite informal Tanglish", r["understanding"] == "correct",
          f"got '{r['understanding']}'")

    print("\n6. Teach-back — deliberate misconception")
    r = client.post(f"{BASE}/teachback", json={
        **ids, "concept": "photosynthesis", "language": "tanglish",
        "explanation": "Plants oda food is soil. Roots la irundhu soil ah saapdum.",
    }).json()
    check("misconception detected", r["understanding"] in ("misconception", "incorrect"),
          f"got '{r['understanding']}'")
    check("names the specific claim", len(r["misconceptions"]) > 0)
    if r["misconceptions"]:
        m = r["misconceptions"][0]
        print(f"      \033[2mclaim: {m['student_claim'][:80]}\033[0m")
        print(f"      \033[2mfix:   {m['correct_concept'][:80]}\033[0m")
    check("difficulty eased", r["difficulty"]["changed"], r["difficulty"]["reason"])

    print("\n7. Practice generation")
    r = client.post(f"{BASE}/practice", json={**ids, "concept": "photosynthesis",
                                              "language": "tanglish"}).json()
    check("5 MCQs", r["counts"]["mcq"] == 5, f"got {r['counts']['mcq']}")
    check("2 short answers", r["counts"]["short_answer"] == 2, f"got {r['counts']['short_answer']}")
    check("MCQs have 4 options",
          all(len(q["options"]) == 4 for q in r["questions"] if q["type"] == "mcq"))
    check("answers withheld from client",
          all("correct_answer" not in q for q in r["questions"]))

    print("\n8. Adaptive difficulty after wrong answers")
    wrong = {q["id"]: (q["options"][0] if q["type"] == "mcq" else "dunno")
             for q in r["questions"]}
    g = client.post(f"{BASE}/practice/submit", json={
        "session_id": doc["session_id"], "set_id": r["set_id"],
        "answers": wrong, "concept": "photosynthesis",
    }).json()
    check("graded", g["total"] == 5, f"{g['correct']}/{g['total']}")
    check("difficulty responded", "difficulty" in g, g["difficulty"]["reason"])

    total = client.get(f"{BASE}/stats").json()
    print(f"\n{'─' * 62}")
    print(f"NIM calls this run: {total['nim_calls'] - before}  ·  "
          f"avg latency {total['avg_latency_ms']}ms")
    print(f"{'FAILURES: ' + str(_failures) if _failures else 'ALL CHECKS PASSED'}\n")
    return 1 if _failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

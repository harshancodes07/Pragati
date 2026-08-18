"""Block 1 — pick the NIM model with evidence, not guesswork.

Catalog IDs churn, so this script asks the key what it can actually reach, then
runs six cases that mirror exactly what Pragati does in the demo. Writes a
scorecard to data/benchmark.json and prints a table.

    python -m scripts.benchmark_nim            # list catalog + score candidates
    python -m scripts.benchmark_nim --list     # just list reachable models
    python -m scripts.benchmark_nim --models a,b,c
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import settings  # noqa: E402
from backend.llm.json_utils import extract_json  # noqa: E402
from backend.llm.provider import NIMError, get_provider  # noqa: E402

# Stand-in textbook content. English on purpose: the cross-lingual case is the
# whole product thesis and must be tested against English source material.
TEXTBOOK = """Photosynthesis is the process by which green plants and some other organisms
use sunlight to synthesise food from carbon dioxide and water. In green plants,
photosynthesis takes place in the chloroplasts, which contain the green pigment
chlorophyll. Chlorophyll absorbs light energy and converts it into chemical
energy. During this process, oxygen is released as a by-product. The food
produced is stored in the form of glucose. Plants absorb water and minerals from
the soil through their roots; the soil itself is not food for the plant."""

# Preference order for auto-selecting candidates from the live catalog.
# Indic-tuned first (25% of the score is regional language), general-strong next.
# Verified against this key's catalog on 2026-08-17. `sarvamai/sarvam-m` and the
# Qwen family are NOT reachable here, so the Indic-tuned shortcut is unavailable
# and we fall back to large general models with the best multilingual coverage.
PREFERRED = [
    "gemma-4",            # Gemma has historically been the strongest Indic generalist
    "llama-3.3-70b",
    "nemotron-3-super",
    "mistral-large-2",
    "glm",
    "kimi",
    "gpt-oss-120b",
]

CASES = [
    {
        "name": "tanglish_explain",
        "task": "Natural Tanglish explanation (not translation)",
        "system": (
            "You are a tutor. Explain in TANGLISH: conversational Tamil written in "
            "Latin script, the way a Tamil teacher actually speaks. Tamil sentence "
            "structure, technical terms kept in English. Do not write in Tamil "
            "script. Do not translate an English sentence word by word. Under 120 words."
        ),
        "user": "Explain photosynthesis to a 14-year-old.",
        "json": False,
    },
    {
        "name": "tamil_script",
        "task": "Natural Tamil script generation",
        "system": (
            "You are a tutor. Explain in natural spoken TAMIL SCRIPT to a "
            "14-year-old. Everyday register, not literary. Keep technical terms in "
            "English. Under 120 words."
        ),
        "user": "Explain photosynthesis.",
        "json": False,
    },
    {
        "name": "grounded_qa",
        "task": "Grounded QA from context",
        "system": (
            "Answer using ONLY the textbook context. Add no outside facts. "
            "Answer in Tanglish (Tamil in Latin script), under 80 words."
        ),
        "user": f"<textbook_context>\n{TEXTBOOK}\n</textbook_context>\n\nWhy do plants need sunlight?",
        "json": False,
    },
    {
        "name": "out_of_scope",
        "task": "Refuses when context lacks the answer",
        "system": (
            "Answer using ONLY the textbook context. If the answer is not present "
            "in the context, reply exactly: NOT_IN_TEXTBOOK"
        ),
        "user": (
            f"<textbook_context>\n{TEXTBOOK}\n</textbook_context>\n\n"
            "Who is the current Prime Minister of India?"
        ),
        "json": False,
        "expect_contains": "NOT_IN_TEXTBOOK",
    },
    {
        "name": "teachback_json",
        "task": "Misconception detection + JSON reliability",
        "system": (
            "Evaluate whether the student understands. Grade the CONCEPT, never the "
            "grammar or language mixing. Respond with ONLY a JSON object: "
            '{"understanding":"correct|partial|misconception|incorrect",'
            '"correct_points":[],"misconceptions":[{"student_claim":"","problem":"",'
            '"correct_concept":""}],"feedback":"","next_action":""}'
        ),
        "user": (
            f"<textbook_context>\n{TEXTBOOK}\n</textbook_context>\n\n"
            "Student explained: 'Plants oda food is soil. Roots la irundhu soil ah "
            "saapdum, adhu dhaan avanga food.'"
        ),
        "json": True,
        "expect_keys": ["understanding", "misconceptions", "feedback"],
    },
    {
        "name": "tanglish_query_english_ctx",
        "task": "Tanglish question against English context",
        "system": "Answer from the context in Tanglish (Tamil in Latin script). Under 80 words.",
        "user": f"<textbook_context>\n{TEXTBOOK}\n</textbook_context>\n\nPhotosynthesis-na enna?",
        "json": False,
    },
]

TAMIL_RANGE = range(0x0B80, 0x0BFF)
# Particles a real Tanglish speaker uses; a literal transliteration lacks them.
TANGLISH_MARKERS = [
    "-na", "-la", "-oda", "-nu", "panra", "panni", "pannum", "irukku", "irundhu",
    "adhu", "idhu", "dhaan", "enna", "ellam", "kudukum", "aagum", "sollradhu",
]


def has_tamil_script(text: str) -> bool:
    return any(ord(ch) in TAMIL_RANGE for ch in text)


def tanglish_markers(text: str) -> int:
    low = text.lower()
    return sum(1 for m in TANGLISH_MARKERS if m in low)


def score_case(case: dict, output: str, parsed: dict | None) -> tuple[float, str]:
    """Return (0-1 score, human note). Heuristic — a sanity filter, not a judge."""
    if not output:
        return 0.0, "empty"

    name = case["name"]

    if name == "tanglish_explain" or name == "tanglish_query_english_ctx":
        markers = tanglish_markers(output)
        if has_tamil_script(output):
            return 0.2, "wrote Tamil script in Tanglish mode"
        if markers >= 4:
            return 1.0, f"{markers} natural markers"
        if markers >= 2:
            return 0.6, f"only {markers} markers — reads translated"
        return 0.3, "no Tanglish register"

    if name == "tamil_script":
        if not has_tamil_script(output):
            return 0.0, "no Tamil script produced"
        tamil_chars = sum(1 for ch in output if ord(ch) in TAMIL_RANGE)
        ratio = tamil_chars / max(len(output), 1)
        return (1.0, f"{ratio:.0%} Tamil chars") if ratio > 0.4 else (0.6, f"only {ratio:.0%} Tamil")

    if name == "grounded_qa":
        hits = sum(k in output.lower() for k in ("chlorophyll", "energy", "light", "food", "glucose"))
        return min(hits / 3, 1.0), f"{hits} concept hits"

    if name == "out_of_scope":
        if case["expect_contains"] in output:
            return 1.0, "refused correctly"
        if "modi" in output.lower() or "minister" in output.lower():
            return 0.0, "ANSWERED FROM OUTSIDE KNOWLEDGE"
        return 0.5, "refused but off-format"

    if name == "teachback_json":
        if parsed is None:
            return 0.0, "JSON parse FAILED"
        missing = [k for k in case["expect_keys"] if k not in parsed]
        if missing:
            return 0.4, f"missing keys: {missing}"
        verdict = str(parsed.get("understanding", "")).lower()
        caught = len(parsed.get("misconceptions") or []) > 0
        if verdict in ("misconception", "incorrect") and caught:
            return 1.0, "caught the soil misconception"
        if caught:
            return 0.7, f"found misconception but graded '{verdict}'"
        return 0.2, f"MISSED the misconception (graded '{verdict}')"

    return 0.5, ""


def pick_candidates(available: list[str], limit: int) -> list[str]:
    chosen: list[str] = []
    for pref in PREFERRED:
        for model in available:
            if pref in model.lower() and model not in chosen:
                chosen.append(model)
                break
        if len(chosen) >= limit:
            break
    return chosen[:limit]


def run_model(provider, model: str) -> dict:
    results, total, latencies = {}, 0.0, []

    for case in CASES:
        messages = [
            {"role": "system", "content": case["system"]},
            {"role": "user", "content": case["user"]},
        ]
        started = time.perf_counter()
        try:
            output = provider.chat(
                messages, task=f"bench:{case['name']}", model=model,
                temperature=0.3, max_tokens=800,
            )
        except NIMError as exc:
            results[case["name"]] = {"score": 0.0, "note": f"ERROR: {str(exc)[:90]}"}
            continue

        elapsed = time.perf_counter() - started
        latencies.append(elapsed)
        parsed = extract_json(output) if case["json"] else None
        score, note = score_case(case, output, parsed)
        total += score
        results[case["name"]] = {
            "score": round(score, 2),
            "note": note,
            "latency_s": round(elapsed, 1),
            "sample": output[:400],
        }

    return {
        "model": model,
        "total": round(total, 2),
        "max": len(CASES),
        "avg_latency_s": round(sum(latencies) / len(latencies), 1) if latencies else None,
        "cases": results,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="only list reachable models")
    ap.add_argument("--models", help="comma-separated model IDs to benchmark")
    ap.add_argument("--limit", type=int, default=3, help="how many models to auto-pick")
    args = ap.parse_args()

    try:
        provider = get_provider()
    except NIMError as exc:
        print(f"✗ {exc}")
        return 1

    print("Fetching model catalog from NIM...")
    try:
        available = provider.list_models()
    except Exception as exc:  # noqa: BLE001
        print(f"✗ Could not list models: {exc}")
        return 1

    print(f"✓ {len(available)} models reachable with this key.\n")

    if args.list:
        for m in available:
            print(f"  {m}")
        return 0

    if args.models:
        candidates = [m.strip() for m in args.models.split(",") if m.strip()]
        unknown = [m for m in candidates if m not in available]
        if unknown:
            print(f"⚠ Not in catalog (will still try): {unknown}\n")
    else:
        candidates = pick_candidates(available, args.limit)

    if not candidates:
        print("✗ No candidates matched. Re-run with --list then --models.")
        return 1

    print(f"Benchmarking {len(candidates)} model(s): {', '.join(candidates)}")
    print(f"{len(CASES)} cases each.\n")

    reports = []
    for model in candidates:
        print(f"── {model}")
        report = run_model(provider, model)
        reports.append(report)
        for case_name, r in report["cases"].items():
            bar = "█" * int(r["score"] * 10)
            print(f"   {case_name:<32} {r['score']:>4.2f} {bar:<10} {r['note']}")
        print(f"   {'TOTAL':<32} {report['total']:>4.2f} / {report['max']}"
              f"   avg {report['avg_latency_s']}s\n")

    reports.sort(key=lambda r: (-r["total"], r["avg_latency_s"] or 999))
    out = settings.data_dir / "benchmark.json"
    out.write_text(json.dumps(reports, indent=2, ensure_ascii=False))

    print("=" * 64)
    print("RANKING")
    for i, r in enumerate(reports, 1):
        print(f"  {i}. {r['model']:<48} {r['total']}/{r['max']}")

    winner = reports[0]
    tamil = winner["cases"].get("tanglish_explain", {}).get("score", 0)
    js = winner["cases"].get("teachback_json", {}).get("score", 0)

    print(f"\nScorecard written to {out}")
    print(f"\nSet in .env:\n  NVIDIA_MODEL={winner['model']}")
    if len(reports) > 1:
        print(f"  NVIDIA_MODEL_BACKUP={reports[1]['model']}")

    # If no single model is both fluent and JSON-reliable, split the roles.
    if tamil < 0.6 or js < 0.6:
        best_tamil = max(reports, key=lambda r: r["cases"].get("tanglish_explain", {}).get("score", 0))
        best_json = max(reports, key=lambda r: r["cases"].get("teachback_json", {}).get("score", 0))
        if best_tamil["model"] != best_json["model"]:
            print("\n⚠ No single model wins both. Split the roles:")
            print(f"  NVIDIA_MODEL_TUTOR={best_tamil['model']}")
            print(f"  NVIDIA_MODEL_STRUCTURED={best_json['model']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

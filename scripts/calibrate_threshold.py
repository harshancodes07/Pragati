"""Calibrate GROUNDING_THRESHOLD against the real demo document.

The threshold decides refusals, so a bad value fails the demo in one of two
visible ways: refusing a legitimate question, or answering "Who is the Prime
Minister of India?" from the model's own knowledge.

This scores in-scope and out-of-scope questions against the ACTUAL indexed
chunks of demo/photosynthesis.txt and picks a value with real separation.

    python -m scripts.calibrate_threshold
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.config import settings  # noqa: E402
from backend.ingest.chunk import chunk_pages  # noqa: E402
from backend.ingest.clean import clean_text  # noqa: E402
from backend.llm.provider import get_provider  # noqa: E402

IN_SCOPE = [
    "Photosynthesis-na enna?",
    "Plants epdi food make pannuthu?",
    "Chlorophyll oda velai enna?",
    "Why do plants need sunlight?",
    "Soil dhaan plant oda food-a?",
    "Oxygen epdi produce aaguthu?",
    "ஒளிச்சேர்க்கை என்றால் என்ன?",
    "प्रकाश संश्लेषण क्या है?",
    "What are the raw materials for photosynthesis?",
    "Stomata enna pannuthu?",
    "Glucose epdi store pannuthu plant?",
    "What is an autotroph?",
]

OUT_OF_SCOPE = [
    "Who is the current Prime Minister of India?",
    "India oda capital enna?",
    "Explain Newton's laws of motion",
    "What is the capital of France?",
    "Bitcoin price enna ippo?",
    "Who won the last cricket world cup?",
    "How do I write a for loop in Python?",
    "இந்தியாவின் ஜனாதிபதி யார்?",
    "What is the human digestive system?",
    "Tell me about the Mughal empire",
]


def main() -> int:
    provider = get_provider()

    text = clean_text((ROOT / "demo" / "photosynthesis.txt").read_text(encoding="utf-8"))
    chunks = chunk_pages([text], "calib")
    print(f"Indexed {len(chunks)} chunks from the demo textbook "
          f"using {settings.nvidia_embed_model}\n")

    P = np.array(provider.embed([c["text"] for c in chunks], input_type="passage"),
                 dtype=np.float32)
    P /= np.maximum(np.linalg.norm(P, axis=1, keepdims=True), 1e-10)

    def top_scores(questions: list[str]) -> list[float]:
        Q = np.array(provider.embed(questions, input_type="query"), dtype=np.float32)
        Q /= np.maximum(np.linalg.norm(Q, axis=1, keepdims=True), 1e-10)
        return [float(np.max(row)) for row in (Q @ P.T)]

    print("IN SCOPE (must be answered)")
    in_scores = top_scores(IN_SCOPE)
    for q, s in zip(IN_SCOPE, in_scores):
        print(f"  {s:.3f}  {q}")

    print("\nOUT OF SCOPE (must be refused)")
    out_scores = top_scores(OUT_OF_SCOPE)
    for q, s in zip(OUT_OF_SCOPE, out_scores):
        print(f"  {s:.3f}  {q}")

    lo_in, hi_out = min(in_scores), max(out_scores)
    print(f"\n{'─' * 66}")
    print(f"in-scope : min {lo_in:.3f}  mean {np.mean(in_scores):.3f}  max {max(in_scores):.3f}")
    print(f"out-scope: min {min(out_scores):.3f}  mean {np.mean(out_scores):.3f}  max {hi_out:.3f}")

    if lo_in > hi_out:
        # Clean separation: sit in the gap, biased low so a legitimate question
        # is never refused on stage.
        threshold = round(hi_out + (lo_in - hi_out) * 0.4, 3)
        print(f"\n✓ Clean separation — gap of {lo_in - hi_out:.3f}")
        print(f"  GROUNDING_THRESHOLD={threshold}")
        errors = 0
    else:
        # Overlap: pick the value maximising correct decisions, breaking ties
        # toward answering rather than refusing.
        best, threshold = -1, 0.0
        for cand in np.arange(0.05, 0.65, 0.005):
            score = sum(s >= cand for s in in_scores) + sum(s < cand for s in out_scores)
            if score > best:
                best, threshold = score, round(float(cand), 3)
        errors = len(in_scores) + len(out_scores) - best
        wrongly_refused = [q for q, s in zip(IN_SCOPE, in_scores) if s < threshold]
        wrongly_answered = [q for q, s in zip(OUT_OF_SCOPE, out_scores) if s >= threshold]
        print(f"\n⚠ Overlap of {hi_out - lo_in:.3f} — no perfect threshold exists")
        print(f"  GROUNDING_THRESHOLD={threshold}  ({errors} misclassified)")
        for q in wrongly_refused:
            print(f"    would refuse (bad):  {q}")
        for q in wrongly_answered:
            print(f"    would answer (bad):  {q}")

    print(f"\n  currently in .env: GROUNDING_THRESHOLD={settings.grounding_threshold}")
    if settings.grounding_threshold > min(in_scores):
        print(f"  ✗ CURRENT VALUE REFUSES "
              f"{sum(s < settings.grounding_threshold for s in in_scores)}"
              f"/{len(in_scores)} VALID QUESTIONS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

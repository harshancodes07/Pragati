"""Block 3 gate — does cross-lingual retrieval actually work?

The product thesis is that a Tanglish question finds an English textbook chunk.
That is a property of the embedding model, not of prompting, so it must be
measured before anything else is built on top of it.

Each candidate embeds the same English chunks and the same student questions,
and we check whether the RIGHT chunk ranks first, and by what margin.

    python -m scripts.benchmark_embed
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import httpx
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import settings  # noqa: E402

CANDIDATES = [
    "nvidia/nemotron-3-embed-1b",
    "baai/bge-m3",
    "nvidia/llama-nemotron-embed-1b-v2",
    "nvidia/llama-3.2-nv-embedqa-1b-v1",
    "nvidia/nv-embedqa-e5-v5",
    "snowflake/arctic-embed-l",
]

# English textbook chunks — deliberately the language mismatch we must bridge.
PASSAGES = [
    "Photosynthesis is the process by which green plants use sunlight to "
    "synthesise food from carbon dioxide and water. Chlorophyll in the "
    "chloroplasts absorbs light energy and converts it to chemical energy.",
    "The plant does not eat the soil. The soil supplies water and dissolved "
    "minerals only. The food itself is manufactured in the leaves as glucose.",
    "Oxygen is released as a by-product of photosynthesis and passes out of the "
    "leaf through the stomata into the air.",
    "Newton's first law states that an object at rest stays at rest unless acted "
    "upon by an external unbalanced force. This property is called inertia.",
    "The human digestive system breaks down food into simpler substances. "
    "Digestion begins in the mouth where saliva acts on starch.",
]

# (question, index of the passage that should rank first, language label)
QUERIES = [
    ("Photosynthesis-na enna?", 0, "tanglish"),
    ("Plants epdi food make pannuthu?", 0, "tanglish"),
    ("Chlorophyll oda velai enna?", 0, "tanglish"),
    ("Soil dhaan plant oda food-a?", 1, "tanglish"),
    ("Oxygen epdi veliya varuthu?", 2, "tanglish"),
    ("ஒளிச்சேர்க்கை என்றால் என்ன?", 0, "tamil"),
    ("தாவரங்கள் எப்படி உணவு தயாரிக்கின்றன?", 0, "tamil"),
    ("प्रकाश संश्लेषण क्या है?", 0, "hindi"),
    ("What is photosynthesis?", 0, "english"),
    ("Why do plants need sunlight?", 0, "english"),
    ("What is inertia?", 3, "english"),
    ("Inertia-na enna?", 3, "tanglish"),
]


def embed(model: str, texts: list[str], input_type: str) -> np.ndarray | None:
    try:
        resp = httpx.post(
            f"{settings.nvidia_base_url}/embeddings",
            headers={"Authorization": f"Bearer {settings.nvidia_api_key}"},
            json={
                "input": texts, "model": model, "input_type": input_type,
                "encoding_format": "float", "truncate": "END",
            },
            timeout=90.0,
        )
        if resp.status_code >= 400:
            print(f"    ✗ {resp.status_code}: {resp.text[:160]}")
            return None
        data = sorted(resp.json()["data"], key=lambda d: d["index"])
        arr = np.array([d["embedding"] for d in data], dtype=np.float32)
        return arr / np.maximum(np.linalg.norm(arr, axis=1, keepdims=True), 1e-10)
    except Exception as exc:  # noqa: BLE001
        print(f"    ✗ {str(exc)[:160]}")
        return None


def main() -> int:
    results = []

    for model in CANDIDATES:
        print(f"\n── {model}")
        started = time.perf_counter()

        P = embed(model, PASSAGES, "passage")
        if P is None:
            continue
        Q = embed(model, [q for q, _, _ in QUERIES], "query")
        if Q is None:
            continue

        elapsed = time.perf_counter() - started
        scores = Q @ P.T  # cosine, both normalised

        hits, by_lang, correct_scores, wrong_scores = 0, {}, [], []

        for i, (question, want, lang) in enumerate(QUERIES):
            ranked = np.argsort(-scores[i])
            got = int(ranked[0])
            ok = got == want
            hits += ok

            bucket = by_lang.setdefault(lang, [0, 0])
            bucket[1] += 1
            bucket[0] += ok

            correct_scores.append(float(scores[i][want]))
            wrong_scores.append(float(max(
                scores[i][j] for j in range(len(PASSAGES)) if j != want
            )))

            mark = "✓" if ok else "✗"
            print(f"    {mark} [{lang:<8}] {question[:34]:<34} "
                  f"top={got} want={want}  {scores[i][want]:.3f}")

        acc = hits / len(QUERIES)
        mean_correct = float(np.mean(correct_scores))
        mean_wrong = float(np.mean(wrong_scores))
        margin = mean_correct - mean_wrong

        print(f"    dim={P.shape[1]}  accuracy={hits}/{len(QUERIES)} ({acc:.0%})  "
              f"correct~{mean_correct:.3f} wrong~{mean_wrong:.3f} margin={margin:+.3f}  "
              f"{elapsed:.1f}s")
        print("    by language: " + "  ".join(
            f"{k} {v[0]}/{v[1]}" for k, v in by_lang.items()))

        results.append({
            "model": model, "dim": int(P.shape[1]), "accuracy": acc,
            "mean_correct": mean_correct, "mean_wrong": mean_wrong,
            "margin": margin, "seconds": elapsed, "by_lang": by_lang,
        })

    if not results:
        print("\n✗ No embedding model worked.")
        return 1

    results.sort(key=lambda r: (-r["accuracy"], -r["margin"]))

    print("\n" + "=" * 72)
    print("RANKING (accuracy, then separation margin)")
    for i, r in enumerate(results, 1):
        print(f"  {i}. {r['model']:<42} {r['accuracy']:.0%}  "
              f"margin {r['margin']:+.3f}  dim {r['dim']}")

    best = results[0]
    # Put the threshold between the correct and the best wrong score, biased
    # toward the wrong side so genuine questions are not refused on stage.
    suggested = round(best["mean_wrong"] + (best["mean_correct"] - best["mean_wrong"]) * 0.35, 2)

    print(f"\nSet in .env:")
    print(f"  NVIDIA_EMBED_MODEL={best['model']}")
    print(f"  NVIDIA_EMBED_DIM={best['dim']}")
    print(f"  GROUNDING_THRESHOLD={suggested}")
    print(f"\n  (correct answers score ~{best['mean_correct']:.3f}, "
          f"best wrong ~{best['mean_wrong']:.3f})")

    if best["accuracy"] < 1.0:
        print("\n⚠ Not every cross-lingual query resolved. Review the ✗ rows above.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

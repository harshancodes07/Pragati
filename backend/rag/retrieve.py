"""Retrieval + the grounding decision.

Grounding is 25% of the score, and the decision to refuse is made HERE, on
retrieval scores — not by asking the LLM to police itself. Two reasons: a
prompt-only guardrail can be talked out of refusing, and a retrieval-side one
refuses instantly without spending a NIM call, which is visible and convincing
on stage.

This is a guardrail, not a proof system. It bounds what the model is allowed to
see; it does not guarantee the model reasons correctly about it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.config import settings
from backend.rag.embeddings import embed_query
from backend.rag.store import get_store


@dataclass
class RetrievalResult:
    grounded: bool
    chunks: list[dict[str, Any]]
    max_score: float
    mean_score: float
    threshold: float
    reason: str

    def to_sources(self, limit: int = 3) -> list[dict[str, Any]]:
        """Citation payload for the grounding card in the UI."""
        return [
            {
                "page": c.get("page_number"),
                "chunk_id": c.get("chunk_id"),
                "text": c.get("text", "")[:500],
                "score": round(c.get("score", 0.0), 3),
            }
            for c in self.chunks[:limit]
        ]


def retrieve(
    question: str,
    *,
    document_id: str | None = None,
    top_k: int | None = None,
    threshold: float | None = None,
) -> RetrievalResult:
    k = top_k or settings.retrieval_top_k
    cutoff = settings.grounding_threshold if threshold is None else threshold

    store = get_store()
    if len(store) == 0:
        return RetrievalResult(False, [], 0.0, 0.0, cutoff, "no_documents_indexed")

    hits = store.search(embed_query(question), top_k=k, document_id=document_id)
    if not hits:
        return RetrievalResult(False, [], 0.0, 0.0, cutoff, "no_matches")

    scores = [h["score"] for h in hits]
    max_score = max(scores)
    mean_score = sum(scores) / len(scores)

    if max_score < cutoff:
        return RetrievalResult(
            False, hits, max_score, mean_score, cutoff, "below_grounding_threshold"
        )

    # Drop weak tail matches: padding the prompt with near-irrelevant chunks
    # dilutes the context and invites the model to wander off-source.
    keep = [h for h in hits if h["score"] >= cutoff * 0.8] or hits[:1]

    return RetrievalResult(True, keep, max_score, mean_score, cutoff, "grounded")


OUT_OF_SCOPE_MESSAGE = {
    "tanglish": (
        "Neenga upload panna textbook-la indha information illa. "
        "Adhanaala enaala idhukku answer solla mudiyaadhu. "
        "Textbook-la irukkura topic pathi kelunga!"
    ),
    "tamil": (
        "நீங்கள் பதிவேற்றிய பாடப்புத்தகத்தில் இந்தத் தகவல் இல்லை. "
        "அதனால் இதற்கு என்னால் பதில் சொல்ல முடியாது. "
        "புத்தகத்தில் உள்ள தலைப்பு பற்றி கேளுங்கள்!"
    ),
    "english": (
        "I couldn't find that information in the textbook you uploaded, "
        "so I can't answer it. Try asking about a topic from your book!"
    ),
    "hindi": (
        "आपने जो किताब अपलोड की है, उसमें यह जानकारी नहीं है। "
        "इसलिए मैं इसका उत्तर नहीं दे सकता। किताब के किसी विषय के बारे में पूछें!"
    ),
    "telugu": (
        "మీరు అప్‌లోడ్ చేసిన పాఠ్యపుస్తకంలో ఈ సమాచారం లేదు. "
        "అందుకే దీనికి నేను సమాధానం చెప్పలేను. పుస్తకంలోని అంశం గురించి అడగండి!"
    ),
    "malayalam": (
        "നിങ്ങൾ അപ്‌ലോഡ് ചെയ്ത പാഠപുസ്തകത്തിൽ ഈ വിവരം ഇല്ല. "
        "അതുകൊണ്ട് എനിക്ക് ഇതിന് ഉത്തരം നൽകാൻ കഴിയില്ല. പുസ്തകത്തിലെ വിഷയത്തെക്കുറിച്ച് ചോദിക്കൂ!"
    ),
}


def out_of_scope_message(language: str) -> str:
    return OUT_OF_SCOPE_MESSAGE.get(language.lower().strip(), OUT_OF_SCOPE_MESSAGE["tanglish"])

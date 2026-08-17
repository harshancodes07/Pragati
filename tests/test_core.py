"""Smoke tests for the pieces that break silently.

Deliberately covers the logic where a bug produces plausible-looking but wrong
output rather than a crash: JSON parsing, chunk provenance, option mapping, the
grounding threshold, and the adaptive rules. None of these need a NIM key.
"""

from pathlib import Path

import numpy as np
import pytest

from backend import adaptive
from backend.ingest.chunk import chunk_pages
from backend.ingest.clean import clean_text, is_meaningful, strip_repeated_headers
from backend.llm.json_utils import extract_json
from backend.llm.service import _normalise_practice, _normalise_teach_back, _resolve_option
from backend.rag.store import NumpyVectorStore


# ------------------------------------------------------------------ json

@pytest.mark.parametrize(
    "raw,expected",
    [
        ('{"a": 1}', {"a": 1}),
        ('```json\n{"a": 1}\n```', {"a": 1}),
        ('Here you go:\n{"a": 1}\nHope that helps!', {"a": 1}),
        ('{"a": 1,}', {"a": 1}),
        ('{"t": "a { brace } inside", "a": 1}', {"t": "a { brace } inside", "a": 1}),
        ("not json at all", None),
        ("", None),
    ],
)
def test_extract_json(raw, expected):
    assert extract_json(raw) == expected


# ----------------------------------------------------------------- clean

def test_clean_rejoins_hyphenated_linebreaks():
    assert "Photosynthesis" in clean_text("Photosyn-\nthesis is a process")


def test_clean_drops_stranded_page_numbers():
    assert "12" not in clean_text("Some body text here.\n  12  \nMore text.")


def test_strip_headers_keeps_body_text():
    """Regression: overlapping head/tail slices once double-counted body lines."""
    pages = [f"BIOLOGY CH.1\nUnique body text for page {i}." for i in range(1, 5)]
    out = strip_repeated_headers(pages)
    assert all("BIOLOGY" not in p for p in out)
    assert all("Unique body text" in p for p in out)


def test_strip_headers_noop_on_short_docs():
    pages = ["A\nB", "A\nC"]
    assert strip_repeated_headers(pages) == pages


def test_is_meaningful():
    assert not is_meaningful("too short")
    assert is_meaningful(" ".join(["word"] * 20))


# ----------------------------------------------------------------- chunk

def test_chunks_preserve_page_numbers():
    chunks = chunk_pages(["Page one content here.", "Page two content here."], "doc1")
    assert {c["page_number"] for c in chunks} == {1, 2}


def test_chunks_never_span_pages():
    chunks = chunk_pages(["alpha " * 200, "beta " * 200], "doc1")
    for c in chunks:
        assert ("alpha" in c["text"]) != ("beta" in c["text"])


def test_chunk_budget_respected_without_punctuation():
    """Regression: OCR output with no sentence boundaries once ignored the budget."""
    chunks = chunk_pages([" ".join(f"w{i}" for i in range(2000))], "doc1", chunk_size=500)
    assert chunks and max(c["tokens"] for c in chunks) <= 550


def test_chunk_ids_unique():
    chunks = chunk_pages(["text " * 400] * 3, "doc1")
    assert len({c["chunk_id"] for c in chunks}) == len(chunks)


# ------------------------------------------------------------------- pdf

DEMO_PDF = Path(__file__).resolve().parent.parent / "demo" / "photosynthesis.pdf"

pdf_only = pytest.mark.skipif(
    not DEMO_PDF.exists(), reason="run scripts/make_demo_assets.py first"
)


@pdf_only
def test_pdf_extraction_uses_text_layer_not_ocr():
    """A born-digital PDF must cost zero NIM calls — the demo's fast path."""
    from backend.ingest.extract import extract_from_pdf

    pages, meta = extract_from_pdf(DEMO_PDF.read_bytes())
    assert meta["ocr_pages"] == 0
    assert len(pages) >= 2
    assert sum(len(p.split()) for p in pages) > 300


@pdf_only
def test_pdf_extraction_keeps_key_concepts():
    from backend.ingest.extract import extract_from_pdf

    text = " ".join(extract_from_pdf(DEMO_PDF.read_bytes())[0]).lower()
    for term in ("chlorophyll", "glucose", "stomata", "chloroplast"):
        assert term in text, f"lost '{term}' during extraction"


@pdf_only
def test_pdf_page_footers_are_stripped():
    """Stranded page numbers must not survive into chunks as noise."""
    from backend.ingest.extract import extract_from_pdf

    pages, _ = extract_from_pdf(DEMO_PDF.read_bytes())
    for page in pages:
        assert not any(line.strip().isdigit() for line in page.split("\n"))


@pdf_only
def test_pdf_chunks_carry_citable_pages():
    from backend.ingest.chunk import chunk_pages
    from backend.ingest.extract import extract_from_pdf

    pages, _ = extract_from_pdf(DEMO_PDF.read_bytes())
    chunks = chunk_pages(pages, "demo")
    assert chunks
    assert all(c["page_number"] >= 1 for c in chunks)
    assert all(c["text"].strip() for c in chunks)


# ----------------------------------------------------------------- store

def _store_with(n=5, dim=8):
    store = NumpyVectorStore()
    rng = np.random.default_rng(0)
    vectors = rng.random((n, dim)).tolist()
    chunks = [
        {"chunk_id": f"c{i}", "document_id": "A" if i < 3 else "B",
         "page_number": i + 1, "text": f"t{i}"}
        for i in range(n)
    ]
    store.add(chunks, vectors)
    return store, vectors


def test_search_ranks_self_first():
    store, vectors = _store_with()
    hits = store.search(vectors[2], top_k=3)
    assert hits[0]["chunk_id"] == "c2"
    assert hits[0]["score"] == pytest.approx(1.0, abs=1e-5)


def test_search_scores_descend():
    store, vectors = _store_with()
    scores = [h["score"] for h in store.search(vectors[0], top_k=5)]
    assert scores == sorted(scores, reverse=True)


def test_search_filters_by_document():
    store, vectors = _store_with()
    hits = store.search(vectors[0], top_k=5, document_id="B")
    assert {h["document_id"] for h in hits} == {"B"}


def test_search_rejects_dimension_mismatch():
    """A changed embedding model must fail loudly, not return garbage rankings."""
    store, _ = _store_with()
    with pytest.raises(ValueError, match="re-index"):
        store.search([0.1] * 99, top_k=1)


def test_add_rejects_count_mismatch():
    store = NumpyVectorStore()
    with pytest.raises(ValueError):
        store.add([{"chunk_id": "a", "document_id": "d"}], [[0.1], [0.2]])


# --------------------------------------------------------------- teach-back

def test_invalid_understanding_falls_back():
    assert _normalise_teach_back({"understanding": "banana"})["understanding"] == "partial"


def test_named_misconception_overrides_correct_label():
    """A model contradicting itself must not be reported as 'correct'."""
    out = _normalise_teach_back({
        "understanding": "correct",
        "misconceptions": [{"student_claim": "soil is food", "problem": "p", "correct_concept": "c"}],
    })
    assert out["understanding"] == "misconception"


def test_string_misconceptions_are_coerced():
    out = _normalise_teach_back({"understanding": "incorrect", "misconceptions": ["soil is food"]})
    assert out["misconceptions"][0]["student_claim"] == "soil is food"


def test_next_action_inferred_when_missing():
    assert _normalise_teach_back({"understanding": "correct"})["next_action"] == "advance"


# ----------------------------------------------------------------- practice

@pytest.mark.parametrize(
    "answer,expected",
    [
        ("B", "Soil"), ("b)", "Soil"), ("Option b", "Soil"), ("option B", "Soil"),
        ("C.", "Water"), ("Soil", "Soil"), ("soil", "Soil"), ("B) Soil", "Soil"),
        ("zzz", None), ("", None), ("Both A and B", None),
    ],
)
def test_resolve_option(answer, expected):
    assert _resolve_option(answer, ["Sunlight", "Soil", "Water", "Air"]) == expected


def test_unmappable_mcq_is_dropped():
    """Better to lose a question than to mark a correct student wrong."""
    out = _normalise_practice(
        [{"type": "mcq", "question": "Q", "options": ["x", "y"], "correct_answer": "zzz"}],
        "medium",
    )
    assert out == []


def test_missing_type_inferred_from_options():
    out = _normalise_practice([{"question": "Q", "correct_answer": "because"}], "medium")
    assert out[0]["type"] == "short_answer"


# ----------------------------------------------------------------- adaptive

@pytest.mark.parametrize(
    "current,understanding,expected",
    [
        ("medium", "correct", "hard"),
        ("medium", "partial", "medium"),
        ("medium", "misconception", "easy"),
        ("hard", "correct", "hard"),      # clamps at the top
        ("easy", "incorrect", "easy"),    # clamps at the bottom
    ],
)
def test_teach_back_difficulty(current, understanding, expected):
    assert adaptive.next_difficulty_from_teach_back(current, understanding)[0] == expected


@pytest.mark.parametrize(
    "correct,total,expected",
    [(5, 5, "hard"), (3, 5, "medium"), (1, 5, "easy"), (0, 0, "medium")],
)
def test_score_difficulty(correct, total, expected):
    assert adaptive.next_difficulty_from_score("medium", correct, total)[0] == expected


def test_short_answers_are_not_auto_graded():
    """Keyword-grading Tanglish would punish exactly the students we serve."""
    questions = [
        {"id": "q0", "type": "mcq", "correct_answer": "Soil", "explanation": ""},
        {"id": "q1", "type": "short_answer", "correct_answer": "model", "explanation": ""},
    ]
    graded = adaptive.grade_answers(questions, {"q0": "Soil", "q1": "anything"})
    assert graded["total"] == 1 and graded["correct"] == 1
    assert graded["results"][1]["correct"] is None


def test_mcq_grading_is_case_insensitive():
    questions = [{"id": "q0", "type": "mcq", "correct_answer": "Soil", "explanation": ""}]
    assert adaptive.grade_answers(questions, {"q0": "  soil "})["correct"] == 1

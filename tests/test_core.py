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
from backend.ingest.clean import (
    clean_text,
    flatten_latex_tables,
    is_meaningful,
    strip_repeated_headers,
)
from backend.llm.json_utils import extract_json
from backend.llm.provider import _is_parse_model
from backend.llm.service import (
    _clamp_score,
    _normalise_practice,
    _normalise_teach_back,
    _resolve_option,
    _trim_doubt_history,
)
from backend.rag.store import NumpyVectorStore
from backend.speech.langs import bcp47, needs_transliteration, stt_mode
from backend.speech.text import TTS_CHAR_LIMIT, split_for_tts, strip_markup


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


# ------------------------------------------------------------------ voice


@pytest.mark.parametrize(
    "language,expected",
    [
        ("tanglish", "ta-IN"),   # rides the Tamil voice
        ("tamil", "ta-IN"),
        ("english", "en-IN"),
        ("hindi", "hi-IN"),
        ("telugu", "te-IN"),
        ("malayalam", "ml-IN"),
        ("klingon", "en-IN"),    # unknown ids must not crash a playback
        ("", "en-IN"),
    ],
)
def test_language_codes(language, expected):
    assert bcp47(language) == expected


def test_tanglish_is_the_only_special_case():
    """Speech treats Tanglish differently on both sides; nothing else is."""
    assert stt_mode("tanglish") == "translit"
    assert needs_transliteration("tanglish") is True
    for other in ("tamil", "english", "hindi", "telugu", "malayalam"):
        assert stt_mode(other) == "transcribe"
        assert needs_transliteration(other) is False


def test_short_answer_is_one_clip():
    assert split_for_tts("Photosynthesis-na enna? Solren.") == [
        "Photosynthesis-na enna? Solren."
    ]


def test_empty_text_synthesises_nothing():
    assert split_for_tts("") == []
    assert split_for_tts("   \n  ") == []


def test_long_answer_splits_on_sentence_boundaries():
    """Every chunk must fit the vendor cap, and cuts must land between sentences."""
    text = "Idhu oru romba periya sentence. " * 80
    chunks = split_for_tts(text)

    assert len(chunks) > 1
    assert all(len(c) <= TTS_CHAR_LIMIT for c in chunks)
    # A boundary split never orphans a fragment mid-sentence.
    assert all(c.endswith(".") for c in chunks)


def test_one_oversized_sentence_falls_back_to_a_hard_split():
    """No sentence boundary to use — split anyway, but never mid-word."""
    chunks = split_for_tts("word " * 600)

    assert len(chunks) > 1
    assert all(len(c) <= TTS_CHAR_LIMIT for c in chunks)
    assert all(w == "word" for c in chunks for w in c.split())


def test_markdown_is_not_read_aloud():
    """'asterisk asterisk' spoken to a student is worse than useless."""
    spoken = strip_markup("## Heading\n**bold** and `code` here\n- a bullet")

    for junk in ("#", "*", "`", "-"):
        assert junk not in spoken
    assert "bold" in spoken and "code" in spoken and "a bullet" in spoken


# ------------------------------------------------------------ vision resize


def _png(width, height):
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(buf, "PNG")
    return buf.getvalue()


def test_oversized_page_is_downscaled_for_the_vision_model():
    """A phone photo is ~4000px; the hosted VLM 500s on those."""
    import io

    from PIL import Image

    from backend.ingest.extract import _MAX_VISION_DIM, downscale_for_vision

    out, mime = downscale_for_vision(_png(1977, 2560), "image/png")

    assert mime == "image/jpeg"
    assert max(Image.open(io.BytesIO(out)).size) <= _MAX_VISION_DIM


def test_downscale_preserves_aspect_ratio():
    import io

    from PIL import Image

    from backend.ingest.extract import downscale_for_vision

    out, _ = downscale_for_vision(_png(2000, 1000), "image/png")
    w, h = Image.open(io.BytesIO(out)).size
    assert w == 2 * h


def test_undecodable_bytes_pass_through_untouched():
    """A resize failure must never be what blocks an upload."""
    from backend.ingest.extract import downscale_for_vision

    data = b"definitely not an image"
    assert downscale_for_vision(data, "image/png") == (data, "image/png")


def test_ocr_prompt_contains_no_worked_example():
    """A concrete example in the OCR prompt gets parroted back as the whole answer.

    Regression: 'e.g. [Diagram: cross-section of a leaf]' in the prompt made the
    vision model return exactly that string instead of transcribing the page,
    which then surfaced as a misleading 'try a clearer photo' error.
    """
    import inspect

    from backend.llm.provider import NIMProvider

    source = inspect.getsource(NIMProvider.ocr_image)
    assert "e.g." not in source, "worked examples in the OCR prompt get parroted"
    assert "cross-section of a leaf" not in source


# --------------------------------------------------------- vision model shape


def test_parse_model_detected_by_name():
    assert _is_parse_model("nvidia/nemotron-parse")
    assert _is_parse_model("nvidia/nemoretriever-parse")
    assert not _is_parse_model("nvidia/llama-3.1-nemotron-nano-vl-8b-v1")
    assert not _is_parse_model("nvidia/nemotron-nano-12b-v2-vl")


def test_latex_table_becomes_plain_lines():
    """nemotron-parse renders tables as LaTeX; that's noise for RAG chunks and
    gibberish for TTS if it survives into the indexed text."""
    raw = (
        "Some heading text.\n\n"
        "\\begin{tabular}{cc}\n"
        "Question 0: What is X? & Answer 0 \\\\\n"
        "Question 1: What is Y? & Answer 1 \\\\\n"
        "\\end{tabular}\n\n"
        "Trailing text."
    )
    out = flatten_latex_tables(raw)

    assert "\\begin{tabular}" not in out
    assert "\\end{tabular}" not in out
    assert "&" not in out
    assert "Question 0: What is X? Answer 0" in out
    assert "Question 1: What is Y? Answer 1" in out
    assert "Some heading text." in out and "Trailing text." in out


def test_text_without_a_table_is_untouched():
    plain = "Photosynthesis is a process. It happens in leaves."
    assert flatten_latex_tables(plain) == plain


# ------------------------------------------------------- teach-back scoring


@pytest.mark.parametrize(
    "raw,expected",
    [
        (82, 82),
        ("82", 82),
        ("82/100", 82),      # models love writing the denominator
        ("85%", 85),
        (0.85, 85),          # a 0-1 float meant a percentage
        (140, 100),          # clamped, not trusted
        (-5, 0),
        (None, 50),          # falls back
        ("banana", 50),
    ],
)
def test_clamp_score_tolerates_model_formats(raw, expected):
    assert _clamp_score(raw, 50) == expected


def test_scores_survive_a_model_that_omits_them():
    """A label-only response must still render a coherent dashboard."""
    out = _normalise_teach_back({"understanding": "correct"})
    assert set(out["scores"]) == {"overall", "concept", "clarity", "completeness", "examples"}
    assert all(0 <= v <= 100 for v in out["scores"].values())


def test_overall_is_averaged_when_only_it_is_missing():
    out = _normalise_teach_back({
        "understanding": "partial",
        "scores": {"concept": 80, "clarity": 60, "completeness": 40, "examples": 40},
    })
    assert out["scores"]["overall"] == 55


def test_named_misconception_caps_the_overall_score():
    """A 95 next to 'misconception detected' reads as a broken grader."""
    out = _normalise_teach_back({
        "understanding": "correct",
        "scores": {k: 95 for k in ("overall", "concept", "clarity", "completeness", "examples")},
        "misconceptions": [{"student_claim": "a", "problem": "b", "correct_concept": "c"}],
    })
    assert out["scores"]["overall"] <= 65
    assert out["understanding"] == "misconception"


def test_did_well_falls_back_to_correct_points():
    """The praise panel must never be empty just because of a field-name choice."""
    out = _normalise_teach_back({
        "understanding": "correct",
        "correct_points": ["you explained the energy transfer"],
    })
    assert out["did_well"] == ["you explained the energy transfer"]


def test_feedback_lists_are_capped():
    out = _normalise_teach_back({
        "understanding": "partial",
        "did_well": [f"point {i}" for i in range(9)],
        "improve": [f"fix {i}" for i in range(9)],
    })
    assert len(out["did_well"]) == 4 and len(out["improve"]) == 4


# --------------------------------------------------------------- doubt chat


def test_doubt_history_trimmed_to_recent_turns():
    """Bounds tokens sent to the model; the frontend keeps the full thread."""
    long = [{"role": "user", "content": str(i)} for i in range(14)]
    trimmed = _trim_doubt_history(long)
    assert len(trimmed) == 10
    assert trimmed[0]["content"] == "4"
    assert trimmed[-1]["content"] == "13"


def test_doubt_history_untouched_when_short():
    short = [{"role": "user", "content": "why is that?"}]
    assert _trim_doubt_history(short) == short

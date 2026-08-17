"""Clean extracted text before chunking.

OCR and PDF extraction both produce artefacts that poison embeddings: hyphenated
line breaks, running headers repeated on every page, page numbers stranded on
their own line. Removing them measurably improves retrieval.
"""

from __future__ import annotations

import re
from collections import Counter

_HYPHEN_BREAK = re.compile(r"(\w+)-\s*\n\s*(\w+)")
_MULTI_NEWLINE = re.compile(r"\n{3,}")
_MULTI_SPACE = re.compile(r"[ \t]{2,}")
_PAGE_NUM_LINE = re.compile(r"^\s*[-–—|]?\s*\d{1,4}\s*[-–—|]?\s*$")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_LATEX_TABULAR = re.compile(r"\\begin\{tabular\}\{[^}]*\}(.*?)\\end\{tabular\}", re.DOTALL)


def clean_text(text: str) -> str:
    """Normalise a single page of extracted text."""
    if not text:
        return ""

    text = _CONTROL.sub("", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Rejoin words split across a line break by hyphenation.
    text = _HYPHEN_BREAK.sub(r"\1\2", text)

    lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if _PAGE_NUM_LINE.match(stripped):
            continue
        lines.append(stripped)

    text = "\n".join(lines)
    text = _MULTI_SPACE.sub(" ", text)
    text = _MULTI_NEWLINE.sub("\n\n", text)
    return text.strip()


def flatten_latex_tables(text: str) -> str:
    """Turn a nemotron-parse LaTeX table into plain lines.

    That model renders every table it detects as raw LaTeX
    (`\\begin{tabular}{cc}` ... `\\\\` row ends ... `\\end{tabular}`), which
    would otherwise sit in RAG chunks as noise and get read aloud verbatim by
    TTS. Cells become space-joined words on one line per row; nothing fancier
    than that is worth building for a textbook-OCR pipeline.
    """
    if "\\begin{tabular}" not in text:
        return text

    def _flatten(match: re.Match) -> str:
        rows = (r.strip() for r in match.group(1).split("\\\\"))
        lines = []
        for row in rows:
            if not row:
                continue
            cells = [c.strip() for c in row.split("&")]
            lines.append(" ".join(c for c in cells if c))
        return "\n".join(lines)

    return _LATEX_TABULAR.sub(_flatten, text)


def strip_repeated_headers(pages: list[str], threshold: float = 0.6) -> list[str]:
    """Drop lines that recur across most pages — running heads and footers.

    Only applies to multi-page documents; with fewer than 3 pages a repeated
    line is far more likely to be real content than a header.
    """
    if len(pages) < 3:
        return pages

    counts: Counter[str] = Counter()
    for page in pages:
        # Headers/footers live in the first and last few lines. Dedupe per page:
        # on a short page the head and tail slices overlap, and double-counting
        # there would make ordinary body text look like boilerplate.
        lines = page.split("\n")
        candidates = {
            line.strip()
            for line in lines[:3] + lines[-3:]
            if 3 < len(line.strip()) < 90
        }
        counts.update(candidates)

    cutoff = max(2, int(len(pages) * threshold))
    boilerplate = {line for line, n in counts.items() if n >= cutoff}
    if not boilerplate:
        return pages

    return ["\n".join(l for l in page.split("\n") if l.strip() not in boilerplate).strip()
            for page in pages]


def is_meaningful(text: str, min_words: int = 12) -> bool:
    """Reject empty or near-empty extractions rather than indexing noise."""
    return len(text.split()) >= min_words

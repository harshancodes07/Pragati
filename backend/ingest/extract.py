"""Turn an upload into a list of cleaned page texts.

Three input types, one output shape. PDFs prefer their own embedded text layer
(free, exact, instant) and only fall back to vision OCR for pages that are
scanned images — that keeps NIM calls, latency and cost down on real textbooks.
"""

from __future__ import annotations

import io
from typing import Any

import fitz  # PyMuPDF

from backend import cache
from backend.ingest.clean import clean_text, is_meaningful, strip_repeated_headers
from backend.llm.provider import NIMError, get_provider

# A PDF page with almost no extractable text is a scan; send it to the VLM.
_MIN_NATIVE_WORDS = 20
_MAX_OCR_PAGES = 12  # guard against someone uploading a 400-page scan mid-demo


class ExtractionError(RuntimeError):
    pass


def extract_from_text(raw: str) -> tuple[list[str], dict[str, Any]]:
    cleaned = clean_text(raw)
    if not is_meaningful(cleaned):
        raise ExtractionError("That text is too short to teach from. Paste a full passage.")
    return [cleaned], {"source": "text", "ocr_pages": 0}


def extract_from_image(data: bytes, mime: str = "image/png") -> tuple[list[str], dict[str, Any]]:
    key = cache.content_hash(data, salt="ocr-v1")
    if (hit := cache.get("ocr", key)) is not None:
        return [hit], {"source": "image", "ocr_pages": 1, "cached": True}

    try:
        raw = get_provider().ocr_image(data, mime=mime)
    except NIMError as exc:
        raise ExtractionError("Couldn't read this page. Try a clearer photo.") from exc

    cleaned = clean_text(raw)
    if not is_meaningful(cleaned):
        raise ExtractionError("Couldn't read enough text from this page. Try a clearer photo.")

    cache.put("ocr", key, cleaned)
    return [cleaned], {"source": "image", "ocr_pages": 1, "cached": False}


def extract_from_pdf(data: bytes) -> tuple[list[str], dict[str, Any]]:
    key = cache.content_hash(data, salt="pdf-v1")
    if (hit := cache.get("pdf", key)) is not None:
        return hit["pages"], {**hit["meta"], "cached": True}

    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:  # noqa: BLE001
        raise ExtractionError("That file isn't a readable PDF.") from exc

    pages: list[str] = []
    ocr_count = 0
    provider = None

    with doc:
        for page in doc:
            native = clean_text(page.get_text("text") or "")

            if len(native.split()) >= _MIN_NATIVE_WORDS:
                pages.append(native)
                continue

            # Scanned page — rasterise and send to the vision model.
            if ocr_count >= _MAX_OCR_PAGES:
                pages.append(native)
                continue

            try:
                if provider is None:
                    provider = get_provider()
                pix = page.get_pixmap(dpi=180)
                img_bytes = pix.tobytes("png")

                page_key = cache.content_hash(img_bytes, salt="ocr-v1")
                if (page_hit := cache.get("ocr", page_key)) is not None:
                    pages.append(page_hit)
                else:
                    text = clean_text(provider.ocr_image(img_bytes, mime="image/png"))
                    cache.put("ocr", page_key, text)
                    pages.append(text)
                ocr_count += 1
            except (NIMError, Exception):  # noqa: BLE001 — a bad page shouldn't kill the upload
                pages.append(native)

    pages = strip_repeated_headers(pages)
    pages = [p for p in pages if p.strip()]

    if not pages or not is_meaningful("\n".join(pages)):
        raise ExtractionError("Couldn't find readable text in that PDF.")

    meta = {"source": "pdf", "ocr_pages": ocr_count, "page_count": len(pages)}
    cache.put("pdf", key, {"pages": pages, "meta": meta})
    return pages, {**meta, "cached": False}


def extract(
    *, data: bytes | None = None, filename: str = "", text: str | None = None
) -> tuple[list[str], dict[str, Any]]:
    """Dispatch on input type. Returns (pages, metadata)."""
    if text is not None and text.strip():
        return extract_from_text(text)

    if data is None or not data:
        raise ExtractionError("No content received. Upload a file or paste some text.")

    name = filename.lower()
    if name.endswith(".pdf") or data[:5] == b"%PDF-":
        return extract_from_pdf(data)

    if name.endswith((".png", ".jpg", ".jpeg", ".webp", ".heic", ".bmp", ".tiff")):
        mime = "image/jpeg" if name.endswith((".jpg", ".jpeg")) else "image/png"
        return extract_from_image(data, mime=mime)

    if name.endswith((".txt", ".md")):
        return extract_from_text(data.decode("utf-8", errors="replace"))

    raise ExtractionError(f"Unsupported file type: {filename or 'unknown'}. Use PDF, image, or text.")

"""Generate demo PDF and page-photo assets from demo/photosynthesis.txt.

The judge flow claims three input paths (text, PDF, photo). This builds real
assets for all three so each one can be rehearsed, and gives the PDF a genuine
text layer so extraction can be verified without spending a NIM call.

    python -m scripts.make_demo_assets
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import fitz

_HEADING = re.compile(r"^\d+\.\d+\s")

# The built-in Helvetica face has no glyphs for these; substitute ASCII so the
# rendered page doesn't show stray interpuncts.
_SUBSTITUTIONS = {"—": " - ", "–": "-", "“": '"', "”": '"', "’": "'", "‘": "'"}

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DEMO = ROOT / "demo"
SRC = DEMO / "photosynthesis.txt"

PAGE_W, PAGE_H = 595, 842  # A4 at 72dpi
MARGIN = 64
BODY_SIZE = 10.5
LEADING = 15.5


def build_pdf(text: str, out: Path) -> int:
    doc = fitz.open()
    font = "helv"

    page = doc.new_page(width=PAGE_W, height=PAGE_H)
    y = MARGIN
    page_no = 1

    for raw_line in text.split("\n"):
        line = raw_line.rstrip()

        # New page when we run out of room, leaving space for the footer.
        if y > PAGE_H - MARGIN - 24:
            page.insert_text((PAGE_W / 2 - 8, PAGE_H - 40), str(page_no),
                             fontname=font, fontsize=9, color=(0.45, 0.45, 0.45))
            page = doc.new_page(width=PAGE_W, height=PAGE_H)
            page_no += 1
            y = MARGIN

        if not line:
            y += LEADING * 0.6
            continue

        # A heading is "6.3 Raw Materials" or an ALL-CAPS title — not "1. Sunlight",
        # which is a list item and should stay body weight.
        heading = bool(_HEADING.match(line)) or line.isupper()
        size = 12.5 if heading else BODY_SIZE
        name = "hebo" if heading else font

        # Wrap by character budget — adequate for a fixed-width demo asset.
        budget = int((PAGE_W - 2 * MARGIN) / (size * 0.5))
        words, current = line.split(), ""
        for word in words:
            if len(current) + len(word) + 1 > budget:
                page.insert_text((MARGIN, y), current, fontname=name, fontsize=size)
                y += LEADING
                current = word
            else:
                current = f"{current} {word}".strip()
        if current:
            page.insert_text((MARGIN, y), current, fontname=name, fontsize=size)
            y += LEADING * (1.4 if heading else 1.0)

    page.insert_text((PAGE_W / 2 - 8, PAGE_H - 40), str(page_no),
                     fontname=font, fontsize=9, color=(0.45, 0.45, 0.45))

    doc.save(out)
    count = doc.page_count
    doc.close()
    return count


def build_page_image(pdf_path: Path, out: Path, page_index: int = 0) -> None:
    """Rasterise one page as a stand-in for a phone photo of a textbook."""
    with fitz.open(pdf_path) as doc:
        pix = doc[page_index].get_pixmap(dpi=150)
        pix.save(out)


def main() -> int:
    if not SRC.exists():
        print(f"✗ Missing {SRC}")
        return 1

    text = SRC.read_text(encoding="utf-8")
    for src_char, replacement in _SUBSTITUTIONS.items():
        text = text.replace(src_char, replacement)

    pdf_path = DEMO / "photosynthesis.pdf"
    pages = build_pdf(text, pdf_path)
    print(f"✓ {pdf_path.relative_to(ROOT)}  ({pages} pages, {pdf_path.stat().st_size // 1024} KB)")

    img_path = DEMO / "photosynthesis_page1.png"
    build_page_image(pdf_path, img_path)
    print(f"✓ {img_path.relative_to(ROOT)}  ({img_path.stat().st_size // 1024} KB)")

    # Verify the PDF carries a real text layer — if it does, ingestion needs
    # zero OCR calls, which is the fast path we want during the demo.
    from backend.ingest.extract import extract_from_pdf

    extracted, meta = extract_from_pdf(pdf_path.read_bytes())
    words = sum(len(p.split()) for p in extracted)
    print(f"\n  text layer: {len(extracted)} pages, {words} words, "
          f"{meta['ocr_pages']} OCR calls needed")

    for probe in ("chlorophyll", "glucose", "stomata", "autotroph"):
        found = [i + 1 for i, p in enumerate(extracted) if probe in p.lower()]
        print(f"  {'✓' if found else '✗'} '{probe}' on page(s) {found or '—'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

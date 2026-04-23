import io
import re
from typing import Optional
import fitz  # PyMuPDF
from PIL import Image
from app.models import RedactionRect


class PDFProcessor:
    def __init__(self, pdf_bytes: bytes):
        self._bytes = pdf_bytes

    def page_count(self) -> int:
        doc = fitz.open(stream=self._bytes, filetype="pdf")
        count = len(doc)
        doc.close()
        return count

    def render_pages(self, dpi: int = 150) -> list[Image.Image]:
        """Render each PDF page to a PIL Image."""
        doc = fitz.open(stream=self._bytes, filetype="pdf")
        images = []
        zoom = dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        try:
            for page in doc:
                pix = page.get_pixmap(matrix=mat)
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                images.append(img)
        finally:
            doc.close()
        return images

    def search_text(self, pattern: str, *, flags: int = re.IGNORECASE) -> list[dict]:
        """Search page text with a regex and return PDF-space rectangles for matches."""
        doc = fitz.open(stream=self._bytes, filetype="pdf")
        try:
            regex = re.compile(pattern, flags)
            matches = []

            for page_num, page in enumerate(doc):
                page_text = page.get_text("text") or ""
                if not page_text.strip():
                    continue

                seen_rects = set()
                for match in regex.finditer(page_text):
                    matched_text = match.group(0).strip()
                    if not matched_text:
                        continue

                    rects = [
                        RedactionRect(x0=rect.x0, y0=rect.y0, x1=rect.x1, y1=rect.y1)
                        for rect in page.search_for(matched_text)
                    ]
                    if not rects:
                        continue

                    context_start = max(0, match.start() - 40)
                    context_end = min(len(page_text), match.end() + 40)
                    context = page_text[context_start:context_end].strip()

                    for rect in rects:
                        signature = (
                            round(rect.x0, 3),
                            round(rect.y0, 3),
                            round(rect.x1, 3),
                            round(rect.y1, 3),
                        )
                        if signature in seen_rects:
                            continue
                        seen_rects.add(signature)
                        matches.append(
                            {
                                "page_num": page_num,
                                "text": matched_text,
                                "context": context,
                                "rects": [rect],
                            }
                        )

            return matches
        finally:
            doc.close()

    def apply_redactions(self, rects_by_page: dict[int, list[RedactionRect]]) -> bytes:
        """
        Apply redactions using PDF annotations.
        This preserves text selectability while blacking out sensitive areas.
        """
        doc = fitz.open(stream=self._bytes, filetype="pdf")
        try:
            for page_idx, rects in rects_by_page.items():
                if page_idx >= len(doc):
                    continue

                page = doc[page_idx]

                # Add redaction annotations for each rectangle
                for rect in rects:
                    # Create fitz.Rect from RedactionRect (PDF coordinates)
                    fitz_rect = fitz.Rect(rect.x0, rect.y0, rect.x1, rect.y1)

                    # Add redaction annotation with black fill
                    page.add_redact_annot(fitz_rect, fill=(0, 0, 0))

                # Apply the redactions to permanently remove content
                # images=2 ensures image content is also redacted
                page.apply_redactions(images=2)

            # Save to bytes buffer
            return doc.write(garbage=4, deflate=True, clean=True)
        finally:
            doc.close()

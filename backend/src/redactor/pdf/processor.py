import io
from typing import Optional
import fitz  # PyMuPDF
from PIL import Image
from redactor.models import RedactionRect


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
            buf = io.BytesIO()
            doc.write(buf, garbage=4, deflate=True, clean=True)
            return buf.getvalue()
        finally:
            doc.close()

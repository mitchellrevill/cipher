import io
from typing import Optional
import pypdfium2 as pdfium
from PIL import Image, ImageDraw
from redactor.models import RedactionRect


class PDFProcessor:
    def __init__(self, pdf_bytes: bytes):
        self._bytes = pdf_bytes

    def page_count(self) -> int:
        doc = pdfium.PdfDocument(self._bytes)
        count = len(doc)
        doc.close()
        return count

    def render_pages(self, dpi: int = 150) -> list[Image.Image]:
        """Render each PDF page to a PIL Image."""
        doc = pdfium.PdfDocument(self._bytes)
        images = []
        scale = dpi / 72
        try:
            for i in range(len(doc)):
                page = doc[i]
                bitmap = page.render(scale=scale, rotation=0)
                images.append(bitmap.to_pil())
                page.close()
        finally:
            doc.close()
        return images

    def apply_redactions(self, rects_by_page: dict[int, list[RedactionRect]]) -> bytes:
        """
        Apply forensic redactions by rendering affected pages to images with
        black boxes drawn over sensitive areas, then rebuilding the PDF.
        Pages without redactions retain their original content via import_pages.
        """
        doc = pdfium.PdfDocument(self._bytes)
        num_pages = len(doc)

        new_doc = pdfium.PdfDocument.new()

        try:
            for page_idx in range(num_pages):
                page = doc[page_idx]
                page_width = page.get_width()
                page_height = page.get_height()

                if page_idx in rects_by_page and rects_by_page[page_idx]:
                    # Render to image at 2x scale (144 DPI), draw black boxes, insert as image page
                    scale = 2.0
                    bitmap = page.render(scale=scale, rotation=0)
                    img = bitmap.to_pil().convert("RGB")
                    draw = ImageDraw.Draw(img)

                    for rect in rects_by_page[page_idx]:
                        # PDF y-axis: origin at bottom-left; PIL y-axis: origin at top-left
                        # Convert PDF points -> image pixels and flip y
                        img_height = img.size[1]
                        px0 = rect.x0 * scale
                        py0 = img_height - rect.y1 * scale  # flip: PDF y1 (higher PDF y) -> lower pixel y
                        px1 = rect.x1 * scale
                        py1 = img_height - rect.y0 * scale  # flip: PDF y0 (lower PDF y) -> higher pixel y
                        draw.rectangle([px0, py0, px1, py1], fill="black")

                    # Save image as JPEG for PdfImage.load_jpeg
                    img_buf = io.BytesIO()
                    img.save(img_buf, format="JPEG", quality=95)
                    img_buf.seek(0)

                    # Create a new page in the output doc matching original dimensions
                    new_page = new_doc.new_page(width=page_width, height=page_height)

                    # Create a PdfImage, load the JPEG, set matrix to fill page, insert
                    pdf_image = pdfium.PdfImage.new(new_doc)
                    pdf_image.load_jpeg(img_buf, inline=True)

                    # PDF origin is bottom-left; scale image to full page dimensions
                    matrix = pdfium.PdfMatrix().scale(page_width, page_height)
                    pdf_image.set_matrix(matrix)

                    new_page.insert_obj(pdf_image)
                    new_page.gen_content()
                    new_page.close()
                else:
                    # No redactions: copy page as-is from source doc
                    new_doc.import_pages(doc, [page_idx])

                page.close()
        finally:
            doc.close()

        buf = io.BytesIO()
        new_doc.save(buf)
        new_doc.close()
        return buf.getvalue()

import io
import pytest
import pypdfium2 as pdfium
from redactor.pdf.processor import PDFProcessor
from redactor.models import RedactionRect

@pytest.fixture
def sample_pdf_bytes():
    """Create a minimal valid single-page PDF in memory."""
    doc = pdfium.PdfDocument.new()
    doc.new_page(width=595, height=842)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()

def test_page_count(sample_pdf_bytes):
    processor = PDFProcessor(sample_pdf_bytes)
    assert processor.page_count() == 1

def test_render_pages_returns_pil_images(sample_pdf_bytes):
    processor = PDFProcessor(sample_pdf_bytes)
    images = processor.render_pages(dpi=72)
    assert len(images) == 1
    assert images[0].size[0] > 0

def test_apply_redactions_returns_valid_pdf(sample_pdf_bytes):
    processor = PDFProcessor(sample_pdf_bytes)
    rects_by_page = {0: [RedactionRect(x0=10, y0=10, x1=100, y1=30)]}
    result = processor.apply_redactions(rects_by_page)
    assert isinstance(result, bytes)
    assert result[:4] == b"%PDF"

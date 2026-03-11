#!/usr/bin/env python3
"""Test redaction output for a job."""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from redactor.config import get_settings
from redactor.storage.blob import get_blob_storage
from redactor.pdf.processor import PDFProcessor


async def test_redaction(job_id: str):
    """Apply redactions and save output."""
    settings = get_settings()

    blob = get_blob_storage(
        settings.azure_storage_account_url,
        settings.azure_storage_container,
        account_key=settings.azure_storage_account_key or None,
    )

    print(f"Testing redaction for job: {job_id}\n")

    # Load suggestions
    suggestions = await blob.load_suggestions(job_id)
    print(f"Loaded {len(suggestions)} suggestions\n")

    # Download original PDF
    try:
        pdf_bytes = await blob.download_original_pdf(job_id)
        print(f"Original PDF: {len(pdf_bytes)} bytes\n")
    except Exception as e:
        print(f"Error downloading PDF: {e}")
        return

    # Group by page
    approved_count = sum(1 for s in suggestions if s.approved)
    print(f"Approved suggestions: {approved_count}/{len(suggestions)}")

    # Use all suggestions for testing (approve all)
    rects_by_page = {}
    for sugg in suggestions:
        if sugg.page_num not in rects_by_page:
            rects_by_page[sugg.page_num] = []
        rects_by_page[sugg.page_num].extend(sugg.rects)

    print(f"\nRectangles by page:")
    for page_idx in sorted(rects_by_page.keys()):
        print(f"  Page {page_idx}: {len(rects_by_page[page_idx])} rectangles")

    # Apply redactions
    print("\nApplying redactions...")
    processor = PDFProcessor(pdf_bytes)
    try:
        redacted_bytes = await asyncio.to_thread(processor.apply_redactions, rects_by_page)
        print(f"Redacted PDF: {len(redacted_bytes)} bytes\n")

        # Save output
        output_file = Path("test_output") / f"redacted_{job_id}.pdf"
        output_file.parent.mkdir(exist_ok=True)
        output_file.write_bytes(redacted_bytes)
        print(f"Saved to: {output_file}")

    except Exception as ex:
        print(f"Error applying redactions: {ex}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_redaction_output.py <job_id>")
        sys.exit(1)

    job_id = sys.argv[1]
    asyncio.run(test_redaction(job_id))

#!/usr/bin/env python3
"""Debug script to examine suggestions and coordinate issues."""

import sys
import json
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from redactor.config import get_settings
from redactor.storage.blob import get_blob_storage
from redactor.models import Suggestion, RedactionRect
from redactor.pdf.processor import PDFProcessor
import pypdfium2 as pdfium


async def debug_suggestions(job_id: str):
    """Debug suggestions for a job."""
    settings = get_settings()

    # Get blob storage
    blob = get_blob_storage(
        settings.azure_storage_account_url,
        settings.azure_storage_container,
        account_key=settings.azure_storage_account_key or None,
    )

    print(f"\n{'='*80}")
    print(f"DEBUG: Job {job_id}")
    print(f"{'='*80}\n")

    # Load suggestions
    suggestions = await blob.load_suggestions(job_id)
    print(f"Total suggestions: {len(suggestions)}\n")

    if not suggestions:
        print("No suggestions found!")
        return

    # Download original PDF
    try:
        pdf_bytes = await blob.download_original_pdf(job_id)
    except Exception as e:
        print(f"Error downloading PDF: {e}")
        return

    # Get PDF page dimensions
    doc = pdfium.PdfDocument(pdf_bytes)
    print(f"PDF pages: {len(doc)}\n")

    # Group suggestions by page
    by_page = {}
    for sugg in suggestions:
        if sugg.page_num not in by_page:
            by_page[sugg.page_num] = []
        by_page[sugg.page_num].append(sugg)

    # Analyze each page
    for page_idx in sorted(by_page.keys()):
        page = doc[page_idx]
        page_width = page.get_width()
        page_height = page.get_height()

        print(f"\n{'-'*80}")
        print(f"PAGE {page_idx} (PDF coords):")
        print(f"  Dimensions: {page_width:.2f}w × {page_height:.2f}h points")
        print(f"  Dimensions: {page_width/72:.2f}w × {page_height/72:.2f}h inches")

        page_suggestions = by_page[page_idx]
        print(f"  Suggestions: {len(page_suggestions)}\n")

        for i, sugg in enumerate(page_suggestions, 1):
            print(f"  [{i}] {sugg.text!r} ({sugg.source})")
            print(f"      Category: {sugg.category}")
            print(f"      Rectangles:")
            for j, rect in enumerate(sugg.rects, 1):
                print(f"        [{j}] x0={rect.x0:.1f}, y0={rect.y0:.1f}, x1={rect.x1:.1f}, y1={rect.y1:.1f}")
                print(f"             width={rect.x1-rect.x0:.1f}, height={rect.y1-rect.y0:.1f}")

                # Verify coordinates are within page bounds
                issues = []
                if rect.x0 < 0 or rect.x1 > page_width:
                    issues.append(f"x out of bounds (page: 0-{page_width:.1f})")
                if rect.y0 < 0 or rect.y1 > page_height:
                    issues.append(f"y out of bounds (page: 0-{page_height:.1f})")
                if rect.x0 >= rect.x1:
                    issues.append("x0 >= x1")
                if rect.y0 >= rect.y1:
                    issues.append("y0 >= y1")

                if issues:
                    print(f"             ⚠️  ISSUE: {', '.join(issues)}")

    doc.close()

    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_suggestions.py <job_id>")
        sys.exit(1)

    job_id = sys.argv[1]
    asyncio.run(debug_suggestions(job_id))

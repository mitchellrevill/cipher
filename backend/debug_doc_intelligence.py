#!/usr/bin/env python3
"""Debug script to analyze Document Intelligence word coordinates."""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from redactor.config import get_settings
from redactor.storage.blob import get_blob_storage
from redactor.pipeline.doc_intelligence import DocIntelligenceClient


async def debug_doc_intelligence(job_id: str):
    """Analyze Document Intelligence output for a job."""
    settings = get_settings()

    # Get blob storage
    blob = get_blob_storage(
        settings.azure_storage_account_url,
        settings.azure_storage_container,
        account_key=settings.azure_storage_account_key or None,
    )

    print(f"\n{'='*80}")
    print(f"DOCUMENT INTELLIGENCE ANALYSIS: Job {job_id}")
    print(f"{'='*80}\n")

    # Download original PDF
    try:
        pdf_bytes = await blob.download_original_pdf(job_id)
    except Exception as e:
        print(f"Error downloading PDF: {e}")
        return

    # Run Document Intelligence analysis
    doc_client = DocIntelligenceClient(
        settings.azure_doc_intel_endpoint,
        settings.azure_doc_intel_key
    )

    print("Analyzing document with Document Intelligence...")
    analysis = await doc_client.analyse(pdf_bytes)

    if isinstance(analysis, Exception):
        print(f"Error: {analysis}")
        return

    print(f"Pages: {len(analysis.pages)}\n")

    # Analyze word coordinates per page
    for page in analysis.pages:
        page_num = page.page_number - 1  # 0-indexed
        words = page.words if hasattr(page, 'words') else []

        print(f"\n{'-'*80}")
        print(f"PAGE {page_num}:")
        print(f"  Page dimensions: {page.get_bounding_regions()[0].width if hasattr(page, 'get_bounding_regions') else 'unknown'}")

        if not words:
            print("  No words found")
            continue

        # Sample first 5 words
        print(f"  Total words: {len(words)}")
        print(f"  Sample words:")
        for i, word in enumerate(words[:5]):
            polygon = getattr(word, "polygon", None)
            if polygon:
                # Convert inches to points
                xs = [polygon[j] * 72 for j in range(0, len(polygon), 2)]
                ys = [polygon[j] * 72 for j in range(1, len(polygon), 2)]
                print(f"    [{i}] '{word.content}'")
                print(f"        Polygon (inches): {polygon[:8]}")  # First 4 points
                print(f"        Converted to PDF points: x={min(xs):.1f}-{max(xs):.1f}, y={min(ys):.1f}-{max(ys):.1f}")
            else:
                print(f"    [{i}] '{word.content}' - no polygon")

    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_doc_intelligence.py <job_id>")
        sys.exit(1)

    job_id = sys.argv[1]
    asyncio.run(debug_doc_intelligence(job_id))

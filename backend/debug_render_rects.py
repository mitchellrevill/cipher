#!/usr/bin/env python3
"""Debug script to render pages with rectangles overlaid for visual inspection."""

import sys
import asyncio
from pathlib import Path
from PIL import Image, ImageDraw

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from redactor.config import get_settings
from redactor.storage.blob import get_blob_storage
from redactor.pdf.processor import PDFProcessor


async def render_with_rects(job_id: str, output_dir: str = "debug_output"):
    """Render PDF pages with rectangle overlays showing where redactions will be applied."""
    settings = get_settings()

    # Get blob storage
    blob = get_blob_storage(
        settings.azure_storage_account_url,
        settings.azure_storage_container,
        account_key=settings.azure_storage_account_key or None,
    )

    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    print(f"\n{'='*80}")
    print(f"RENDER: Job {job_id}")
    print(f"{'='*80}\n")

    # Load suggestions
    suggestions = await blob.load_suggestions(job_id)
    print(f"Total suggestions: {len(suggestions)}\n")

    # Download original PDF
    try:
        pdf_bytes = await blob.download_original_pdf(job_id)
    except Exception as e:
        print(f"Error downloading PDF: {e}")
        return

    # Process PDF
    processor = PDFProcessor(pdf_bytes)

    # Render pages at 2x scale (matching apply_redactions)
    from pypdfium2 import PdfDocument
    doc = PdfDocument(pdf_bytes)
    scale = 2.0

    # Group suggestions by page
    rects_by_page = {}
    for sugg in suggestions:
        if sugg.page_num not in rects_by_page:
            rects_by_page[sugg.page_num] = []
        rects_by_page[sugg.page_num].extend(sugg.rects)

    # Render and overlay
    for page_idx in range(len(doc)):
        page = doc[page_idx]
        page_width = page.get_width()
        page_height = page.get_height()

        # Render at same scale as apply_redactions
        bitmap = page.render(scale=scale, rotation=0)
        img = bitmap.to_pil().convert("RGB")
        draw = ImageDraw.Draw(img, "RGBA")

        print(f"Page {page_idx}:")
        print(f"  PDF dims: {page_width:.1f} × {page_height:.1f} points")
        print(f"  Image dims: {img.width} × {img.height} pixels")
        print(f"  Scale: {scale}")

        if page_idx in rects_by_page:
            print(f"  Rectangles: {len(rects_by_page[page_idx])}")

            img_height = img.size[1]
            for rect_idx, rect in enumerate(rects_by_page[page_idx]):
                # Convert PDF coords to image coords
                # Note: This is simple rendering, not the PDF matrix transform
                # The rectangles are already in pixels in the rendered image
                px0 = rect.x0 * scale
                py0 = img_height - rect.y1 * scale
                px1 = rect.x1 * scale
                py1 = img_height - rect.y0 * scale

                print(f"    [{rect_idx}] PDF({rect.x0:.1f}, {rect.y0:.1f}, {rect.x1:.1f}, {rect.y1:.1f}) " +
                      f"-> IMG({px0:.1f}, {py0:.1f}, {px1:.1f}, {py1:.1f})")

                # Draw semi-transparent red box to show where redactions will be
                draw.rectangle([px0, py0, px1, py1], outline="red", width=2)
                # Draw filled semi-transparent box
                draw.rectangle([px0, py0, px1, py1], fill=(255, 0, 0, 50))
        else:
            print(f"  Rectangles: 0")

        # Save image
        output_file = output_path / f"page_{page_idx:03d}_with_rects.png"
        img.save(output_file)
        print(f"  > Saved to {output_file}\n")

        page.close()

    doc.close()
    print(f"All pages saved to {output_path}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_render_rects.py <job_id> [output_dir]")
        sys.exit(1)

    job_id = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "debug_output"
    asyncio.run(render_with_rects(job_id, output_dir))

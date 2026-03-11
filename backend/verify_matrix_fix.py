#!/usr/bin/env python3
"""Verify the matrix transformation fix."""

# PDF page dimensions (from the document)
page_width = 595.28
page_height = 841.89

# Render scale (2x)
render_scale = 2.0
img_width = page_width * render_scale  # 1190.56
img_height = page_height * render_scale  # 1683.78

# Example redaction rectangle in PDF points
rect_x0, rect_y0 = 203.5, 257.9  # Bottom-left in PDF coords
rect_x1, rect_y1 = 373.1, 269.5  # Top-right in PDF coords

# Convert to image pixels (as done in apply_redactions)
px0 = rect_x0 * render_scale
py0 = img_height - rect_y1 * render_scale
px1 = rect_x1 * render_scale
py1 = img_height - rect_y0 * render_scale

print("="*80)
print("MATRIX TRANSFORMATION VERIFICATION")
print("="*80)
print(f"\nOriginal PDF rectangle:")
print(f"  PDF coords: ({rect_x0}, {rect_y0}) to ({rect_x1}, {rect_y1})")
print(f"\nPage dimensions: {page_width} × {page_height} points")
print(f"Rendered image: {img_width} × {img_height} pixels (at {render_scale}x scale)")

print(f"\nRedaction in rendered image pixels:")
print(f"  Image coords: ({px0}, {py0}) to ({px1}, {py1})")

print(f"\n{'-'*80}")
print("OLD MATRIX: scale(page_width, page_height)")
print(f"{'-'*80}")
print("Maps image (1, 1) -> PDF (page_width, page_height)")
print("  Problem: Doesn't flip y-axis for coordinate system mismatch")

# Approximate the old transformation
# scale(page_width, page_height) maps (0,0) to (0,0) and (1,1) to (page_width, page_height)
old_pdf_x0 = px0 * page_width / img_width
old_pdf_y0 = py0 * page_height / img_height
old_pdf_x1 = px1 * page_width / img_width
old_pdf_y1 = py1 * page_height / img_height

print(f"\nTransformed PDF coords (OLD):")
print(f"  ({old_pdf_x0:.1f}, {old_pdf_y0:.1f}) to ({old_pdf_x1:.1f}, {old_pdf_y1:.1f})")
print(f"  ERROR: y-coordinates are inverted! [WRONG]")

print(f"\n{'-'*80}")
print("NEW MATRIX: scale(page_width, -page_height) then translate(0, page_height)")
print(f"{'-'*80}")
print("Properly flips y-axis for PDF coordinate system")

# New transformation with y-flip and translation
# scale(page_width, -page_height): (x, y) -> (x*page_width/img_width, -y*page_height/img_height)
# translate(0, page_height): (x, y) -> (x, y + page_height)
new_pdf_x0 = px0 * page_width / img_width
new_pdf_y0 = page_height - (py0 * page_height / img_height)
new_pdf_x1 = px1 * page_width / img_width
new_pdf_y1 = page_height - (py1 * page_height / img_height)

print(f"\nTransformed PDF coords (NEW):")
print(f"  ({new_pdf_x0:.1f}, {new_pdf_y0:.1f}) to ({new_pdf_x1:.1f}, {new_pdf_y1:.1f})")

# Check if matches original
# Note: y-coordinates are swapped due to image y-axis flip
x_match = abs(new_pdf_x0 - rect_x0) < 0.1 and abs(new_pdf_x1 - rect_x1) < 0.1
# After transformation, new_pdf_y0 should match rect_y1, and new_pdf_y1 should match rect_y0
y_match = abs(new_pdf_y0 - rect_y1) < 0.1 and abs(new_pdf_y1 - rect_y0) < 0.1

if x_match and y_match:
    print(f"  MATCHES ORIGINAL! [OK]")
    print(f"  (Y values are swapped due to coordinate flip, which is correct)")
else:
    print(f"  Error in transformation!")
    if not x_match:
        print(f"    X mismatch: expected {rect_x0}-{rect_x1}, got {new_pdf_x0:.1f}-{new_pdf_x1:.1f}")
    if not y_match:
        print(f"    Y mismatch: expected {rect_y1}-{rect_y0} (flipped), got {new_pdf_y0:.1f}-{new_pdf_y1:.1f}")

print(f"\n{'='*80}\n")

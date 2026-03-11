#!/usr/bin/env python3
"""Test how pypdfium2 PdfMatrix works."""

import pypdfium2 as pdfium

print("Testing PdfMatrix API:\n")

# Test 1: Empty matrix
m = pdfium.PdfMatrix()
print(f"1. Empty matrix: {m}")

# Test 2: Scale
m = pdfium.PdfMatrix().scale(100, 200)
print(f"2. scale(100, 200): {m}")

# Test 3: Translate
m = pdfium.PdfMatrix().translate(50, 75)
print(f"3. translate(50, 75): {m}")

# Test 4: Chain scale then translate
m = pdfium.PdfMatrix()
m.scale(100, 200)
m.translate(50, 75)
print(f"4. scale then translate (chainable?): {m}")

# Test 5: Create with constructor parameters
try:
    m = pdfium.PdfMatrix(100, 0, 0, 200, 0, 0)
    print(f"5. Constructor with params: {m}")
except Exception as e:
    print(f"5. Constructor failed: {e}")

# Test 6: Check method signatures
print(f"\n6. Method info:")
m = pdfium.PdfMatrix()
print(f"   scale method: {m.scale}")
print(f"   translate method: {m.translate}")

# Test 7: Try to understand the matrix representation
m = pdfium.PdfMatrix().scale(595.28, -841.89)
print(f"\n7. scale(595.28, -841.89): {m}")
print(f"   Dir: {[x for x in dir(m) if not x.startswith('_')]}")

# Test 8: Chain from constructor
print(f"\n8. PdfMatrix().scale(595.28, -841.89).translate(0, 841.89):")
m = pdfium.PdfMatrix().scale(595.28, -841.89).translate(0, 841.89)
print(f"   {m}")
print(f"   a={m.a}, d={m.d}, e={m.e}, f={m.f}")

# Test 9: Use multiply to combine
print(f"\n9. Using multiply:")
scale_matrix = pdfium.PdfMatrix().scale(595.28, -841.89)
translate_matrix = pdfium.PdfMatrix().translate(0, 841.89)
combined = scale_matrix.multiply(translate_matrix)
print(f"   {combined}")
print(f"   a={combined.a}, d={combined.d}, e={combined.e}, f={combined.f}")

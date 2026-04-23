import pytest
from unittest.mock import MagicMock
from app.pipeline.fuzzy_matcher import find_text_rects, merge_line_rects
from app.models import RedactionRect

def _make_word(content: str, x0_pts: float, y0_pts: float, x1_pts: float, y1_pts: float):
    """Helper: simulate a Document Intelligence word object with polygon in inches."""
    word = MagicMock()
    word.content = content
    word.span = MagicMock()
    word.span.offset = 0
    word.span.length = len(content)
    # polygon in inches (divide points by 72)
    word.polygon = [
        x0_pts/72, y0_pts/72,   # top-left
        x1_pts/72, y0_pts/72,   # top-right
        x1_pts/72, y1_pts/72,   # bottom-right
        x0_pts/72, y1_pts/72,   # bottom-left
    ]
    return word

def test_find_text_rects_exact_match():
    words = [_make_word("John", 10, 10, 50, 25), _make_word("Smith", 55, 10, 110, 25)]
    rects = find_text_rects("John Smith", words)
    assert len(rects) == 1
    assert rects[0].x0 == pytest.approx(10.0, abs=1)
    assert rects[0].x1 == pytest.approx(110.0, abs=1)

def test_find_text_rects_single_word():
    words = [_make_word("John", 10, 10, 50, 25)]
    rects = find_text_rects("John", words)
    assert len(rects) == 1

def test_find_text_rects_no_match_returns_empty():
    words = [_make_word("Hello", 10, 10, 50, 25)]
    rects = find_text_rects("ZZZ", words)
    assert rects == []

def test_merge_line_rects_merges_adjacent():
    rects = [
        RedactionRect(x0=10, y0=10, x1=50, y1=25),
        RedactionRect(x0=55, y0=10, x1=110, y1=25),
    ]
    merged = merge_line_rects(rects)
    assert len(merged) == 1
    assert merged[0].x0 == 10
    assert merged[0].x1 == 110

def test_merge_line_rects_keeps_separate_lines():
    rects = [
        RedactionRect(x0=10, y0=10, x1=50, y1=25),   # line 1
        RedactionRect(x0=10, y0=30, x1=50, y1=45),   # line 2
    ]
    merged = merge_line_rects(rects)
    assert len(merged) == 2

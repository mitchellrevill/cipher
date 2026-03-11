from collections import defaultdict
from rapidfuzz import fuzz
import fitz  # PyMuPDF
from redactor.models import RedactionRect

SCALING_FACTOR = 72.0  # Document Intelligence returns inches; PDF uses points (72 per inch)
FUZZY_THRESHOLD = 90   # Minimum score (0-100) to accept a match


def _normalize(text: str) -> str:
    """Normalise text for fuzzy comparison — strip punctuation and case."""
    for ch in ("'s", "\u2019s", "'", ".", ",", "(", ")", " "):
        text = text.replace(ch, "")
    return text.lower()


def _word_to_rect(word) -> RedactionRect | None:
    """Convert a Document Intelligence word polygon (inches) to a RedactionRect (PDF points).

    Uses PyMuPDF's Quad class to properly handle the 4-point polygon geometry
    before converting to axis-aligned bounding box.
    """
    poly = getattr(word, "polygon", None)
    if not poly or len(poly) < 8:
        return None

    # Convert polygon points from inches to PDF points, creating fitz.Point objects
    points = [
        fitz.Point(poly[k] * SCALING_FACTOR, poly[k+1] * SCALING_FACTOR)
        for k in range(0, len(poly), 2)
    ]

    # Use fitz.Quad to properly handle the polygon, then convert to rect
    quad_rect = fitz.Quad(points).rect

    return RedactionRect(x0=quad_rect.x0, y0=quad_rect.y0, x1=quad_rect.x1, y1=quad_rect.y1)


def merge_line_rects(rects: list[RedactionRect]) -> list[RedactionRect]:
    """Merge horizontally consecutive rects that share the same line (y0 value)."""
    if not rects:
        return []
    lines: dict[int, list[RedactionRect]] = defaultdict(list)
    for r in rects:
        lines[round(r.y0)].append(r)

    merged = []
    for _y in sorted(lines):
        sorted_rects = sorted(lines[_y], key=lambda r: r.x0)
        current = sorted_rects[0]
        for nxt in sorted_rects[1:]:
            gap = nxt.x0 - current.x1
            line_height = current.y1 - current.y0
            max_gap = line_height * 0.75  # allow small inter-word spacing
            if gap <= max_gap:
                current = RedactionRect(
                    x0=current.x0, y0=current.y0,
                    x1=nxt.x1, y1=max(current.y1, nxt.y1)
                )
            else:
                merged.append(current)
                current = nxt
        merged.append(current)
    return merged


def find_text_rects(
    text_to_find: str,
    words: list,
    threshold: int = FUZZY_THRESHOLD,
) -> list[RedactionRect]:
    """
    Fuzzy-match `text_to_find` against a list of Document Intelligence word objects.
    Returns merged RedactionRects for the best match, or [] if no match above threshold.
    """
    norm_target = _normalize(text_to_find)
    best_score = 0
    best_words: list = []

    for i in range(len(words)):
        for j in range(i, min(i + 15, len(words))):  # cap sliding window at 15 words
            candidate = words[i : j + 1]
            reconstructed = _normalize("".join(w.content for w in candidate))
            score = fuzz.ratio(reconstructed, norm_target)
            if score > best_score:
                best_score = score
                best_words = candidate
            if best_score == 100:
                break
        if best_score == 100:
            break

    if best_score < threshold or not best_words:
        return []

    individual_rects = [r for w in best_words if (r := _word_to_rect(w))]
    return merge_line_rects(individual_rects)

import { useCallback, useEffect, useRef, useState } from "react";
import Fuse from "fuse.js";
import type { PDFDocumentProxy } from "pdfjs-dist";
import type { ExtractedText, SearchResult, TextMatch } from "@/types/search";
import type { RedactionRect } from "@/api/services";

const SEARCH_DEBOUNCE_MS = 300;

type Matrix = [number, number, number, number, number, number];

interface TextStyle {
  ascent?: number;
  descent?: number;
  vertical?: boolean;
}

interface FuzzyItemCandidate {
  pageNum: number;
  text: string;
  searchKey: string;
  rects: RedactionRect[];
  candidateId: string;
}

interface TextItemGeometry {
  left: number;
  top: number;
  textWidth: number;
  fontHeight: number;
  angle: number;
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

interface ItemSegment {
  text: string;
  normalized: string;
  start: number;
  end: number;
  rect: RedactionRect;
}

const SEARCH_TOKEN_REGEX = /[\p{L}\p{N}]+(?:[’'_-][\p{L}\p{N}]+)*/gu;

function multiplyTransform(left: Matrix, right: Matrix): Matrix {
  return [
    left[0] * right[0] + left[2] * right[1],
    left[1] * right[0] + left[3] * right[1],
    left[0] * right[2] + left[2] * right[3],
    left[1] * right[2] + left[3] * right[3],
    left[0] * right[4] + left[2] * right[5] + left[4],
    left[1] * right[4] + left[3] * right[5] + left[5],
  ];
}

function getFontAscent(fontHeight: number, style: TextStyle | undefined): number {
  if (style?.ascent) {
    return fontHeight * style.ascent;
  }

  if (style?.descent) {
    return fontHeight * (1 + style.descent);
  }

  return fontHeight;
}

function normalizeSearchValue(value: string): string {
  return value.normalize("NFKC").replace(/\s+/g, " ").trim().toLowerCase();
}

function normalizeSearchToken(value: string): string {
  return value
    .normalize("NFKC")
    .toLowerCase()
    .replace(/^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu, "")
    .replace(/[“”"'`.,;:!?()[\]{}]/g, "")
    .trim();
}

function tokenizeSearchValue(value: string): string[] {
  const matches = value.match(SEARCH_TOKEN_REGEX) ?? [];
  return matches.map(normalizeSearchToken).filter((token) => token.length > 0);
}

function getRectFromGeometrySegment(
  geometry: Pick<TextItemGeometry, "left" | "top" | "textWidth" | "fontHeight" | "angle">,
  startRatio: number,
  endRatio: number
): RedactionRect {
  const clampedStartRatio = Math.max(0, Math.min(1, startRatio));
  const clampedEndRatio = Math.max(clampedStartRatio, Math.min(1, endRatio));
  const startX = geometry.left + geometry.textWidth * clampedStartRatio * Math.cos(geometry.angle);
  const startY = geometry.top + geometry.textWidth * clampedStartRatio * Math.sin(geometry.angle);
  const endX = geometry.left + geometry.textWidth * clampedEndRatio * Math.cos(geometry.angle);
  const endY = geometry.top + geometry.textWidth * clampedEndRatio * Math.sin(geometry.angle);

  const corners = [
    { x: startX, y: startY },
    { x: endX, y: endY },
    {
      x: startX - geometry.fontHeight * Math.sin(geometry.angle),
      y: startY + geometry.fontHeight * Math.cos(geometry.angle),
    },
    {
      x: endX - geometry.fontHeight * Math.sin(geometry.angle),
      y: endY + geometry.fontHeight * Math.cos(geometry.angle),
    },
  ];

  const xs = corners.map((corner) => corner.x);
  const ys = corners.map((corner) => corner.y);

  return {
    x0: Math.min(...xs),
    y0: Math.min(...ys),
    x1: Math.max(...xs),
    y1: Math.max(...ys),
  };
}

function getTextItemGeometry(
  item: Record<string, unknown> & { str: string; fontName?: string },
  viewportTransform: Matrix,
  style: TextStyle | undefined
): TextItemGeometry {
  const itemTransform = Array.isArray(item.transform)
    ? (item.transform as Matrix)
    : ([1, 0, 0, 1, 0, 0] as Matrix);
  const tx = multiplyTransform(viewportTransform, itemTransform);
  let angle = Math.atan2(tx[1], tx[0]);

  if (style?.vertical) {
    angle += Math.PI / 2;
  }

  const fontHeight = Math.hypot(tx[2], tx[3]);
  const fontAscent = getFontAscent(fontHeight, style);
  const textWidth = Math.abs(
    Number(style?.vertical ? item.height : item.width) || Math.abs(tx[0]) || Math.abs(tx[2])
  );

  let left: number;
  let top: number;

  if (angle === 0) {
    left = tx[4];
    top = tx[5] - fontAscent;
  } else {
    left = tx[4] + fontAscent * Math.sin(angle);
    top = tx[5] - fontAscent * Math.cos(angle);
  }

  return {
    left,
    top,
    textWidth,
    fontHeight,
    angle,
    ...getRectFromGeometrySegment(
      {
        left,
        top,
        textWidth,
        fontHeight,
        angle,
      },
      0,
      1
    ),
  };
}

function mergeConsecutiveRects(rects: RedactionRect[]): RedactionRect[] {
  if (rects.length <= 1) {
    return rects;
  }

  const lines = new Map<number, RedactionRect[]>();

  for (const rect of rects) {
    const key = Math.round(rect.y0);
    const line = lines.get(key) ?? [];
    line.push(rect);
    lines.set(key, line);
  }

  const merged: RedactionRect[] = [];

  for (const lineRects of Array.from(lines.values())) {
    const sortedRects = [...lineRects].sort((left, right) => left.x0 - right.x0);
    let current = { ...sortedRects[0] };

    for (let index = 1; index < sortedRects.length; index++) {
      const next = sortedRects[index];
      const currentHeight = Math.max(1, current.y1 - current.y0);
      const maxGap = currentHeight * 0.75;
      const actualGap = next.x0 - current.x1;

      if (actualGap <= maxGap) {
        current = {
          x0: Math.min(current.x0, next.x0),
          y0: Math.min(current.y0, next.y0),
          x1: Math.max(current.x1, next.x1),
          y1: Math.max(current.y1, next.y1),
        };
      } else {
        merged.push(current);
        current = { ...next };
      }
    }

    merged.push(current);
  }

  return merged.sort((left, right) => (left.y0 - right.y0) || (left.x0 - right.x0));
}

function buildItemSegments(text: string, geometry: TextItemGeometry): ItemSegment[] {
  const segments: ItemSegment[] = [];

  for (const match of text.matchAll(SEARCH_TOKEN_REGEX)) {
    const segmentText = match[0];
    const start = match.index ?? 0;
    const end = start + segmentText.length;
    const normalized = normalizeSearchToken(segmentText);

    if (!normalized) {
      continue;
    }

    const startRatio = text.length > 0 ? start / text.length : 0;
    const endRatio = text.length > 0 ? end / text.length : 1;

    segments.push({
      text: segmentText,
      normalized,
      start,
      end,
      rect: getRectFromGeometrySegment(geometry, startRatio, endRatio),
    });
  }

  return segments;
}

function findSegmentSequenceMatches(
  pageData: ExtractedText,
  query: string,
  startingMatchId: number
): TextMatch[] {
  const queryTokens = tokenizeSearchValue(query);

  if (queryTokens.length === 0) {
    return [];
  }

  const pageSegments = pageData.items.flatMap((item) => item.segments);
  const matches: TextMatch[] = [];
  let matchId = startingMatchId;

  for (let index = 0; index <= pageSegments.length - queryTokens.length; index++) {
    const candidateSegments = pageSegments.slice(index, index + queryTokens.length);
    const isMatch = candidateSegments.every(
      (segment, candidateIndex) => segment.normalized === queryTokens[candidateIndex]
    );

    if (!isMatch) {
      continue;
    }

    matches.push({
      text: candidateSegments.map((segment) => segment.text).join(" "),
      pageNum: pageData.pageNum,
      rects: mergeConsecutiveRects(candidateSegments.map((segment) => segment.rect)),
      matchId: `match-${matchId++}`,
    });
  }

  return matches;
}

function findExactMatches(
  pageData: ExtractedText,
  query: string,
  startingMatchId: number
): TextMatch[] {
  const segmentMatches = findSegmentSequenceMatches(pageData, query, startingMatchId);

  if (segmentMatches.length > 0) {
    return segmentMatches;
  }

  const pageText = pageData.text.toLowerCase();
  const queryLower = query.toLowerCase();
  const matches: TextMatch[] = [];
  let startPos = 0;
  let matchId = startingMatchId;

  while (true) {
    const pos = pageText.indexOf(queryLower, startPos);
    if (pos === -1) {
      break;
    }

    const foundRects: RedactionRect[] = [];
    let currentCharPos = 0;

    for (const item of pageData.items) {
      const itemStartPos = currentCharPos;
      const itemEndPos = currentCharPos + item.text.length;

      if (itemEndPos > pos && itemStartPos < pos + query.length) {
        const relativeStart = Math.max(0, pos - itemStartPos);
        const relativeEnd = Math.min(item.text.length, pos + query.length - itemStartPos);
        const startRatio = item.text.length > 0 ? relativeStart / item.text.length : 0;
        const endRatio = item.text.length > 0 ? relativeEnd / item.text.length : 1;

        foundRects.push(
          getRectFromGeometrySegment(
            {
              left: item.left,
              top: item.top,
              textWidth: item.textWidth,
              fontHeight: item.fontHeight,
              angle: item.angle,
            },
            startRatio,
            endRatio
          )
        );
      }

      currentCharPos = itemEndPos + 1;
    }

    if (foundRects.length > 0) {
      matches.push({
        text: pageData.text.slice(pos, pos + query.length).trim() || query,
        pageNum: pageData.pageNum,
        rects: mergeConsecutiveRects(foundRects),
        matchId: `match-${matchId++}`,
      });
    }

    startPos = pos + 1;
  }

  return matches;
}

export function useFuzzySearch(
  pdfDocument: PDFDocumentProxy | null,
  searchQuery: string
): SearchResult {
  const [matches, setMatches] = useState<TextMatch[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState<string | undefined>();

  const extractedTextRef = useRef<ExtractedText[]>([]);
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    extractedTextRef.current = [];
    setMatches([]);
    setError(undefined);
    setIsSearching(false);
  }, [pdfDocument]);

  // Extract text from all pages (runs once, cached)
  const extractAllText = useCallback(async () => {
    if (!pdfDocument) return;

    try {
      const pages = pdfDocument.numPages;
      const extracted: ExtractedText[] = [];

      for (let pageNum = 1; pageNum <= pages; pageNum++) {
        try {
          const page = await pdfDocument.getPage(pageNum);
          const textContent = await page.getTextContent();
          const viewport = page.getViewport({ scale: 1 });
          const styles = textContent.styles as Record<string, TextStyle>;

          let fullText = "";
          const items: ExtractedText["items"] = [];

          for (const item of textContent.items) {
            if ("str" in item && item.str) {
              fullText += item.str + " ";

              const textItem = item as Record<string, unknown> & { str: string; fontName?: string };
              const geometry = getTextItemGeometry(
                textItem,
                viewport.transform as Matrix,
                textItem.fontName ? styles[textItem.fontName] : undefined
              );

              items.push({
                text: item.str,
                left: geometry.left,
                top: geometry.top,
                textWidth: geometry.textWidth,
                fontHeight: geometry.fontHeight,
                angle: geometry.angle,
                x0: geometry.x0,
                y0: geometry.y0,
                x1: geometry.x1,
                y1: geometry.y1,
                segments: buildItemSegments(item.str, geometry),
                fontName: item.fontName,
              });
            }
          }

          extracted.push({
            pageNum: pageNum - 1, // 0-indexed
            text: fullText.trim(),
            items,
          });
        } catch (pageError) {
          console.warn(`Failed to extract text from page ${pageNum}:`, pageError);
          // Continue with next page
        }
      }

      extractedTextRef.current = extracted;
      setError(undefined);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setError(`Failed to extract PDF text: ${message}`);
      console.error("Text extraction error:", err);
    }
  }, [pdfDocument]);

  // Perform fuzzy search
  const performSearch = useCallback(async (query: string) => {
    if (!query.trim()) {
      setMatches([]);
      return;
    }

    setIsSearching(true);
    setError(undefined);

    try {
      // If text not extracted yet, extract it first
      if (extractedTextRef.current.length === 0 && pdfDocument) {
        await extractAllText();
      }

      const extracted = extractedTextRef.current;
      if (extracted.length === 0) {
        setMatches([]);
        setIsSearching(false);
        return;
      }

      const allMatches: TextMatch[] = [];
      let matchId = 0;

      for (const pageData of extracted) {
        const exactMatches = findExactMatches(pageData, query, matchId);
        allMatches.push(...exactMatches);
        matchId += exactMatches.length;
      }

      if (allMatches.length > 0) {
        setMatches(allMatches);
        return;
      }

      const normalizedQuery = normalizeSearchValue(query);
      const fuzzyCandidates: FuzzyItemCandidate[] = extracted.flatMap((pageData) =>
        pageData.items
          .flatMap((item, index) => {
            if (item.segments.length > 0) {
              return item.segments.map((segment, segmentIndex) => ({
                pageNum: pageData.pageNum,
                text: segment.text,
                searchKey: segment.normalized,
                rects: [segment.rect],
                candidateId: `${pageData.pageNum}-${index}-${segmentIndex}-${segment.text}`,
              }));
            }

            return [{
              pageNum: pageData.pageNum,
              text: item.text,
              searchKey: normalizeSearchValue(item.text),
              rects: [
                {
                  x0: item.x0,
                  y0: item.y0,
                  x1: item.x1,
                  y1: item.y1,
                },
              ],
              candidateId: `${pageData.pageNum}-${index}-${item.text}`,
            }];
          })
          .filter((item) => item.searchKey.length > 0)
      );

      const fuseOptions = {
        keys: ["searchKey"],
        threshold: 0.35,
        includeScore: true,
      };

      const fuzzyResults = new Fuse(fuzzyCandidates, fuseOptions).search(normalizedQuery);
      const seenCandidateIds = new Set<string>();

      for (const result of fuzzyResults) {
        if (seenCandidateIds.has(result.item.candidateId)) {
          continue;
        }

        seenCandidateIds.add(result.item.candidateId);
        allMatches.push({
          text: result.item.text,
          pageNum: result.item.pageNum,
          rects: result.item.rects,
          matchId: `match-${matchId++}`,
        });
      }

      setMatches(allMatches);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setError(`Search failed: ${message}`);
      console.error("Search error:", err);
      setMatches([]);
    } finally {
      setIsSearching(false);
    }
  }, [pdfDocument, extractAllText]);

  // Debounced search
  useEffect(() => {
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    debounceTimerRef.current = setTimeout(() => {
      void performSearch(searchQuery);
    }, SEARCH_DEBOUNCE_MS);

    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, [searchQuery, performSearch]);

  // Extract text on mount when PDF is available
  useEffect(() => {
    if (pdfDocument && extractedTextRef.current.length === 0) {
      void extractAllText();
    }
  }, [pdfDocument, extractAllText]);

  return {
    matches,
    totalMatches: matches.length,
    isSearching,
    error,
  };
}

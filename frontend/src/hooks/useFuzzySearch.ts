import { useCallback, useEffect, useRef, useState } from "react";
import Fuse from "fuse.js";
import type { PDFDocumentProxy } from "pdfjs-dist";
import type { ExtractedText, SearchResult, TextMatch } from "@/types/search";
import type { RedactionRect } from "@/api/services";

const SEARCH_DEBOUNCE_MS = 300;

export function useFuzzySearch(
  pdfDocument: PDFDocumentProxy | null,
  searchQuery: string
): SearchResult {
  const [matches, setMatches] = useState<TextMatch[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState<string | undefined>();

  const extractedTextRef = useRef<ExtractedText[]>([]);
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);

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

          let fullText = "";
          const items: ExtractedText["items"] = [];

          for (const item of textContent.items) {
            if ("str" in item && item.str) {
              fullText += item.str + " ";

              // Store individual item info for coordinate mapping
              // Type assertion needed for pdfjs TextItem coordinate properties
              const textItem = item as Record<string, unknown>;
              items.push({
                text: item.str,
                x0: (textItem.x as number) || 0,
                y0: (textItem.y as number) || 0,
                width: ((textItem.width as number) || 0),
                height: ((textItem.height as number) || 0),
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

      // Create fuse index from all text
      const fuseOptions = {
        keys: ["text"],
        threshold: 0.4, // 60% match threshold for typo tolerance
        includeScore: true,
      };

      const fuse = new Fuse(extracted, fuseOptions);
      const searchResults = fuse.search(query);

      // Convert fuse results back to match rectangles
      const allMatches: TextMatch[] = [];
      let matchId = 0;

      for (const result of searchResults) {
        const pageData = result.item;

        // Find all occurrences of the query in this page's text
        // Use case-insensitive search to find positions
        const pageText = pageData.text.toLowerCase();
        const queryLower = query.toLowerCase();
        let startPos = 0;

        while (true) {
          const pos = pageText.indexOf(queryLower, startPos);
          if (pos === -1) break;

          // Map text position to rectangle coordinates
          // This uses a simplified approach: find items that fall within the match range
          let foundRects: RedactionRect[] = [];
          let currentCharPos = 0;

          for (const item of pageData.items) {
            const itemStartPos = currentCharPos;
            const itemEndPos = currentCharPos + item.text.length;

            // Check if this item overlaps with the match
            if (itemEndPos > pos && itemStartPos < pos + query.length) {
              foundRects.push({
                x0: item.x0,
                y0: item.y0,
                x1: item.x0 + item.width,
                y1: item.y0 + item.height,
              });
            }

            currentCharPos = itemEndPos + 1; // +1 for space
          }

          if (foundRects.length > 0) {
            allMatches.push({
              text: query,
              pageNum: pageData.pageNum,
              rects: foundRects,
              matchId: `match-${matchId++}`,
            });
          }

          startPos = pos + 1;
        }
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

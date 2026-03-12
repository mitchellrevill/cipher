import type { RedactionRect } from "@/api/services";

export interface TextMatch {
  text: string;
  pageNum: number;
  rects: RedactionRect[];
  matchId: string; // Unique ID per match
}

export interface SearchResult {
  matches: TextMatch[];
  totalMatches: number;
  isSearching: boolean;
  error?: string;
}

export interface ExtractedText {
  pageNum: number;
  text: string;
  items: Array<{
    text: string;
    left: number;
    top: number;
    textWidth: number;
    fontHeight: number;
    angle: number;
    x0: number;
    y0: number;
    x1: number;
    y1: number;
    segments: Array<{
      text: string;
      normalized: string;
      start: number;
      end: number;
      rect: RedactionRect;
    }>;
    fontName?: string;
  }>;
}

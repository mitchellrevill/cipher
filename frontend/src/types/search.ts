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
    x0: number;
    y0: number;
    width: number;
    height: number;
    fontName?: string;
  }>;
}

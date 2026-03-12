import { useMemo, useState } from "react";
import type { PageViewport } from "pdfjs-dist";
import { cn } from "@/lib/utils";
import type { TextMatch } from "@/types/search";

interface SearchHighlightOverlayProps {
  matches: TextMatch[];
  onMatchClick: (match: TextMatch) => void;
  viewport: PageViewport;
  pageNumber: number;
}

export function SearchHighlightOverlay({
  matches,
  onMatchClick,
  viewport,
  pageNumber,
}: SearchHighlightOverlayProps) {
  const [hoveredMatchId, setHoveredMatchId] = useState<string | null>(null);

  // Filter matches for current page and convert to viewport coordinates
  const pageMatches = useMemo(() => {
    return matches
      .filter((match) => match.pageNum === pageNumber - 1)
      .flatMap((match) =>
        match.rects.map((rect) => ({
          matchId: match.matchId,
          text: match.text,
          rect: rect,
          viewportRect: viewport.convertToViewportRectangle([
            rect.x0,
            rect.y0,
            rect.x1,
            rect.y1,
          ]),
        }))
      );
  }, [matches, pageNumber, viewport]);

  if (pageMatches.length === 0) {
    return null;
  }

  return (
    <>
      {pageMatches.map(({ matchId, text, viewportRect }) => {
        const [x0, y0, x1, y1] = viewportRect;
        const left = Math.min(x0, x1);
        const top = Math.min(y0, y1);
        const width = Math.abs(x1 - x0);
        const height = Math.abs(y1 - y0);

        const isHovered = hoveredMatchId === matchId;

        return (
          <div
            key={matchId}
            className={cn(
              "absolute border-2 transition-all cursor-pointer rounded-sm",
              isHovered
                ? "border-amber-600 bg-amber-300/25 shadow-[0_0_0_2px_rgba(217,119,6,0.3)]"
                : "border-amber-500/70 bg-amber-300/10"
            )}
            style={{
              left: `${left}px`,
              top: `${top}px`,
              width: `${width}px`,
              height: `${height}px`,
            }}
            onMouseEnter={() => setHoveredMatchId(matchId)}
            onMouseLeave={() => setHoveredMatchId(null)}
            onClick={() => {
              const match = matches.find((m) => m.matchId === matchId);
              if (match) {
                onMatchClick(match);
              }
            }}
            title={`Click to redact: "${text}"`}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                const match = matches.find((m) => m.matchId === matchId);
                if (match) {
                  onMatchClick(match);
                }
              }
            }}
          >
            {/* Tooltip on hover */}
            {isHovered && (
              <div className="absolute -top-8 left-0 bg-slate-900 text-white text-xs rounded px-2 py-1 whitespace-nowrap pointer-events-none z-10">
                {text}
              </div>
            )}
          </div>
        );
      })}
    </>
  );
}

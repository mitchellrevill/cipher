import { useMemo, useState } from "react";
import type { PageViewport } from "pdfjs-dist";
import { cn } from "@/lib/utils";
import type { TextMatch } from "@/types/search";

interface SearchHighlightOverlayProps {
  matches: TextMatch[];
  onMatchClick: (match: TextMatch) => void;
  viewport: PageViewport;
  pageNumber: number;
  activeMatchId?: string | null;
}

export function SearchHighlightOverlay({
  matches,
  onMatchClick,
  viewport,
  pageNumber,
  activeMatchId,
}: SearchHighlightOverlayProps) {
  const [hoveredMatchId, setHoveredMatchId] = useState<string | null>(null);

  // Filter matches for current page and convert to viewport coordinates
  const pageMatches = useMemo(() => {
    return matches
      .filter((match) => match.pageNum === pageNumber - 1)
      .flatMap((match) =>
        match.rects.map((rect, rectIndex) => ({
          matchId: match.matchId,
          text: match.text,
          rectIndex,
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
      {pageMatches.map(({ matchId, text, rectIndex, viewportRect }) => {
        const [x0, y0, x1, y1] = viewportRect;
        const left = Math.min(x0, x1);
        const top = Math.min(y0, y1);
        const width = Math.abs(x1 - x0);
        const height = Math.abs(y1 - y0);

        const isHovered = hoveredMatchId === matchId;
        const isActive = activeMatchId === matchId;

        return (
          <div
            key={`${matchId}-${rectIndex}`}
            data-search-match-id={matchId}
            className={cn(
              "absolute z-10 border-2 transition-all cursor-pointer rounded-sm",
              isActive
                ? "border-blue-400 bg-blue-400/30 shadow-[0_0_0_2px_rgba(96,165,250,0.45),0_0_0_6px_rgba(96,165,250,0.14)]"
                : isHovered
                  ? "border-blue-500 bg-blue-400/24 shadow-[0_0_0_2px_rgba(59,130,246,0.28)]"
                  : "border-blue-500/80 bg-blue-400/14"
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
            {(isHovered || isActive) && (
              <div
                className={cn(
                  "absolute left-0 max-w-56 rounded px-2 py-1 text-xs whitespace-nowrap pointer-events-none z-20",
                  isActive
                    ? "-top-9 bg-blue-500 text-blue-950 font-medium shadow-lg"
                    : "-top-8 bg-slate-900 text-white"
                )}
                title={text}
              >
                {text}
              </div>
            )}
          </div>
        );
      })}
    </>
  );
}

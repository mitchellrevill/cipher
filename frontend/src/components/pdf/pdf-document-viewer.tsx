import { useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import {
  GlobalWorkerOptions,
  getDocument,
  type PDFDocumentLoadingTask,
  type PDFDocumentProxy,
  type PageViewport,
  type RenderTask,
} from "pdfjs-dist";
import { Loader2, SquareDashedMousePointer } from "lucide-react";
import { Badge } from "@/components/ui";
import { cn } from "@/lib/utils";
import type { RedactionRect, Suggestion } from "@/api/services";

GlobalWorkerOptions.workerSrc = new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url).toString();

interface PdfSource {
  url: string;
  label: string;
}

interface PageStatusBadgeProps {
  stage: string;
  stageLabel: string;
  errorMessage?: string;
}

function PageStatusBadge({ stage, stageLabel, errorMessage }: PageStatusBadgeProps) {
  const bgColor = {
    pending: "bg-slate-200 dark:bg-slate-700",
    analyzing_layout: "bg-blue-200 dark:bg-blue-900 animate-pulse",
    pii_detection: "bg-blue-200 dark:bg-blue-900 animate-pulse",
    matching: "bg-blue-200 dark:bg-blue-900 animate-pulse",
    complete: "bg-green-200 dark:bg-green-900",
    error: "bg-red-200 dark:bg-red-900",
  }[stage] || "bg-gray-200";

  const textColor = {
    pending: "text-slate-600 dark:text-slate-300",
    analyzing_layout: "text-blue-600 dark:text-blue-300",
    pii_detection: "text-blue-600 dark:text-blue-300",
    matching: "text-blue-600 dark:text-blue-300",
    complete: "text-green-600 dark:text-green-300",
    error: "text-red-600 dark:text-red-300",
  }[stage] || "text-gray-600";

  return (
    <div
      className={`absolute top-1 right-1 px-2 py-1 rounded text-xs font-medium ${bgColor} ${textColor}`}
      title={errorMessage || stageLabel}
    >
      {stage === "complete" ? "✓" : stage === "error" ? "✗" : stageLabel.split(" ")[0]}
    </div>
  );
}

interface PdfDocumentViewerProps {
  source?: PdfSource;
  suggestions: Suggestion[];
  isLoading?: boolean;
  drawMode?: boolean;
  selectedSuggestionId?: string | null;
  onSuggestionSelect?: (suggestionId: string) => void;
  onManualRedactionCreated?: (pageIndex: number, rect: RedactionRect) => void;
  pageStatus?: Record<number, { stage: string; stageLabel: string; errorMessage?: string }>;
}

interface DraftRect {
  left: number;
  top: number;
  width: number;
  height: number;
}

interface OverlayBox extends DraftRect {
  id: string;
  approved: boolean;
  source: Suggestion["source"];
}

function getDocumentPageIndex(pageNum: number, pageCount: number, prefersOneBased: boolean): number {
  if (prefersOneBased) {
    return Math.max(0, Math.min(pageCount - 1, pageNum - 1));
  }

  return Math.max(0, Math.min(pageCount - 1, pageNum));
}

function getOverlayBox(rect: RedactionRect, viewport: PageViewport): DraftRect {
  const [x0, y0, x1, y1] = viewport.convertToViewportRectangle([rect.x0, rect.y0, rect.x1, rect.y1]);

  return {
    left: Math.min(x0, x1),
    top: Math.min(y0, y1),
    width: Math.abs(x1 - x0),
    height: Math.abs(y1 - y0),
  };
}

function PdfPageCanvas({
  pdfDocument,
  pageNumber,
  renderWidth,
  suggestions,
  selectedSuggestionId,
  drawMode = false,
  onSuggestionSelect,
  onManualRedactionCreated,
  pageStatus,
}: {
  pdfDocument: PDFDocumentProxy;
  pageNumber: number;
  renderWidth: number;
  suggestions: Suggestion[];
  selectedSuggestionId?: string | null;
  drawMode?: boolean;
  onSuggestionSelect?: (suggestionId: string) => void;
  onManualRedactionCreated?: (pageIndex: number, rect: RedactionRect) => void;
  pageStatus?: Record<number, { stage: string; stageLabel: string; errorMessage?: string }>;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const overlayRef = useRef<HTMLDivElement | null>(null);
  const startPointRef = useRef<{ x: number; y: number } | null>(null);
  const [viewport, setViewport] = useState<PageViewport | null>(null);
  const [draftRect, setDraftRect] = useState<DraftRect | null>(null);
  const [isRendering, setIsRendering] = useState(true);

  useEffect(() => {
    let cancelled = false;
    let renderTask: RenderTask | null = null;

    async function renderPage() {
      setIsRendering(true);

      try {
        const page = await pdfDocument.getPage(pageNumber);
        const baseViewport = page.getViewport({ scale: 1 });
        const scale = Math.max(0.65, Math.min(2.2, renderWidth / baseViewport.width));
        const nextViewport = page.getViewport({ scale });
        const canvas = canvasRef.current;

        if (!canvas || cancelled) {
          return;
        }

        const context = canvas.getContext("2d");
        if (!context) {
          return;
        }

        const ratio = window.devicePixelRatio || 1;
        canvas.width = Math.floor(nextViewport.width * ratio);
        canvas.height = Math.floor(nextViewport.height * ratio);
        canvas.style.width = `${nextViewport.width}px`;
        canvas.style.height = `${nextViewport.height}px`;

        context.setTransform(ratio, 0, 0, ratio, 0, 0);
        context.clearRect(0, 0, nextViewport.width, nextViewport.height);

        renderTask = page.render({
          canvas,
          canvasContext: context,
          viewport: nextViewport,
        });

        await renderTask.promise;
        if (!cancelled) {
          setViewport(nextViewport);
          setIsRendering(false);
        }
      } catch {
        if (!cancelled) {
          setIsRendering(false);
        }
      }
    }

    void renderPage();

    return () => {
      cancelled = true;
      renderTask?.cancel();
    };
  }, [pageNumber, pdfDocument, renderWidth]);

  const overlayBoxes = useMemo<OverlayBox[]>(() => {
    if (!viewport) {
      return [];
    }

    return suggestions.flatMap((suggestion) =>
      suggestion.rects.map((rect) => ({
        ...getOverlayBox(rect, viewport),
        id: suggestion.id,
        approved: suggestion.approved,
        source: suggestion.source,
      }))
    );
  }, [suggestions, viewport]);

  const getPoint = (event: ReactPointerEvent<HTMLDivElement>) => {
    const bounds = overlayRef.current?.getBoundingClientRect();
    if (!bounds) {
      return null;
    }

    return {
      x: Math.max(0, Math.min(bounds.width, event.clientX - bounds.left)),
      y: Math.max(0, Math.min(bounds.height, event.clientY - bounds.top)),
    };
  };

  const handlePointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!drawMode || !viewport) {
      return;
    }

    const point = getPoint(event);
    if (!point) {
      return;
    }

    event.currentTarget.setPointerCapture(event.pointerId);
    startPointRef.current = point;
    setDraftRect({ left: point.x, top: point.y, width: 0, height: 0 });
  };

  const handlePointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!drawMode || !startPointRef.current) {
      return;
    }

    const point = getPoint(event);
    if (!point) {
      return;
    }

    const start = startPointRef.current;
    setDraftRect({
      left: Math.min(start.x, point.x),
      top: Math.min(start.y, point.y),
      width: Math.abs(point.x - start.x),
      height: Math.abs(point.y - start.y),
    });
  };

  const finishDraft = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!drawMode || !startPointRef.current || !viewport || !draftRect) {
      startPointRef.current = null;
      return;
    }

    const point = getPoint(event);
    const start = startPointRef.current;
    startPointRef.current = null;
    setDraftRect(null);

    if (!point || draftRect.width < 8 || draftRect.height < 8) {
      return;
    }

    const [startX, startY] = viewport.convertToPdfPoint(start.x, start.y);
    const [endX, endY] = viewport.convertToPdfPoint(point.x, point.y);

    onManualRedactionCreated?.(pageNumber - 1, {
      x0: Math.min(startX, endX),
      y0: Math.min(startY, endY),
      x1: Math.max(startX, endX),
      y1: Math.max(startY, endY),
    });
  };

  return (
    <div className="rounded-[1.5rem] border border-border/70 bg-white/80 p-4 shadow-sm shadow-slate-300/20 backdrop-blur dark:bg-card/90">
      <div className="mb-3 flex items-center justify-between gap-3 text-xs uppercase tracking-[0.24em] text-muted-foreground">
        <span>Page {pageNumber}</span>
        {isRendering ? (
          <span className="inline-flex items-center gap-2">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            Rendering
          </span>
        ) : null}
      </div>

      <div className="relative mx-auto w-fit overflow-hidden rounded-[1rem] border border-border/70 bg-muted/20">
        <canvas ref={canvasRef} className="block max-w-full" />
        {pageStatus?.[pageNumber - 1] && (
          <PageStatusBadge
            stage={pageStatus[pageNumber - 1].stage}
            stageLabel={pageStatus[pageNumber - 1].stageLabel}
            errorMessage={pageStatus[pageNumber - 1].errorMessage}
          />
        )}
        {viewport ? (
          <div
            ref={overlayRef}
            className={cn(
              "absolute inset-0 select-none touch-none",
              drawMode ? "cursor-crosshair" : "cursor-default"
            )}
            onPointerDown={handlePointerDown}
            onPointerMove={handlePointerMove}
            onPointerUp={finishDraft}
            onPointerLeave={finishDraft}
          >
            {overlayBoxes.map((box, index) => {
              const isSelected = selectedSuggestionId === box.id;
              return (
                <button
                  key={`${box.id}-${index}`}
                  type="button"
                  className={cn(
                    "absolute rounded-sm border transition-all",
                    box.approved
                      ? "border-emerald-500/90 bg-emerald-400/18"
                      : "border-amber-500/90 bg-amber-300/18",
                    box.source === "manual" && "border-sky-500/90 bg-sky-400/18",
                    isSelected && "ring-2 ring-offset-1 ring-slate-950/35"
                  )}
                  style={{
                    left: `${box.left}px`,
                    top: `${box.top}px`,
                    width: `${box.width}px`,
                    height: `${box.height}px`,
                  }}
                  onClick={() => onSuggestionSelect?.(box.id)}
                  title={box.id}
                />
              );
            })}

            {draftRect ? (
              <div
                className="absolute border-2 border-sky-500 bg-sky-400/15"
                style={{
                  left: `${draftRect.left}px`,
                  top: `${draftRect.top}px`,
                  width: `${draftRect.width}px`,
                  height: `${draftRect.height}px`,
                }}
              />
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}

export function PdfDocumentViewer({
  source,
  suggestions,
  isLoading = false,
  drawMode = false,
  selectedSuggestionId,
  onSuggestionSelect,
  onManualRedactionCreated,
  pageStatus,
}: PdfDocumentViewerProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [documentHandle, setDocumentHandle] = useState<PDFDocumentProxy | null>(null);
  const [pageCount, setPageCount] = useState(0);
  const [renderWidth, setRenderWidth] = useState(820);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const node = containerRef.current;
    if (!node) {
      return;
    }

    const updateWidth = () => {
      const nextWidth = Math.max(320, Math.min(960, node.clientWidth - 24));
      setRenderWidth(nextWidth);
    };

    updateWidth();
    const observer = new ResizeObserver(updateWidth);
    observer.observe(node);

    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    let cancelled = false;
    let loadingTask: PDFDocumentLoadingTask | null = null;

    async function loadDocument() {
      if (!source?.url) {
        setDocumentHandle(null);
        setPageCount(0);
        setError(null);
        return;
      }

      try {
        setError(null);
        loadingTask = getDocument(source.url);
        const pdf = await loadingTask.promise;

        if (!cancelled) {
          setDocumentHandle(pdf);
          setPageCount(pdf.numPages);
        }
      } catch {
        if (!cancelled) {
          setDocumentHandle(null);
          setPageCount(0);
          setError("Unable to load the PDF preview.");
        }
      }
    }

    void loadDocument();

    return () => {
      cancelled = true;
      loadingTask?.destroy();
    };
  }, [source?.url]);

  const prefersOneBasedPages = useMemo(() => {
    if (!pageCount || suggestions.length === 0) {
      return false;
    }

    return suggestions.every((suggestion) => suggestion.page_num >= 1) && suggestions.some((suggestion) => suggestion.page_num === pageCount);
  }, [pageCount, suggestions]);

  return (
    <div ref={containerRef} className="min-h-[38rem] rounded-[1.75rem] border border-border/70 bg-[linear-gradient(180deg,rgba(248,250,252,0.95),rgba(241,245,249,0.82))] p-4 shadow-inner shadow-slate-300/20 dark:bg-card">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-sm font-medium text-foreground">PDF review surface</div>
          <div className="text-sm text-muted-foreground">
            {source ? source.label : "Upload a PDF or load a generated redacted file to preview it here."}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {drawMode ? (
            <Badge variant="secondary" className="rounded-full px-3 py-1">
              <SquareDashedMousePointer className="mr-2 h-3.5 w-3.5" />
              Draw mode
            </Badge>
          ) : null}
          {pageCount > 0 ? <Badge variant="outline" className="rounded-full px-3 py-1">{pageCount} pages</Badge> : null}
        </div>
      </div>

      {isLoading ? (
        <div className="flex min-h-[30rem] items-center justify-center text-muted-foreground">
          <Loader2 className="mr-3 h-5 w-5 animate-spin" />
          Loading workspace...
        </div>
      ) : error ? (
        <div className="flex min-h-[30rem] items-center justify-center rounded-[1.5rem] border border-destructive/30 bg-destructive/10 px-6 text-center text-sm text-destructive">
          {error}
        </div>
      ) : !documentHandle || pageCount === 0 ? (
        <div className="flex min-h-[30rem] items-center justify-center rounded-[1.5rem] border border-dashed border-border/80 bg-background/70 px-6 text-center text-sm text-muted-foreground">
          Preview becomes available after you upload a PDF in this browser session or generate a redacted file.
        </div>
      ) : (
        <div className="space-y-5">
          {Array.from({ length: pageCount }, (_, index) => {
            const pageSuggestions = suggestions.filter(
              (suggestion) => getDocumentPageIndex(suggestion.page_num, pageCount, prefersOneBasedPages) === index
            );

            return (
              <PdfPageCanvas
                key={`${source?.url ?? "pdf"}-${index + 1}`}
                pdfDocument={documentHandle}
                pageNumber={index + 1}
                renderWidth={renderWidth}
                suggestions={pageSuggestions}
                selectedSuggestionId={selectedSuggestionId}
                drawMode={drawMode}
                onSuggestionSelect={onSuggestionSelect}
                onManualRedactionCreated={onManualRedactionCreated}
                pageStatus={pageStatus}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}
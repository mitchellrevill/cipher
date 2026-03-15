import { useEffect, useState, useCallback, useRef } from "react";
import { Suggestion } from "@/api/services";
import { getAuthorizationHeaders } from "@/auth/msal";
import { ENV } from "@/config/env";

interface StreamSuggestion {
  id: string;
  text: string;
  category: string;
  reasoning: string;
  context?: string;
  page_nums: number[];
  first_found_on: number;
  rects?: Array<{ x0: number; y0: number; x1: number; y1: number }>;
}

export function useSuggestionStreamListener(
  jobId: string | null,
  onPageStatusUpdate?: (pageNum: number, stage: string) => void,
  onSuggestionFound?: (suggestion: Suggestion) => void
) {
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const suggestionsMapRef = useRef<Record<string, Suggestion>>({});

  const deduplicateSuggestions = useCallback(
    (newSuggestion: StreamSuggestion, jobId: string): Suggestion => {
      // Check if we already have this suggestion (by text + category)
      const existingKey = Object.keys(suggestionsMapRef.current).find(
        (key) => {
          const s = suggestionsMapRef.current[key];
          return s.text === newSuggestion.text && s.category === newSuggestion.category;
        }
      );

      // Ensure suggestion ID is valid - fallback to generated ID if missing
      const suggestionId = newSuggestion.id || `${newSuggestion.text}-${newSuggestion.category}`;

      if (existingKey) {
        // Update existing suggestion with new pages
        const existing = suggestionsMapRef.current[existingKey];
        const updated: Suggestion = {
          ...existing,
          page_num: newSuggestion.first_found_on,
          page_nums: newSuggestion.page_nums,
          rects: newSuggestion.rects
            ? newSuggestion.rects.map((r) => ({
                x0: r.x0,
                y0: r.y0,
                x1: r.x1,
                y1: r.y1,
              }))
            : existing.rects,
        };
        suggestionsMapRef.current[existingKey] = updated;
        return updated;
      } else {
        // New suggestion
        const sugg: Suggestion = {
          id: suggestionId,
          job_id: jobId,
          text: newSuggestion.text,
          category: newSuggestion.category,
          reasoning: newSuggestion.reasoning,
          context: newSuggestion.context || "",
          page_num: newSuggestion.first_found_on,
          page_nums: newSuggestion.page_nums,
          approved: false,
          rects: newSuggestion.rects
            ? newSuggestion.rects.map((r) => ({
                x0: r.x0,
                y0: r.y0,
                x1: r.x1,
                y1: r.y1,
              }))
            : [],
          source: "ai",
          created_at: new Date().toISOString(),
        };
        suggestionsMapRef.current[suggestionId] = sugg;
        return sugg;
      }
    },
    []
  );

  // Note: onPageStatusUpdate and onSuggestionFound should be memoized with useCallback()
  // to prevent unnecessary EventSource reconnections. If they're recreated on each render,
  // the effect will re-run and create a new EventSource connection even if jobId hasn't changed.
  useEffect(() => {
    if (!jobId) {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }
      return;
    }

    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    const processEventChunk = (chunk: string) => {
      const lines = chunk.split(/\r?\n/);
      let eventName = "message";
      const dataLines: string[] = [];

      for (const line of lines) {
        if (line.startsWith("event:")) {
          eventName = line.slice(6).trim();
        } else if (line.startsWith("data:")) {
          dataLines.push(line.slice(5).trim());
        }
      }

      if (dataLines.length === 0) {
        return;
      }

      try {
        const payload = JSON.parse(dataLines.join("\n")) as Record<string, unknown>;
        if (eventName === "page_status") {
          onPageStatusUpdate?.(Number(payload.page_num), String(payload.status ?? ""));
          return;
        }

        if (eventName === "suggestion_found") {
          const data = payload as unknown as StreamSuggestion;
          const deduped = deduplicateSuggestions(data, jobId);
          onSuggestionFound?.(deduped);
          setSuggestions((prev) => {
            const filtered = prev.filter((s) => s.id !== data.id);
            return [...filtered, deduped];
          });
          return;
        }

        if (eventName === "analysis_complete") {
          setIsConnected(false);
          return;
        }

        if (eventName === "error") {
          setError(typeof payload.error === "string" ? payload.error : "Analysis failed");
          setIsConnected(false);
        }
      } catch (err) {
        console.error("Failed to parse stream event", err);
      }
    };

    void (async () => {
      try {
        const authHeaders = await getAuthorizationHeaders();
        const response = await fetch(`${ENV.BACKEND_URL}/api/jobs/${jobId}/stream-analysis`, {
          headers: authHeaders,
          signal: abortController.signal,
        });

        if (!response.ok) {
          const text = await response.text();
          throw new Error(text || `Streaming failed with status ${response.status}`);
        }

        if (!response.body) {
          throw new Error("Streaming response body was empty.");
        }

        setIsConnected(true);
        setError(null);

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { value, done } = await reader.read();
          buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });

          const chunks = buffer.split(/\r?\n\r?\n/);
          buffer = chunks.pop() ?? "";

          for (const chunk of chunks) {
            if (chunk.trim()) {
              processEventChunk(chunk);
            }
          }

          if (done) {
            if (buffer.trim()) {
              processEventChunk(buffer);
            }
            break;
          }
        }
      } catch (err) {
        if (abortController.signal.aborted) {
          return;
        }

        setError(err instanceof Error ? err.message : "Connection lost");
        setIsConnected(false);
      }
    })();

    return () => {
      abortController.abort();
      abortControllerRef.current = null;
    };
  }, [jobId, onPageStatusUpdate, onSuggestionFound, deduplicateSuggestions]);

  return {
    suggestions,
    isConnected,
    error,
    clearSuggestions: () => {
      setSuggestions([]);
      suggestionsMapRef.current = {};
    },
  };
}

import { useEffect, useState, useCallback, useRef } from "react";
import { Suggestion } from "@/api/services";

interface StreamSuggestion {
  id: string;
  text: string;
  category: string;
  reasoning: string;
  context: string;
  page_nums: number[];
  first_found_on: number;
}

export function useSuggestionStreamListener(
  jobId: string | null,
  onPageStatusUpdate?: (pageNum: number, stage: string) => void,
  onSuggestionFound?: (suggestion: Suggestion) => void
) {
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
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

      if (existingKey) {
        // Update existing suggestion with new pages
        const existing = suggestionsMapRef.current[existingKey];
        const updated: Suggestion = {
          ...existing,
          page_num: newSuggestion.first_found_on,
          // Note: multi-page support will be handled via page_nums array in future
        };
        suggestionsMapRef.current[existingKey] = updated;
        return updated;
      } else {
        // New suggestion
        const sugg: Suggestion = {
          id: newSuggestion.id,
          job_id: jobId,
          text: newSuggestion.text,
          category: newSuggestion.category,
          reasoning: newSuggestion.reasoning,
          context: newSuggestion.context,
          page_num: newSuggestion.first_found_on,
          approved: false,
          rects: [], // Will be filled by actual API
          source: "ai",
          created_at: new Date().toISOString(),
        };
        suggestionsMapRef.current[newSuggestion.id] = sugg;
        return sugg;
      }
    },
    []
  );

  useEffect(() => {
    if (!jobId) {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      return;
    }

    const eventSource = new EventSource(`/api/jobs/${jobId}/stream-analysis`);
    eventSourceRef.current = eventSource;

    eventSource.addEventListener("page_status", (event: Event) => {
      try {
        const data = JSON.parse((event as MessageEvent).data);
        onPageStatusUpdate?.(data.page_num, data.status);
      } catch (err) {
        console.error("Failed to parse page_status event", err);
      }
    });

    eventSource.addEventListener("suggestion_found", (event: Event) => {
      try {
        const data = JSON.parse((event as MessageEvent).data) as StreamSuggestion;
        const deduped = deduplicateSuggestions(data, jobId);
        onSuggestionFound?.(deduped);
        setSuggestions((prev) => {
          // Remove old version if exists, add new one
          const filtered = prev.filter((s) => s.id !== data.id);
          return [...filtered, deduped];
        });
      } catch (err) {
        console.error("Failed to parse suggestion_found event", err);
      }
    });

    eventSource.addEventListener("analysis_complete", () => {
      console.log("Analysis streaming complete");
    });

    eventSource.addEventListener("error", (event: Event) => {
      try {
        const data = JSON.parse((event as MessageEvent).data);
        setError(data.error || "Analysis failed");
      } catch {
        setError("Connection lost");
      }
      eventSource.close();
      eventSourceRef.current = null;
      setIsConnected(false);
    });

    eventSource.onopen = () => {
      setIsConnected(true);
      setError(null);
    };

    return () => {
      eventSource.close();
      eventSourceRef.current = null;
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

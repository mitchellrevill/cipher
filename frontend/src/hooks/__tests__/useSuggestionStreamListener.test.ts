import { renderHook } from "@testing-library/react";
import { vi } from "vitest";
import { useSuggestionStreamListener } from "../useSuggestionStreamListener";

// Mock EventSource
global.EventSource = vi.fn(() => ({
  addEventListener: vi.fn(),
  close: vi.fn(),
  onopen: null,
})) as any;

describe("useSuggestionStreamListener", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("initializes with empty suggestions and disconnected state", () => {
    const { result } = renderHook(() => useSuggestionStreamListener(null));

    expect(result.current.suggestions).toEqual([]);
    expect(result.current.isConnected).toBe(false);
    expect(result.current.error).toBe(null);
  });

  it("provides clearSuggestions function", () => {
    const { result } = renderHook(() => useSuggestionStreamListener(null));

    expect(typeof result.current.clearSuggestions).toBe("function");
  });

  it("closes EventSource when jobId is null", () => {
    const mockEventSource = {
      addEventListener: vi.fn(),
      close: vi.fn(),
      onopen: null,
    };
    (global.EventSource as any).mockReturnValue(mockEventSource);

    const { rerender } = renderHook(
      ({ jobId }) => useSuggestionStreamListener(jobId),
      { initialProps: { jobId: "job-123" } }
    );

    rerender({ jobId: null });

    expect(mockEventSource.close).toHaveBeenCalled();
  });
});

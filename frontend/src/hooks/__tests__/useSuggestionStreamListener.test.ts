import { act, renderHook } from "@testing-library/react";
import { vi } from "vitest";
import * as msalAuth from "@/auth/msal";
import { useSuggestionStreamListener } from "../useSuggestionStreamListener";

Object.defineProperty(globalThis, "fetch", {
  value: vi.fn(),
  writable: true,
});

vi.spyOn(msalAuth, "getAuthorizationHeaders").mockResolvedValue({ Authorization: "Bearer test-token" });

describe("useSuggestionStreamListener", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (global.fetch as any).mockResolvedValue({
      ok: true,
      body: {
        getReader: () => ({
          read: vi.fn().mockResolvedValue({ done: true, value: undefined }),
        }),
      },
    });
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

  it("aborts the stream when jobId becomes null", async () => {
    const abortSpy = vi.spyOn(AbortController.prototype, "abort");
    const { rerender } = renderHook(
      ({ jobId }) => useSuggestionStreamListener(jobId),
      { initialProps: { jobId: "job-123" } }
    );

    await act(async () => {
      rerender({ jobId: null });
    });

    expect(abortSpy).toHaveBeenCalled();
  });
});

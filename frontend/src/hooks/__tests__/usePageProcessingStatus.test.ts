import { renderHook, act } from "@testing-library/react";
import { usePageProcessingStatus } from "../usePageProcessingStatus";

describe("usePageProcessingStatus", () => {
  it("initializes all pages as pending", () => {
    const { result } = renderHook(() => usePageProcessingStatus(5));

    for (let i = 0; i < 5; i++) {
      expect(result.current.pageStatus[i].stage).toBe("pending");
    }
  });

  it("updates page status", () => {
    const { result } = renderHook(() => usePageProcessingStatus(3));

    act(() => {
      result.current.updatePageStatus(1, "pii_detection");
    });

    expect(result.current.pageStatus[1].stage).toBe("pii_detection");
    expect(result.current.pageStatus[0].stage).toBe("pending");
  });

  it("counts completed pages", () => {
    const { result } = renderHook(() => usePageProcessingStatus(5));

    act(() => {
      result.current.updatePageStatus(0, "complete");
      result.current.updatePageStatus(1, "complete");
      result.current.updatePageStatus(2, "pii_detection");
    });

    expect(result.current.getCompletedPageCount()).toBe(2);
  });

  it("identifies current processing page", () => {
    const { result } = renderHook(() => usePageProcessingStatus(3));

    act(() => {
      result.current.updatePageStatus(0, "complete");
      result.current.updatePageStatus(1, "pii_detection");
      result.current.updatePageStatus(2, "pending");
    });

    expect(result.current.getCurrentProcessingPage()).toBe(1);
  });
});

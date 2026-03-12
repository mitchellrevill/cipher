import { useState, useCallback } from "react";

export type PageStage =
  | "pending"
  | "analyzing_layout"
  | "pii_detection"
  | "matching"
  | "complete"
  | "error";

export interface PageStatus {
  stage: PageStage;
  error_message?: string;
}

export function usePageProcessingStatus(totalPages: number) {
  const [pageStatus, setPageStatus] = useState<Record<number, PageStatus>>(() => {
    const initial: Record<number, PageStatus> = {};
    for (let i = 0; i < totalPages; i++) {
      initial[i] = { stage: "pending" };
    }
    return initial;
  });

  const updatePageStatus = useCallback(
    (pageNum: number, stage: PageStage, errorMessage?: string) => {
      setPageStatus((prev) => ({
        ...prev,
        [pageNum]: { stage, error_message: errorMessage },
      }));
    },
    []
  );

  const getStageLabel = useCallback((stage: PageStage): string => {
    const labels: Record<PageStage, string> = {
      pending: "Waiting",
      analyzing_layout: "Analyzing layout",
      pii_detection: "Detecting PII",
      matching: "Matching coordinates",
      complete: "Done",
      error: "Error",
    };
    return labels[stage] || stage;
  }, []);

  const getCompletedPageCount = useCallback((): number => {
    return Object.values(pageStatus).filter((s) => s.stage === "complete").length;
  }, [pageStatus]);

  const getCurrentProcessingPage = useCallback((): number | null => {
    const entry = Object.entries(pageStatus).find(
      ([_, status]) =>
        status.stage !== "pending" && status.stage !== "complete" && status.stage !== "error"
    );
    return entry ? parseInt(entry[0]) : null;
  }, [pageStatus]);

  const getCurrentStage = useCallback((): PageStage | null => {
    const entry = Object.entries(pageStatus).find(
      ([_, status]) =>
        status.stage !== "pending" && status.stage !== "complete" && status.stage !== "error"
    );
    return entry ? pageStatus[entry[0]]?.stage || null : null;
  }, [pageStatus]);

  return {
    pageStatus,
    updatePageStatus,
    getStageLabel,
    getCompletedPageCount,
    getCurrentProcessingPage,
    getCurrentStage,
  };
}

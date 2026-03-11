import { useSyncExternalStore } from "react";
import { getActiveJobId, getRecentJobs, subscribeRecentJobs } from "@/lib/recent-jobs";

interface RecentJobsSnapshot {
  recentJobs: ReturnType<typeof getRecentJobs>;
  activeJobId: string | null;
}

let cachedSnapshot: RecentJobsSnapshot = {
  recentJobs: [],
  activeJobId: null,
};

let cachedSignature = "";

function getSnapshot(): RecentJobsSnapshot {
  const recentJobs = getRecentJobs();
  const activeJobId = getActiveJobId();
  const nextSignature = JSON.stringify({ activeJobId, recentJobs });

  if (nextSignature === cachedSignature) {
    return cachedSnapshot;
  }

  cachedSignature = nextSignature;
  cachedSnapshot = {
    recentJobs,
    activeJobId,
  };

  return cachedSnapshot;
}

export function useRecentJobs(): RecentJobsSnapshot {
  return useSyncExternalStore(subscribeRecentJobs, getSnapshot, getSnapshot);
}
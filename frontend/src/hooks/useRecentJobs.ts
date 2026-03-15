import { useSyncExternalStore } from "react";
import { getRecentJobs, subscribeRecentJobs } from "@/lib/recent-jobs";

interface RecentJobsSnapshot {
  recentJobs: ReturnType<typeof getRecentJobs>;
}

let cachedSnapshot: RecentJobsSnapshot = {
  recentJobs: [],
};

let cachedSignature = "";

function getSnapshot(): RecentJobsSnapshot {
  const recentJobs = getRecentJobs();
  const nextSignature = JSON.stringify({ recentJobs });

  if (nextSignature === cachedSignature) {
    return cachedSnapshot;
  }

  cachedSignature = nextSignature;
  cachedSnapshot = {
    recentJobs,
  };

  return cachedSnapshot;
}

export function useRecentJobs(): RecentJobsSnapshot {
  return useSyncExternalStore(subscribeRecentJobs, getSnapshot, getSnapshot);
}
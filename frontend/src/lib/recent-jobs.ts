import { parseJSON } from "@/lib/utils";
import type { JobStatus } from "@/api/services";

const RECENT_JOBS_STORAGE_KEY = "cipher.recentJobs";
const RECENT_JOBS_EVENT = "cipher:recent-jobs-updated";

export interface RecentJobRecord {
  jobId: string;
  filename: string;
  createdAt: string;
  status: JobStatus;
  suggestionsCount?: number;
  fileSize?: number;
  completedAt?: string;
  error?: string;
  hasRedactedPdf?: boolean;
}

interface LocalPdfRecord {
  fileName: string;
  fileSize: number;
  objectUrl: string;
}

const localPdfRegistry = new Map<string, LocalPdfRecord>();

function canUseStorage(): boolean {
  return typeof window !== "undefined";
}

function emitRecentJobsUpdated() {
  if (!canUseStorage()) {
    return;
  }

  window.dispatchEvent(new CustomEvent(RECENT_JOBS_EVENT));
}

export function getRecentJobs(): RecentJobRecord[] {
  if (!canUseStorage()) {
    return [];
  }

  const raw = window.localStorage.getItem(RECENT_JOBS_STORAGE_KEY);
  const jobs = parseJSON<RecentJobRecord[]>(raw ?? "[]", []);

  return jobs
    .filter((job) => typeof job.jobId === "string" && job.jobId.length > 0)
    .sort((left, right) => new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime());
}

export function subscribeRecentJobs(callback: () => void): () => void {
  if (!canUseStorage()) {
    return () => {};
  }

  const onStorage = (event: StorageEvent) => {
    if (event.key === RECENT_JOBS_STORAGE_KEY) {
      callback();
    }
  };

  window.addEventListener("storage", onStorage);
  window.addEventListener(RECENT_JOBS_EVENT, callback);

  return () => {
    window.removeEventListener("storage", onStorage);
    window.removeEventListener(RECENT_JOBS_EVENT, callback);
  };
}

export function upsertRecentJob(job: RecentJobRecord) {
  if (!canUseStorage()) {
    return;
  }

  const jobs = getRecentJobs();
  const existing = jobs.find((entry) => entry.jobId === job.jobId);
  const mergedJob = {
    ...existing,
    ...job,
  };

  if (existing && JSON.stringify(existing) === JSON.stringify(mergedJob)) {
    return;
  }

  const nextJobs = [
    mergedJob,
    ...jobs.filter((entry) => entry.jobId !== job.jobId),
  ].slice(0, 20);

  window.localStorage.setItem(RECENT_JOBS_STORAGE_KEY, JSON.stringify(nextJobs));
  emitRecentJobsUpdated();
}

export function registerLocalPdf(jobId: string, file: File): string {
  const existing = localPdfRegistry.get(jobId);
  if (existing) {
    URL.revokeObjectURL(existing.objectUrl);
  }

  const objectUrl = URL.createObjectURL(file);
  localPdfRegistry.set(jobId, {
    fileName: file.name,
    fileSize: file.size,
    objectUrl,
  });

  return objectUrl;
}

export function getLocalPdfUrl(jobId: string): string | null {
  return localPdfRegistry.get(jobId)?.objectUrl ?? null;
}

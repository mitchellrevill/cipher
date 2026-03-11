import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merge class names using clsx for conditional classes
 * and tailwind-merge to resolve Tailwind CSS conflicts
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/**
 * Safely parse JSON with type safety
 */
export function parseJSON<T>(json: string, fallback: T): T {
  try {
    return JSON.parse(json) as T;
  } catch {
    return fallback;
  }
}

/**
 * Format bytes to human-readable size
 */
export function formatBytes(
  bytes: number,
  options?: {
    decimals?: number;
    sizeType?: "accurate" | "normal";
  }
): string {
  const { decimals = 0, sizeType = "normal" } = options || {};

  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes =
    sizeType === "accurate"
      ? ["Bytes", "KiB", "MiB", "GiB", "TiB"]
      : ["B", "KB", "MB", "GB", "TB"];

  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return bytes === 0 ? "0 B" : `${(bytes / Math.pow(k, i)).toFixed(dm)} ${sizes[i]}`;
}

/**
 * Delay execution for specified milliseconds
 */
export function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Check if code is running in browser
 */
export const isBrowser = typeof window !== "undefined";

/**
 * Get query parameters from URL
 */
export function getQueryParams(
  url: string = isBrowser ? window.location.href : ""
): Record<string, string> {
  const searchParams = new URL(url, "http://localhost").searchParams;
  const params: Record<string, string> = {};

  searchParams.forEach((value, key) => {
    params[key] = value;
  });

  return params;
}

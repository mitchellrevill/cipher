/**
 * Common types used throughout the application
 */

export interface User {
  id: string;
  email: string;
  name: string;
  roles: string[];
}

export interface PaginationParams {
  page: number;
  limit: number;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  limit: number;
}

export interface ErrorResponse {
  error: string;
  message: string;
  statusCode: number;
}

export type ToastType = "success" | "error" | "info" | "warning";

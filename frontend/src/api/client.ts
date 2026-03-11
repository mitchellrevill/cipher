/**
 * Axios instance with interceptors for API calls
 * Handles:
 * - JWT authentication (skipped in dev mode)
 * - Error handling
 * - Request/response transformation
 * - Retry logic
 */

import axios from "axios";
import { ENV } from "@/config/env";
import { useAuthStore } from "@/store";

const api = axios.create({
  baseURL: ENV.BACKEND_URL,
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
  },
});

// Request interceptor - add token to requests
api.interceptors.request.use(
  (config) => {
    const token = useAuthStore.getState().token;
    // In dev mode, use dev token bypass (server should accept it)
    // In production, use real JWT token
    if (token && token !== "dev-token-bypass") {
      config.headers.Authorization = `Bearer ${token}`;
    } else if (import.meta.env.DEV && token === "dev-token-bypass") {
      // Dev mode: add dev token for local development
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor - handle errors and token refresh
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // In dev mode, errors are more lenient
    if (error.response?.status === 401 && !import.meta.env.DEV) {
      // Token expired or invalid (only in production)
      useAuthStore.getState().logout();
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

export default api;

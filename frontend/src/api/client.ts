/**
 * Axios instance with interceptors for API calls
 * Handles:
 * - JWT authentication (skipped in dev mode)
 * - Error handling
 * - Request/response transformation
 * - Retry logic
 */

import axios from "axios";
import { getAuthorizationHeaders, isMsalConfigured, redirectToLogin } from "@/auth/msal";
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
  async (config) => {
    const headers = await getAuthorizationHeaders();
    if (headers.Authorization) {
      config.headers.Authorization = headers.Authorization;
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
    if (error.response?.status === 401 && isMsalConfigured) {
      useAuthStore.getState().clearAuth();
      redirectToLogin(window.location.href, "session-expired");
    }
    return Promise.reject(error);
  }
);

export default api;

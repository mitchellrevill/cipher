/**
 * Environment configuration
 * Loads from import.meta.env with proper typing
 */

export const ENV = {
  DEV: import.meta.env.DEV,
  PROD: import.meta.env.PROD,
  SSR: import.meta.env.SSR,
  BACKEND_URL: import.meta.env.VITE_BACKEND_URL || "http://localhost:8000",
  USE_MOCK_DATA:
    import.meta.env.VITE_USE_MOCK_DATA === "true" ||
    (import.meta.env.DEV && import.meta.env.VITE_USE_MOCK_DATA !== "false"),
  MSAL_CLIENT_ID: import.meta.env.VITE_MSAL_CLIENT_ID || "",
  MSAL_AUTHORITY: import.meta.env.VITE_MSAL_AUTHORITY || "",
  MSAL_REDIRECT_URI: import.meta.env.VITE_MSAL_REDIRECT_URI || window.location.origin,
  MSAL_API_SCOPE: import.meta.env.VITE_MSAL_API_SCOPE || "",
} as const;

export const isDevelopment = ENV.DEV;
export const isProduction = ENV.PROD;

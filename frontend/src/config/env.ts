/**
 * Environment configuration
 * Loads from import.meta.env with proper typing
 */

const browserOrigin = typeof window === "undefined" ? "" : window.location.origin;
const msalTenantId = import.meta.env.VITE_MSAL_TENANT_ID || "";
const defaultBackendUrl = import.meta.env.DEV ? "http://localhost:8000" : browserOrigin;

export const ENV = {
  DEV: import.meta.env.DEV,
  PROD: import.meta.env.PROD,
  SSR: import.meta.env.SSR,
  BACKEND_URL: import.meta.env.VITE_BACKEND_URL || defaultBackendUrl,
  USE_MOCK_DATA:
    import.meta.env.VITE_USE_MOCK_DATA === "true" ||
    (import.meta.env.DEV && import.meta.env.VITE_USE_MOCK_DATA !== "false"),
  MSAL_CLIENT_ID: import.meta.env.VITE_MSAL_CLIENT_ID || "",
  MSAL_TENANT_ID: msalTenantId,
  MSAL_AUTHORITY: import.meta.env.VITE_MSAL_AUTHORITY || (msalTenantId ? `https://login.microsoftonline.com/${msalTenantId}` : ""),
  MSAL_REDIRECT_URI: import.meta.env.VITE_MSAL_REDIRECT_URI || browserOrigin,
  MSAL_API_SCOPE: import.meta.env.VITE_MSAL_API_SCOPE || "",
} as const;

export const isDevelopment = ENV.DEV;
export const isProduction = ENV.PROD;

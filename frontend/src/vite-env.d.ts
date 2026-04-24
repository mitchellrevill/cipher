// Vite environment variable types
interface ImportMetaEnv {
  readonly VITE_BACKEND_URL?: string;
  readonly VITE_USE_MOCK_DATA?: string;
  readonly VITE_MSAL_CLIENT_ID: string;
  readonly VITE_MSAL_TENANT_ID?: string;
  readonly VITE_MSAL_AUTHORITY?: string;
  readonly VITE_MSAL_REDIRECT_URI?: string;
  readonly VITE_MSAL_API_SCOPE?: string;
  readonly DEV: boolean;
  readonly PROD: boolean;
  readonly SSR: boolean;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

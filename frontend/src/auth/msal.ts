import {
  type AccountInfo,
  InteractionRequiredAuthError,
  PublicClientApplication,
} from "@azure/msal-browser";
import { ENV } from "@/config/env";
import { useAuthStore } from "@/store";
import type { User } from "@/types";

const DEV_MODE = import.meta.env.DEV;

export const apiScope = ENV.MSAL_CLIENT_ID ? `api://${ENV.MSAL_CLIENT_ID}/access_as_user` : "";

export const loginRequest = {
  scopes: ["openid", "profile", "email", apiScope].filter(Boolean),
};

export const msalInstance = new PublicClientApplication({
  auth: {
    clientId: ENV.MSAL_CLIENT_ID,
    authority: ENV.MSAL_AUTHORITY,
    redirectUri: ENV.MSAL_REDIRECT_URI,
  },
  cache: {
    cacheLocation: "sessionStorage",
  },
});

export const isMsalConfigured = Boolean(ENV.MSAL_CLIENT_ID && ENV.MSAL_AUTHORITY);

export function accountToUser(account: AccountInfo): User {
  const claims = account.idTokenClaims as Record<string, unknown> | undefined;
  const oid = typeof claims?.oid === "string" ? claims.oid : account.localAccountId;
  const name = typeof claims?.name === "string" ? claims.name : account.name || "";
  const email = typeof claims?.email === "string"
    ? claims.email
    : typeof claims?.preferred_username === "string"
      ? claims.preferred_username
      : account.username;

  return {
    id: oid,
    name,
    email,
    roles: ["user"],
  };
}

export function redirectToLogin(
  redirectTarget = window.location.href,
  reason: "auth-required" | "session-expired" | "signed-out" | "auth-error" = "auth-required"
): never {
  const loginUrl = new URL("/login", window.location.origin);
  if (redirectTarget) {
    loginUrl.searchParams.set("redirect", redirectTarget);
  }
  loginUrl.searchParams.set("reason", reason);
  window.location.assign(loginUrl.toString());
  throw new Error("Redirecting to login");
}

export async function getAccessToken(): Promise<string | null> {
  const state = useAuthStore.getState();
  if (DEV_MODE && state.token === "dev-token-bypass") {
    return state.token;
  }

  if (!isMsalConfigured) {
    redirectToLogin(window.location.href, "auth-error");
  }

  const account = state.msalAccount ?? msalInstance.getActiveAccount() ?? msalInstance.getAllAccounts()[0] ?? null;
  if (!account) {
    redirectToLogin(window.location.href, "auth-required");
  }

  try {
    msalInstance.setActiveAccount(account);
    const result = await msalInstance.acquireTokenSilent({
      account,
      scopes: loginRequest.scopes,
    });
    return result.accessToken;
  } catch (error) {
    if (error instanceof InteractionRequiredAuthError) {
      useAuthStore.getState().clearAuth();
      redirectToLogin(window.location.href, "session-expired");
    }

    throw error;
  }
}

export async function getAuthorizationHeaders(): Promise<Record<string, string>> {
  const token = await getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}
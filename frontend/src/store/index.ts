/**
 * Zustand store for application state management
 * Features:
 * - User authentication state
 * - UI state (theme, sidebar, etc.)
 * - Global notifications
 */

import type { AccountInfo } from "@azure/msal-browser";
import { create } from "zustand";
import { devtools } from "zustand/middleware";
import { msalInstance } from "@/auth/msal";
import type { User } from "@/types";

// Dev mode: bypass authentication
const DEV_MODE = import.meta.env.DEV;

const DEV_USER: User = {
  id: "dev-user-123",
  email: "dev@example.com",
  name: "Developer",
  roles: ["admin"],
};

export interface AuthState {
  user: User | null;
  token: string | null;
  msalAccount: AccountInfo | null;
  isAuthenticated: boolean;
  isLoggingOut: boolean;
  isLoading: boolean;
  error: string | null;
  setUser: (user: User | null) => void;
  setToken: (token: string | null) => void;
  setMsalAccount: (account: AccountInfo | null) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  clearAuth: () => void;
  logout: () => Promise<void>;
}

export const useAuthStore = create<AuthState>()(
  devtools(
    (set, get) => ({
      user: DEV_MODE ? DEV_USER : null,
      token: null,
      msalAccount: null,
      isAuthenticated: false,
      isLoggingOut: false,
      isLoading: false,
      error: null,
      setUser: (user) => set({ user, isAuthenticated: !!user }),
      setToken: (token) => set((state) => ({ token, isAuthenticated: !!(token || state.user || state.msalAccount) })),
      setMsalAccount: (msalAccount) =>
        set((state) => ({ msalAccount, isAuthenticated: !!(msalAccount || state.user || state.token) })),
      setLoading: (isLoading) => set({ isLoading }),
      setError: (error) => set({ error }),
      clearAuth: () => {
        set({
          user: null,
          token: null,
          msalAccount: null,
          isAuthenticated: false,
          isLoggingOut: false,
          error: null,
        });
      },
      logout: async () => {
        set({ isLoggingOut: true, error: null });
        if (DEV_MODE) {
          set({
            user: null,
            token: null,
            msalAccount: null,
            isAuthenticated: false,
            isLoggingOut: false,
            error: null,
          });
          return;
        }

        const state = get();
        const account = state.msalAccount ?? msalInstance.getActiveAccount() ?? msalInstance.getAllAccounts()[0] ?? null;

        try {
          if (account) {
            await msalInstance.logoutPopup({
              account,
              postLogoutRedirectUri: `${window.location.origin}/login?reason=signed-out`,
            });
          }
        } finally {
          set({
            user: null,
            token: null,
            msalAccount: null,
            isAuthenticated: false,
            isLoggingOut: false,
            error: null,
          });
        }
      },
    }),
    { name: "auth-store" }
  )
);

export interface UIState {
  sidebarOpen: boolean;
  theme: "light" | "dark" | "system";
  setSidebarOpen: (open: boolean) => void;
  setTheme: (theme: "light" | "dark" | "system") => void;
  toggleSidebar: () => void;
}

export const useUIStore = create<UIState>()(
  devtools(
    (set) => ({
      sidebarOpen: true,
      theme: (localStorage.getItem("theme") as "light" | "dark" | "system") || "system",
      setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),
      setTheme: (theme) => {
        localStorage.setItem("theme", theme);
        set({ theme });
      },
      toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
    }),
    { name: "ui-store" }
  )
);

export { useWorkspaceStore, type ChatContextFile } from "./workspace-store";

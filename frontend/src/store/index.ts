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

export interface AuthState {
  user: User | null;
  msalAccount: AccountInfo | null;
  isAuthenticated: boolean;
  isLoggingOut: boolean;
  isLoading: boolean;
  error: string | null;
  setUser: (user: User | null) => void;
  setMsalAccount: (account: AccountInfo | null) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  clearAuth: () => void;
  logout: () => Promise<void>;
}

export const useAuthStore = create<AuthState>()(
  devtools(
    (set, get) => ({
      user: null,
      msalAccount: null,
      isAuthenticated: false,
      isLoggingOut: false,
      isLoading: false,
      error: null,
      setUser: (user) => set((state) => ({ user, isAuthenticated: !!(user || state.msalAccount) })),
      setMsalAccount: (msalAccount) =>
        set((state) => ({ msalAccount, isAuthenticated: !!(msalAccount || state.user) })),
      setLoading: (isLoading) => set({ isLoading }),
      setError: (error) => set({ error }),
      clearAuth: () => {
        set({
          user: null,
          msalAccount: null,
          isAuthenticated: false,
          isLoggingOut: false,
          error: null,
        });
      },
      logout: async () => {
        set({ isLoggingOut: true, error: null });
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

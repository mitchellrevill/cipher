/**
 * Zustand store for application state management
 * Features:
 * - User authentication state
 * - UI state (theme, sidebar, etc.)
 * - Global notifications
 */

import { create } from "zustand";
import { devtools } from "zustand/middleware";
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
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  setUser: (user: User | null) => void;
  setToken: (token: string | null) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  devtools(
    (set) => ({
      user: DEV_MODE ? DEV_USER : null,
      token: DEV_MODE ? "dev-token-bypass" : localStorage.getItem("auth_token"),
      isAuthenticated: DEV_MODE ? true : !!localStorage.getItem("auth_token"),
      isLoading: false,
      error: null,
      setUser: (user) => set({ user, isAuthenticated: !!user }),
      setToken: (token) => {
        if (token) {
          localStorage.setItem("auth_token", token);
        } else {
          localStorage.removeItem("auth_token");
        }
        set({ token, isAuthenticated: !!token });
      },
      setLoading: (isLoading) => set({ isLoading }),
      setError: (error) => set({ error }),
      logout: () => {
        localStorage.removeItem("auth_token");
        set({
          user: DEV_MODE ? DEV_USER : null,
          token: DEV_MODE ? "dev-token-bypass" : null,
          isAuthenticated: DEV_MODE ? true : false,
          error: null,
        });
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

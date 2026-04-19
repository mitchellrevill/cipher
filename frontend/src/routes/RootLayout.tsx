import { Outlet, useRouterState } from "@tanstack/react-router";
import { ThemeProvider } from "@/components/theme-provider";
import { AppShell } from "@/components/layout/app-shell";
import { Toaster } from "@/components/ui";
import { allThemeIds } from "@/lib/themes";
import { useAuthStore } from "@/store";

/**
 * Root layout component
 * Provider setup for:
 * - Query Client (TanStack Query)
 * - Theme provider
 * - Auth state
 */

export default function RootLayout() {
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  });
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const showShell = pathname !== "/login" || isAuthenticated;

  return (
    <ThemeProvider attribute="class" defaultTheme="light" themes={allThemeIds} enableSystem disableTransitionOnChange>
      <Toaster />
      {showShell ? (
        <AppShell>
          <Outlet />
        </AppShell>
      ) : (
        <div className="min-h-screen bg-background text-foreground">
          <Outlet />
        </div>
      )}
    </ThemeProvider>
  );
}

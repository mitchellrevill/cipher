/**
 * Main App Component
 * Sets up providers (Query Client, Theme, etc.)
 */

import { useEffect } from "react";
import type { AccountInfo } from "@azure/msal-browser";
import { MsalProvider, useMsal } from "@azure/msal-react";
import { QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { RouterProvider } from "@tanstack/react-router";
import { accountToUser, msalInstance } from "@/auth/msal";
import { queryClient } from "./lib/query-client";
import { router } from "./routes";
import { useAuthStore } from "./store";

function AuthBootstrap() {
  const { instance, accounts } = useMsal();
  const setUser = useAuthStore((state) => state.setUser);
  const setToken = useAuthStore((state) => state.setToken);
  const setMsalAccount = useAuthStore((state) => state.setMsalAccount);

  useEffect(() => {
    if (import.meta.env.DEV) {
      return;
    }

    const account: AccountInfo | null =
      accounts[0] ?? instance.getActiveAccount() ?? msalInstance.getAllAccounts()[0] ?? null;

    if (!account) {
      return;
    }

    instance.setActiveAccount(account);
    setMsalAccount(account);
    setUser(accountToUser(account));
    setToken(null);
  }, [accounts, instance, setMsalAccount, setToken, setUser]);

  return null;
}

function App() {
  const showDevtools = import.meta.env.DEV && window.location.search.includes("debug");

  return (
    <MsalProvider instance={msalInstance}>
      <QueryClientProvider client={queryClient}>
        <AuthBootstrap />
        <RouterProvider router={router} />
        {showDevtools ? <ReactQueryDevtools initialIsOpen={false} /> : null}
      </QueryClientProvider>
    </MsalProvider>
  );
}

export default App;

/**
 * Main App Component
 * Sets up providers (Query Client, Theme, etc.)
 */

import { MsalProvider } from "@azure/msal-react";
import { QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { RouterProvider } from "@tanstack/react-router";
import { msalInstance } from "@/auth/msal";
import { queryClient } from "./lib/query-client";
import { router } from "./routes";

function App() {
  const showDevtools = import.meta.env.DEV && window.location.search.includes("debug");

  return (
    <MsalProvider instance={msalInstance}>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
        {showDevtools ? <ReactQueryDevtools initialIsOpen={false} /> : null}
      </QueryClientProvider>
    </MsalProvider>
  );
}

export default App;

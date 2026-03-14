/**
 * TanStack Router configuration and routes
 * File-based routing with TanStack Router
 */

import { RootRoute, Route, Router } from "@tanstack/react-router";
import RootLayout from "@/routes/RootLayout";
import IndexRoute from "@/routes/index";
import LoginRoute from "@/routes/login";
import DocumentsRoute from "@/routes/documents";
import WorkspaceDetailsRoute from "@/routes/workspaces.$workspaceId";

const rootRoute = new RootRoute({
  component: RootLayout,
});

const indexRoute = new Route({
  getParentRoute: () => rootRoute,
  path: "/",
  component: IndexRoute,
});

const loginRoute = new Route({
  getParentRoute: () => rootRoute,
  path: "/login",
  component: LoginRoute,
});

const documentsRoute = new Route({
  getParentRoute: () => rootRoute,
  path: "/documents",
  component: DocumentsRoute,
});

const workspaceDetailsRoute = new Route({
  getParentRoute: () => rootRoute,
  path: "/workspaces/$workspaceId",
  component: WorkspaceDetailsRoute,
});

const routeTree = rootRoute.addChildren([indexRoute, loginRoute, documentsRoute, workspaceDetailsRoute]);

export const router = new Router({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

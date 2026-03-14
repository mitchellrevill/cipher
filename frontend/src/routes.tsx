/**
 * TanStack Router configuration and routes
 */

import { RootRoute, Route, Router } from "@tanstack/react-router";
import RootLayout from "@/routes/RootLayout";
import IndexRoute from "@/routes/index";
import LoginRoute from "@/routes/login";
import DesignerRoute from "@/routes/designer";
import WorkspacesRoute from "@/routes/workspace.index";
import WorkspaceDetailsRoute from "@/routes/workspace.$workspaceId";

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

const workspacesIndexRoute = new Route({
  getParentRoute: () => rootRoute,
  path: "/workspace",
  component: WorkspacesRoute,
});

const workspaceDetailsRoute = new Route({
  getParentRoute: () => rootRoute,
  path: "/workspace/$workspaceId",
  component: WorkspaceDetailsRoute,
});

const workspaceDesignerRoute = new Route({
  getParentRoute: () => rootRoute,
  path: "/workspace/$workspaceId/designer",
  component: DesignerRoute,
});

const designerRoute = new Route({
  getParentRoute: () => rootRoute,
  path: "/designer",
  component: DesignerRoute,
});

const routeTree = rootRoute.addChildren([
  indexRoute,
  loginRoute,
  workspacesIndexRoute,       // /workspace
  workspaceDetailsRoute,      // /workspace/$workspaceId
  workspaceDesignerRoute,     // /workspace/$workspaceId/designer
  designerRoute,              // /designer
]);

export const router = new Router({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

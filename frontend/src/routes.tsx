/**
 * TanStack Router configuration and routes
 */

import { redirect, RootRoute, Route, Router } from "@tanstack/react-router";
import { useAuthStore } from "@/store";
import RootLayout from "@/routes/RootLayout";
import IndexRoute from "@/routes/index";
import LoginRoute from "@/routes/login";
import DesignerRoute from "@/routes/designer";
import JobsRoute from "@/routes/jobs";
import WorkspacesRoute from "@/routes/workspace.index";
import WorkspaceDetailsRoute from "@/routes/workspace.$workspaceId";

const rootRoute = new RootRoute({
  component: RootLayout,
  beforeLoad: ({ location }) => {
    if (location.pathname === "/login") {
      return;
    }

    if (!useAuthStore.getState().isAuthenticated) {
      throw redirect({
        to: "/login",
        search: {
          redirect: location.href,
        },
      });
    }
  },
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
  path: "/workspace/$workspaceId/designer/$jobId",
  component: DesignerRoute,
});

const workspaceDesignerNewRoute = new Route({
  getParentRoute: () => rootRoute,
  path: "/workspace/$workspaceId/designer/new",
  component: DesignerRoute,
});

const designerRoute = new Route({
  getParentRoute: () => rootRoute,
  path: "/designer/$jobId",
  component: DesignerRoute,
});

const designerNewRoute = new Route({
  getParentRoute: () => rootRoute,
  path: "/designer/new",
  component: DesignerRoute,
});

const jobsRoute = new Route({
  getParentRoute: () => rootRoute,
  path: "/jobs",
  component: JobsRoute,
});

const routeTree = rootRoute.addChildren([
  indexRoute,
  loginRoute,
  jobsRoute,                  // /jobs
  workspacesIndexRoute,       // /workspace
  workspaceDetailsRoute,      // /workspace/$workspaceId
  workspaceDesignerRoute,     // /workspace/$workspaceId/designer/$jobId
  workspaceDesignerNewRoute,  // /workspace/$workspaceId/designer/new
  designerRoute,              // /designer/$jobId
  designerNewRoute,           // /designer/new
]);

export const router = new Router({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

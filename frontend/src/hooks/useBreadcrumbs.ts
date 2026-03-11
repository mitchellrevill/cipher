import { useRouterState } from "@tanstack/react-router";
import type { SmartBreadcrumbItem } from "@/components/ui/smart-breadcrumb";

const routeLabels: Record<string, string> = {
  documents: "Workspace",
  login: "Sign In",
};

function formatSegment(segment: string) {
  return routeLabels[segment] ?? segment.charAt(0).toUpperCase() + segment.slice(1).replace(/-/g, " ");
}

export function useBreadcrumbs(): SmartBreadcrumbItem[] {
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  });

  const segments = pathname.split("/").filter(Boolean);

  return segments.map((segment, index) => ({
    label: formatSegment(segment),
    to: "/" + segments.slice(0, index + 1).join("/"),
    isCurrentPage: index === segments.length - 1,
  }));
}
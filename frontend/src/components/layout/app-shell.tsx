import React, { useState, type PropsWithChildren } from "react";
import {
  ChevronLeft,
  ChevronRight,
  Files,
  FolderKanban,
  House,
  Loader2,
  LogOut,
  MoreHorizontal,
  PanelsTopLeft,
  User,
} from "lucide-react";
import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import { WorkspaceSidebarJobs } from "@/components/workspace/workspace-sidebar-jobs";
import { useRecentJobs } from "@/hooks/useRecentJobs";
import { ThemeToggle } from "@/components/theme-toggle";
import {
  Button,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui";
import { cn } from "@/lib/utils";
import { useAuthStore, useUIStore } from "@/store";
import { toast } from "sonner";

const SIDEBAR_LAYOUT_KEY = "cipher.shell.sidebar.layout";

interface NavItemConfig {
  id: string;
  icon: React.ElementType;
  label: string;
  to: string;
  mobileShortLabel?: string;
}

interface NavSectionConfig {
  id: string;
  label?: string;
  items: ReadonlyArray<NavItemConfig>;
}

const PRIMARY_NAV_ITEMS: ReadonlyArray<NavItemConfig> = [
  { id: "overview", icon: House, label: "Overview", to: "/", mobileShortLabel: "Home" },
  { id: "jobs", icon: Files, label: "All Jobs", to: "/jobs", mobileShortLabel: "Jobs" },
  { id: "workspaces", icon: FolderKanban, label: "Workspaces", to: "/workspace", mobileShortLabel: "Work" },
];

const NAV_SECTIONS: ReadonlyArray<NavSectionConfig> = [
  { id: "workspace", label: "Workspaces", items: PRIMARY_NAV_ITEMS },
];

const readStringStorage = (key: string, fallback: string): string => {
  try {
    return window.localStorage.getItem(key) ?? fallback;
  } catch {
    return fallback;
  }
};

const getUserInitials = (name?: string | null, email?: string | null): string => {
  const source = name || email || "U";
  return source
    .split(/[\s@]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() ?? "")
    .join("");
};

export function AppShell({ children }: PropsWithChildren) {
  const isOpen = useUIStore((s) => s.sidebarOpen);
  const setIsOpen = useUIStore((s) => s.setSidebarOpen);
  const { recentJobs } = useRecentJobs();
  const [sidebarLayout, setSidebarLayout] = useState<"left" | "top">(() =>
    readStringStorage(SIDEBAR_LAYOUT_KEY, "left") === "top" ? "top" : "left"
  );

  const pathname = useRouterState({ select: (s) => s.location.pathname });
    const activeJobId = (() => {
      const designerPathMatch = pathname.match(/\/designer\/([^/]+)$/);
      if (!designerPathMatch) {
        return null;
      }

      return designerPathMatch[1] === "new" ? null : designerPathMatch[1];
    })();

  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const isLoggingOut = useAuthStore((s) => s.isLoggingOut);

  const userInitials = getUserInitials(user?.name, user?.email);

  const toggleSidebar = () => {
    setIsOpen(!isOpen);
  };

  const toggleLayout = () => {
    setSidebarLayout((prev) => {
      const next = prev === "left" ? "top" : "left";
      window.localStorage.setItem(SIDEBAR_LAYOUT_KEY, next);
      return next;
    });
  };

  const handleSidebarJobSelect = (jobId: string) => {
    void navigate({ to: "/designer/$jobId", params: { jobId } });
  };

  const handleLogout = async () => {
    try {
      await logout();
      toast.success("Signed out.");
      window.location.assign("/login?reason=signed-out");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to sign out cleanly.";
      toast.error(message);
    }
  };

  const renderDesktopLink = (item: NavItemConfig) => {
    const isActive = item.to === "/" ? pathname === "/" : pathname.startsWith(item.to);
    return (
      <Link
        key={item.id}
        to={item.to}
        aria-label={sidebarLayout === "left" && !isOpen ? item.label : undefined}
        className={cn(
          "flex items-center rounded-lg p-2 transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
          sidebarLayout === "left" ? "w-full" : "",
          isActive && "bg-sidebar-accent text-sidebar-accent-foreground"
        )}
      >
        <item.icon className="h-5 w-5 flex-shrink-0" />
        <span className={cn("ml-3 hidden", sidebarLayout === "top" ? "inline" : isOpen && "inline")}>
          {item.label}
        </span>
      </Link>
    );
  };

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      {/* Mobile bottom nav */}
      <nav
        aria-label="Primary"
        className="fixed bottom-0 left-0 right-0 z-50 border-t border-border bg-background pb-[env(safe-area-inset-bottom)] md:hidden"
      >
        <ul className="flex h-16 items-center justify-around px-2">
          {PRIMARY_NAV_ITEMS.map((item) => {
            const isActive = item.to === "/" ? pathname === "/" : pathname.startsWith(item.to);
            return (
              <li key={item.id}>
                <Link
                  to={item.to}
                  aria-label={item.label}
                  className={cn(
                    "flex min-h-[2.75rem] min-w-16 flex-col items-center justify-center rounded-lg px-2 py-1.5 text-foreground transition-colors hover:bg-muted",
                    isActive && "bg-accent text-accent-foreground"
                  )}
                >
                  <item.icon className="h-5 w-5" />
                  <span className="mt-1 max-w-[8ch] truncate text-[0.7rem]">
                    {item.mobileShortLabel ?? item.label.split(" ")[0]}
                  </span>
                </Link>
              </li>
            );
          })}
          <li>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  className="flex min-h-[2.75rem] min-w-16 flex-col items-center justify-center px-2 py-1.5 text-foreground hover:bg-muted"
                  aria-label="More menu"
                  disabled={isLoggingOut}
                >
                  <MoreHorizontal className="h-5 w-5" />
                  <span className="mt-1 text-[0.7rem]">More</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" side="top" className="mb-2 w-56">
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={() => void handleLogout()} className="text-red-400 focus:text-red-300" disabled={isLoggingOut}>
                  {isLoggingOut ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <LogOut className="mr-2 h-4 w-4" />}
                  <span>{isLoggingOut ? "Signing out..." : "Logout"}</span>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </li>
        </ul>
      </nav>

      {/* Desktop sidebar / top bar */}
      <div
        className={cn(
          "hidden md:fixed md:left-0 md:top-0 md:z-40 md:flex bg-sidebar text-sidebar-foreground transition-all duration-300 ease-in-out border-sidebar-border",
          sidebarLayout === "top"
            ? "md:h-16 md:w-full md:flex-row md:border-b"
            : cn("md:h-full md:flex-col md:border-r", isOpen ? "md:w-64" : "md:w-16")
        )}
      >
        {sidebarLayout === "left" && (
          <Button
            variant="ghost"
            className="absolute z-50 h-8 w-8 rounded-full border border-sidebar-border bg-sidebar-accent p-0 text-sidebar-accent-foreground hover:bg-sidebar-accent/80 md:-right-4 md:top-4"
            onClick={toggleSidebar}
            aria-label={isOpen ? "Collapse sidebar" : "Expand sidebar"}
          >
            {isOpen ? <ChevronLeft /> : <ChevronRight />}
          </Button>
        )}

        <div className={cn("flex h-full w-full min-h-0", sidebarLayout === "top" ? "md:flex-row" : "md:flex-col")}>
          {/* Logo — left sidebar expanded only */}
          {sidebarLayout === "left" && isOpen && (
            <div className="flex h-24 w-full flex-shrink-0 items-center justify-center overflow-hidden bg-sidebar pt-4">
              <img
                src="/logo.png"
                alt="Barnsley Council Logo"
                className="h-full w-full object-contain transition-all duration-300"
              />
            </div>
          )}

          {/* Nav links */}
          <nav
            aria-label="Primary"
            className={cn(
              "flex min-h-0 flex-1 p-4",
              sidebarLayout === "top"
                ? "flex-row space-x-2 space-y-0"
                : cn(
                    "flex-col space-x-0 space-y-2 overflow-y-auto hide-scrollbar",
                    !isOpen && "items-center"
                  )
            )}
          >
            {NAV_SECTIONS.map((section) => (
              <React.Fragment key={section.id}>
                {sidebarLayout === "left" && isOpen && section.label && (
                  <div className="mx-2 my-3 flex items-center">
                    <div className="h-px flex-grow bg-sidebar-border" />
                    <span className="px-3 text-xs font-medium uppercase tracking-wider text-sidebar-foreground/60">
                      {section.label}
                    </span>
                    <div className="h-px flex-grow bg-sidebar-border" />
                  </div>
                )}
                {section.items.map(renderDesktopLink)}
              </React.Fragment>
            ))}
          </nav>

          {sidebarLayout === "left" && isOpen ? (
            <div className="border-t border-sidebar-border px-2 py-2">
              <WorkspaceSidebarJobs
                jobs={recentJobs}
                selectedJobId={activeJobId}
                onJobSelect={handleSidebarJobSelect}
              />
            </div>
          ) : null}

          {/* Profile area */}
          <div className="flex-shrink-0">
            {sidebarLayout === "top" && (
              <div className="mr-4 flex items-center space-x-2">
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" className="h-full space-x-3 px-3 py-3 hover:bg-sidebar-accent">
                      <div className="flex h-8 w-8 items-center justify-center rounded-full bg-white/10 text-xs font-semibold text-sidebar-foreground">
                        {userInitials}
                      </div>
                      {user && (
                        <span className="block max-w-[180px] truncate text-sm font-medium text-sidebar-foreground">
                          {user.email}
                        </span>
                      )}
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-64">
                    {user && (
                      <div className="border-b px-3 py-2">
                        <div className="text-sm font-medium">{user.email}</div>
                      </div>
                    )}
                    <DropdownMenuItem onClick={toggleLayout}>
                      <PanelsTopLeft className="mr-2 h-4 w-4" />
                      <span>Switch to Left Sidebar</span>
                    </DropdownMenuItem>
                    <DropdownMenuItem>
                      <User className="mr-2 h-4 w-4" />
                      <span>Profile Settings</span>
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem onClick={() => void handleLogout()} className="text-red-400 focus:text-red-300" disabled={isLoggingOut}>
                      {isLoggingOut ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <LogOut className="mr-2 h-4 w-4" />}
                      <span>{isLoggingOut ? "Signing out..." : "Logout"}</span>
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
                <Button
                  variant="ghost"
                  className="h-full px-3 py-3 text-red-400 hover:bg-red-900/20 hover:text-red-300"
                  onClick={() => void handleLogout()}
                  aria-label="Logout"
                  disabled={isLoggingOut}
                >
                  {isLoggingOut ? <Loader2 className="h-5 w-5 animate-spin" /> : <LogOut className="h-5 w-5" />}
                </Button>
              </div>
            )}

            {sidebarLayout === "left" && (
              <div className="mt-auto flex w-full flex-col">
                <div className="mt-2 rounded-lg px-3 py-2 transition-colors hover:bg-sidebar-accent">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <button
                        type="button"
                        className={cn(
                          "w-full cursor-pointer p-0",
                          !isOpen
                            ? "flex flex-col items-center space-y-2 py-2"
                            : "flex flex-row items-center space-x-3 py-2"
                        )}
                        aria-label="Open profile menu"
                      >
                        <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-white/10 text-sm font-semibold text-sidebar-foreground">
                          {userInitials}
                        </div>
                        {user && isOpen && (
                          <div className="min-w-0 text-left">
                            <span className="block max-w-full truncate text-sm font-medium text-sidebar-foreground">
                              {user.email}
                            </span>
                          </div>
                        )}
                      </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-64">
                      {user && (
                        <div className="border-b px-3 py-2">
                          <div className="text-sm font-medium">{user.email}</div>
                        </div>
                      )}
                      <DropdownMenuItem onClick={toggleLayout}>
                        <PanelsTopLeft className="mr-2 h-4 w-4" />
                        <span>Switch to Top Bar</span>
                      </DropdownMenuItem>
                      <DropdownMenuItem>
                        <User className="mr-2 h-4 w-4" />
                        <span>Profile Settings</span>
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
                <div className="mt-auto border-t border-sidebar-border p-4">
                  <Button
                    variant="ghost"
                    className={cn(
                      "w-full justify-start p-4 text-red-400 hover:bg-red-900/20 hover:text-red-300",
                      !isOpen && "flex-col space-y-2"
                    )}
                    onClick={() => void handleLogout()}
                    aria-label="Logout"
                    disabled={isLoggingOut}
                  >
                    {isLoggingOut ? <Loader2 className="h-5 w-5 animate-spin" /> : <LogOut className="h-5 w-5" />}
                    {isOpen && <span className="ml-3">{isLoggingOut ? "Signing out..." : "Logout"}</span>}
                  </Button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Content area */}
      <div
        className={cn(
          "flex-1 flex flex-col min-h-0 transition-all duration-300 ease-in-out",
          "pb-[calc(4rem+env(safe-area-inset-bottom))] md:pb-0",
          sidebarLayout === "top"
            ? "md:mt-16"
            : isOpen
              ? "md:mt-0 md:ml-64"
              : "md:mt-0 md:ml-16"
        )}
      >
        {/* Slim top bar with theme toggle */}
        <div className="hidden sm:flex flex-shrink-0 h-14 items-center justify-end px-4 border-b border-border/30 bg-background/60 backdrop-blur-sm">
          <ThemeToggle />
        </div>
        {/* Main content area */}
        <div className="flex-1 min-h-0 overflow-hidden">
          {children}
        </div>
      </div>
    </div>
  );
}
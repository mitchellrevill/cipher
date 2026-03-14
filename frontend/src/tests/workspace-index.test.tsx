import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { WorkspaceListItem } from "@/api/services";

vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => vi.fn(),
}));

vi.mock("@/components/workspace/create-workspace-dialog", () => ({
  CreateWorkspaceDialog: ({ open }: { open: boolean }) =>
    open ? <div data-testid="create-dialog" /> : null,
}));

const mockWorkspaces: WorkspaceListItem[] = [
  {
    id: "ws-1",
    name: "HR Contracts",
    description: "All HR related docs",
    document_ids: ["d1", "d2"],
    rule_ids: ["r1"],
    exclusion_ids: [],
    created_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "ws-2",
    name: "Legal Review",
    document_ids: [],
    rule_ids: [],
    exclusion_ids: [],
    created_at: "2026-01-02T00:00:00Z",
  },
];

function makeWrapper(queryClient: QueryClient) {
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

let WorkspacesRoute: React.ComponentType;
beforeAll(async () => {
  const mod = await import("@/routes/workspace.index");
  WorkspacesRoute = mod.default;
});

describe("WorkspacesRoute", () => {
  it("renders the Workspaces heading", async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    qc.setQueryData(["workspaces"], mockWorkspaces);
    render(<WorkspacesRoute />, { wrapper: makeWrapper(qc) });
    expect(await screen.findByText("Workspaces")).toBeInTheDocument();
  });

  it("renders a card for each workspace", async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    qc.setQueryData(["workspaces"], mockWorkspaces);
    render(<WorkspacesRoute />, { wrapper: makeWrapper(qc) });
    expect(await screen.findByText("HR Contracts")).toBeInTheDocument();
    expect(screen.getByText("Legal Review")).toBeInTheDocument();
  });

  it("shows document, rule and exclusion counts as badges", async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    qc.setQueryData(["workspaces"], mockWorkspaces);
    render(<WorkspacesRoute />, { wrapper: makeWrapper(qc) });
    await screen.findByText("HR Contracts");
    expect(screen.getByText("2 files")).toBeInTheDocument();
    expect(screen.getByText("1 rules")).toBeInTheDocument();
    expect(screen.getAllByText("0 exclusions").length).toBeGreaterThan(0);
  });

  it("shows empty state when no workspaces exist", async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    qc.setQueryData(["workspaces"], []);
    render(<WorkspacesRoute />, { wrapper: makeWrapper(qc) });
    expect(await screen.findByText(/no workspaces yet/i)).toBeInTheDocument();
  });

  it("opens the create dialog when 'New workspace' is clicked", async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    qc.setQueryData(["workspaces"], []);
    render(<WorkspacesRoute />, { wrapper: makeWrapper(qc) });
    await screen.findByText(/no workspaces yet/i);
    fireEvent.click(screen.getByRole("button", { name: /new workspace/i }));
    expect(screen.getByTestId("create-dialog")).toBeInTheDocument();
  });
});

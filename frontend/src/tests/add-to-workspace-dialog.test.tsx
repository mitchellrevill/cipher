import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AddToWorkspaceDialog } from "@/components/workspace/add-to-workspace-dialog";

const mockWorkspaces = [
  { id: "ws-1", name: "HR Contracts", documents: [], rules: [], exclusions: [] },
  { id: "ws-2", name: "Legal Review", documents: [], rules: [], exclusions: [] },
];

function makeWrapper(queryClient: QueryClient) {
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe("AddToWorkspaceDialog", () => {
  it("lists workspaces from the query cache", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(["workspaces"], mockWorkspaces);

    render(<AddToWorkspaceDialog jobId="j1" open={true} onOpenChange={vi.fn()} />, {
      wrapper: makeWrapper(queryClient),
    });

    expect(await screen.findByText("HR Contracts")).toBeInTheDocument();
    expect(screen.getByText("Legal Review")).toBeInTheDocument();
  });

  it("filters workspaces by search text", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(["workspaces"], mockWorkspaces);

    render(<AddToWorkspaceDialog jobId="j1" open={true} onOpenChange={vi.fn()} />, {
      wrapper: makeWrapper(queryClient),
    });

    fireEvent.change(await screen.findByPlaceholderText("Search workspaces…"), {
      target: { value: "legal" },
    });

    expect(screen.getByText("Legal Review")).toBeInTheDocument();
    expect(screen.queryByText("HR Contracts")).not.toBeInTheDocument();
  });

  it("enables the Add button only when a workspace is selected", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(["workspaces"], mockWorkspaces);

    render(<AddToWorkspaceDialog jobId="j1" open={true} onOpenChange={vi.fn()} />, {
      wrapper: makeWrapper(queryClient),
    });

    const addButton = screen.getByRole("button", { name: /add to workspace/i });
    expect(addButton).toBeDisabled();

    fireEvent.click(await screen.findByText("HR Contracts"));
    expect(addButton).not.toBeDisabled();
  });
});

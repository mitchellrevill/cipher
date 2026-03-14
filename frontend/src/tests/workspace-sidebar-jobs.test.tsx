import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { WorkspaceSidebarJobs } from "@/components/workspace/workspace-sidebar-jobs";

const mockJobs = [
  { jobId: "j1", filename: "contract.pdf", status: "complete", createdAt: new Date().toISOString() },
  { jobId: "j2", filename: "report.pdf", status: "processing", createdAt: new Date().toISOString() },
] as const;

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe("WorkspaceSidebarJobs", () => {
  it("renders all job filenames", () => {
    renderWithClient(<WorkspaceSidebarJobs jobs={[...mockJobs]} selectedJobId={null} onJobSelect={vi.fn()} />);
    expect(screen.getByText("contract.pdf")).toBeInTheDocument();
    expect(screen.getByText("report.pdf")).toBeInTheDocument();
  });

  it("marks the selected job with data-selected=true", () => {
    renderWithClient(<WorkspaceSidebarJobs jobs={[...mockJobs]} selectedJobId="j1" onJobSelect={vi.fn()} />);
    const button = screen.getByText("contract.pdf").closest("button");
    expect(button).toHaveAttribute("data-selected", "true");
  });

  it("calls onJobSelect with the correct jobId when clicked", () => {
    const onSelect = vi.fn();
    renderWithClient(<WorkspaceSidebarJobs jobs={[...mockJobs]} selectedJobId={null} onJobSelect={onSelect} />);
    fireEvent.click(screen.getByText("contract.pdf"));
    expect(onSelect).toHaveBeenCalledWith("j1");
  });

  it('shows "Add to workspace" on right-click', async () => {
    renderWithClient(<WorkspaceSidebarJobs jobs={[...mockJobs]} selectedJobId={null} onJobSelect={vi.fn()} />);
    fireEvent.contextMenu(screen.getByText("contract.pdf"));
    expect(await screen.findByText("Add to workspace")).toBeInTheDocument();
  });

  it("shows empty state when no jobs", () => {
    renderWithClient(<WorkspaceSidebarJobs jobs={[]} selectedJobId={null} onJobSelect={vi.fn()} />);
    expect(screen.getByText(/no jobs yet/i)).toBeInTheDocument();
  });
});

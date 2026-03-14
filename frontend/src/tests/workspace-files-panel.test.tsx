import { DndContext } from "@dnd-kit/core";
import { fireEvent, render, screen } from "@testing-library/react";
import { WorkspaceFilesPanel } from "@/components/workspace/workspace-files-panel";

const files = [
  { id: "j1", filename: "contract.pdf", status: "complete", workspaceId: "ws-1" },
  { id: "j2", filename: "report.pdf", status: "processing", workspaceId: "ws-1" },
];

const wrap = (ui: React.ReactElement) => render(<DndContext>{ui}</DndContext>);

describe("WorkspaceFilesPanel", () => {
  it('renders a "Files" heading', () => {
    wrap(<WorkspaceFilesPanel files={files} selectedJobId={null} onJobSelect={vi.fn()} onAddToChat={vi.fn()} />);
    expect(screen.getByText("Files")).toBeInTheDocument();
  });

  it("renders all file items", () => {
    wrap(<WorkspaceFilesPanel files={files} selectedJobId={null} onJobSelect={vi.fn()} onAddToChat={vi.fn()} />);
    expect(screen.getByText("contract.pdf")).toBeInTheDocument();
    expect(screen.getByText("report.pdf")).toBeInTheDocument();
  });

  it("marks the selected job", () => {
    wrap(<WorkspaceFilesPanel files={files} selectedJobId="j1" onJobSelect={vi.fn()} onAddToChat={vi.fn()} />);
    const button = screen.getByText("contract.pdf").closest("button");
    expect(button).toHaveAttribute("data-selected", "true");
  });

  it("calls onJobSelect when a file is clicked", () => {
    const onSelect = vi.fn();
    wrap(<WorkspaceFilesPanel files={files} selectedJobId={null} onJobSelect={onSelect} onAddToChat={vi.fn()} />);
    fireEvent.click(screen.getByText("contract.pdf"));
    expect(onSelect).toHaveBeenCalledWith("j1");
  });

  it("shows empty state when files list is empty", () => {
    wrap(<WorkspaceFilesPanel files={[]} selectedJobId={null} onJobSelect={vi.fn()} onAddToChat={vi.fn()} />);
    expect(screen.getByText(/no files in this workspace/i)).toBeInTheDocument();
  });
});

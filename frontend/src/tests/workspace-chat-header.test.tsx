import { fireEvent, render, screen } from "@testing-library/react";
import { WorkspaceChatHeader } from "@/components/workspace/workspace-chat-header";

const workspace = {
  id: "ws-1",
  name: "HR Contracts",
  rules: [{ id: "r1" }, { id: "r2" }],
  exclusions: [],
  documents: [],
};

describe("WorkspaceChatHeader", () => {
  const baseProps = {
    activeJobId: "j1",
    onRulesClick: vi.fn(),
    onExclusionsClick: vi.fn(),
    onAddToWorkspace: vi.fn(),
    onCreateWorkspace: vi.fn(),
  };

  it("shows workspace name", () => {
    render(<WorkspaceChatHeader workspace={workspace as any} {...baseProps} />);
    expect(screen.getByText("HR Contracts")).toBeInTheDocument();
  });

  it("shows rules count badge", () => {
    render(<WorkspaceChatHeader workspace={workspace as any} {...baseProps} />);
    expect(screen.getByRole("button", { name: /rules/i })).toHaveTextContent("2");
  });

  it("shows exclusions count badge", () => {
    render(<WorkspaceChatHeader workspace={workspace as any} {...baseProps} />);
    expect(screen.getByRole("button", { name: /exclusions/i })).toHaveTextContent("0");
  });

  it("calls onRulesClick when Rules button clicked", () => {
    const onRulesClick = vi.fn();
    render(<WorkspaceChatHeader workspace={workspace as any} {...baseProps} onRulesClick={onRulesClick} />);
    fireEvent.click(screen.getByRole("button", { name: /rules/i }));
    expect(onRulesClick).toHaveBeenCalled();
  });

  it("shows no-workspace state when workspace is null", () => {
    render(<WorkspaceChatHeader workspace={null} {...baseProps} />);
    expect(screen.getByText(/no workspace/i)).toBeInTheDocument();
  });

  it("shows Add to workspace and Create workspace buttons when no workspace and a job is active", () => {
    render(<WorkspaceChatHeader workspace={null} {...baseProps} />);
    expect(screen.getByRole("button", { name: /add to workspace/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /create workspace/i })).toBeInTheDocument();
  });

  it("hides action buttons when no workspace and no active job", () => {
    render(<WorkspaceChatHeader workspace={null} {...baseProps} activeJobId={null} />);
    expect(screen.queryByRole("button", { name: /add to workspace/i })).not.toBeInTheDocument();
  });
});

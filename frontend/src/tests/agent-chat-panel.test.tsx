import { DndContext } from "@dnd-kit/core";
import { fireEvent, render, screen } from "@testing-library/react";
import { AgentChatPanel } from "@/components/chat/agent-chat-panel";
import { useWorkspaceStore } from "@/store/workspace-store";

const baseProps = {
  conversation: { messages: [] },
  promptPresets: [],
  isStreaming: false,
  chatInput: "",
  onChatInputChange: vi.fn(),
  onSubmit: vi.fn(),
  inputPlaceholder: "Ask a question",
  inputDisabled: false,
  onQuickPrompt: vi.fn(),
  renderMessageText: (text: string) => text,
};

describe("AgentChatPanel context pills", () => {
  beforeEach(() => {
    useWorkspaceStore.getState().reset();
  });

  it("renders a pill for each context file in the store", () => {
    useWorkspaceStore.setState({
      selectedWorkspaceId: "ws-1",
      chatContextFiles: [{ jobId: "j1", filename: "contract.pdf", workspaceId: "ws-1" }],
    });

    render(
      <DndContext>
        <AgentChatPanel {...baseProps} />
      </DndContext>
    );

    expect(screen.getByText("contract.pdf")).toBeInTheDocument();
  });

  it("removes a pill when its dismiss button is clicked", () => {
    useWorkspaceStore.setState({
      selectedWorkspaceId: "ws-1",
      chatContextFiles: [{ jobId: "j1", filename: "contract.pdf", workspaceId: "ws-1" }],
    });

    render(
      <DndContext>
        <AgentChatPanel {...baseProps} />
      </DndContext>
    );

    fireEvent.click(screen.getByRole("button", { name: /remove contract.pdf/i }));
    expect(useWorkspaceStore.getState().chatContextFiles).toHaveLength(0);
  });
});

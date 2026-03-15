import { DndContext } from "@dnd-kit/core";
import { fireEvent, render, screen } from "@testing-library/react";
import { AgentChatPanel } from "@/components/chat/agent-chat-panel";
import { useWorkspaceStore } from "@/store/workspace-store";
import type { Suggestion } from "@/api/services";

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

function makeSuggestion(overrides: Partial<Suggestion> = {}): Suggestion {
  return {
    id: "s1",
    job_id: "j1",
    text: "John Smith",
    category: "person",
    reasoning: "Personal name",
    context: "…John Smith…",
    page_num: 0,
    rects: [],
    approved: false,
    source: "ai",
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

const baseSuggestionsSection = {
  suggestions: [] as Suggestion[],
  selectedSuggestionId: null,
  onSuggestionSelect: vi.fn(),
  onApprovalChange: vi.fn(),
  onDelete: vi.fn(),
  getSuggestionPageLabel: vi.fn().mockReturnValue("p.1"),
  isLoading: false,
  hasJobData: true,
  jobStatus: "complete",
};

describe("AgentChatPanel suggestionsSection", () => {
  it("does not render suggestions section when suggestionsSection prop is absent", () => {
    render(<DndContext><AgentChatPanel {...baseProps} /></DndContext>);
    expect(screen.queryByText(/suggestions/i)).not.toBeInTheDocument();
  });

  it("renders suggestions header when suggestionsSection prop is provided", () => {
    render(
      <DndContext>
        <AgentChatPanel {...baseProps} suggestionsSection={baseSuggestionsSection} />
      </DndContext>
    );
    expect(screen.getByText(/suggestions · /i)).toBeInTheDocument();
  });

  it("shows loading spinner when isLoading is true", () => {
    render(
      <DndContext>
        <AgentChatPanel
          {...baseProps}
          suggestionsSection={{ ...baseSuggestionsSection, isLoading: true, hasJobData: false }}
        />
      </DndContext>
    );
    expect(screen.getByText(/loading suggestions/i)).toBeInTheDocument();
  });

  it("shows error message when error is provided", () => {
    render(
      <DndContext>
        <AgentChatPanel
          {...baseProps}
          suggestionsSection={{ ...baseSuggestionsSection, error: "Unable to load job.", hasJobData: false }}
        />
      </DndContext>
    );
    expect(screen.getByText("Unable to load job.")).toBeInTheDocument();
  });

  it("shows no-job-data message when hasJobData is false", () => {
    render(
      <DndContext>
        <AgentChatPanel
          {...baseProps}
          suggestionsSection={{ ...baseSuggestionsSection, hasJobData: false, jobStatus: null }}
        />
      </DndContext>
    );
    expect(screen.getByText(/no job data yet/i)).toBeInTheDocument();
  });

  it("shows 'No suggestions found' when job is complete with empty suggestions", () => {
    render(
      <DndContext>
        <AgentChatPanel
          {...baseProps}
          suggestionsSection={{ ...baseSuggestionsSection, suggestions: [], jobStatus: "complete" }}
        />
      </DndContext>
    );
    expect(screen.getByText(/no suggestions found/i)).toBeInTheDocument();
  });

  it("shows 'Waiting for analysis' when job is not complete with empty suggestions", () => {
    render(
      <DndContext>
        <AgentChatPanel
          {...baseProps}
          suggestionsSection={{ ...baseSuggestionsSection, suggestions: [], jobStatus: "processing" }}
        />
      </DndContext>
    );
    expect(screen.getByText(/waiting for analysis/i)).toBeInTheDocument();
  });

  it("renders suggestion items", () => {
    render(
      <DndContext>
        <AgentChatPanel
          {...baseProps}
          suggestionsSection={{
            ...baseSuggestionsSection,
            suggestions: [makeSuggestion()],
            getSuggestionPageLabel: () => "p.1",
          }}
        />
      </DndContext>
    );
    expect(screen.getByText("John Smith")).toBeInTheDocument();
    expect(screen.getByText("p.1")).toBeInTheDocument();
  });

  it("calls onSuggestionSelect when a suggestion item is clicked", () => {
    const onSelect = vi.fn();
    const suggestion = makeSuggestion();
    render(
      <DndContext>
        <AgentChatPanel
          {...baseProps}
          suggestionsSection={{
            ...baseSuggestionsSection,
            suggestions: [suggestion],
            onSuggestionSelect: onSelect,
          }}
        />
      </DndContext>
    );
    fireEvent.click(screen.getByText("John Smith"));
    expect(onSelect).toHaveBeenCalledWith(suggestion);
  });

  it("collapses the suggestions list when the toggle button is clicked", () => {
    render(
      <DndContext>
        <AgentChatPanel
          {...baseProps}
          suggestionsSection={{
            ...baseSuggestionsSection,
            suggestions: [makeSuggestion()],
          }}
        />
      </DndContext>
    );
    expect(screen.getByText("John Smith")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /toggle suggestions/i }));
    expect(screen.queryByText("John Smith")).not.toBeInTheDocument();
  });
});

describe("AgentChatPanel delete suggestion", () => {
  it("renders a delete button for each suggestion row", () => {
    const onDelete = vi.fn();

    render(
      <DndContext>
        <AgentChatPanel
          {...baseProps}
          suggestionsSection={{
            ...baseSuggestionsSection,
            suggestions: [makeSuggestion()],
            onDelete,
          }}
        />
      </DndContext>
    );

    expect(screen.getByRole("button", { name: /delete suggestion/i })).toBeInTheDocument();
  });

  it("calls onDelete with suggestion id when delete button is clicked", () => {
    const onDelete = vi.fn();

    render(
      <DndContext>
        <AgentChatPanel
          {...baseProps}
          suggestionsSection={{
            ...baseSuggestionsSection,
            suggestions: [makeSuggestion({ id: "s-abc" })],
            onDelete,
          }}
        />
      </DndContext>
    );

    fireEvent.click(screen.getByRole("button", { name: /delete suggestion/i }));
    expect(onDelete).toHaveBeenCalledWith("s-abc");
  });
});

import { act, renderHook } from "@testing-library/react";
import { useWorkspaceStore } from "@/store/workspace-store";

describe("useWorkspaceStore", () => {
  beforeEach(() => {
    useWorkspaceStore.getState().reset();
  });

  it("starts with no selected workspace", () => {
    const { result } = renderHook(() => useWorkspaceStore());
    expect(result.current.selectedWorkspaceId).toBeNull();
  });

  it("sets selected workspace", () => {
    const { result } = renderHook(() => useWorkspaceStore());
    act(() => result.current.setSelectedWorkspaceId("ws-123"));
    expect(result.current.selectedWorkspaceId).toBe("ws-123");
  });

  it("adds a drag context file without duplicates", () => {
    const { result } = renderHook(() => useWorkspaceStore());
    const file = { jobId: "j1", filename: "doc.pdf", workspaceId: "ws-1" };
    act(() => result.current.addDragContextFile(file));
    act(() => result.current.addDragContextFile(file));
    expect(result.current.chatContextFiles).toHaveLength(1);
  });

  it("removes a drag context file by jobId", () => {
    const { result } = renderHook(() => useWorkspaceStore());
    act(() => result.current.addDragContextFile({ jobId: "j1", filename: "doc.pdf", workspaceId: "ws-1" }));
    act(() => result.current.removeDragContextFile("j1"));
    expect(result.current.chatContextFiles).toHaveLength(0);
  });

  it("clears all context files", () => {
    const { result } = renderHook(() => useWorkspaceStore());
    act(() => result.current.addDragContextFile({ jobId: "j1", filename: "a.pdf", workspaceId: "ws-1" }));
    act(() => result.current.addDragContextFile({ jobId: "j2", filename: "b.pdf", workspaceId: "ws-1" }));
    act(() => result.current.clearChatContext());
    expect(result.current.chatContextFiles).toHaveLength(0);
  });
});

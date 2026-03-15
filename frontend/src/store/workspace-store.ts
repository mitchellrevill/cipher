import { create } from "zustand";

export interface ChatContextFile {
  jobId: string;
  filename: string;
  workspaceId: string;
}

interface WorkspaceStoreState {
  selectedWorkspaceId: string | null;
  chatContextFiles: ChatContextFile[];
  setSelectedWorkspaceId: (id: string | null) => void;
  addDragContextFile: (file: ChatContextFile) => void;
  removeDragContextFile: (jobId: string) => void;
  reset: () => void;
}

const INITIAL_STATE = {
  selectedWorkspaceId: null,
  chatContextFiles: [],
} satisfies Pick<WorkspaceStoreState, "selectedWorkspaceId" | "chatContextFiles">;

export const useWorkspaceStore = create<WorkspaceStoreState>((set) => ({
  ...INITIAL_STATE,
  setSelectedWorkspaceId: (id) => set({ selectedWorkspaceId: id }),
  addDragContextFile: (file) =>
    set((state) => ({
      chatContextFiles: state.chatContextFiles.some((entry) => entry.jobId === file.jobId)
        ? state.chatContextFiles
        : [...state.chatContextFiles, file],
    })),
  removeDragContextFile: (jobId) =>
    set((state) => ({
      chatContextFiles: state.chatContextFiles.filter((file) => file.jobId !== jobId),
    })),
  reset: () => set(INITIAL_STATE),
}));

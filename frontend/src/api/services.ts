import axios from "axios";
import api from "./client";
import { ENV } from "@/config/env";
import { useAuthStore } from "@/store";

export type JobStatus = "pending" | "processing" | "complete" | "failed";
export type SuggestionSource = "ai" | "manual" | "agent";

export interface RedactionRect {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

export interface Suggestion {
  id: string;
  job_id: string;
  text: string;
  category: string;
  reasoning: string;
  context: string;
  page_num: number;
  page_nums?: number[];
  rects: RedactionRect[];
  approved: boolean;
  source: SuggestionSource;
  created_at: string;
  updated_at?: string | null;
}

export interface RedactionJob {
  job_id: string;
  status: JobStatus;
  filename?: string | null;
  page_count: number;
  suggestions: Suggestion[];
  error?: string | null;
  created_at?: string | null;
  completed_at?: string | null;
  user_id?: string | null;
  suggestions_count: number;
  instructions?: string | null;
  workspace_id?: string | null;
}

export interface UploadDocumentInput {
  file: File;
  instructions?: string;
  workspaceId?: string;
}

export interface UploadDocumentResponse {
  job_id: string;
}

export interface ApplyRedactionsResponse {
  status: "applied";
  redaction_count: number;
}

export interface ApprovalUpdateResponse {
  id: string;
  approved: boolean;
}

export interface BulkApprovalResponse {
  approved: boolean;
  updated_count: number;
}

export interface AgentChatRequest {
  jobId: string;
  message: string;
  workspaceId?: string;
  sessionId?: string;
}

export interface AgentChatResponse {
  session_id: string;
  response: string;
}

export type AgentStreamEvent =
  | { type: "session"; session_id: string }
  | { type: "text_delta"; delta: string }
  | { type: "tool_start" | "tool_result" | "tool_error"; tool_name: string; summary?: string }
  | { type: "done"; response: string; session_id: string }
  | { type: "error"; error: string };

export interface WorkspaceRule {
  id: string;
  workspace_id: string;
  pattern: string;
  category: string;
  confidence_threshold: number;
  applies_to?: string[] | null;
  created_at?: string;
  updated_at?: string | null;
}

export interface WorkspaceExclusion {
  id: string;
  workspace_id: string;
  document_id: string;
  reason: string;
  created_at?: string;
}

export interface WorkspaceDocumentState {
  id: string;
  excluded?: boolean;
  reason?: string | null;
  filename?: string | null;
  status?: JobStatus | string | null;
  page_count?: number;
  suggestions_count?: number;
}

export interface WorkspaceState {
  id: string;
  user_id?: string;
  name: string;
  description?: string | null;
  document_ids?: string[];
  rule_ids?: string[];
  exclusion_ids?: string[];
  created_at?: string;
  updated_at?: string | null;
  documents: WorkspaceDocumentState[];
  rules: WorkspaceRule[];
  exclusions: WorkspaceExclusion[];
  stats?: {
    document_count: number;
    rule_count: number;
    exclusion_count: number;
  };
}

export interface WorkspaceListItem {
  id: string;
  name: string;
  description?: string | null;
  document_ids?: string[];
  rule_ids?: string[];
  exclusion_ids?: string[];
  created_at?: string;
  updated_at?: string | null;
}

export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string" && detail.length > 0) {
      return detail;
    }

    const message = error.response?.data?.message;
    if (typeof message === "string" && message.length > 0) {
      return message;
    }
  }

  if (error instanceof Error && error.message.length > 0) {
    return error.message;
  }

  return fallback;
}

class RedactionJobService {
  async uploadDocument({ file, instructions = "", workspaceId }: UploadDocumentInput): Promise<UploadDocumentResponse> {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("instructions", instructions);
    if (workspaceId) {
      formData.append("workspace_id", workspaceId);
    }

    const response = await api.post<UploadDocumentResponse>("/api/jobs", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });

    return response.data;
  }

  async listJobs(params: { skip?: number; limit?: number; unassigned?: boolean } = {}): Promise<RedactionJob[]> {
    const response = await api.get<RedactionJob[]>("/api/jobs", { params });
    return response.data;
  }

  async getJob(jobId: string): Promise<RedactionJob> {
    const response = await api.get<RedactionJob>(`/api/jobs/${jobId}`);
    return response.data;
  }

  async updateSuggestionApproval(jobId: string, suggestionId: string, approved: boolean): Promise<ApprovalUpdateResponse> {
    const response = await api.patch<ApprovalUpdateResponse>(`/api/jobs/${jobId}/redactions/${suggestionId}`, {
      approved,
    });

    return response.data;
  }

  async approveAllSuggestions(jobId: string): Promise<BulkApprovalResponse> {
    const response = await api.post<BulkApprovalResponse>(`/api/jobs/${jobId}/redactions/approve-all`);

    return response.data;
  }

  async addManualRedaction(jobId: string, pageNum: number, rects: RedactionRect[]): Promise<Suggestion> {
    const response = await api.post<Suggestion>(`/api/jobs/${jobId}/redactions/manual`, {
      page_num: pageNum,
      rects,
    });

    return response.data;
  }

  async applyRedactions(jobId: string): Promise<ApplyRedactionsResponse> {
    const response = await api.post<ApplyRedactionsResponse>(`/api/jobs/${jobId}/redactions/apply`);
    return response.data;
  }

  async downloadRedactedPdf(jobId: string): Promise<Blob> {
    const response = await api.get<Blob>(`/api/jobs/${jobId}/download`, {
      responseType: "blob",
    });

    return response.data;
  }

  async downloadOriginalPdf(jobId: string): Promise<Blob> {
    const response = await api.get<Blob>(`/api/jobs/${jobId}/download-original`, {
      responseType: "blob",
    });

    return response.data;
  }
}

class RedactionAgentService {
  async chat({ jobId, message, workspaceId, sessionId }: AgentChatRequest): Promise<AgentChatResponse> {
    const response = await api.post<AgentChatResponse>("/api/agent/chat", {
      job_id: jobId,
      message,
      workspace_id: workspaceId,
      session_id: sessionId,
    });

    return response.data;
  }

  async streamChat(
    { jobId, message, workspaceId, sessionId }: AgentChatRequest,
    handlers: {
      onEvent?: (event: AgentStreamEvent) => void;
      signal?: AbortSignal;
    } = {}
  ): Promise<void> {
    const token = useAuthStore.getState().token;
    const url = new URL("/api/agent/chat/stream", ENV.BACKEND_URL).toString();
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        job_id: jobId,
        message,
        workspace_id: workspaceId,
        session_id: sessionId,
      }),
      signal: handlers.signal,
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `Streaming chat failed with status ${response.status}`);
    }

    if (!response.body) {
      throw new Error("Streaming response body was empty.");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    const processEventChunk = (chunk: string) => {
      const lines = chunk.split(/\r?\n/);
      let eventName = "message";
      const dataLines: string[] = [];

      for (const line of lines) {
        if (line.startsWith("event:")) {
          eventName = line.slice(6).trim();
        } else if (line.startsWith("data:")) {
          dataLines.push(line.slice(5).trim());
        }
      }

      if (dataLines.length === 0) {
        return;
      }

      const payload = JSON.parse(dataLines.join("\n")) as Record<string, unknown>;
      const normalizedType = (typeof payload.type === "string" ? payload.type : eventName) as AgentStreamEvent["type"];

      switch (normalizedType) {
        case "session":
          if (typeof payload.session_id === "string") {
            handlers.onEvent?.({ type: "session", session_id: payload.session_id });
          }
          break;
        case "text_delta":
          if (typeof payload.delta === "string") {
            handlers.onEvent?.({ type: "text_delta", delta: payload.delta });
          }
          break;
        case "tool_start":
        case "tool_result":
        case "tool_error":
          if (typeof payload.tool_name === "string") {
            handlers.onEvent?.({
              type: normalizedType,
              tool_name: payload.tool_name,
              summary: typeof payload.summary === "string" ? payload.summary : undefined,
            });
          }
          break;
        case "done":
          if (typeof payload.response === "string" && typeof payload.session_id === "string") {
            handlers.onEvent?.({ type: "done", response: payload.response, session_id: payload.session_id });
          }
          break;
        case "error":
          if (typeof payload.error === "string") {
            handlers.onEvent?.({ type: "error", error: payload.error });
          }
          break;
      }
    };

    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });

      const chunks = buffer.split(/\r?\n\r?\n/);
      buffer = chunks.pop() ?? "";

      for (const chunk of chunks) {
        if (chunk.trim()) {
          processEventChunk(chunk);
        }
      }

      if (done) {
        if (buffer.trim()) {
          processEventChunk(buffer);
        }
        break;
      }
    }
  }
}

class WorkspaceServiceApi {
  async listWorkspaces(): Promise<WorkspaceListItem[]> {
    const response = await api.get<WorkspaceListItem[]>("/api/workspaces");
    return response.data;
  }

  async createWorkspace(name: string, description?: string): Promise<WorkspaceState> {
    const response = await api.post<WorkspaceState>("/api/workspaces", {
      name,
      description,
    });
    return response.data;
  }

  async getWorkspace(workspaceId: string): Promise<WorkspaceState> {
    const response = await api.get<WorkspaceState>(`/api/workspaces/${workspaceId}`);
    return response.data;
  }

  async addDocument(workspaceId: string, documentId: string): Promise<WorkspaceState> {
    const response = await api.post<WorkspaceState>(`/api/workspaces/${workspaceId}/documents`, {
      document_id: documentId,
    });
    return response.data;
  }

  async removeDocument(workspaceId: string, documentId: string): Promise<WorkspaceState> {
    const response = await api.delete<WorkspaceState>(`/api/workspaces/${workspaceId}/documents/${documentId}`);
    return response.data;
  }

  async createRule(
    workspaceId: string,
    payload: { pattern: string; category: string; confidenceThreshold?: number; appliesTo?: string[] }
  ): Promise<WorkspaceRule> {
    const response = await api.post<WorkspaceRule>(`/api/workspaces/${workspaceId}/rules`, {
      pattern: payload.pattern,
      category: payload.category,
      confidence_threshold: payload.confidenceThreshold ?? 0.8,
      applies_to: payload.appliesTo,
    });
    return response.data;
  }

  async excludeDocument(workspaceId: string, documentId: string, reason: string): Promise<WorkspaceExclusion> {
    const response = await api.post<WorkspaceExclusion>(`/api/workspaces/${workspaceId}/exclusions`, {
      document_id: documentId,
      reason,
    });
    return response.data;
  }

  async removeExclusion(workspaceId: string, exclusionId: string): Promise<WorkspaceState> {
    const response = await api.delete<WorkspaceState>(`/api/workspaces/${workspaceId}/exclusions/${exclusionId}`);
    return response.data;
  }
}

export const redactionJobService = new RedactionJobService();
export const redactionAgentService = new RedactionAgentService();
export const workspaceService = new WorkspaceServiceApi();

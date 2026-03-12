import axios from "axios";
import api from "./client";

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
}

export interface UploadDocumentInput {
  file: File;
  instructions?: string;
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

export interface AgentChatRequest {
  jobId: string;
  message: string;
  sessionId?: string;
  previousResponseId?: string;
}

export interface AgentChatResponse {
  session_id: string;
  response: string;
  response_id: string;
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
  async uploadDocument({ file, instructions = "" }: UploadDocumentInput): Promise<UploadDocumentResponse> {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("instructions", instructions);

    const response = await api.post<UploadDocumentResponse>("/api/jobs", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });

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
}

class RedactionAgentService {
  async chat({ jobId, message, sessionId, previousResponseId }: AgentChatRequest): Promise<AgentChatResponse> {
    const response = await api.post<AgentChatResponse>("/api/agent/chat", {
      job_id: jobId,
      message,
      session_id: sessionId,
      previous_response_id: previousResponseId,
    });

    return response.data;
  }
}

export const redactionJobService = new RedactionJobService();
export const redactionAgentService = new RedactionAgentService();

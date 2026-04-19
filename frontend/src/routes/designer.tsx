import React, { startTransition, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { DndContext } from "@dnd-kit/core";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "@tanstack/react-router";
import {
  ArrowUpFromLine,
  CheckSquare,
  ChevronLeft,
  ChevronRight,
  Download,
  Loader2,
  Plus,
  ShieldCheck,
  WandSparkles,
  X,
} from "lucide-react";
import {
  getApiErrorMessage,
  redactionAgentService,
  redactionJobService,
  workspaceService,
  type AgentStreamEvent,
  type RedactionJob,
  type Suggestion,
} from "@/api/services";
import {
  AgentChatPanel,
  type AgentConversationState,
  type AgentToolEvent,
} from "@/components/chat/agent-chat-panel";
import { PdfDocumentViewer } from "@/components/pdf/pdf-document-viewer";
import { SearchToolbar } from "@/components/search/SearchToolbar";
import { AddToWorkspaceDialog } from "@/components/workspace/add-to-workspace-dialog";
import { CreateWorkspaceDialog } from "@/components/workspace/create-workspace-dialog";
import { WorkspaceChatHeader } from "@/components/workspace/workspace-chat-header";
import { WorkspaceExclusionsSlideover } from "@/components/workspace/workspace-exclusions-slideover";
import { WorkspaceRulesSlideover } from "@/components/workspace/workspace-rules-slideover";
import {
  Badge,
  Button,
  Label,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Textarea,
} from "@/components/ui";
import { usePageProcessingStatus, useSuggestionStreamListener, useRedactionHotkeys } from "@/hooks";
import { useFuzzySearch } from "@/hooks/useFuzzySearch";
import { useRecentJobs } from "@/hooks/useRecentJobs";
import { queryClient } from "@/lib/query-client";
import {
  getLocalPdfUrl,
  registerLocalPdf,
  upsertRecentJob,
  type RecentJobRecord,
} from "@/lib/recent-jobs";
import { cn, formatBytes } from "@/lib/utils";
import { useUIStore, useWorkspaceStore } from "@/store";
import type { TextMatch } from "@/types/search";
import { toast } from "sonner";

const EMPTY_CONVERSATION: AgentConversationState = { messages: [] };

const AGENT_PROMPT_PRESETS = [
  "Search this document for names, emails, and phone numbers I may have missed.",
  "Find context-aware redactions around addresses, account numbers, and related references.",
  "Summarize the riskiest pages and tell me where to jump next.",
];

const NO_WORKSPACE_VALUE = "__no-workspace__";

function StatusBadge({ status }: { status: RecentJobRecord["status"] }) {
  const cls =
    status === "complete"
      ? "bg-emerald-500/12 text-emerald-700 dark:text-emerald-300"
      : status === "failed"
        ? "bg-destructive/12 text-destructive"
        : "bg-amber-500/12 text-amber-700 dark:text-amber-300";
  return (
    <Badge variant="secondary" className={cn("rounded-full border-0 capitalize text-xs", cls)}>
      {status}
    </Badge>
  );
}

function sortSuggestions(suggestions: Suggestion[]): Suggestion[] {
  return [...suggestions].sort((a, b) => {
    if (a.page_num !== b.page_num) return a.page_num - b.page_num;
    return Number(a.approved) - Number(b.approved);
  });
}

export default function DocumentsRoute() {
  const navigate = useNavigate();
  const { recentJobs } = useRecentJobs();
  const setSidebarOpen = useUIStore((s) => s.setSidebarOpen);
  const selectedWorkspaceId = useWorkspaceStore((state) => state.selectedWorkspaceId);
  const setSelectedWorkspaceId = useWorkspaceStore((state) => state.setSelectedWorkspaceId);

  const { workspaceId: urlWorkspaceId, jobId } = useParams({ strict: false }) as {
    workspaceId?: string;
    jobId?: string;
  };

  useEffect(() => {
    if (urlWorkspaceId) {
      setSelectedWorkspaceId(urlWorkspaceId);
    }
  }, [urlWorkspaceId, setSelectedWorkspaceId]);

  const [selectedJobId, setSelectedJobId] = useState<string | null>(jobId ?? null);
  const userClearedSelectionRef = useRef(false);
  const [, setLocalPdfCacheVersion] = useState(0);
  const [dragOver, setDragOver] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [instructions, setInstructions] = useState(
    "Flag personal data, contact details, financial identifiers, and any free-form contextual references that could expose identity."
  );
  const [viewerMode, setViewerMode] = useState<"original" | "redacted">("original");
  const [drawMode, setDrawMode] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeSearchMatchIndex, setActiveSearchMatchIndex] = useState(-1);
  const [pdfDocument, setPdfDocument] = useState<any>(null);
  const { matches: searchMatches, totalMatches, isSearching: isSearching_fuzzy, error: searchError } = useFuzzySearch(
    pdfDocument,
    searchQuery
  );
  const [selectedSuggestionId, setSelectedSuggestionId] = useState<string | null>(null);
  const [chatInput, setChatInput] = useState("");
  const [chatByJob, setChatByJob] = useState<Record<string, AgentConversationState>>({});
  const [streamingJobId, setStreamingJobId] = useState<string | null>(null);
  const [redactedPreviewUrls, setRedactedPreviewUrls] = useState<Record<string, string>>({});
  const [chatCollapsed, setChatCollapsed] = useState(true);
  const [createWorkspaceOpen, setCreateWorkspaceOpen] = useState(false);
  const [addToWorkspaceOpen, setAddToWorkspaceOpen] = useState(false);
  const [rulesOpen, setRulesOpen] = useState(false);
  const [exclusionsOpen, setExclusionsOpen] = useState(false);
  const [focusPageRequest, setFocusPageRequest] = useState<{ pageNumber: number; requestId: number } | null>(null);
  const redactedPreviewUrlsRef = useRef<Record<string, string>>({});
  const chatAbortRef = useRef<AbortController | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    redactedPreviewUrlsRef.current = redactedPreviewUrls;
  }, [redactedPreviewUrls]);

  useEffect(() => {
    return () => {
      Object.values(redactedPreviewUrlsRef.current).forEach((url) => URL.revokeObjectURL(url));
      chatAbortRef.current?.abort();
    };
  }, []);

  useEffect(() => {
    setSelectedJobId(jobId ?? null);
  }, [jobId]);

  const selectedRecentJob = useMemo(
    () => recentJobs.find((job) => job.jobId === selectedJobId) ?? null,
    [recentJobs, selectedJobId]
  );

  const jobQuery = useQuery({
    queryKey: ["redaction-job", selectedJobId],
    enabled: !!selectedJobId,
    queryFn: () => redactionJobService.getJob(selectedJobId!),
    refetchInterval: ({ state }) => {
      const job = state.data as RedactionJob | undefined;
      return job && (job.status === "pending" || job.status === "processing") ? 2000 : false;
    },
  });

  const workspacesQuery = useQuery({
    queryKey: ["workspaces"],
    queryFn: () => workspaceService.listWorkspaces(),
  });

  const workspaceQuery = useQuery({
    queryKey: ["workspace", selectedWorkspaceId],
    enabled: !!selectedWorkspaceId,
    queryFn: () => workspaceService.getWorkspace(selectedWorkspaceId!),
  });

  useEffect(() => {
    const job = jobQuery.data;
    if (!job || !selectedJobId) return;
    upsertRecentJob({
      jobId: job.job_id,
      filename: job.filename ?? selectedRecentJob?.filename ?? "untitled.pdf",
      createdAt: job.created_at ?? selectedRecentJob?.createdAt ?? new Date().toISOString(),
      status: job.status,
      suggestionsCount: job.suggestions.length,
      fileSize: selectedRecentJob?.fileSize,
      completedAt: job.completed_at ?? undefined,
      error: job.error ?? undefined,
      hasRedactedPdf: selectedRecentJob?.hasRedactedPdf,
    });
  }, [jobQuery.data, selectedJobId, selectedRecentJob]);

  const activeJob = jobQuery.data;
  const activeWorkspace = workspaceQuery.data ?? null;

  useEffect(() => {
    // When a URL workspace is set (e.g. /workspace/$id/designer), let it take precedence.
    if (urlWorkspaceId) return;
    // Don't touch workspace selection while no job is loaded.
    if (!activeJob) return;
    // Sync workspace selection to the active job's assigned workspace (or clear it).
    setSelectedWorkspaceId(activeJob.workspace_id ?? null);
  }, [activeJob?.job_id, activeJob?.workspace_id, urlWorkspaceId, setSelectedWorkspaceId]);

  // Initialize page processing status tracking
  const {
    pageStatus,
    updatePageStatus,
    getStageLabel,
  } = usePageProcessingStatus(activeJob?.suggestions?.length ?? 0);

  // Initialize suggestion streaming listener
  useSuggestionStreamListener(
    selectedJobId,
    (pageNum, stage) => {
      updatePageStatus(pageNum, stage as any);
    },
    (suggestion) => {
      // Suggestion received via SSE - log for now
      console.log("New suggestion via stream:", suggestion);
    }
  );

  const sortedSuggestions = useMemo(() => sortSuggestions(activeJob?.suggestions ?? []), [activeJob?.suggestions]);
  const approvedCount = useMemo(() => sortedSuggestions.filter((s) => s.approved).length, [sortedSuggestions]);
  const activeSearchMatch = useMemo(
    () =>
      activeSearchMatchIndex >= 0 && activeSearchMatchIndex < searchMatches.length
        ? searchMatches[activeSearchMatchIndex]
        : null,
    [activeSearchMatchIndex, searchMatches]
  );
  const pageCount = pdfDocument?.numPages ?? activeJob?.page_count ?? 0;
  const prefersOneBasedSuggestionPages = useMemo(() => {
    if (!pageCount || sortedSuggestions.length === 0) {
      return false;
    }

    return (
      sortedSuggestions.every((suggestion) => suggestion.page_num >= 1) &&
      sortedSuggestions.some((suggestion) => suggestion.page_num === pageCount)
    );
  }, [pageCount, sortedSuggestions]);
  const localPdfUrl = selectedJobId ? getLocalPdfUrl(selectedJobId) : null;
  const redactedPreviewUrl = selectedJobId ? redactedPreviewUrls[selectedJobId] : undefined;

  useEffect(() => {
    if (!searchQuery.trim() || searchMatches.length === 0) {
      setActiveSearchMatchIndex(-1);
      return;
    }

    setActiveSearchMatchIndex((currentIndex) => {
      if (currentIndex >= 0 && currentIndex < searchMatches.length) {
        return currentIndex;
      }

      return 0;
    });
  }, [searchMatches, searchQuery]);

  useEffect(() => {
    if (viewerMode === "original" && !localPdfUrl && redactedPreviewUrl) setViewerMode("redacted");
  }, [localPdfUrl, redactedPreviewUrl, viewerMode]);

  // Load original PDF from server if not in local cache
  useEffect(() => {
    if (!selectedJobId || localPdfUrl) return;

    const loadPdfFromServer = async () => {
      try {
        await loadOriginalPdf(selectedJobId);
        // registerLocalPdf updates an in-memory Map (no React state), so we must
        // trigger a re-render to pick up the new localPdfUrl from the registry.
        setLocalPdfCacheVersion((v) => v + 1);
      } catch (error) {
        // Silently fail — PDF might not be available yet or user can view redacted version
        console.debug("Original PDF not available from server");
      }
    };

    void loadPdfFromServer();
  }, [selectedJobId, localPdfUrl]);

  useEffect(() => {
    if (selectedSuggestionId && !sortedSuggestions.some((s) => s.id === selectedSuggestionId)) {
      setSelectedSuggestionId(null);
    }
  }, [selectedSuggestionId, sortedSuggestions]);

  const viewerSource = useMemo(() => {
    if (viewerMode === "original" && localPdfUrl) return { url: localPdfUrl, label: "Original" };
    if (viewerMode === "redacted" && redactedPreviewUrl) return { url: redactedPreviewUrl, label: "Redacted" };
    if (localPdfUrl) return { url: localPdfUrl, label: "Original" };
    if (redactedPreviewUrl) return { url: redactedPreviewUrl, label: "Redacted" };
    return undefined;
  }, [localPdfUrl, redactedPreviewUrl, viewerMode]);

  const canDraw = viewerMode === "original" && !!localPdfUrl && !!selectedJobId;
  const conversation = selectedJobId ? chatByJob[selectedJobId] ?? EMPTY_CONVERSATION : EMPTY_CONVERSATION;
  const isChatStreaming = selectedJobId !== null && streamingJobId === selectedJobId;
  const isReviewMode = !!selectedJobId;

  const updateConversation = useCallback(
    (jobId: string, updater: (current: AgentConversationState) => AgentConversationState) => {
      setChatByJob((current) => ({
        ...current,
        [jobId]: updater(current[jobId] ?? EMPTY_CONVERSATION),
      }));
    },
    []
  );

  const appendToolEvent = useCallback(
    (jobId: string, assistantMessageId: string, event: AgentToolEvent) => {
      updateConversation(jobId, (current) => ({
        ...current,
        messages: current.messages.map((message) =>
          message.id === assistantMessageId
            ? {
                ...message,
                toolEvents: [...(message.toolEvents ?? []), event],
              }
            : message
        ),
      }));
    },
    [updateConversation]
  );

  const getSuggestionViewerPageNumber = useCallback(
    (suggestion: Suggestion | null) => {
      if (!suggestion || pageCount <= 0) {
        return null;
      }

      const rawPage = suggestion.page_nums?.[0] ?? suggestion.page_num;
      const oneBasedPage = prefersOneBasedSuggestionPages ? rawPage : rawPage + 1;

      return Math.max(1, Math.min(pageCount, oneBasedPage));
    },
    [pageCount, prefersOneBasedSuggestionPages]
  );

  const getSuggestionPageLabel = useCallback(
    (suggestion: Suggestion) => {
      if (suggestion.page_nums && suggestion.page_nums.length > 0) {
        return `pp. ${suggestion.page_nums.map((p) => p + 1).join(", ")}`;
      }
      const page = getSuggestionViewerPageNumber(suggestion);
      return `p.${page ?? suggestion.page_num + 1}`;
    },
    [getSuggestionViewerPageNumber]
  );

  const requestPageFocus = useCallback(
    (pageNumber: number) => {
      if (pageCount <= 0) {
        return;
      }

      const normalizedPage = Math.max(1, Math.min(pageCount, Math.floor(pageNumber)));
      setFocusPageRequest((current) => ({
        pageNumber: normalizedPage,
        requestId: (current?.requestId ?? 0) + 1,
      }));
    },
    [pageCount]
  );

  const refreshWorkspaceQueries = useCallback(
    (workspaceId?: string | null) => {
      void queryClient.invalidateQueries({ queryKey: ["workspaces"] });
      if (workspaceId) {
        void queryClient.invalidateQueries({ queryKey: ["workspace", workspaceId] });
      }
    },
    []
  );

  // Initialize hotkeys for review mode
  useRedactionHotkeys({
    selectedSuggestionId,
    suggestions: sortedSuggestions,
    onSuggestionSelect: setSelectedSuggestionId,
    onApprovalChange: (suggestionId, approved) =>
      approvalMutation.mutate({ suggestionId, approved }),
    onApproveAll: () => void approveAllMutation.mutateAsync(),
  });

  async function loadRedactedPreview(jobId: string): Promise<string> {
    const blob = await redactionJobService.downloadRedactedPdf(jobId);
    const objectUrl = URL.createObjectURL(blob);
    setRedactedPreviewUrls((cur) => {
      const prev = cur[jobId];
      if (prev) URL.revokeObjectURL(prev);
      return { ...cur, [jobId]: objectUrl };
    });
    upsertRecentJob({
      jobId,
      filename: selectedRecentJob?.filename ?? activeJob?.filename ?? "redacted.pdf",
      createdAt: selectedRecentJob?.createdAt ?? activeJob?.created_at ?? new Date().toISOString(),
      status: activeJob?.status ?? "complete",
      suggestionsCount: activeJob?.suggestions.length ?? 0,
      fileSize: selectedRecentJob?.fileSize,
      completedAt: activeJob?.completed_at ?? undefined,
      error: activeJob?.error ?? undefined,
      hasRedactedPdf: true,
    });
    return objectUrl;
  }

  async function loadOriginalPdf(jobId: string): Promise<string> {
    try {
      const blob = await redactionJobService.downloadOriginalPdf(jobId);
      const objectUrl = URL.createObjectURL(blob);
      registerLocalPdf(jobId, new File([blob], selectedRecentJob?.filename ?? "original.pdf", { type: "application/pdf" }));
      return objectUrl;
    } catch (error) {
      console.error("Failed to load original PDF from server:", error);
      throw error;
    }
  }

  const uploadMutation = useMutation({
    mutationFn: redactionJobService.uploadDocument,
    onSuccess: async ({ job_id }, variables) => {
      registerLocalPdf(job_id, variables.file);
      upsertRecentJob({
        jobId: job_id,
        filename: variables.file.name,
        createdAt: new Date().toISOString(),
        status: "pending",
        suggestionsCount: 0,
        fileSize: variables.file.size,
      });
      setSelectedJobId(job_id);
      setSelectedFile(null);
      setViewerMode("original");
      setDrawMode(false);
      setSelectedSuggestionId(null);
      setSidebarOpen(false);
      await queryClient.invalidateQueries({ queryKey: ["redaction-job", job_id] });
      refreshWorkspaceQueries(selectedWorkspaceId);
      const targetWorkspaceId = selectedWorkspaceId ?? urlWorkspaceId;
      if (targetWorkspaceId) {
        void navigate({
          to: "/workspace/$workspaceId/designer/$jobId",
          params: { workspaceId: targetWorkspaceId, jobId: job_id },
        });
      } else {
        void navigate({ to: "/designer/$jobId", params: { jobId: job_id } });
      }
      toast.success("Upload accepted – processing started.");
    },
    onError: (error) => {
      toast.error(getApiErrorMessage(error, "Unable to upload the PDF."));
    },
  });

  const approvalMutation = useMutation({
    mutationFn: ({ suggestionId, approved }: { suggestionId: string; approved: boolean }) =>
      redactionJobService.updateSuggestionApproval(selectedJobId!, suggestionId, approved),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["redaction-job", selectedJobId] });
    },
    onError: (error) => toast.error(getApiErrorMessage(error, "Unable to update suggestion.")),
  });

  const approveAllMutation = useMutation({
    mutationFn: () => redactionJobService.approveAllSuggestions(selectedJobId!),
    onSuccess: async ({ updated_count }) => {
      queryClient.setQueryData<RedactionJob | undefined>(["redaction-job", selectedJobId], (currentJob) => {
        if (!currentJob || updated_count === 0) {
          return currentJob;
        }

        return {
          ...currentJob,
          suggestions: currentJob.suggestions.map((suggestion) =>
            suggestion.approved
              ? suggestion
              : {
                  ...suggestion,
                  approved: true,
                }
          ),
        };
      });

      if (updated_count > 0) {
        toast.success(`Approved ${updated_count} suggestions.`);
        return;
      }

      toast.success("All suggestions were already approved.");
    },
    onError: (error) => toast.error(getApiErrorMessage(error, "Unable to approve all suggestions.")),
  });

  const deleteSuggestionMutation = useMutation({
    mutationFn: (suggestionId: string) => redactionJobService.deleteSuggestion(selectedJobId!, suggestionId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["redaction-job", selectedJobId] });
    },
    onError: (error) => toast.error(getApiErrorMessage(error, "Failed to delete suggestion.")),
  });

  const manualRedactionMutation = useMutation({
    mutationFn: ({ pageIndex, rects }: { pageIndex: number; rects: Suggestion["rects"] }) =>
      redactionJobService.addManualRedaction(selectedJobId!, pageIndex, rects),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["redaction-job", selectedJobId] });
      toast.success("Manual redaction added.");
    },
    onError: (error) => toast.error(getApiErrorMessage(error, "Unable to save manual redaction.")),
  });

  const redactAllSearchMatchesMutation = useMutation({
    mutationFn: async () => {
      if (!selectedJobId) {
        throw new Error("Select a job first.");
      }

      const matchesByPage = new Map<number, Suggestion["rects"]>();

      for (const match of searchMatches) {
        if (match.rects.length === 0) {
          continue;
        }

        const existingRects = matchesByPage.get(match.pageNum) ?? [];
        matchesByPage.set(match.pageNum, [...existingRects, ...match.rects]);
      }

      const pageEntries = Array.from(matchesByPage.entries());

      if (pageEntries.length === 0) {
        return { redactedMatches: 0, affectedPages: 0 };
      }

      await Promise.all(
        pageEntries.map(([pageIndex, rects]) =>
          redactionJobService.addManualRedaction(selectedJobId, pageIndex, rects)
        )
      );

      return {
        redactedMatches: searchMatches.length,
        affectedPages: pageEntries.length,
      };
    },
    onSuccess: async ({ redactedMatches, affectedPages }) => {
      await queryClient.invalidateQueries({ queryKey: ["redaction-job", selectedJobId] });

      if (redactedMatches === 0) {
        toast.info("No search matches available to redact.");
        return;
      }

      toast.success(
        `Redacted ${redactedMatches} ${redactedMatches === 1 ? "instance" : "instances"} across ${affectedPages} ${affectedPages === 1 ? "page" : "pages"}.`
      );
    },
    onError: (error) => toast.error(getApiErrorMessage(error, "Unable to redact all search matches.")),
  });

  const applyMutation = useMutation({
    mutationFn: () => redactionJobService.applyRedactions(selectedJobId!),
    onSuccess: async (result) => {
      toast.success(`Applied ${result.redaction_count} redactions.`);
      if (selectedJobId) {
        try {
          await loadRedactedPreview(selectedJobId);
          setViewerMode("redacted");
        } catch (error) {
          toast.error(getApiErrorMessage(error, "Redactions applied but preview unavailable."));
        }
      }
    },
    onError: (error) => toast.error(getApiErrorMessage(error, "Unable to apply redactions.")),
  });

  const handleSelectJob = (jobId: string) => {
    startTransition(() => setSelectedJobId(jobId));
    setViewerMode(getLocalPdfUrl(jobId) ? "original" : "redacted");
    setDrawMode(false);
    setSelectedSuggestionId(null);
    setSidebarOpen(false);

    const targetWorkspaceId = selectedWorkspaceId ?? urlWorkspaceId;
    if (targetWorkspaceId) {
      void navigate({
        to: "/workspace/$workspaceId/designer/$jobId",
        params: { workspaceId: targetWorkspaceId, jobId },
      });
      return;
    }

    void navigate({ to: "/designer/$jobId", params: { jobId } });
  };

  const handleFileDrop = useCallback((file: File) => {
    if (file.type !== "application/pdf") {
      toast.error("Cipher supports PDF files only.");
      return;
    }
    setSelectedFile(file);
  }, []);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = () => setDragOver(false);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileDrop(file);
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFileDrop(file);
  };

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      toast.error("Drop a PDF first.");
      return;
    }
    await uploadMutation.mutateAsync({
      file: selectedFile,
      instructions,
      workspaceId: selectedWorkspaceId ?? undefined,
    });
  };

  const handleDownload = async () => {
    if (!selectedJobId) return;
    try {
      const url = redactedPreviewUrl ?? (await loadRedactedPreview(selectedJobId));
      const a = document.createElement("a");
      a.href = url;
      a.download = `${(selectedRecentJob?.filename ?? "document").replace(/\.pdf$/i, "")}_redacted.pdf`;
      a.click();
      setViewerMode("redacted");
    } catch (error) {
      toast.error(getApiErrorMessage(error, "No redacted PDF available yet."));
    }
  };

  const handleChatSubmit = useCallback(() => {
    const trimmed = chatInput.trim();
    if (!trimmed || !selectedJobId || isChatStreaming) return;

    const jobId = selectedJobId;
    const message = trimmed;
    const assistantMessageId = `assistant-${Date.now()}`;
    const userMessageId = `user-${Date.now()}`;
    const existingConversation = chatByJob[jobId] ?? EMPTY_CONVERSATION;

    setChatInput("");
    setStreamingJobId(jobId);
    chatAbortRef.current?.abort();
    const controller = new AbortController();
    chatAbortRef.current = controller;

    updateConversation(jobId, (current) => ({
      ...current,
      messages: [
        ...current.messages,
        { id: userMessageId, role: "user", text: message },
        { id: assistantMessageId, role: "assistant", text: "", status: "streaming", toolEvents: [] },
      ],
    }));

    const handleStreamEvent = (event: AgentStreamEvent) => {
      switch (event.type) {
        case "session":
          updateConversation(jobId, (current) => ({ ...current, sessionId: event.session_id }));
          break;
        case "text_delta":
          updateConversation(jobId, (current) => ({
            ...current,
            messages: current.messages.map((chatMessage) =>
              chatMessage.id === assistantMessageId
                ? { ...chatMessage, text: `${chatMessage.text}${event.delta}`, status: "streaming" }
                : chatMessage
            ),
          }));
          break;
        case "tool_start":
          appendToolEvent(jobId, assistantMessageId, {
            id: `tool_start-${event.tool_name}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
            type: "tool_start",
            toolName: event.tool_name,
            summary: event.summary,
          });
          break;
        case "tool_result":
        case "tool_error": {
          // Transition the most recent matching tool_start card rather than adding a new one
          const terminalType = event.type;
          updateConversation(jobId, (current) => ({
            ...current,
            messages: current.messages.map((chatMessage) => {
              if (chatMessage.id !== assistantMessageId) return chatMessage;
              const toolEvents = chatMessage.toolEvents ?? [];
              const reversedIdx = [...toolEvents]
                .reverse()
                .findIndex((e) => e.type === "tool_start" && e.toolName === event.tool_name);
              const startIdx = reversedIdx === -1 ? -1 : toolEvents.length - 1 - reversedIdx;
              if (startIdx === -1) {
                return {
                  ...chatMessage,
                  toolEvents: [
                    ...toolEvents,
                    {
                      id: `${terminalType}-${event.tool_name}-${Date.now()}`,
                      type: terminalType,
                      toolName: event.tool_name,
                      summary: event.summary,
                    },
                  ],
                };
              }
              return {
                ...chatMessage,
                toolEvents: toolEvents.map((e, i) =>
                  i === startIdx
                    ? { ...e, type: terminalType, summary: event.summary }
                    : e
                ),
              };
            }),
          }));
          break;
        }
        case "done":
          updateConversation(jobId, (current) => ({
            ...current,
            sessionId: event.session_id,
            messages: current.messages.map((chatMessage) =>
              chatMessage.id === assistantMessageId
                ? {
                    ...chatMessage,
                    text: chatMessage.text || event.response,
                    status: "done",
                  }
                : chatMessage
            ),
          }));
          // Refresh job suggestions + workspace state so agent-created rules/suggestions appear immediately
          void queryClient.invalidateQueries({ queryKey: ["redaction-job", jobId] });
          if (selectedWorkspaceId) {
            void queryClient.invalidateQueries({ queryKey: ["workspace", selectedWorkspaceId] });
            void queryClient.invalidateQueries({ queryKey: ["workspaces"] });
          }
          break;
        case "error":
          updateConversation(jobId, (current) => ({
            ...current,
            messages: current.messages.map((chatMessage) =>
              chatMessage.id === assistantMessageId
                ? {
                    ...chatMessage,
                    text: chatMessage.text || event.error,
                    status: "error",
                  }
                : chatMessage
            ),
          }));
          break;
      }
    };

    void redactionAgentService
      .streamChat(
        {
          jobId,
          message,
          workspaceId: selectedWorkspaceId ?? undefined,
          sessionId: existingConversation.sessionId,
        },
        {
          signal: controller.signal,
          onEvent: handleStreamEvent,
        }
      )
      .catch((error) => {
        if (controller.signal.aborted) {
          return;
        }

        updateConversation(jobId, (current) => ({
          ...current,
          messages: current.messages.map((chatMessage) =>
            chatMessage.id === assistantMessageId
              ? {
                  ...chatMessage,
                  text: chatMessage.text || getApiErrorMessage(error, "Assistant could not respond."),
                  status: "error",
                }
              : chatMessage
          ),
        }));
        toast.error(getApiErrorMessage(error, "Assistant could not respond."));
      })
      .finally(() => {
        setStreamingJobId((current) => (current === jobId ? null : current));
        if (chatAbortRef.current === controller) {
          chatAbortRef.current = null;
        }
      });
  }, [appendToolEvent, chatByJob, chatInput, isChatStreaming, selectedJobId, selectedWorkspaceId, updateConversation]);

  const handleQuickPrompt = (prompt: string) => {
    setChatInput(prompt);
  };

  const handleClearSearch = () => {
    setSearchQuery("");
    setActiveSearchMatchIndex(-1);
  };

  const handleFindNextMatch = () => {
    if (searchMatches.length === 0) {
      return;
    }

    setActiveSearchMatchIndex((currentIndex) => {
      if (currentIndex < 0) {
        return 0;
      }

      return (currentIndex + 1) % searchMatches.length;
    });
  };

  const renderMessageWithPageTokens = useCallback(
    (text: string) => {
      const parts = text.split(/(\[\[page:\d+\]\])/g);
      return parts.map((part, i) => {
        const match = /^\[\[page:(\d+)\]\]$/.exec(part);
        if (match) {
          const page = parseInt(match[1], 10);
          return (
            <button
              key={i}
              type="button"
              onClick={() => requestPageFocus(page)}
              className="inline-flex items-center gap-1 rounded-full border border-primary/30 bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary hover:bg-primary/20 transition-colors mx-0.5"
            >
              ↗ p.{page}
            </button>
          );
        }
        return <span key={i}>{part}</span>;
      });
    },
    [requestPageFocus]
  );

  const handleSuggestionSelect = (suggestion: Suggestion) => {
    setSelectedSuggestionId(suggestion.id);

    const targetPage = getSuggestionViewerPageNumber(suggestion);
    if (targetPage) {
      requestPageFocus(targetPage);
    }
  };

  // ──────────────────────────────────────────────────
  // UPLOAD MODE
  // ──────────────────────────────────────────────────
  if (!isReviewMode) {
    return (
      <>
        <div className="h-full overflow-auto flex flex-col items-center justify-center px-4 py-16">
          <div className="w-full max-w-lg space-y-8">
          {/* Header */}
            <div className="space-y-1 text-center">
              <div className="flex items-center justify-center gap-2 text-muted-foreground mb-3">
                <ShieldCheck className="h-6 w-6" />
              </div>
              <h1 className="text-2xl font-semibold tracking-tight">Redaction Workspace</h1>
              <p className="text-sm text-muted-foreground">Drop a PDF to begin AI-assisted redaction</p>
            </div>

            <form onSubmit={handleUploadSubmit} className="space-y-4">
            {/* Drag and drop zone */}
              <div
                className={cn(
                  "relative flex flex-col items-center justify-center rounded-2xl border-2 border-dashed p-12 text-center transition-colors cursor-pointer",
                  dragOver
                    ? "border-primary bg-primary/5"
                    : selectedFile
                      ? "border-emerald-500/50 bg-emerald-500/5"
                      : "border-border hover:border-muted-foreground/40 hover:bg-muted/20"
                )}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => e.key === "Enter" && fileInputRef.current?.click()}
                aria-label="Upload PDF"
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="application/pdf"
                  className="sr-only"
                  onChange={handleFileInput}
                />
                {selectedFile ? (
                  <>
                    <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
                      <ShieldCheck className="h-6 w-6" />
                    </div>
                    <div className="font-medium text-foreground">{selectedFile.name}</div>
                    <div className="mt-1 text-sm text-muted-foreground">
                      {formatBytes(selectedFile.size)} · Click to change
                    </div>
                    <button
                      type="button"
                      className="absolute right-3 top-3 rounded-full p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedFile(null);
                      }}
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </>
                ) : (
                  <>
                    <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-muted text-muted-foreground">
                      <ArrowUpFromLine className="h-6 w-6" />
                    </div>
                    <div className="font-medium text-foreground">
                      {dragOver ? "Drop to upload" : "Drop PDF here"}
                    </div>
                    <div className="mt-1 text-sm text-muted-foreground">or click to browse</div>
                  </>
                )}
              </div>

            {/* Instructions */}
              <div className="space-y-1.5">
                <Label htmlFor="instructions" className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Redaction instructions
                </Label>
                <Textarea
                  id="instructions"
                  value={instructions}
                  onChange={(e) => setInstructions((e as React.ChangeEvent<HTMLTextAreaElement>).target.value)}
                  placeholder="Describe what to redact…"
                  className="resize-none text-sm"
                  rows={3}
                />
              </div>

              <div className="space-y-1.5">
                <div className="flex items-center justify-between gap-2">
                  <Label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Workspace
                  </Label>
                  <Button type="button" variant="ghost" className="h-7 px-2 text-xs" onClick={() => setCreateWorkspaceOpen(true)}>
                    <Plus className="mr-1 h-3.5 w-3.5" />
                    New
                  </Button>
                </div>
                <Select
                  value={selectedWorkspaceId ?? NO_WORKSPACE_VALUE}
                  onValueChange={(value) => setSelectedWorkspaceId(value === NO_WORKSPACE_VALUE ? null : value)}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="No workspace selected" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={NO_WORKSPACE_VALUE}>No workspace</SelectItem>
                    {(workspacesQuery.data ?? []).map((workspace) => (
                      <SelectItem key={workspace.id} value={workspace.id}>
                        {workspace.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  {selectedWorkspaceId
                    ? "The upload will be attached to the selected workspace automatically."
                    : "Optional: select a workspace to share rules and exclusions across related documents."}
                </p>
              </div>

              <Button
                type="submit"
                size="lg"
                className="w-full"
                disabled={!selectedFile || uploadMutation.isPending}
              >
                {uploadMutation.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <WandSparkles className="mr-2 h-4 w-4" />
                )}
                Analyze document
              </Button>
            </form>

          {/* Recent jobs */}
            {recentJobs.length > 0 && (
              <div className="space-y-2">
                <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Recent sessions
                </div>
                <div className="space-y-1.5">
                  {recentJobs.slice(0, 5).map((job) => (
                    <button
                      key={job.jobId}
                      type="button"
                      onClick={() => handleSelectJob(job.jobId)}
                      className="flex w-full items-center justify-between rounded-xl border border-border/70 px-3 py-2.5 text-left text-sm transition-colors hover:bg-muted/40"
                    >
                      <div className="min-w-0">
                        <div className="truncate font-medium text-foreground">{job.filename}</div>
                        <div className="text-xs text-muted-foreground">
                          {new Date(job.createdAt).toLocaleDateString()} · {job.suggestionsCount ?? 0} suggestions
                        </div>
                      </div>
                      <StatusBadge status={job.status} />
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
        <CreateWorkspaceDialog
          open={createWorkspaceOpen}
          onOpenChange={setCreateWorkspaceOpen}
          onCreated={(workspace) => setSelectedWorkspaceId(workspace.id)}
        />
      </>
    );
  }

  // ──────────────────────────────────────────────────
  // REVIEW MODE
  // ──────────────────────────────────────────────────
  return (
    <>
      <DndContext>
        <div className="flex h-full overflow-hidden">
          <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
            <div className="flex shrink-0 items-center gap-2 border-b border-border/60 bg-background/80 px-3 py-2 backdrop-blur-sm">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => {
                  userClearedSelectionRef.current = true;
                  setSelectedJobId(null);
                  setSidebarOpen(true);
                  const targetWorkspaceId = selectedWorkspaceId ?? urlWorkspaceId;
                  if (targetWorkspaceId) {
                    void navigate({
                      to: "/workspace/$workspaceId/designer/new",
                      params: { workspaceId: targetWorkspaceId },
                    });
                    return;
                  }

                  void navigate({ to: "/designer/new" });
                }}
                className="text-xs"
              >
                <ArrowUpFromLine className="h-4 w-4" />
                New document
              </Button>

              <div className="min-w-0 flex-1">
                <div className="mb-2 flex items-center gap-2">
                  <span className="truncate text-sm font-medium text-foreground">
                    {selectedRecentJob?.filename ?? activeJob?.filename ?? "Document"}
                  </span>
                  {selectedRecentJob ? <StatusBadge status={selectedRecentJob.status} /> : null}
                  {jobQuery.isFetching ? <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" /> : null}
                </div>
                <SearchToolbar
                  value={searchQuery}
                  onChange={setSearchQuery}
                  onClear={handleClearSearch}
                  matchCount={totalMatches}
                  isSearching={isSearching_fuzzy}
                  error={searchError}
                  activeMatchIndex={activeSearchMatchIndex}
                  activeMatch={activeSearchMatch}
                  onFindNext={totalMatches > 0 ? handleFindNextMatch : undefined}
                  onRedactAllInstances={
                    totalMatches > 0 ? () => void redactAllSearchMatchesMutation.mutateAsync() : undefined
                  }
                  isRedactingAllInstances={redactAllSearchMatchesMutation.isPending}
                />
              </div>

              <div className="flex shrink-0 items-center gap-1.5">
                <div className="flex items-center overflow-hidden rounded-lg border border-border/70">
                  <button
                    type="button"
                    onClick={() => setViewerMode("original")}
                    disabled={!localPdfUrl}
                    className={cn(
                      "px-2.5 py-1 text-xs transition-colors",
                      viewerMode === "original"
                        ? "bg-accent text-accent-foreground"
                        : "text-muted-foreground hover:bg-muted/50 disabled:opacity-40"
                    )}
                  >
                    Original
                  </button>
                  <button
                    type="button"
                    onClick={() => setViewerMode("redacted")}
                    disabled={!redactedPreviewUrl && !selectedRecentJob?.hasRedactedPdf}
                    className={cn(
                      "border-l border-border/70 px-2.5 py-1 text-xs transition-colors",
                      viewerMode === "redacted"
                        ? "bg-accent text-accent-foreground"
                        : "text-muted-foreground hover:bg-muted/50 disabled:opacity-40"
                    )}
                  >
                    Redacted
                  </button>
                </div>

                <Button
                  variant={drawMode ? "default" : "outline"}
                  size="sm"
                  onClick={() => setDrawMode((value) => !value)}
                  disabled={!canDraw}
                  className="h-7 text-xs"
                >
                  Draw
                </Button>

                <Button
                  size="sm"
                  onClick={() => void applyMutation.mutateAsync()}
                  disabled={!activeJob || activeJob.status !== "complete" || approvedCount === 0 || applyMutation.isPending}
                  className="h-7 text-xs"
                >
                  {applyMutation.isPending ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <CheckSquare className="mr-1 h-3 w-3" />}
                  Apply {approvedCount > 0 ? `(${approvedCount})` : ""}
                </Button>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => void approveAllMutation.mutateAsync()}
                  disabled={!activeJob || sortedSuggestions.length === 0 || sortedSuggestions.every((suggestion) => suggestion.approved) || approveAllMutation.isPending}
                  className="h-7 text-xs"
                  title="Approve all unapproved suggestions (Ctrl+Shift+A)"
                >
                  {approveAllMutation.isPending ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <CheckSquare className="mr-1 h-3 w-3" />}
                  Approve All
                </Button>

                <Button variant="outline" size="sm" onClick={() => void handleDownload()} disabled={!selectedJobId} className="h-7 text-xs">
                  <Download className="mr-1 h-3 w-3" />
                  Download
                </Button>
              </div>
            </div>

            <div className="flex min-h-0 flex-1 flex-col overflow-hidden bg-muted/20">
              <div className="mx-auto min-h-0 w-full max-w-[64rem] flex-1 overflow-y-auto px-4 py-4">
                <PdfDocumentViewer
                  source={viewerSource}
                  suggestions={sortedSuggestions}
                  searchMatches={searchMatches}
                  activeSearchMatchId={activeSearchMatch?.matchId ?? null}
                  isLoading={jobQuery.isLoading}
                  drawMode={drawMode && canDraw}
                  selectedSuggestionId={selectedSuggestionId}
                  focusPageRequest={focusPageRequest}
                  onSuggestionSelect={setSelectedSuggestionId}
                  onManualRedactionCreated={(pageIndex, rect) =>
                    manualRedactionMutation.mutate({ pageIndex, rects: [rect] })
                  }
                  onSearchMatchRedacted={(match: TextMatch) => {
                    if (match.rects.length > 0) {
                      manualRedactionMutation.mutate({
                        pageIndex: match.pageNum,
                        rects: match.rects,
                      });
                    }
                  }}
                  onDocumentLoaded={setPdfDocument}
                  pageStatus={Object.fromEntries(
                    Object.entries(pageStatus).map(([num, status]) => [
                      parseInt(num, 10),
                      {
                        stage: status.stage,
                        stageLabel: getStageLabel(status.stage),
                        errorMessage: status.error_message,
                      },
                    ])
                  )}
                />
              </div>
            </div>
          </div>

          <div className={cn("shrink-0 overflow-hidden border-l border-border/60 bg-background transition-all duration-200", chatCollapsed ? "w-12" : "w-[28rem] xl:w-[36rem]") }>
            {chatCollapsed ? (
              <div className="flex h-full items-center justify-center">
                <button
                  type="button"
                  onClick={() => setChatCollapsed(false)}
                  className="flex h-full w-full items-center justify-center text-muted-foreground transition-colors hover:bg-muted/40 hover:text-foreground"
                  title="Show chat"
                  aria-label="Show chat"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
              </div>
            ) : (
              <div className="flex h-full flex-col overflow-hidden">
                <div className="flex shrink-0 items-center justify-between border-b border-border/60 bg-muted/10 px-3 py-2">
                  <div className="min-w-0">
                    <div className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">Chat</div>
                    <div className="truncate text-sm text-foreground">Assistant and suggestions</div>
                  </div>

                  <button
                    type="button"
                    onClick={() => setChatCollapsed(true)}
                    className="rounded-lg p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
                    title="Hide chat"
                    aria-label="Hide chat"
                  >
                    <ChevronRight className="h-4 w-4" />
                  </button>
                </div>

                <WorkspaceChatHeader
                  workspace={activeWorkspace}
                  activeJobId={selectedJobId}
                  onRulesClick={() => setRulesOpen(true)}
                  onExclusionsClick={() => setExclusionsOpen(true)}
                  onAddToWorkspace={() => setAddToWorkspaceOpen(true)}
                  onCreateWorkspace={() => setCreateWorkspaceOpen(true)}
                />
                <AgentChatPanel
                  conversation={conversation}
                  promptPresets={AGENT_PROMPT_PRESETS}
                  isStreaming={isChatStreaming}
                  chatInput={chatInput}
                  onChatInputChange={setChatInput}
                  onSubmit={handleChatSubmit}
                  inputPlaceholder={selectedJobId ? "Ask about these files…" : "Select a job first"}
                  inputDisabled={!selectedJobId || isChatStreaming}
                  onQuickPrompt={handleQuickPrompt}
                  renderMessageText={renderMessageWithPageTokens}
                  suggestionsSection={{
                    suggestions: sortedSuggestions,
                    selectedSuggestionId,
                    onSuggestionSelect: handleSuggestionSelect,
                    onApprovalChange: (id, approved) => approvalMutation.mutate({ suggestionId: id, approved }),
                    onDelete: (suggestionId) => deleteSuggestionMutation.mutate(suggestionId),
                    getSuggestionPageLabel,
                    isLoading: jobQuery.isLoading,
                    hasJobData: !!activeJob,
                    jobStatus: activeJob?.status ?? null,
                    error: jobQuery.error
                      ? getApiErrorMessage(jobQuery.error, "Unable to load job.")
                      : null,
                  }}
                />
              </div>
            )}
          </div>
        </div>
      </DndContext>

      {selectedJobId ? (
        <AddToWorkspaceDialog
          jobId={selectedJobId}
          jobFilename={selectedRecentJob?.filename}
          open={addToWorkspaceOpen}
          onOpenChange={setAddToWorkspaceOpen}
          initialWorkspaceId={selectedWorkspaceId}
          onAdded={(workspaceId) => setSelectedWorkspaceId(workspaceId)}
        />
      ) : null}

      <CreateWorkspaceDialog
        open={createWorkspaceOpen}
        onOpenChange={setCreateWorkspaceOpen}
        onCreated={(workspace) => setSelectedWorkspaceId(workspace.id)}
      />

      {activeWorkspace ? (
        <>
          <WorkspaceRulesSlideover open={rulesOpen} onOpenChange={setRulesOpen} workspace={activeWorkspace} />
      <WorkspaceExclusionsSlideover
        open={exclusionsOpen}
        onOpenChange={setExclusionsOpen}
        workspace={activeWorkspace}
        activeJobId={selectedJobId}
      />
        </>
      ) : null}
    </>
  );
}


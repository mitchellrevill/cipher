import React, { startTransition, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  ArrowUpFromLine,
  Ban,
  CheckSquare,
  ChevronLeft,
  ChevronRight,
  Download,
  FilePlus2,
  FolderKanban,
  Loader2,
  Plus,
  Send,
  ShieldCheck,
  Sparkles,
  Trash2,
  WandSparkles,
  X,
} from "lucide-react";
import { toast } from "sonner";
import {
  getApiErrorMessage,
  redactionAgentService,
  redactionJobService,
  workspaceService,
  type AgentDirective,
  type RedactionJob,
  type Suggestion,
  type WorkspaceDocumentState,
} from "@/api/services";
import { PdfDocumentViewer } from "@/components/pdf/pdf-document-viewer";
import { SearchToolbar } from "@/components/search/SearchToolbar";
import {
  Badge,
  Button,
  Checkbox,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  Input,
  Label,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Textarea,
} from "@/components/ui";
import {
  PromptInput,
  PromptInputAction,
  PromptInputActions,
  PromptInputTextarea,
} from "@/components/ui/prompt-input";
import { usePageProcessingStatus, useSuggestionStreamListener, useRedactionHotkeys } from "@/hooks";
import { useRecentJobs } from "@/hooks/useRecentJobs";
import { useFuzzySearch } from "@/hooks/useFuzzySearch";
import type { TextMatch } from "@/types/search";
import { queryClient } from "@/lib/query-client";
import {
  getLocalPdfUrl,
  registerLocalPdf,
  removeRecentJob,
  setActiveJobId,
  upsertRecentJob,
  type RecentJobRecord,
} from "@/lib/recent-jobs";
import { cn, formatBytes } from "@/lib/utils";
import { useUIStore } from "@/store";

interface ChatMessage {
  role: "user" | "assistant";
  text: string;
}

interface ConversationState {
  messages: ChatMessage[];
  sessionId?: string;
  responseId?: string;
}

const EMPTY_CONVERSATION: ConversationState = { messages: [] };

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
  const { recentJobs, activeJobId } = useRecentJobs();
  const setSidebarOpen = useUIStore((s) => s.setSidebarOpen);

  const [selectedJobId, setSelectedJobId] = useState<string | null>(
    activeJobId ?? recentJobs[0]?.jobId ?? null
  );
  const userClearedSelectionRef = useRef(false);
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
  const [chatByJob, setChatByJob] = useState<Record<string, ConversationState>>({});
  const [redactedPreviewUrls, setRedactedPreviewUrls] = useState<Record<string, string>>({});
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<string | null>(null);
  const [isCreateWorkspaceOpen, setIsCreateWorkspaceOpen] = useState(false);
  const [newWorkspaceName, setNewWorkspaceName] = useState("");
  const [newWorkspaceDescription, setNewWorkspaceDescription] = useState("");
  const [isRuleDialogOpen, setIsRuleDialogOpen] = useState(false);
  const [rulePattern, setRulePattern] = useState("");
  const [ruleCategory, setRuleCategory] = useState("PII");
  const [isExcludeDialogOpen, setIsExcludeDialogOpen] = useState(false);
  const [excludeReason, setExcludeReason] = useState("Excluded from workspace automation");
  const [focusPageRequest, setFocusPageRequest] = useState<{ pageNumber: number; requestId: number } | null>(null);
  const redactedPreviewUrlsRef = useRef<Record<string, string>>({});
  const chatEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    redactedPreviewUrlsRef.current = redactedPreviewUrls;
  }, [redactedPreviewUrls]);

  useEffect(() => {
    return () => {
      Object.values(redactedPreviewUrlsRef.current).forEach((url) => URL.revokeObjectURL(url));
    };
  }, []);

  useEffect(() => {
    if (recentJobs.length === 0) {
      if (selectedJobId !== null) setSelectedJobId(null);
      return;
    }
    // If user explicitly cleared the selection, don't auto-select
    if (userClearedSelectionRef.current) {
      userClearedSelectionRef.current = false;
      return;
    }
    if (selectedJobId && recentJobs.some((job) => job.jobId === selectedJobId)) return;
    setSelectedJobId(activeJobId ?? recentJobs[0]?.jobId ?? null);
  }, [activeJobId, recentJobs, selectedJobId]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatByJob, selectedJobId]);

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
      suggestionsCount: job.suggestions_count || job.suggestions.length,
      fileSize: selectedRecentJob?.fileSize,
      completedAt: job.completed_at ?? undefined,
      error: job.error ?? undefined,
      hasRedactedPdf: selectedRecentJob?.hasRedactedPdf,
    });
  }, [jobQuery.data, selectedJobId, selectedRecentJob]);

  const activeJob = jobQuery.data;
  const activeWorkspace = workspaceQuery.data ?? null;

  useEffect(() => {
    if (activeJob?.workspace_id && activeJob.workspace_id !== selectedWorkspaceId) {
      setSelectedWorkspaceId(activeJob.workspace_id);
      return;
    }

    if (!selectedWorkspaceId && workspacesQuery.data && workspacesQuery.data.length === 1) {
      setSelectedWorkspaceId(workspacesQuery.data[0].id);
    }
  }, [activeJob?.workspace_id, selectedWorkspaceId, workspacesQuery.data]);

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
  const currentWorkspaceDocument = useMemo(
    () => activeWorkspace?.documents.find((document) => document.id === selectedJobId) ?? null,
    [activeWorkspace?.documents, selectedJobId]
  );
  const currentWorkspaceExclusion = useMemo(
    () => activeWorkspace?.exclusions.find((exclusion) => exclusion.document_id === selectedJobId) ?? null,
    [activeWorkspace?.exclusions, selectedJobId]
  );
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
  const workspaceDocumentCount = activeWorkspace?.stats?.document_count ?? activeWorkspace?.documents.length ?? 0;
  const workspaceRuleCount = activeWorkspace?.stats?.rule_count ?? activeWorkspace?.rules.length ?? 0;
  const workspaceExclusionCount = activeWorkspace?.stats?.exclusion_count ?? activeWorkspace?.exclusions.length ?? 0;

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
  const isReviewMode = !!selectedJobId;

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

  const getWorkspaceDocumentLabel = useCallback(
    (document: WorkspaceDocumentState) => {
      if (document.filename) {
        return document.filename;
      }

      const recent = recentJobs.find((job) => job.jobId === document.id);
      return recent?.filename ?? document.id;
    },
    [recentJobs]
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
      suggestionsCount: activeJob?.suggestions_count ?? activeJob?.suggestions.length,
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
      setActiveJobId(job_id);
      startTransition(() => setSelectedJobId(job_id));
      setSelectedFile(null);
      setViewerMode("original");
      setDrawMode(false);
      setSelectedSuggestionId(null);
      setSidebarOpen(false);
      await queryClient.invalidateQueries({ queryKey: ["redaction-job", job_id] });
      refreshWorkspaceQueries(selectedWorkspaceId);
      toast.success("Upload accepted – processing started.");
    },
    onError: (error) => {
      toast.error(getApiErrorMessage(error, "Unable to upload the PDF."));
    },
  });

  const createWorkspaceMutation = useMutation({
    mutationFn: async () => workspaceService.createWorkspace(newWorkspaceName.trim(), newWorkspaceDescription.trim() || undefined),
    onSuccess: (workspace) => {
      setSelectedWorkspaceId(workspace.id);
      setIsCreateWorkspaceOpen(false);
      setNewWorkspaceName("");
      setNewWorkspaceDescription("");
      refreshWorkspaceQueries(workspace.id);
      toast.success(`Workspace ${workspace.name} created.`);
    },
    onError: (error) => toast.error(getApiErrorMessage(error, "Unable to create workspace.")),
  });

  const addDocumentToWorkspaceMutation = useMutation({
    mutationFn: async () => {
      if (!selectedWorkspaceId || !selectedJobId) {
        throw new Error("Select a workspace and a job first.");
      }

      return workspaceService.addDocument(selectedWorkspaceId, selectedJobId);
    },
    onSuccess: () => {
      refreshWorkspaceQueries(selectedWorkspaceId);
      toast.success("Document added to workspace.");
    },
    onError: (error) => toast.error(getApiErrorMessage(error, "Unable to add the document to the workspace.")),
  });

  const createWorkspaceRuleMutation = useMutation({
    mutationFn: async () => {
      if (!selectedWorkspaceId) {
        throw new Error("Select a workspace first.");
      }

      return workspaceService.createRule(selectedWorkspaceId, {
        pattern: rulePattern.trim(),
        category: ruleCategory.trim(),
      });
    },
    onSuccess: (rule) => {
      setIsRuleDialogOpen(false);
      setRulePattern("");
      setRuleCategory("PII");
      refreshWorkspaceQueries(selectedWorkspaceId);
      toast.success(`Rule ${rule.id} created.`);
    },
    onError: (error) => toast.error(getApiErrorMessage(error, "Unable to create workspace rule.")),
  });

  const excludeDocumentMutation = useMutation({
    mutationFn: async () => {
      if (!selectedWorkspaceId || !selectedJobId) {
        throw new Error("Select a workspace and a job first.");
      }

      return workspaceService.excludeDocument(selectedWorkspaceId, selectedJobId, excludeReason.trim());
    },
    onSuccess: () => {
      setIsExcludeDialogOpen(false);
      setExcludeReason("Excluded from workspace automation");
      refreshWorkspaceQueries(selectedWorkspaceId);
      toast.success("Document excluded from workspace automation.");
    },
    onError: (error) => toast.error(getApiErrorMessage(error, "Unable to exclude this document.")),
  });

  const removeExclusionMutation = useMutation({
    mutationFn: async () => {
      if (!selectedWorkspaceId || !currentWorkspaceExclusion) {
        throw new Error("Select an excluded document first.");
      }

      return workspaceService.removeExclusion(selectedWorkspaceId, currentWorkspaceExclusion.id);
    },
    onSuccess: () => {
      refreshWorkspaceQueries(selectedWorkspaceId);
      toast.success("Document restored to workspace automation.");
    },
    onError: (error) => toast.error(getApiErrorMessage(error, "Unable to remove the exclusion.")),
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

  const chatMutation = useMutation({
    mutationFn: async (message: string) => {
      if (!selectedJobId) throw new Error("Select a job first.");
      const existing = chatByJob[selectedJobId] ?? EMPTY_CONVERSATION;
      return redactionAgentService.chat({
        jobId: selectedJobId,
        message,
        workspaceId: selectedWorkspaceId ?? undefined,
        sessionId: existing.sessionId,
        previousResponseId: existing.responseId,
      });
    },
    onSuccess: (response, message) => {
      if (!selectedJobId) return;
      setChatByJob((cur) => {
        const existing = cur[selectedJobId] ?? EMPTY_CONVERSATION;
        return {
          ...cur,
          [selectedJobId]: {
            sessionId: response.session_id,
            responseId: response.response_id,
            messages: [
              ...existing.messages,
              { role: "user", text: message },
              { role: "assistant", text: response.response },
            ],
          },
        };
      });
      handleAgentDirectives(response.directives);
      setChatInput("");
    },
    onError: (error) => toast.error(getApiErrorMessage(error, "Assistant could not respond.")),
  });

  const handleSelectJob = (jobId: string) => {
    setActiveJobId(jobId);
    startTransition(() => setSelectedJobId(jobId));
    setViewerMode(getLocalPdfUrl(jobId) ? "original" : "redacted");
    setDrawMode(false);
    setSelectedSuggestionId(null);
    setSidebarOpen(false);
  };

  const handleAgentDirectives = useCallback(
    (directives?: AgentDirective[]) => {
      if (!directives || directives.length === 0) {
        return;
      }

      directives.forEach((directive) => {
        const isCurrentDocument = !directive.document_id || directive.document_id === selectedJobId;

        if (directive.document_id && directive.document_id !== selectedJobId) {
          const matchingRecentJob = recentJobs.find((job) => job.jobId === directive.document_id);
          if (matchingRecentJob) {
            handleSelectJob(directive.document_id);
          }
        }

        if (directive.type === "jump_to_page" && directive.page && isCurrentDocument) {
          requestPageFocus(directive.page);
        }

        if ((directive.type === "focus_suggestion" || directive.type === "highlight_text") && directive.suggestion_id && isCurrentDocument) {
          setSelectedSuggestionId(directive.suggestion_id);
        }

        if (directive.type === "refresh_workspace") {
          refreshWorkspaceQueries(directive.workspace_id ?? selectedWorkspaceId);
        }
      });
    },
    [recentJobs, refreshWorkspaceQueries, requestPageFocus, selectedJobId, selectedWorkspaceId]
  );

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

  const handleChatSubmit = () => {
    const trimmed = chatInput.trim();
    if (!trimmed || !selectedJobId || chatMutation.isPending) return;
    void chatMutation.mutateAsync(trimmed);
  };

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

  const workspaceDialogs = (
    <>
      <Dialog open={isCreateWorkspaceOpen} onOpenChange={setIsCreateWorkspaceOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create workspace</DialogTitle>
            <DialogDescription>Group related documents so the assistant can reason across them.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="workspace-name">Name</Label>
              <Input
                id="workspace-name"
                value={newWorkspaceName}
                onChange={(e) => setNewWorkspaceName(e.target.value)}
                placeholder="Q1 compliance batch"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="workspace-description">Description</Label>
              <Textarea
                id="workspace-description"
                value={newWorkspaceDescription}
                onChange={(e) => setNewWorkspaceDescription((e as React.ChangeEvent<HTMLTextAreaElement>).target.value)}
                placeholder="Optional context for this document set"
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setIsCreateWorkspaceOpen(false)}>
              Cancel
            </Button>
            <Button
              type="button"
              onClick={() => void createWorkspaceMutation.mutateAsync()}
              disabled={newWorkspaceName.trim().length === 0 || createWorkspaceMutation.isPending}
            >
              {createWorkspaceMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}
              Create workspace
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={isRuleDialogOpen} onOpenChange={setIsRuleDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create workspace rule</DialogTitle>
            <DialogDescription>Save a reusable pattern that can be applied across non-excluded documents.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="rule-pattern">Pattern</Label>
              <Input
                id="rule-pattern"
                value={rulePattern}
                onChange={(e) => setRulePattern(e.target.value)}
                placeholder="\\b\\d{3}-\\d{2}-\\d{4}\\b"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="rule-category">Category</Label>
              <Input
                id="rule-category"
                value={ruleCategory}
                onChange={(e) => setRuleCategory(e.target.value)}
                placeholder="PII"
              />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setIsRuleDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              type="button"
              onClick={() => void createWorkspaceRuleMutation.mutateAsync()}
              disabled={!selectedWorkspaceId || rulePattern.trim().length === 0 || ruleCategory.trim().length === 0 || createWorkspaceRuleMutation.isPending}
            >
              {createWorkspaceRuleMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}
              Save rule
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={isExcludeDialogOpen} onOpenChange={setIsExcludeDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Exclude current document</DialogTitle>
            <DialogDescription>Excluded documents are skipped when the assistant applies workspace rules.</DialogDescription>
          </DialogHeader>
          <div className="space-y-1.5">
            <Label htmlFor="exclude-reason">Reason</Label>
            <Textarea
              id="exclude-reason"
              value={excludeReason}
              onChange={(e) => setExcludeReason((e as React.ChangeEvent<HTMLTextAreaElement>).target.value)}
              rows={3}
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setIsExcludeDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              type="button"
              onClick={() => void excludeDocumentMutation.mutateAsync()}
              disabled={!selectedWorkspaceId || !selectedJobId || excludeReason.trim().length === 0 || excludeDocumentMutation.isPending}
            >
              {excludeDocumentMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Ban className="mr-2 h-4 w-4" />}
              Exclude document
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );

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
                  <Button type="button" variant="ghost" className="h-7 px-2 text-xs" onClick={() => setIsCreateWorkspaceOpen(true)}>
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
        {workspaceDialogs}
      </>
    );
  }

  // ──────────────────────────────────────────────────
  // REVIEW MODE
  // ──────────────────────────────────────────────────
  return (
    <>
      <div className="flex h-full overflow-hidden">
      {/* ── Left jobs rail (collapsible) ── */}
      <div
        className={cn(
          "flex-shrink-0 border-r border-border/60 bg-background transition-all duration-200 overflow-hidden flex flex-col",
          sidebarCollapsed ? "w-0 border-0" : "w-56"
        )}
      >
        <div className="flex items-center justify-between px-3 py-3 border-b border-border/60">
          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Jobs</span>
          <button
            type="button"
            onClick={() => {
              userClearedSelectionRef.current = true;
              setSelectedJobId(null);
              setSidebarOpen(true);
            }}
            className="rounded-lg p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
            title="New document"
          >
            <ArrowUpFromLine className="h-3.5 w-3.5" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto py-2 space-y-0.5 px-1.5">
          {recentJobs.map((job) => {
            const isSelected = job.jobId === selectedJobId;
            return (
              <div key={job.jobId} className="group relative">
                <button
                  type="button"
                  onClick={() => handleSelectJob(job.jobId)}
                  className={cn(
                    "w-full rounded-lg px-2 py-2 text-left text-sm transition-colors",
                    isSelected
                      ? "bg-accent text-accent-foreground"
                      : "hover:bg-muted/60 text-muted-foreground hover:text-foreground"
                  )}
                >
                  <div className="truncate font-medium">{job.filename}</div>
                  <div className="mt-0.5 flex items-center gap-1.5">
                    <StatusBadge status={job.status} />
                  </div>
                </button>
                <button
                  type="button"
                  onClick={() => removeRecentJob(job.jobId)}
                  className="absolute right-1 top-1 hidden rounded p-0.5 text-muted-foreground hover:text-destructive group-hover:flex"
                >
                  <Trash2 className="h-3 w-3" />
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Main viewer ── */}
      <div className="flex-1 min-w-0 flex flex-col overflow-hidden">
        {/* Toolbar */}
        <div className="flex-shrink-0 flex items-center gap-2 border-b border-border/60 bg-background/80 backdrop-blur-sm px-3 py-2">
          <button
            type="button"
            onClick={() => setSidebarCollapsed((v) => !v)}
            className="rounded-lg p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
            title={sidebarCollapsed ? "Show jobs" : "Hide jobs"}
          >
            {sidebarCollapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
          </button>

          <div className="min-w-0 flex-1 flex flex-col justify-center">
            <div className="flex items-center gap-2 mb-2">
              <span className="truncate font-medium text-sm text-foreground">
                {selectedRecentJob?.filename ?? activeJob?.filename ?? "Document"}
              </span>
              {selectedRecentJob && <StatusBadge status={selectedRecentJob.status} />}
              {jobQuery.isFetching && <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />}
            </div>
            {/* Search toolbar */}
            <div className="min-w-0">
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
                onRedactAllInstances={totalMatches > 0 ? () => void redactAllSearchMatchesMutation.mutateAsync() : undefined}
                isRedactingAllInstances={redactAllSearchMatchesMutation.isPending}
              />
            </div>
          </div>

          <div className="flex items-center gap-1.5 flex-shrink-0">
            <div className="flex items-center rounded-lg border border-border/70 overflow-hidden">
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
                  "px-2.5 py-1 text-xs transition-colors border-l border-border/70",
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
              onClick={() => setDrawMode((v) => !v)}
              disabled={!canDraw}
              className="text-xs h-7"
            >
              Draw
            </Button>

            <Button
              size="sm"
              onClick={() => void applyMutation.mutateAsync()}
              disabled={!activeJob || activeJob.status !== "complete" || approvedCount === 0 || applyMutation.isPending}
              className="text-xs h-7"
            >
              {applyMutation.isPending ? (
                <Loader2 className="mr-1 h-3 w-3 animate-spin" />
              ) : (
                <CheckSquare className="mr-1 h-3 w-3" />
              )}
              Apply {approvedCount > 0 ? `(${approvedCount})` : ""}
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={() => void approveAllMutation.mutateAsync()}
              disabled={!activeJob || sortedSuggestions.length === 0 || sortedSuggestions.every((s) => s.approved) || approveAllMutation.isPending}
              className="text-xs h-7"
              title="Approve all unapproved suggestions (Ctrl+Shift+A)"
            >
              {approveAllMutation.isPending ? (
                <Loader2 className="mr-1 h-3 w-3 animate-spin" />
              ) : (
                <CheckSquare className="mr-1 h-3 w-3" />
              )}
              Approve All
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={() => void handleDownload()}
              disabled={!selectedJobId}
              className="text-xs h-7"
            >
              <Download className="mr-1 h-3 w-3" />
              Download
            </Button>
          </div>
        </div>

        {/* PDF Canvas */}
        <div className="flex-1 overflow-y-auto bg-muted/20">
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
              // When user clicks a search match, create a manual redaction
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

      {/* ── Right panel ── */}
      <div className="flex-shrink-0 w-[28rem] xl:w-[36rem] border-l border-border/60 flex flex-col overflow-hidden bg-background">
        <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
          <div className="flex-shrink-0 border-b border-border/60 px-4 py-3 space-y-3">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
                  <FolderKanban className="h-3.5 w-3.5" />
                  Workspace
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  Manage shared rules and exclusions for related documents.
                </p>
              </div>
              <Button type="button" variant="outline" className="h-8 px-2.5 text-xs" onClick={() => setIsCreateWorkspaceOpen(true)}>
                <Plus className="mr-1 h-3.5 w-3.5" />
                New
              </Button>
            </div>

            <Select
              value={selectedWorkspaceId ?? NO_WORKSPACE_VALUE}
              onValueChange={(value) => setSelectedWorkspaceId(value === NO_WORKSPACE_VALUE ? null : value)}
            >
              <SelectTrigger className="h-9 text-xs">
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

            {selectedWorkspaceId ? (
              workspaceQuery.isLoading ? (
                <div className="rounded-xl border border-border/60 bg-muted/20 px-3 py-2 text-xs text-muted-foreground flex items-center gap-2">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Loading workspace state…
                </div>
              ) : workspaceQuery.error ? (
                <div className="rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
                  {getApiErrorMessage(workspaceQuery.error, "Unable to load workspace state.")}
                </div>
              ) : activeWorkspace ? (
                <div className="space-y-3 rounded-xl border border-border/60 bg-muted/20 p-3">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <Badge variant="secondary" className="rounded-full border-0">{workspaceDocumentCount} docs</Badge>
                    <Badge variant="secondary" className="rounded-full border-0">{workspaceRuleCount} rules</Badge>
                    <Badge variant="secondary" className="rounded-full border-0">{workspaceExclusionCount} exclusions</Badge>
                  </div>

                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      className="h-8 px-2.5 text-xs"
                      disabled={!selectedJobId || !!currentWorkspaceDocument || addDocumentToWorkspaceMutation.isPending}
                      onClick={() => void addDocumentToWorkspaceMutation.mutateAsync()}
                    >
                      {addDocumentToWorkspaceMutation.isPending ? (
                        <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <FilePlus2 className="mr-1 h-3.5 w-3.5" />
                      )}
                      {currentWorkspaceDocument ? "In workspace" : "Add current doc"}
                    </Button>

                    <Button
                      type="button"
                      variant="outline"
                      className="h-8 px-2.5 text-xs"
                      disabled={!selectedWorkspaceId}
                      onClick={() => setIsRuleDialogOpen(true)}
                    >
                      <Plus className="mr-1 h-3.5 w-3.5" />
                      Add rule
                    </Button>

                    {currentWorkspaceExclusion ? (
                      <Button
                        type="button"
                        variant="outline"
                        className="h-8 px-2.5 text-xs"
                        disabled={removeExclusionMutation.isPending}
                        onClick={() => void removeExclusionMutation.mutateAsync()}
                      >
                        {removeExclusionMutation.isPending ? (
                          <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <CheckSquare className="mr-1 h-3.5 w-3.5" />
                        )}
                        Re-include current doc
                      </Button>
                    ) : (
                      <Button
                        type="button"
                        variant="outline"
                        className="h-8 px-2.5 text-xs"
                        disabled={!selectedJobId || !currentWorkspaceDocument}
                        onClick={() => setIsExcludeDialogOpen(true)}
                      >
                        <Ban className="mr-1 h-3.5 w-3.5" />
                        Exclude current doc
                      </Button>
                    )}
                  </div>

                  <div className="grid gap-3 xl:grid-cols-3">
                    <div className="space-y-1.5">
                      <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">Documents</div>
                      <div className="space-y-1 max-h-28 overflow-y-auto pr-1">
                        {activeWorkspace.documents.length > 0 ? (
                          activeWorkspace.documents.map((document) => (
                            <button
                              key={document.id}
                              type="button"
                              onClick={() => handleSelectJob(document.id)}
                              className={cn(
                                "w-full rounded-lg border px-2.5 py-2 text-left text-[11px] transition-colors",
                                document.id === selectedJobId ? "border-primary/30 bg-primary/5" : "border-border/60 hover:bg-muted/50"
                              )}
                            >
                              <div className="truncate font-medium text-foreground">{getWorkspaceDocumentLabel(document)}</div>
                              <div className="mt-1 text-[10px] text-muted-foreground">
                                {document.excluded ? `Excluded · ${document.reason ?? "No reason"}` : `${document.suggestions_count ?? 0} suggestions`}
                              </div>
                            </button>
                          ))
                        ) : (
                          <div className="rounded-lg border border-border/60 px-2.5 py-2 text-[11px] text-muted-foreground">
                            No documents in this workspace yet.
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="space-y-1.5">
                      <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">Rules</div>
                      <div className="space-y-1 max-h-28 overflow-y-auto pr-1">
                        {activeWorkspace.rules.length > 0 ? (
                          activeWorkspace.rules.map((rule) => (
                            <div key={rule.id} className="rounded-lg border border-border/60 px-2.5 py-2 text-[11px]">
                              <div className="font-medium text-foreground">{rule.category}</div>
                              <div className="mt-1 truncate font-mono text-[10px] text-muted-foreground">{rule.pattern}</div>
                            </div>
                          ))
                        ) : (
                          <div className="rounded-lg border border-border/60 px-2.5 py-2 text-[11px] text-muted-foreground">
                            No reusable rules yet.
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="space-y-1.5">
                      <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">Exclusions</div>
                      <div className="space-y-1 max-h-28 overflow-y-auto pr-1">
                        {activeWorkspace.exclusions.length > 0 ? (
                          activeWorkspace.exclusions.map((exclusion) => (
                            <div key={exclusion.id} className="rounded-lg border border-border/60 px-2.5 py-2 text-[11px]">
                              <div className="truncate font-medium text-foreground">{getWorkspaceDocumentLabel({ id: exclusion.document_id })}</div>
                              <div className="mt-1 line-clamp-2 text-[10px] text-muted-foreground">{exclusion.reason}</div>
                            </div>
                          ))
                        ) : (
                          <div className="rounded-lg border border-border/60 px-2.5 py-2 text-[11px] text-muted-foreground">
                            No exclusions in this workspace.
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ) : null
            ) : (
              <div className="rounded-xl border border-border/60 bg-muted/20 px-3 py-2 text-xs text-muted-foreground">
                Select a workspace to enable shared rules, exclusions, and multi-document agent context.
              </div>
            )}
          </div>

          <div className="flex-1 min-h-0 overflow-y-auto px-4 py-4 space-y-3">
            {conversation.messages.length === 0 ? (
              <div className="space-y-3">
                <div className="rounded-xl border border-border/60 bg-muted/20 p-3 text-sm text-muted-foreground">
                  Ask the assistant to search, explain redactions, or jump to a page. It can output{" "}
                  <code className="font-mono opacity-70">{"[[page:N]]"}</code> tokens to navigate directly.
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {AGENT_PROMPT_PRESETS.map((prompt) => (
                    <button
                      key={prompt}
                      type="button"
                      onClick={() => handleQuickPrompt(prompt)}
                      className="rounded-full border border-border/60 px-2.5 py-1.5 text-left text-[11px] leading-4 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              conversation.messages.map((msg, i) => (
                <div
                  key={`${msg.role}-${i}`}
                  className={cn(
                    "rounded-2xl px-3.5 py-3 text-sm leading-relaxed",
                    msg.role === "assistant"
                      ? "mr-10 border border-border/60 bg-muted/40 text-foreground"
                      : "ml-12 bg-primary text-primary-foreground"
                  )}
                >
                  {renderMessageWithPageTokens(msg.text)}
                </div>
              ))
            )}
            <div ref={chatEndRef} />
          </div>
          <div className="flex-shrink-0 border-t border-border/60 px-4 py-3">
            <div className="mb-2 flex items-center justify-between gap-2">
              <span className="text-[11px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
                Suggestions
              </span>
              <span className="text-[11px] text-muted-foreground">
                {sortedSuggestions.length} total
              </span>
            </div>

            <div className="h-56 overflow-y-auto space-y-1.5 pr-1">
              {jobQuery.isLoading ? (
                <div className="flex items-center gap-2 rounded-xl border border-border/60 px-3 py-2 text-xs text-muted-foreground">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Loading suggestions…
                </div>
              ) : jobQuery.error ? (
                <div className="rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
                  {getApiErrorMessage(jobQuery.error, "Unable to load job.")}
                </div>
              ) : !activeJob ? (
                <div className="rounded-xl border border-border/60 px-3 py-3 text-xs text-muted-foreground">
                  No job data yet — still processing?
                </div>
              ) : sortedSuggestions.length === 0 ? (
                <div className="rounded-xl border border-border/60 px-3 py-3 text-xs text-muted-foreground flex items-center gap-2">
                  <Sparkles className="h-4 w-4" />
                  {activeJob.status === "complete" ? "No suggestions found." : "Waiting for analysis…"}
                </div>
              ) : (
                sortedSuggestions.map((suggestion) => {
                  const isSelected = selectedSuggestionId === suggestion.id;
                  const suggestionPageLabel =
                    suggestion.page_nums && suggestion.page_nums.length > 0
                      ? `pp. ${suggestion.page_nums.map((page) => page + 1).join(", ")}`
                      : `p.${getSuggestionViewerPageNumber(suggestion) ?? suggestion.page_num + 1}`;

                  return (
                    <button
                      key={suggestion.id}
                      type="button"
                      onClick={() => handleSuggestionSelect(suggestion)}
                      className={cn(
                        "w-full rounded-xl border px-2.5 py-2 text-left text-[11px] transition-colors",
                        isSelected ? "border-primary/30 bg-primary/5" : "border-border/60 hover:bg-muted/40"
                      )}
                    >
                      <div className="flex items-start gap-2">
                        <Checkbox
                          checked={suggestion.approved}
                          onCheckedChange={(checked) =>
                            approvalMutation.mutate({ suggestionId: suggestion.id, approved: checked === true })
                          }
                          onClick={(e) => e.stopPropagation()}
                          className="mt-0.5 flex-shrink-0"
                        />
                        <div className="min-w-0 flex-1">
                          <div className="truncate font-medium text-foreground">
                            {suggestion.text || "Manual redaction"}
                          </div>
                          <div className="mt-1 flex items-center gap-1.5 flex-wrap text-[10px] text-muted-foreground">
                            <span>{suggestionPageLabel}</span>
                            <Badge
                              variant="outline"
                              className="rounded-full border-border/60 px-1.5 py-0 text-[10px] capitalize"
                            >
                              {suggestion.category}
                            </Badge>
                          </div>
                          {suggestion.reasoning ? (
                            <div className="mt-1 line-clamp-2 text-muted-foreground">
                              {suggestion.reasoning}
                            </div>
                          ) : null}
                        </div>
                      </div>
                    </button>
                  );
                })
              )}
            </div>
          </div>

          <div className="flex-shrink-0 border-t border-border/60 p-3">
            <PromptInput
              value={chatInput}
              onValueChange={setChatInput}
              onSubmit={handleChatSubmit}
              isLoading={chatMutation.isPending}
              disabled={!selectedJobId || chatMutation.isPending}
              className="rounded-xl border-border/70 bg-muted/30"
            >
              <PromptInputTextarea
                placeholder={selectedJobId ? "Ask about this document…" : "Select a job first"}
                className="min-h-[44px] text-sm"
              />
              <PromptInputActions className="justify-end px-1 pb-1">
                <PromptInputAction tooltip="Send message" side="top">
                  <button
                    type="button"
                    onClick={handleChatSubmit}
                    disabled={!selectedJobId || chatInput.trim().length === 0 || chatMutation.isPending}
                    className={cn(
                      "flex h-8 w-8 items-center justify-center rounded-lg transition-colors",
                      chatInput.trim().length > 0 && selectedJobId && !chatMutation.isPending
                        ? "bg-primary text-primary-foreground hover:bg-primary/90"
                        : "bg-muted text-muted-foreground cursor-not-allowed"
                    )}
                  >
                    {chatMutation.isPending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Send className="h-4 w-4" />
                    )}
                  </button>
                </PromptInputAction>
              </PromptInputActions>
            </PromptInput>
          </div>
        </div>
      </div>
      </div>
      {workspaceDialogs}
    </>
  );
}


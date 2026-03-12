import React, { startTransition, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  ArrowUpFromLine,
  Bot,
  CheckSquare,
  ChevronLeft,
  ChevronRight,
  Download,
  Loader2,
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
  type RedactionJob,
  type Suggestion,
} from "@/api/services";
import { PdfDocumentViewer } from "@/components/pdf/pdf-document-viewer";
import {
  Badge,
  Button,
  Checkbox,
  Label,
  Textarea,
} from "@/components/ui";
import {
  PromptInput,
  PromptInputAction,
  PromptInputActions,
  PromptInputTextarea,
} from "@/components/ui/prompt-input";
import { usePageProcessingStatus, useSuggestionStreamListener } from "@/hooks";
import { useRecentJobs } from "@/hooks/useRecentJobs";
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
  const [selectedSuggestionId, setSelectedSuggestionId] = useState<string | null>(null);
  const [chatInput, setChatInput] = useState("");
  const [chatByJob, setChatByJob] = useState<Record<string, ConversationState>>({});
  const [redactedPreviewUrls, setRedactedPreviewUrls] = useState<Record<string, string>>({});
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
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

  // Initialize page processing status tracking
  const {
    pageStatus,
    updatePageStatus,
    getCurrentProcessingPage,
    getCurrentStage,
    getStageLabel,
  } = usePageProcessingStatus(activeJob?.suggestions?.length ?? 0);

  // Initialize suggestion streaming listener
  const {
    isConnected: isStreamConnected,
  } = useSuggestionStreamListener(
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
  const localPdfUrl = selectedJobId ? getLocalPdfUrl(selectedJobId) : null;
  const redactedPreviewUrl = selectedJobId ? redactedPreviewUrls[selectedJobId] : undefined;

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
    mutationFn: async () => {
      const unapproved = sortedSuggestions.filter((s) => !s.approved);
      const results = await Promise.all(
        unapproved.map((s) =>
          redactionJobService.updateSuggestionApproval(selectedJobId!, s.id, true)
        )
      );
      return results;
    },
    onSuccess: async () => {
      const unapprovedCount = sortedSuggestions.filter((s) => !s.approved).length;
      await queryClient.invalidateQueries({ queryKey: ["redaction-job", selectedJobId] });
      toast.success(`Approved ${unapprovedCount} suggestions.`);
    },
    onError: (error) => toast.error(getApiErrorMessage(error, "Unable to approve all suggestions.")),
  });

  const manualRedactionMutation = useMutation({
    mutationFn: ({ pageIndex, rect }: { pageIndex: number; rect: Suggestion["rects"][number] }) =>
      redactionJobService.addManualRedaction(selectedJobId!, pageIndex, [rect]),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["redaction-job", selectedJobId] });
      toast.success("Manual redaction added.");
    },
    onError: (error) => toast.error(getApiErrorMessage(error, "Unable to save manual redaction.")),
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
    await uploadMutation.mutateAsync({ file: selectedFile, instructions });
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

  // ──────────────────────────────────────────────────
  // UPLOAD MODE
  // ──────────────────────────────────────────────────
  if (!isReviewMode) {
    return (
      <div className="flex min-h-full flex-col items-center justify-center px-4 py-16">
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
    );
  }

  // ──────────────────────────────────────────────────
  // REVIEW MODE
  // ──────────────────────────────────────────────────
  return (
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

          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="truncate font-medium text-sm text-foreground">
                {selectedRecentJob?.filename ?? activeJob?.filename ?? "Document"}
              </span>
              {selectedRecentJob && <StatusBadge status={selectedRecentJob.status} />}
              {jobQuery.isFetching && <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />}
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
        <div className="flex-1 overflow-hidden bg-muted/20">
          <PdfDocumentViewer
            source={viewerSource}
            suggestions={sortedSuggestions}
            isLoading={jobQuery.isLoading}
            drawMode={drawMode && canDraw}
            selectedSuggestionId={selectedSuggestionId}
            onSuggestionSelect={setSelectedSuggestionId}
            onManualRedactionCreated={(pageIndex, rect) =>
              manualRedactionMutation.mutate({ pageIndex, rect })
            }
            onApprovalChange={(suggestionId, approved) =>
              approvalMutation.mutate({ suggestionId, approved })
            }
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

      {/* ── Right panel: suggestions + chat ── */}
      <div className="flex-shrink-0 w-72 xl:w-80 border-l border-border/60 flex flex-col overflow-hidden bg-background">
        <div className="flex items-center justify-between px-3 py-2.5 border-b border-border/60">
          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Suggestions
          </span>
          {activeJob && (
            <div className="flex items-center gap-2 flex-wrap">
              {isStreamConnected && (
                <span className="text-xs text-amber-600 dark:text-amber-400 flex items-center gap-1">
                  <span className="h-2 w-2 rounded-full bg-amber-600 dark:bg-amber-400 animate-pulse" />
                  Processing
                </span>
              )}
              {getCurrentProcessingPage() !== null && (
                <span className="text-xs text-muted-foreground">
                  Page {getCurrentProcessingPage()! + 1}: {getStageLabel(getCurrentStage() as any)}...
                </span>
              )}
              <span className="text-xs text-muted-foreground">
                {approvedCount}/{sortedSuggestions.length} approved
              </span>
            </div>
          )}
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto p-2 space-y-1.5">
          {jobQuery.isLoading ? (
            <div className="flex items-center gap-2 p-3 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading…
            </div>
          ) : jobQuery.error ? (
            <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
              {getApiErrorMessage(jobQuery.error, "Unable to load job.")}
            </div>
          ) : !activeJob ? (
            <div className="px-3 py-4 text-xs text-muted-foreground">
              No job data yet — still processing?
            </div>
          ) : sortedSuggestions.length === 0 ? (
            <div className="px-3 py-4 text-xs text-muted-foreground flex items-center gap-2">
              <Sparkles className="h-4 w-4" />
              {activeJob.status === "complete" ? "No suggestions found." : "Waiting for analysis…"}
            </div>
          ) : (
            sortedSuggestions.map((suggestion) => {
              const isSelected = selectedSuggestionId === suggestion.id;
              return (
                <button
                  key={suggestion.id}
                  type="button"
                  onClick={() => setSelectedSuggestionId(suggestion.id)}
                  className={cn(
                    "w-full rounded-xl border px-3 py-2.5 text-left text-xs transition-colors",
                    isSelected
                      ? "border-primary/30 bg-primary/5"
                      : "border-border/60 hover:bg-muted/40"
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
                      <div className="font-medium text-foreground truncate">
                        {suggestion.text || "Manual redaction"}
                      </div>
                      <div className="mt-0.5 flex items-center gap-1.5 flex-wrap">
                        {/* Show all pages where suggestion appears */}
                        {suggestion.page_nums && suggestion.page_nums.length > 0 ? (
                          <span className="text-muted-foreground text-xs">
                            pp. {suggestion.page_nums.map(p => p + 1).join(", ")}
                          </span>
                        ) : (
                          <span className="text-muted-foreground">p.{suggestion.page_num + 1}</span>
                        )}
                        <Badge variant="outline" className="rounded-full text-[10px] px-1.5 py-0 capitalize border-border/60">
                          {suggestion.category}
                        </Badge>
                      </div>
                      {suggestion.reasoning && (
                        <div className="mt-1 text-muted-foreground line-clamp-2">{suggestion.reasoning}</div>
                      )}
                    </div>
                  </div>
                </button>
              );
            })
          )}
        </div>

        {/* Chat divider */}
        <div className="border-t border-border/60 flex items-center gap-2 px-3 py-2">
          <Bot className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Assistant</span>
        </div>

        {/* Chat messages */}
        <div className="h-44 overflow-y-auto px-3 py-2 space-y-2">
          {conversation.messages.length === 0 ? (
            <div className="text-xs text-muted-foreground py-2">
              Ask the assistant about this document…
            </div>
          ) : (
            conversation.messages.map((msg, i) => (
              <div
                key={`${msg.role}-${i}`}
                className={cn(
                  "rounded-xl px-3 py-2 text-xs leading-relaxed",
                  msg.role === "assistant"
                    ? "bg-muted/60 text-foreground"
                    : "bg-primary text-primary-foreground ml-4"
                )}
              >
                {msg.text}
              </div>
            ))
          )}
          <div ref={chatEndRef} />
        </div>

        {/* Prompt-kit chat input */}
        <div className="border-t border-border/60 p-2">
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
              className="text-xs min-h-[36px]"
            />
            <PromptInputActions className="justify-end px-1 pb-1">
              <PromptInputAction tooltip="Send message" side="top">
                <button
                  type="button"
                  onClick={handleChatSubmit}
                  disabled={!selectedJobId || chatInput.trim().length === 0 || chatMutation.isPending}
                  className={cn(
                    "flex h-7 w-7 items-center justify-center rounded-lg transition-colors",
                    chatInput.trim().length > 0 && selectedJobId && !chatMutation.isPending
                      ? "bg-primary text-primary-foreground hover:bg-primary/90"
                      : "bg-muted text-muted-foreground cursor-not-allowed"
                  )}
                >
                  {chatMutation.isPending ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Send className="h-3.5 w-3.5" />
                  )}
                </button>
              </PromptInputAction>
            </PromptInputActions>
          </PromptInput>
        </div>
      </div>
    </div>
  );
}


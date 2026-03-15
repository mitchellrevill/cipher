import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "@tanstack/react-router";
import { ArrowLeft, ExternalLink, FolderKanban, Loader2, Plus, Trash2 } from "lucide-react";
import { workspaceService } from "@/api/services";
import { AddToWorkspaceDialog } from "@/components/workspace/add-to-workspace-dialog";
import { WorkspaceExclusionsSlideover } from "@/components/workspace/workspace-exclusions-slideover";
import { WorkspaceRulesSlideover } from "@/components/workspace/workspace-rules-slideover";
import { Badge, Button, PageHeading } from "@/components/ui";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useRecentJobs } from "@/hooks/useRecentJobs";
import { setActiveJobId } from "@/lib/recent-jobs";
import { useWorkspaceStore } from "@/store/workspace-store";
import { toast } from "sonner";

export default function WorkspaceDetailsRoute() {
  const { workspaceId } = useParams({ strict: false }) as { workspaceId: string };
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { recentJobs } = useRecentJobs();
  const setSelectedWorkspaceId = useWorkspaceStore((state) => state.setSelectedWorkspaceId);
  const [rulesOpen, setRulesOpen] = useState(false);
  const [exclusionsOpen, setExclusionsOpen] = useState(false);
  const [addDialogJobId, setAddDialogJobId] = useState<string | null>(null);

  const { data: workspace, isLoading, error } = useQuery({
    queryKey: ["workspace", workspaceId],
    queryFn: () => workspaceService.getWorkspace(workspaceId),
  });

  const removeDocumentMutation = useMutation({
    mutationFn: (documentId: string) => workspaceService.removeDocument(workspaceId, documentId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["workspace", workspaceId] });
      await queryClient.invalidateQueries({ queryKey: ["workspaces"] });
      toast.success("Document removed from workspace.");
    },
    onError: () => toast.error("Failed to remove document from workspace."),
  });

  const availableRecentJobs = useMemo(() => {
    if (!workspace) {
      return [];
    }

    const workspaceJobIds = new Set(workspace.documents.map((document) => document.id));
    return recentJobs.filter((job) => !workspaceJobIds.has(job.jobId));
  }, [recentJobs, workspace]);

  const handleOpenStudio = (jobId?: string | null) => {
    if (jobId) {
      setActiveJobId(jobId);
    }
    setSelectedWorkspaceId(workspaceId);
    void navigate({ to: "/workspace/$workspaceId/designer", params: { workspaceId } });
  };

  if (isLoading) {
    return <div className="p-8 text-sm text-muted-foreground">Loading workspace…</div>;
  }

  if (error || !workspace) {
    return <div className="p-8 text-sm text-destructive">Unable to load workspace.</div>;
  }

  return (
    <>
      <div className="flex h-full flex-col overflow-hidden bg-background">
        <div className="px-6 pt-3">
          <Button type="button" variant="ghost" size="sm" className="-ml-2" onClick={() => handleOpenStudio()}>
            <ArrowLeft className="h-4 w-4" />
            Back to studio
          </Button>
        </div>
        <PageHeading
          title={workspace.name}
          description={workspace.description ?? undefined}
          icon={<FolderKanban />}
          actions={
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="secondary" className="rounded-full border-0">{workspace.documents.length} files</Badge>
              <Badge variant="secondary" className="rounded-full border-0">{workspace.rules.length} rules</Badge>
              <Badge variant="secondary" className="rounded-full border-0">{workspace.exclusions.length} exclusions</Badge>
              <Button type="button" variant="outline" size="sm" onClick={() => setRulesOpen(true)}>
                Manage rules
              </Button>
              <Button type="button" variant="outline" size="sm" onClick={() => setExclusionsOpen(true)}>
                Manage exclusions
              </Button>
            </div>
          }
          bleed={false}
        />

        <div className="flex-1 overflow-hidden px-6 py-5">
          <Tabs defaultValue="files" className="flex h-full flex-col">
            <TabsList>
              <TabsTrigger value="files">Files</TabsTrigger>
              <TabsTrigger value="rules">Rules</TabsTrigger>
              <TabsTrigger value="exclusions">Exclusions</TabsTrigger>
            </TabsList>

            <TabsContent value="files" className="min-h-0 flex-1">
              <div className="grid h-full gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(280px,1fr)]">
                <ScrollArea className="h-full rounded-2xl border border-border/60">
                  <div className="space-y-3 p-4">
                    {workspace.documents.length > 0 ? (
                      workspace.documents.map((document) => (
                        <div key={document.id} className="flex flex-wrap items-start justify-between gap-3 rounded-xl border border-border/60 bg-muted/20 px-4 py-3">
                          <div className="min-w-0">
                            <div className="truncate font-medium text-foreground">{document.filename ?? document.id}</div>
                            <div className="mt-1 text-xs text-muted-foreground">
                              {document.excluded ? `Excluded · ${document.reason ?? "No reason"}` : `${document.suggestions_count ?? 0} suggestions`}
                            </div>
                          </div>
                          <div className="flex flex-wrap gap-2">
                            <Button type="button" variant="outline" size="sm" onClick={() => handleOpenStudio(document.id)}>
                              Open in studio
                              <ExternalLink className="h-4 w-4" />
                            </Button>
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              onClick={() => void removeDocumentMutation.mutateAsync(document.id)}
                              disabled={removeDocumentMutation.isPending}
                            >
                              {removeDocumentMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                              Remove
                            </Button>
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="rounded-xl border border-dashed border-border/60 px-4 py-10 text-center text-sm text-muted-foreground">
                        No documents in this workspace yet.
                      </div>
                    )}
                  </div>
                </ScrollArea>

                <div className="flex flex-col rounded-2xl border border-border/60 bg-muted/20 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="text-sm font-medium">Add recent files</div>
                      <div className="text-xs text-muted-foreground">Attach recent jobs to this workspace without leaving the page.</div>
                    </div>
                    <Button type="button" size="sm" onClick={() => setAddDialogJobId(availableRecentJobs[0]?.jobId ?? null)} disabled={availableRecentJobs.length === 0}>
                      <Plus className="h-4 w-4" />
                      Add file
                    </Button>
                  </div>

                  <div className="mt-4 flex-1 space-y-2 overflow-y-auto">
                    {availableRecentJobs.length > 0 ? (
                      availableRecentJobs.map((job) => (
                        <div key={job.jobId} className="flex items-center justify-between gap-3 rounded-xl border border-border/60 bg-background px-3 py-2.5">
                          <div className="min-w-0">
                            <div className="truncate font-medium text-foreground">{job.filename}</div>
                            <div className="text-xs text-muted-foreground">{job.status}</div>
                          </div>
                          <Button type="button" variant="outline" size="sm" onClick={() => setAddDialogJobId(job.jobId)}>
                            Add
                          </Button>
                        </div>
                      ))
                    ) : (
                      <div className="rounded-xl border border-dashed border-border/60 px-4 py-8 text-center text-sm text-muted-foreground">
                        No recent jobs available to add.
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </TabsContent>

            <TabsContent value="rules" className="min-h-0 flex-1">
              <div className="space-y-4 rounded-2xl border border-border/60 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-sm font-medium">Workspace rules</div>
                    <div className="text-xs text-muted-foreground">Reusable patterns used by the assistant across this workspace.</div>
                  </div>
                  <Button type="button" size="sm" onClick={() => setRulesOpen(true)}>
                    <Plus className="h-4 w-4" />
                    Add rule
                  </Button>
                </div>

                <div className="space-y-3">
                  {workspace.rules.length > 0 ? (
                    workspace.rules.map((rule) => (
                      <div key={rule.id} className="rounded-xl border border-border/60 bg-muted/20 px-4 py-3">
                        <div className="font-medium text-foreground">{rule.category}</div>
                        <div className="mt-1 break-all font-mono text-xs text-muted-foreground">{rule.pattern}</div>
                      </div>
                    ))
                  ) : (
                    <div className="rounded-xl border border-dashed border-border/60 px-4 py-10 text-center text-sm text-muted-foreground">
                      No rules yet.
                    </div>
                  )}
                </div>
              </div>
            </TabsContent>

            <TabsContent value="exclusions" className="min-h-0 flex-1">
              <div className="space-y-4 rounded-2xl border border-border/60 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-sm font-medium">Workspace exclusions</div>
                    <div className="text-xs text-muted-foreground">Files excluded from shared rule automation.</div>
                  </div>
                  <Button type="button" size="sm" onClick={() => setExclusionsOpen(true)}>
                    Manage exclusions
                  </Button>
                </div>

                <div className="space-y-3">
                  {workspace.exclusions.length > 0 ? (
                    workspace.exclusions.map((exclusion) => (
                      <div key={exclusion.id} className="rounded-xl border border-border/60 bg-muted/20 px-4 py-3">
                        <div className="font-medium text-foreground">{exclusion.document_id}</div>
                        <div className="mt-1 text-xs text-muted-foreground">{exclusion.reason}</div>
                      </div>
                    ))
                  ) : (
                    <div className="rounded-xl border border-dashed border-border/60 px-4 py-10 text-center text-sm text-muted-foreground">
                      No exclusions yet.
                    </div>
                  )}
                </div>
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </div>

      {addDialogJobId ? (
        <AddToWorkspaceDialog
          jobId={addDialogJobId}
          open={true}
          onOpenChange={(open) => {
            if (!open) {
              setAddDialogJobId(null);
            }
          }}
          initialWorkspaceId={workspaceId}
        />
      ) : null}

      <WorkspaceRulesSlideover open={rulesOpen} onOpenChange={setRulesOpen} workspace={workspace} />
      <WorkspaceExclusionsSlideover
        open={exclusionsOpen}
        onOpenChange={setExclusionsOpen}
        workspace={workspace}
        activeJobId={null}
      />
    </>
  );
}

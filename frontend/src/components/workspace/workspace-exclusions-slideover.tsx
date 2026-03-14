import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Ban, CheckCircle2, Loader2 } from "lucide-react";
import { workspaceService, type WorkspaceState } from "@/api/services";
import { Button, Label, Textarea } from "@/components/ui";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { toast } from "sonner";

interface WorkspaceExclusionsSlideoverProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  workspace: WorkspaceState;
  activeJobId: string | null;
  contentClassName?: string;
}

export function WorkspaceExclusionsSlideover({
  open,
  onOpenChange,
  workspace,
  activeJobId,
  contentClassName,
}: WorkspaceExclusionsSlideoverProps) {
  const queryClient = useQueryClient();
  const [reason, setReason] = useState("Excluded from workspace automation");

  const activeJobExclusion = useMemo(
    () => workspace.exclusions.find((exclusion) => exclusion.document_id === activeJobId) ?? null,
    [activeJobId, workspace.exclusions]
  );
  const activeJobInWorkspace = useMemo(
    () => workspace.documents.some((document) => document.id === activeJobId),
    [activeJobId, workspace.documents]
  );

  const reincludeMutation = useMutation({
    mutationFn: (exclusionId: string) => workspaceService.removeExclusion(workspace.id, exclusionId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["workspace", workspace.id] });
      await queryClient.invalidateQueries({ queryKey: ["workspaces"] });
      toast.success("Document restored to workspace automation.");
    },
    onError: () => toast.error("Failed to re-include"),
  });

  const excludeMutation = useMutation({
    mutationFn: () => workspaceService.excludeDocument(workspace.id, activeJobId!, reason.trim()),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["workspace", workspace.id] });
      await queryClient.invalidateQueries({ queryKey: ["workspaces"] });
      toast.success("Document excluded from workspace automation.");
    },
    onError: () => toast.error("Failed to exclude"),
  });

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className={contentClassName}>
        <div className="flex h-full flex-col gap-4 p-6">
          <SheetHeader>
            <SheetTitle>{workspace.name} exclusions</SheetTitle>
            <SheetDescription>Exclude files from shared rule automation while keeping them in the workspace.</SheetDescription>
          </SheetHeader>

          {activeJobId && activeJobInWorkspace && !activeJobExclusion ? (
            <div className="space-y-3 rounded-xl border border-border/60 bg-muted/20 p-4">
              <div className="text-sm font-medium">Exclude current file</div>
              <div className="space-y-1.5">
                <Label htmlFor="workspace-exclusion-reason">Reason</Label>
                <Textarea
                  id="workspace-exclusion-reason"
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                  rows={3}
                />
              </div>
              <div className="flex justify-end">
                <Button
                  type="button"
                  size="sm"
                  onClick={() => void excludeMutation.mutateAsync()}
                  disabled={reason.trim().length === 0 || excludeMutation.isPending}
                >
                  {excludeMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Ban className="h-4 w-4" />}
                  Exclude current file
                </Button>
              </div>
            </div>
          ) : null}

          <ScrollArea className="min-h-0 flex-1 rounded-xl border border-border/60">
            <div className="space-y-3 p-4">
              {workspace.exclusions.length > 0 ? (
                workspace.exclusions.map((exclusion) => (
                  <div key={exclusion.id} className="rounded-xl border border-border/60 bg-background px-3 py-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="font-medium text-foreground">{exclusion.document_id}</div>
                        <div className="mt-1 text-xs text-muted-foreground">{exclusion.reason}</div>
                      </div>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => void reincludeMutation.mutateAsync(exclusion.id)}
                        disabled={reincludeMutation.isPending}
                      >
                        {reincludeMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                        Re-include
                      </Button>
                    </div>
                  </div>
                ))
              ) : (
                <div className="rounded-xl border border-dashed border-border/60 px-4 py-8 text-center text-sm text-muted-foreground">
                  No exclusions in this workspace.
                </div>
              )}
            </div>
          </ScrollArea>
        </div>
      </SheetContent>
    </Sheet>
  );
}

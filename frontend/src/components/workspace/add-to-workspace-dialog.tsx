import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Loader2, Plus } from "lucide-react";
import { workspaceService } from "@/api/services";
import { Button, Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, Input } from "@/components/ui";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { CreateWorkspaceDialog } from "./create-workspace-dialog";

interface AddToWorkspaceDialogProps {
  jobId: string;
  jobFilename?: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialWorkspaceId?: string | null;
  onAdded?: (workspaceId: string) => void;
}

export function AddToWorkspaceDialog({
  jobId,
  jobFilename,
  open,
  onOpenChange,
  initialWorkspaceId = null,
  onAdded,
}: AddToWorkspaceDialogProps) {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<string | null>(initialWorkspaceId);
  const [createOpen, setCreateOpen] = useState(false);

  const { data: workspaces = [] } = useQuery({
    queryKey: ["workspaces"],
    queryFn: () => workspaceService.listWorkspaces(),
    staleTime: 30_000,
  });

  const filteredWorkspaces = useMemo(
    () => workspaces.filter((workspace) => workspace.name.toLowerCase().includes(search.toLowerCase())),
    [search, workspaces]
  );

  const addMutation = useMutation({
    mutationFn: () => workspaceService.addDocument(selectedWorkspaceId!, jobId),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["workspaces"] }),
        queryClient.invalidateQueries({ queryKey: ["workspace", selectedWorkspaceId] }),
      ]);
      toast.success("Added document to workspace.");
      onAdded?.(selectedWorkspaceId!);
      onOpenChange(false);
      setSearch("");
    },
    onError: () => {
      toast.error("Failed to add to workspace");
    },
  });

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add to workspace</DialogTitle>
            <DialogDescription>
              {jobFilename ? `Choose a workspace for ${jobFilename}.` : "Choose a workspace for this document."}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3">
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search workspaces…"
            />

            <ScrollArea className="h-64 rounded-xl border border-border/60">
              <div className="space-y-1 p-2">
                {filteredWorkspaces.length > 0 ? (
                  filteredWorkspaces.map((workspace) => {
                    const selected = workspace.id === selectedWorkspaceId;
                    return (
                      <button
                        key={workspace.id}
                        type="button"
                        onClick={() => setSelectedWorkspaceId((current) => (current === workspace.id ? null : workspace.id))}
                        className={cn(
                          "flex w-full items-start justify-between rounded-lg border px-3 py-2 text-left transition-colors",
                          selected
                            ? "border-primary/40 bg-primary/6 text-foreground"
                            : "border-transparent hover:border-border/70 hover:bg-muted/40"
                        )}
                      >
                        <div className="min-w-0">
                          <div className="truncate font-medium">{workspace.name}</div>
                          {workspace.description ? (
                            <div className="mt-1 text-xs text-muted-foreground">{workspace.description}</div>
                          ) : null}
                        </div>
                        <span className="mt-0.5 flex h-5 w-5 items-center justify-center rounded-full border border-border/70">
                          {selected ? <Check className="h-3.5 w-3.5 text-primary" /> : null}
                        </span>
                      </button>
                    );
                  })
                ) : (
                  <div className="rounded-lg border border-dashed border-border/60 px-3 py-8 text-center text-sm text-muted-foreground">
                    No matching workspaces.
                  </div>
                )}
              </div>
            </ScrollArea>

            <Button type="button" variant="ghost" className="justify-start px-2" onClick={() => setCreateOpen(true)}>
              <Plus className="h-4 w-4" />
              Create new workspace
            </Button>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button
              type="button"
              onClick={() => void addMutation.mutateAsync()}
              disabled={!selectedWorkspaceId || addMutation.isPending}
            >
              {addMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Add to workspace
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <CreateWorkspaceDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={(workspace) => {
          setSelectedWorkspaceId(workspace.id);
          setCreateOpen(false);
        }}
      />
    </>
  );
}

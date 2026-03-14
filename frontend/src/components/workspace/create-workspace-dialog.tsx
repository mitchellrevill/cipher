import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, Plus } from "lucide-react";
import { workspaceService, type WorkspaceState } from "@/api/services";
import { Button, Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, Input, Label, Textarea } from "@/components/ui";
import { toast } from "sonner";

interface CreateWorkspaceDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  defaultName?: string;
  defaultDescription?: string;
  onCreated?: (workspace: WorkspaceState) => void;
}

export function CreateWorkspaceDialog({
  open,
  onOpenChange,
  defaultName = "",
  defaultDescription = "",
  onCreated,
}: CreateWorkspaceDialogProps) {
  const queryClient = useQueryClient();
  const [name, setName] = useState(defaultName);
  const [description, setDescription] = useState(defaultDescription);

  useEffect(() => {
    if (!open) {
      setName(defaultName);
      setDescription(defaultDescription);
    }
  }, [defaultDescription, defaultName, open]);

  const createMutation = useMutation({
    mutationFn: () => workspaceService.createWorkspace(name.trim(), description.trim() || undefined),
    onSuccess: async (workspace) => {
      await queryClient.invalidateQueries({ queryKey: ["workspaces"] });
      toast.success(`Workspace ${workspace.name} created.`);
      onCreated?.(workspace);
      onOpenChange(false);
      setName(defaultName);
      setDescription(defaultDescription);
    },
    onError: () => {
      toast.error("Failed to create workspace");
    },
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create workspace</DialogTitle>
          <DialogDescription>Group related documents, rules, and exclusions into one reusable workspace.</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="workspace-name">Name</Label>
            <Input
              id="workspace-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="HR Contracts"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="workspace-description">Description</Label>
            <Textarea
              id="workspace-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Optional context for this workspace"
              rows={4}
            />
          </div>
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            type="button"
            onClick={() => void createMutation.mutateAsync()}
            disabled={name.trim().length === 0 || createMutation.isPending}
          >
            {createMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Plus className="h-4 w-4" />
            )}
            Create workspace
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

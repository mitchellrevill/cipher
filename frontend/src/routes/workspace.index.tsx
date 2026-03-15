import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { FolderKanban, Loader2, Plus, WandSparkles } from "lucide-react";
import { workspaceService } from "@/api/services";
import { CreateWorkspaceDialog } from "@/components/workspace/create-workspace-dialog";
import { Badge, Button, PageHeading } from "@/components/ui";

export default function WorkspacesRoute() {
  const navigate = useNavigate();
  const [createOpen, setCreateOpen] = useState(false);

  const { data: workspaces, isLoading } = useQuery({
    queryKey: ["workspaces"],
    queryFn: () => workspaceService.listWorkspaces(),
  });

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <>
      <div className="flex h-full flex-col overflow-hidden">
        <PageHeading
          title="Workspaces"
          description="Manage your document workspaces"
          icon={<FolderKanban />}
          actions={
            <Button type="button" onClick={() => setCreateOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              New workspace
            </Button>
          }
          bleed={false}
        />
        <div className="flex-1 overflow-auto px-6 py-6">

        {workspaces && workspaces.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border/60 px-4 py-16 text-center">
            <FolderKanban className="mx-auto mb-3 h-8 w-8 text-muted-foreground" />
            <div className="text-sm font-medium text-foreground">No workspaces yet</div>
            <div className="mt-1 text-xs text-muted-foreground">
              Create a workspace to organise related documents.
            </div>
            <Button
              type="button"
              size="sm"
              className="mt-4"
              onClick={() => setCreateOpen(true)}
            >
              <Plus className="mr-2 h-3.5 w-3.5" />
              Create first workspace
            </Button>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {(workspaces ?? []).map((workspace) => (
              <div
                key={workspace.id}
                className="space-y-4 rounded-2xl border border-border/60 bg-background p-4"
              >
                <div className="flex items-start gap-3">
                  <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                    <FolderKanban className="h-5 w-5" />
                  </div>
                  <div className="min-w-0">
                    <div className="truncate font-medium text-foreground">{workspace.name}</div>
                    {workspace.description ? (
                      <div className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">
                        {workspace.description}
                      </div>
                    ) : null}
                  </div>
                </div>

                <div className="flex flex-wrap gap-1.5">
                  <Badge variant="secondary" className="rounded-full border-0">
                    {workspace.document_ids?.length ?? 0} files
                  </Badge>
                  <Badge variant="secondary" className="rounded-full border-0">
                    {workspace.rule_ids?.length ?? 0} rules
                  </Badge>
                  <Badge variant="secondary" className="rounded-full border-0">
                    {workspace.exclusion_ids?.length ?? 0} exclusions
                  </Badge>
                </div>

                <div className="flex gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="flex-1"
                    onClick={() =>
                      void navigate({
                        to: "/workspace/$workspaceId",
                        params: { workspaceId: workspace.id },
                      })
                    }
                  >
                    Open
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    className="flex-1"
                    onClick={() => {
                      const firstJobId = workspace.document_ids?.[0];
                      if (firstJobId) {
                        void navigate({
                          to: "/workspace/$workspaceId/designer/$jobId",
                          params: { workspaceId: workspace.id, jobId: firstJobId },
                        });
                        return;
                      }

                      void navigate({
                        to: "/workspace/$workspaceId/designer/new",
                        params: { workspaceId: workspace.id },
                      });
                    }}
                  >
                    <WandSparkles className="mr-1 h-3.5 w-3.5" />
                    Open in designer
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
        </div>
      </div>

      <CreateWorkspaceDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={(workspace) =>
          void navigate({
            to: "/workspace/$workspaceId",
            params: { workspaceId: workspace.id },
          })
        }
      />
    </>
  );
}

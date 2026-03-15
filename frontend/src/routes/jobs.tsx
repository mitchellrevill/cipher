import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { Files, FolderKanban, FolderPlus, Loader2, WandSparkles } from "lucide-react";
import { redactionJobService } from "@/api/services";
import { Button, PageHeading } from "@/components/ui";
import { AddToWorkspaceDialog } from "@/components/workspace/add-to-workspace-dialog";
import { setActiveJobId } from "@/lib/recent-jobs";
import { cn } from "@/lib/utils";

const STATUS_STYLES: Record<string, string> = {
  complete: "bg-green-500/10 text-green-600 dark:text-green-400",
  processing: "bg-blue-500/10 text-blue-600 dark:text-blue-400",
  pending: "bg-yellow-500/10 text-yellow-600 dark:text-yellow-400",
  failed: "bg-destructive/10 text-destructive",
};

export default function JobsRoute() {
  const navigate = useNavigate();
  const [unassignedOnly, setUnassignedOnly] = useState(false);
  const [addWorkspaceJobId, setAddWorkspaceJobId] = useState<string | null>(null);

  const { data: jobs, isLoading } = useQuery({
    queryKey: ["jobs", { unassigned: unassignedOnly }],
    queryFn: () => redactionJobService.listJobs({ unassigned: unassignedOnly }),
  });

  const handleOpen = (jobId: string) => {
    setActiveJobId(jobId);
    void navigate({ to: "/designer" });
  };

  const filterToggle = (
    <div className="flex items-center gap-1 rounded-lg border border-border/60 bg-muted/30 p-1">
      <button
        type="button"
        onClick={() => setUnassignedOnly(false)}
        className={cn(
          "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
          !unassignedOnly
            ? "bg-background text-foreground shadow-sm"
            : "text-muted-foreground hover:text-foreground"
        )}
      >
        All
      </button>
      <button
        type="button"
        onClick={() => setUnassignedOnly(true)}
        className={cn(
          "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
          unassignedOnly
            ? "bg-background text-foreground shadow-sm"
            : "text-muted-foreground hover:text-foreground"
        )}
      >
        Unassigned
      </button>
    </div>
  );

  return (
    <>
    <div className="flex h-full flex-col overflow-hidden">
      <PageHeading
        title="All Jobs"
        description="Every document processed through the pipeline"
        icon={<Files />}
        actions={filterToggle}
        bleed={false}
      />
      <div className="flex-1 overflow-auto px-6 py-6">

      {isLoading ? (
        <div className="flex h-40 items-center justify-center">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      ) : !jobs || jobs.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border/60 px-4 py-16 text-center">
          <Files className="mx-auto mb-3 h-8 w-8 text-muted-foreground" />
          <div className="text-sm font-medium text-foreground">
            {unassignedOnly ? "No unassigned jobs" : "No jobs yet"}
          </div>
          <div className="mt-1 text-xs text-muted-foreground">
            {unassignedOnly
              ? "All processed documents have been added to a workspace."
              : "Upload a document in the designer to get started."}
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          {jobs.map((job) => (
            <div
              key={job.job_id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border/60 bg-background px-4 py-3"
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="truncate font-medium text-foreground">
                    {job.filename ?? job.job_id}
                  </span>
                  <span
                    className={cn(
                      "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium capitalize",
                      STATUS_STYLES[job.status] ?? "bg-muted text-muted-foreground"
                    )}
                  >
                    {job.status}
                  </span>
                </div>
                <div className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
                  {job.created_at ? (
                    <span>{new Date(job.created_at).toLocaleString()}</span>
                  ) : null}
                  {job.suggestions_count > 0 ? (
                    <>
                      <span>·</span>
                      <span>{job.suggestions_count} suggestions</span>
                    </>
                  ) : null}
                  {job.workspace_id ? (
                    <>
                      <span>·</span>
                      <span className="flex items-center gap-1">
                        <FolderKanban className="h-3 w-3" />
                        In workspace
                      </span>
                    </>
                  ) : (
                    <>
                      <span>·</span>
                      <button
                        type="button"
                        onClick={(e) => { e.stopPropagation(); setAddWorkspaceJobId(job.job_id); }}
                        className="flex items-center gap-1 text-muted-foreground/60 transition-colors hover:text-primary"
                      >
                        <FolderPlus className="h-3 w-3" />
                        Add to workspace
                      </button>
                    </>
                  )}
                </div>
              </div>

              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => handleOpen(job.job_id)}
              >
                <WandSparkles className="mr-1.5 h-3.5 w-3.5" />
                Open in designer
              </Button>
            </div>
          ))}
        </div>
      )}
      </div>
    </div>

      {addWorkspaceJobId && (
        <AddToWorkspaceDialog
          jobId={addWorkspaceJobId}
          jobFilename={jobs?.find((j) => j.job_id === addWorkspaceJobId)?.filename}
          open={true}
          onOpenChange={(open) => { if (!open) setAddWorkspaceJobId(null); }}
        />
      )}
    </>
  );
}

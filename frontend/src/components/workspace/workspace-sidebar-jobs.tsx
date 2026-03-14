import { useState, type ElementType } from "react";
import { CheckCircle, Clock, FileText, Loader2, Plus, XCircle } from "lucide-react";
import { AddToWorkspaceDialog } from "@/components/workspace/add-to-workspace-dialog";
import { ContextMenu, ContextMenuContent, ContextMenuItem, ContextMenuTrigger } from "@/components/ui/context-menu";
import type { RecentJobRecord } from "@/lib/recent-jobs";
import { cn } from "@/lib/utils";

const STATUS_ICON: Record<string, ElementType> = {
  complete: CheckCircle,
  failed: XCircle,
  pending: Clock,
  processing: Loader2,
};

interface WorkspaceSidebarJobsProps {
  jobs: RecentJobRecord[];
  selectedJobId: string | null;
  onJobSelect: (jobId: string) => void;
  className?: string;
}

export function WorkspaceSidebarJobs({ jobs, selectedJobId, onJobSelect, className }: WorkspaceSidebarJobsProps) {
  const [dialogJob, setDialogJob] = useState<RecentJobRecord | null>(null);

  return (
    <>
      <div className={cn("flex flex-col gap-0.5 px-2 py-1", className)}>
        <div className="px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-sidebar-foreground/60">
          Recent jobs
        </div>

        {jobs.length > 0 ? (
          jobs.map((job) => {
            const Icon = STATUS_ICON[job.status] ?? FileText;
            const isSelected = job.jobId === selectedJobId;
            return (
              <ContextMenu key={job.jobId}>
                <ContextMenuTrigger asChild>
                  <button
                    type="button"
                    data-selected={isSelected}
                    onClick={() => onJobSelect(job.jobId)}
                    className={cn(
                      "flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-sm transition-colors",
                      isSelected
                        ? "bg-sidebar-accent text-sidebar-accent-foreground"
                        : "text-sidebar-foreground/75 hover:bg-sidebar-accent/70 hover:text-sidebar-accent-foreground"
                    )}
                  >
                    <Icon className={cn("h-4 w-4 shrink-0", job.status === "processing" && "animate-spin")} />
                    <span className="truncate">{job.filename}</span>
                  </button>
                </ContextMenuTrigger>
                <ContextMenuContent>
                  <ContextMenuItem onSelect={() => onJobSelect(job.jobId)}>Open job</ContextMenuItem>
                  <ContextMenuItem onSelect={() => setDialogJob(job)}>
                    <Plus className="mr-2 h-4 w-4" />
                    Add to workspace
                  </ContextMenuItem>
                </ContextMenuContent>
              </ContextMenu>
            );
          })
        ) : (
          <div className="rounded-lg border border-dashed border-sidebar-border px-3 py-4 text-sm text-sidebar-foreground/60">
            No jobs yet.
          </div>
        )}
      </div>

      {dialogJob ? (
        <AddToWorkspaceDialog
          jobId={dialogJob.jobId}
          jobFilename={dialogJob.filename}
          open={true}
          onOpenChange={(open) => {
            if (!open) {
              setDialogJob(null);
            }
          }}
        />
      ) : null}
    </>
  );
}

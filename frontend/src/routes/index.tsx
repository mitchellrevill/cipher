import { useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, FileSearch, House } from "lucide-react";
import { redactionJobService, workspaceService } from "@/api/services";
import { Button, Card, CardContent, CardHeader, CardTitle, PageHeading } from "@/components/ui";

export default function IndexRoute() {
  const navigate = useNavigate();
  const jobsQuery = useQuery({
    queryKey: ["jobs", { limit: 6 }],
    queryFn: () => redactionJobService.listJobs({ limit: 6 }),
  });
  const workspacesQuery = useQuery({
    queryKey: ["workspaces"],
    queryFn: () => workspaceService.listWorkspaces(),
  });

  const recentJobs = jobsQuery.data ?? [];
  const workspaces = workspacesQuery.data ?? [];
  const processingJobs = recentJobs.filter((j) => j.status === "pending" || j.status === "processing").length;
  const completedJobs = recentJobs.filter((j) => j.status === "complete").length;

  const openWorkspace = async (jobId?: string) => {
    if (jobId) {
      await navigate({ to: "/designer/$jobId", params: { jobId } });
      return;
    }

    await navigate({ to: "/designer/new" });
  };

  return (
    <div className="flex h-full flex-col overflow-auto">
      <PageHeading
        title="Overview"
        description="Document redaction pipeline status"
        icon={<House />}
        bleed={false}
      />
      <div className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6 space-y-8">

      {/* Stats */}
      <div className="grid gap-3 sm:grid-cols-3">
        <Card>
          <CardContent className="p-4">
            <div className="text-xs text-muted-foreground uppercase tracking-wider">Processing</div>
            <div className="mt-1.5 text-3xl font-semibold tabular-nums">{processingJobs}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-xs text-muted-foreground uppercase tracking-wider">Completed</div>
            <div className="mt-1.5 text-3xl font-semibold tabular-nums">{completedJobs}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-xs text-muted-foreground uppercase tracking-wider">Workspaces</div>
            <div className="mt-1.5 text-3xl font-semibold tabular-nums">{workspaces.length}</div>
          </CardContent>
        </Card>
      </div>

      {/* CTA */}
      <div className="flex gap-3">
        <Button onClick={() => void openWorkspace()}>
          Upload new document
          <ArrowRight className="ml-2 h-4 w-4" />
        </Button>
        {recentJobs[0] && (
          <Button variant="outline" onClick={() => void openWorkspace(recentJobs[0].job_id)}>
            Resume latest job
          </Button>
        )}
      </div>

      {/* Recent sessions */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-sm font-medium">
            <FileSearch className="h-4 w-4" />
            Recent sessions
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          {jobsQuery.isLoading ? (
            <div className="rounded-lg border border-dashed border-border px-4 py-5 text-sm text-muted-foreground">
              Loading recent jobs…
            </div>
          ) : recentJobs.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border px-4 py-5 text-sm text-muted-foreground">
              No saved sessions yet. Upload a PDF to get started.
            </div>
          ) : (
            <div className="divide-y divide-border/60">
              {recentJobs.slice(0, 6).map((job) => (
                <button
                  key={job.job_id}
                  type="button"
                  className="w-full py-3 text-left transition-colors hover:bg-muted/30 px-1 rounded-lg"
                  onClick={() => void openWorkspace(job.job_id)}
                >
                  <div className="text-sm font-medium text-foreground">{job.filename ?? job.job_id}</div>
                  <div className="mt-0.5 text-xs text-muted-foreground">
                    {job.created_at ? new Date(job.created_at).toLocaleString() : "Unknown date"}
                    {" · "}
                    <span className="capitalize">{job.status}</span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium">Recent workspaces</CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          {workspacesQuery.isLoading ? (
            <div className="rounded-lg border border-dashed border-border px-4 py-5 text-sm text-muted-foreground">
              Loading workspaces…
            </div>
          ) : workspaces.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border px-4 py-5 text-sm text-muted-foreground">
              No workspaces yet.
            </div>
          ) : (
            <div className="divide-y divide-border/60">
              {workspaces.slice(0, 6).map((workspace) => (
                <button
                  key={workspace.id}
                  type="button"
                  className="w-full py-3 text-left transition-colors hover:bg-muted/30 px-1 rounded-lg"
                  onClick={() =>
                    void navigate({
                      to: "/workspace/$workspaceId",
                      params: { workspaceId: workspace.id },
                    })
                  }
                >
                  <div className="text-sm font-medium text-foreground">{workspace.name}</div>
                  <div className="mt-0.5 text-xs text-muted-foreground">
                    {(workspace.document_ids?.length ?? 0)} files · {(workspace.rule_ids?.length ?? 0)} rules
                  </div>
                </button>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
      </div>
    </div>
  );
}


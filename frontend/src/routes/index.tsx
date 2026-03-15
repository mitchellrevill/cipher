import { useNavigate } from "@tanstack/react-router";
import { ArrowRight, FileSearch, House } from "lucide-react";
import { Button, Card, CardContent, CardHeader, CardTitle, PageHeading } from "@/components/ui";
import { useRecentJobs } from "@/hooks/useRecentJobs";
import { setActiveJobId } from "@/lib/recent-jobs";
import { formatBytes } from "@/lib/utils";

export default function IndexRoute() {
  const navigate = useNavigate();
  const { recentJobs } = useRecentJobs();

  const processingJobs = recentJobs.filter((j) => j.status === "pending" || j.status === "processing").length;
  const completedJobs = recentJobs.filter((j) => j.status === "complete").length;

  const openWorkspace = async (jobId?: string) => {
    if (jobId) setActiveJobId(jobId);
    await navigate({ to: "/designer" });
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
            <div className="text-xs text-muted-foreground uppercase tracking-wider">Total sessions</div>
            <div className="mt-1.5 text-3xl font-semibold tabular-nums">{recentJobs.length}</div>
          </CardContent>
        </Card>
      </div>

      {/* CTA */}
      <div className="flex gap-3">
        <Button onClick={() => void openWorkspace()}>
          Open workspace
          <ArrowRight className="ml-2 h-4 w-4" />
        </Button>
        {recentJobs[0] && (
          <Button variant="outline" onClick={() => void openWorkspace(recentJobs[0].jobId)}>
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
          {recentJobs.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border px-4 py-5 text-sm text-muted-foreground">
              No saved sessions yet. Upload a PDF to get started.
            </div>
          ) : (
            <div className="divide-y divide-border/60">
              {recentJobs.slice(0, 6).map((job) => (
                <button
                  key={job.jobId}
                  type="button"
                  className="w-full py-3 text-left transition-colors hover:bg-muted/30 px-1 rounded-lg"
                  onClick={() => void openWorkspace(job.jobId)}
                >
                  <div className="text-sm font-medium text-foreground">{job.filename}</div>
                  <div className="mt-0.5 text-xs text-muted-foreground">
                    {new Date(job.createdAt).toLocaleString()}
                    {job.fileSize ? ` · ${formatBytes(job.fileSize, { decimals: 1 })}` : ""}
                    {" · "}
                    <span className="capitalize">{job.status}</span>
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


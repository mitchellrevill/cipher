import { ArrowUpRight, Ban, BookOpen, Briefcase, Plus } from "lucide-react";
import type { WorkspaceState } from "@/api/services";
import { Button } from "@/components/ui";
import { cn } from "@/lib/utils";

interface WorkspaceChatHeaderProps {
  workspace: WorkspaceState | null;
  activeJobId: string | null;
  onRulesClick: () => void;
  onExclusionsClick: () => void;
  onAddToWorkspace: () => void;
  onCreateWorkspace: () => void;
  className?: string;
}

export function WorkspaceChatHeader({
  workspace,
  activeJobId,
  onRulesClick,
  onExclusionsClick,
  onAddToWorkspace,
  onCreateWorkspace,
  className,
}: WorkspaceChatHeaderProps) {
  if (!workspace) {
    return (
      <div className={cn("border-b border-border/60 bg-muted/20 px-3 py-2.5", className)}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="text-sm font-medium text-foreground">No workspace selected</div>
            <div className="text-xs text-muted-foreground">Choose a workspace to reuse rules and exclusions across documents.</div>
          </div>

          {activeJobId ? (
            <div className="flex flex-wrap items-center gap-2">
              <Button type="button" variant="outline" size="sm" onClick={onAddToWorkspace}>
                <Briefcase className="h-4 w-4" />
                Add to workspace
              </Button>
              <Button type="button" size="sm" onClick={onCreateWorkspace}>
                <Plus className="h-4 w-4" />
                Create workspace
              </Button>
            </div>
          ) : null}
        </div>
      </div>
    );
  }

  const rulesCount = workspace.stats?.rule_count ?? workspace.rules.length;
  const exclusionsCount = workspace.stats?.exclusion_count ?? workspace.exclusions.length;

  return (
    <div className={cn("border-b border-border/60 bg-muted/20 px-3 py-2.5", className)}>
      <div className="flex flex-wrap items-center gap-2">
        <div className="mr-2 min-w-0 flex-1">
          <div className="truncate text-sm font-semibold text-foreground">{workspace.name}</div>
          {workspace.description ? <div className="truncate text-xs text-muted-foreground">{workspace.description}</div> : null}
        </div>

        <Button type="button" variant="outline" size="sm" onClick={onRulesClick} aria-label="Rules">
          <BookOpen className="h-4 w-4" />
          Rules {rulesCount}
        </Button>
        <Button type="button" variant="outline" size="sm" onClick={onExclusionsClick} aria-label="Exclusions">
          <Ban className="h-4 w-4" />
          Exclusions {exclusionsCount}
        </Button>
        <Button type="button" variant="ghost" size="sm" asChild>
          <a href={`/workspace/${workspace.id}`}>
            Open workspace
            <ArrowUpRight className="h-4 w-4" />
          </a>
        </Button>
      </div>
    </div>
  );
}

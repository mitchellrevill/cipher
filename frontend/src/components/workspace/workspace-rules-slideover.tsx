import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { BookOpen, Loader2, Plus } from "lucide-react";
import { workspaceService, type WorkspaceState } from "@/api/services";
import { Button, Input, Label } from "@/components/ui";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { toast } from "sonner";

interface WorkspaceRulesSlideoverProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  workspace: WorkspaceState;
  contentClassName?: string;
}

export function WorkspaceRulesSlideover({ open, onOpenChange, workspace, contentClassName }: WorkspaceRulesSlideoverProps) {
  const queryClient = useQueryClient();
  const [pattern, setPattern] = useState("");
  const [category, setCategory] = useState("PII");
  const [showForm, setShowForm] = useState(false);

  const rulesCount = useMemo(() => workspace.stats?.rule_count ?? workspace.rules.length, [workspace.rules.length, workspace.stats?.rule_count]);

  const createMutation = useMutation({
    mutationFn: () =>
      workspaceService.createRule(workspace.id, {
        pattern: pattern.trim(),
        category: category.trim(),
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["workspace", workspace.id] });
      await queryClient.invalidateQueries({ queryKey: ["workspaces"] });
      setPattern("");
      setCategory("PII");
      setShowForm(false);
      toast.success("Rule added to workspace.");
    },
    onError: () => toast.error("Failed to add rule"),
  });

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className={contentClassName}>
        <div className="flex h-full flex-col gap-4 p-6">
          <SheetHeader>
            <SheetTitle>{workspace.name} rules</SheetTitle>
            <SheetDescription>Reusable redaction patterns shared across workspace files.</SheetDescription>
          </SheetHeader>

          <div className="flex items-center justify-between gap-3 rounded-xl border border-border/60 bg-muted/20 px-3 py-2">
            <div>
              <div className="text-sm font-medium">{rulesCount} rules</div>
              <div className="text-xs text-muted-foreground">Patterns that the assistant can apply across related documents.</div>
            </div>
            <Button type="button" size="sm" onClick={() => setShowForm((current) => !current)}>
              <Plus className="h-4 w-4" />
              Add rule
            </Button>
          </div>

          {showForm ? (
            <div className="space-y-3 rounded-xl border border-border/60 p-4">
              <div className="space-y-1.5">
                <Label htmlFor="workspace-rule-pattern">Pattern</Label>
                <Input
                  id="workspace-rule-pattern"
                  value={pattern}
                  onChange={(event) => setPattern(event.target.value)}
                  placeholder="\\b\\d{3}-\\d{2}-\\d{4}\\b"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="workspace-rule-category">Category</Label>
                <Input
                  id="workspace-rule-category"
                  value={category}
                  onChange={(event) => setCategory(event.target.value)}
                  placeholder="PII"
                />
              </div>
              <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" size="sm" onClick={() => setShowForm(false)}>
                  Cancel
                </Button>
                <Button
                  type="button"
                  size="sm"
                  onClick={() => void createMutation.mutateAsync()}
                  disabled={pattern.trim().length === 0 || category.trim().length === 0 || createMutation.isPending}
                >
                  {createMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                  Save rule
                </Button>
              </div>
            </div>
          ) : null}

          <ScrollArea className="min-h-0 flex-1 rounded-xl border border-border/60">
            <div className="space-y-3 p-4">
              {workspace.rules.length > 0 ? (
                workspace.rules.map((rule) => (
                  <div key={rule.id} className="rounded-xl border border-border/60 bg-background px-3 py-3">
                    <div className="flex items-start gap-3">
                      <div className="mt-0.5 flex h-8 w-8 items-center justify-center rounded-xl bg-primary/10 text-primary">
                        <BookOpen className="h-4 w-4" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="font-medium text-foreground">{rule.category}</div>
                        <div className="mt-1 break-all font-mono text-xs text-muted-foreground">{rule.pattern}</div>
                      </div>
                    </div>
                  </div>
                ))
              ) : (
                <div className="rounded-xl border border-dashed border-border/60 px-4 py-8 text-center text-sm text-muted-foreground">
                  No workspace rules yet.
                </div>
              )}
            </div>
          </ScrollArea>
        </div>
      </SheetContent>
    </Sheet>
  );
}

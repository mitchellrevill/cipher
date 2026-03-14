import { useDraggable } from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import { CheckCircle, Clock, FileText, Loader2, MessageSquarePlus, XCircle, type LucideIcon } from "lucide-react";
import type { ChatContextFile } from "@/store/workspace-store";
import { cn } from "@/lib/utils";

export interface PanelFile {
  id: string;
  filename: string | null;
  status: string;
  workspaceId?: string;
}

interface WorkspaceFilesPanelProps {
  files: PanelFile[];
  selectedJobId: string | null;
  onJobSelect: (id: string) => void;
  onAddToChat: (file: ChatContextFile) => void;
}

const STATUS_ICON: Record<string, LucideIcon> = {
  complete: CheckCircle,
  failed: XCircle,
  pending: Clock,
  processing: Loader2,
};

function DraggableFileItem({
  file,
  selected,
  onSelect,
  onAddToChat,
}: {
  file: PanelFile;
  selected: boolean;
  onSelect: () => void;
  onAddToChat: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: `file-${file.id}`,
    data: {
      jobId: file.id,
      filename: file.filename ?? file.id,
      workspaceId: file.workspaceId ?? "",
    } satisfies ChatContextFile,
  });

  const style = {
    transform: CSS.Translate.toString(transform),
  };

  const Icon = STATUS_ICON[file.status] ?? FileText;

  return (
    <div ref={setNodeRef} style={style} className={cn(isDragging && "opacity-60")}> 
      <div
        className={cn(
          "group flex items-center gap-2 rounded-xl border px-2.5 py-2 transition-colors",
          selected ? "border-primary/40 bg-primary/6" : "border-transparent hover:border-border/70 hover:bg-muted/40"
        )}
        {...attributes}
        {...listeners}
      >
        <button
          type="button"
          data-selected={selected}
          onClick={onSelect}
          className="flex min-w-0 flex-1 items-center gap-2 text-left"
        >
          <Icon className={cn("h-4 w-4 shrink-0 text-muted-foreground", file.status === "processing" && "animate-spin")} />
          <span className="truncate text-sm text-foreground">{file.filename ?? file.id}</span>
        </button>
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            onAddToChat();
          }}
          className="rounded-lg p-1 text-muted-foreground opacity-0 transition-opacity hover:bg-muted hover:text-foreground group-hover:opacity-100"
          aria-label={`Add ${file.filename ?? file.id} to chat`}
        >
          <MessageSquarePlus className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

export function WorkspaceFilesPanel({ files, selectedJobId, onJobSelect, onAddToChat }: WorkspaceFilesPanelProps) {
  return (
    <div className="flex h-full flex-col border-r border-border/60 bg-background">
      <div className="border-b border-border/60 px-3 py-3">
        <div className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Files</div>
        <div className="mt-1 text-xs text-muted-foreground">Click to open or drag into chat.</div>
      </div>

      <div className="flex-1 space-y-1 overflow-y-auto px-2 py-2">
        {files.length > 0 ? (
          files.map((file) => (
            <DraggableFileItem
              key={file.id}
              file={file}
              selected={file.id === selectedJobId}
              onSelect={() => onJobSelect(file.id)}
              onAddToChat={() =>
                onAddToChat({
                  jobId: file.id,
                  filename: file.filename ?? file.id,
                  workspaceId: file.workspaceId ?? "",
                })
              }
            />
          ))
        ) : (
          <div className="rounded-xl border border-dashed border-border/60 px-4 py-8 text-center text-sm text-muted-foreground">
            No files in this workspace yet.
          </div>
        )}
      </div>
    </div>
  );
}

import { Loader2, Search, WandSparkles, X } from "lucide-react";
import { Input } from "@/components/ui";
import type { TextMatch } from "@/types/search";

interface SearchToolbarProps {
  value: string;
  onChange: (value: string) => void;
  onClear: () => void;
  matchCount: number;
  isSearching: boolean;
  error?: string;
  activeMatchIndex?: number;
  activeMatch?: TextMatch | null;
  onFindNext?: () => void;
  onRedactAllInstances?: () => void;
  isRedactingAllInstances?: boolean;
}

export function SearchToolbar({
  value,
  onChange,
  onClear,
  matchCount,
  isSearching,
  error,
  activeMatchIndex = -1,
  activeMatch = null,
  onFindNext,
  onRedactAllInstances,
  isRedactingAllInstances = false,
}: SearchToolbarProps) {
  const hasMatches = value && !isSearching && matchCount > 0;

  return (
    <div className="flex items-center gap-2 px-3 py-2 bg-background border border-border/60 rounded-lg">
      <Search className="h-4 w-4 text-muted-foreground flex-shrink-0" />

      <Input
        type="text"
        placeholder="Search PDF text..."
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="flex-1 min-w-0 h-8 text-sm border-0 bg-transparent focus-visible:ring-0 px-2"
        disabled={isSearching}
      />

      {value && (
        <button
          type="button"
          onClick={onClear}
          className="flex-shrink-0 p-1 text-muted-foreground hover:text-foreground hover:bg-muted rounded transition-colors"
          title="Clear search"
        >
          <X className="h-4 w-4" />
        </button>
      )}

      {isSearching && (
        <span className="text-xs text-muted-foreground px-2 flex-shrink-0">
          Searching...
        </span>
      )}

      {hasMatches ? (
        <>
          <span className="text-xs text-muted-foreground px-2 flex-shrink-0 whitespace-nowrap">
            {activeMatchIndex + 1}/{matchCount} · p.{(activeMatch?.pageNum ?? 0) + 1}
          </span>

          {activeMatch?.text ? (
            <span
              className="hidden max-w-44 truncate rounded-md bg-amber-500/10 px-2 py-1 text-xs text-amber-700 dark:text-amber-300 md:inline-block"
              title={activeMatch.text}
            >
              “{activeMatch.text}”
            </span>
          ) : null}

          <button
            type="button"
            onClick={onFindNext}
            className="flex-shrink-0 rounded-md border border-border/70 px-2 py-1 text-xs font-medium text-foreground transition-colors hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={!onFindNext}
            title="Jump to the next search match"
          >
            Find next
          </button>

          <button
            type="button"
            onClick={onRedactAllInstances}
            className="flex flex-shrink-0 items-center gap-1 rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-1 text-xs font-medium text-amber-700 transition-colors hover:bg-amber-500/15 disabled:cursor-not-allowed disabled:opacity-50 dark:text-amber-300"
            disabled={!onRedactAllInstances || isRedactingAllInstances}
            title="Create redactions for all current search matches"
          >
            {isRedactingAllInstances ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <WandSparkles className="h-3.5 w-3.5" />
            )}
            Redact all instances
          </button>
        </>
      ) : null}

      {error && (
        <span className="text-xs text-destructive px-2 flex-shrink-0 truncate" title={error}>
          Error
        </span>
      )}
    </div>
  );
}

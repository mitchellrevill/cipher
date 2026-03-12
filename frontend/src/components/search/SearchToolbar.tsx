import { X, Search } from "lucide-react";
import { Input } from "@/components/ui";
import { cn } from "@/lib/utils";

interface SearchToolbarProps {
  value: string;
  onChange: (value: string) => void;
  onClear: () => void;
  matchCount: number;
  isSearching: boolean;
  error?: string;
}

export function SearchToolbar({
  value,
  onChange,
  onClear,
  matchCount,
  isSearching,
  error,
}: SearchToolbarProps) {
  return (
    <div className="flex items-center gap-2 px-3 py-2 bg-background border border-border/60 rounded-lg">
      <Search className="h-4 w-4 text-muted-foreground flex-shrink-0" />

      <Input
        type="text"
        placeholder="Search PDF (fuzzy match)..."
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

      {value && !isSearching && matchCount > 0 && (
        <span className="text-xs text-muted-foreground px-2 flex-shrink-0 whitespace-nowrap">
          {matchCount} {matchCount === 1 ? "match" : "matches"}
        </span>
      )}

      {error && (
        <span className="text-xs text-destructive px-2 flex-shrink-0 truncate" title={error}>
          Error
        </span>
      )}
    </div>
  );
}

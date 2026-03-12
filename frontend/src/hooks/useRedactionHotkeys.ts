import { useHotkey } from "@tanstack/react-hotkeys";
import type { Suggestion } from "@/api/services";

interface UseRedactionHotkeysProps {
  selectedSuggestionId: string | null;
  suggestions: Suggestion[];
  onSuggestionSelect: (id: string) => void;
  onApprovalChange: (id: string, approved: boolean) => void;
  onApproveAll: () => void;
}

export function useRedactionHotkeys({
  selectedSuggestionId,
  suggestions,
  onSuggestionSelect,
  onApprovalChange,
  onApproveAll,
}: UseRedactionHotkeysProps) {
  // A: Approve current suggestion
  useHotkey("A", () => {
    if (selectedSuggestionId) {
      onApprovalChange(selectedSuggestionId, true);
    }
  });

  // R: Reject current suggestion
  useHotkey("R", () => {
    if (selectedSuggestionId) {
      onApprovalChange(selectedSuggestionId, false);
    }
  });

  // Ctrl+Shift+A: Approve all
  useHotkey("Mod+Shift+A", (event: KeyboardEvent) => {
    event.preventDefault();
    onApproveAll();
  });

  // Arrow Up: Previous suggestion
  useHotkey("ArrowUp", (event: KeyboardEvent) => {
    event.preventDefault();
    if (!selectedSuggestionId && suggestions.length > 0) {
      onSuggestionSelect(suggestions[0].id);
      return;
    }
    const currentIndex = suggestions.findIndex((s) => s.id === selectedSuggestionId);
    if (currentIndex > 0) {
      onSuggestionSelect(suggestions[currentIndex - 1].id);
    }
  });

  // Arrow Down: Next suggestion
  useHotkey("ArrowDown", (event: KeyboardEvent) => {
    event.preventDefault();
    if (!selectedSuggestionId && suggestions.length > 0) {
      onSuggestionSelect(suggestions[0].id);
      return;
    }
    const currentIndex = suggestions.findIndex((s) => s.id === selectedSuggestionId);
    if (currentIndex < suggestions.length - 1) {
      onSuggestionSelect(suggestions[currentIndex + 1].id);
    }
  });
}

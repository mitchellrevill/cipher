import { useState, type ReactNode } from "react";
import { useDroppable } from "@dnd-kit/core";
import {
	Bot,
	CheckCircle2,
	ChevronDown,
	FilePlus2,
	FileSearch,
	FolderKanban,
	Loader2,
	MessageSquareText,
	Search,
	Send,
	ShieldBan,
	Sparkles,
	Trash2,
	User2,
	WandSparkles,
	X,
} from "lucide-react";
import { Badge, Checkbox } from "@/components/ui";

import {
	PromptInput,
	PromptInputAction,
	PromptInputActions,
	PromptInputTextarea,
} from "@/components/ui/prompt-input";
import { MotionDiv } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { useWorkspaceStore } from "@/store/workspace-store";
import type { Suggestion } from "@/api/services";

export interface AgentToolEvent {
	id: string;
	type: "tool_start" | "tool_result" | "tool_error";
	toolName: string;
	summary?: string;
}

export interface AgentChatMessage {
	id: string;
	role: "user" | "assistant";
	text: string;
	status?: "streaming" | "done" | "error";
	toolEvents?: AgentToolEvent[];
}

export interface AgentConversationState {
	messages: AgentChatMessage[];
	sessionId?: string;
}

export interface SuggestionsSection {
	suggestions: Suggestion[];
	selectedSuggestionId: string | null;
	onSuggestionSelect: (s: Suggestion) => void;
	onApprovalChange: (id: string, approved: boolean) => void;
	onDelete: (suggestionId: string) => void;
	getSuggestionPageLabel: (s: Suggestion) => string;
	isLoading: boolean;
	hasJobData: boolean;
	jobStatus: string | null;
	error?: string | null;
}

interface AgentChatPanelProps {
	conversation: AgentConversationState;
	promptPresets: string[];
	isStreaming: boolean;
	chatInput: string;
	onChatInputChange: (value: string) => void;
	onSubmit: () => void;
	inputPlaceholder?: string;
	inputDisabled?: boolean;
	onQuickPrompt: (prompt: string) => void;
	renderMessageText: (text: string) => ReactNode;
	suggestionsSection?: SuggestionsSection;
}

const TOOL_ICON_MAP: Record<string, typeof Search> = {
	search_document: Search,
	search_workspace: Search,
	get_document_summary: FileSearch,
	list_document_suggestions: MessageSquareText,
	get_suggestion_details: MessageSquareText,
	get_workspace_state: FolderKanban,
	create_rule: WandSparkles,
	create_suggestion: FilePlus2,
	apply_rule: Sparkles,
	approve_suggestion: CheckCircle2,
	preview_bulk_approval: CheckCircle2,
	apply_bulk_approval: Sparkles,
	bulk_create_suggestions: FilePlus2,
	exclude_document: ShieldBan,
	list_workspace_rules: FolderKanban,
	list_workspace_exclusions: ShieldBan,
	add_document_to_workspace: FilePlus2,
	delete_suggestion: Trash2,
	remove_document_from_workspace: Trash2,
	remove_exclusion: CheckCircle2,
};

function formatToolName(toolName: string): string {
	return toolName
		.split("_")
		.map((part) => part.charAt(0).toUpperCase() + part.slice(1))
		.join(" ");
}

function ToolEventCard({ event }: { event: AgentToolEvent }) {
	const Icon = TOOL_ICON_MAP[event.toolName] ?? MessageSquareText;
	const toneClass =
		event.type === "tool_error"
			? "border-destructive/30 bg-destructive/8 text-destructive"
			: event.type === "tool_result"
				? "border-emerald-500/20 bg-emerald-500/8 text-emerald-700 dark:text-emerald-300"
				: "border-primary/20 bg-primary/8 text-primary";

	return (
		<div className={cn("rounded-2xl border px-3 py-2", toneClass)}>
			<div className="flex items-center gap-2">
				<div className="flex h-7 w-7 items-center justify-center rounded-xl bg-background/70">
					{event.type === "tool_start" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Icon className="h-3.5 w-3.5" />}
				</div>
				<div className="min-w-0 flex-1">
					<div className="flex items-center gap-2">
						<span className="truncate text-[11px] font-semibold uppercase tracking-[0.18em]">
							{formatToolName(event.toolName)}
						</span>
						<Badge
							variant="secondary"
							className={cn(
								"rounded-full border-0 px-1.5 py-0 text-[10px]",
								event.type === "tool_error"
									? "bg-destructive/15 text-destructive"
									: event.type === "tool_result"
										? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300"
										: "bg-primary/15 text-primary"
							)}
						>
							{event.type === "tool_start" ? "Running" : event.type === "tool_result" ? "Done" : "Error"}
						</Badge>
					</div>
					{event.summary ? <p className="mt-1 text-xs leading-relaxed opacity-90">{event.summary}</p> : null}
				</div>
			</div>
		</div>
	);
}

function EmptyState({ promptPresets, onQuickPrompt }: Pick<AgentChatPanelProps, "promptPresets" | "onQuickPrompt">) {
	return (
		<div className="space-y-3">
			<div className="rounded-3xl border border-border/60 bg-muted/20 p-4 text-sm text-muted-foreground">
				Ask the assistant to search, explain redactions, or jump to a page. Streaming responses and tool activity will appear here live.
			</div>
			<div className="flex flex-wrap gap-2">
				{promptPresets.map((prompt) => (
					<button
						key={prompt}
						type="button"
						onClick={() => onQuickPrompt(prompt)}
						className="rounded-full border border-border/60 bg-background px-3 py-2 text-left text-[11px] leading-4 text-muted-foreground transition-colors hover:border-primary/30 hover:bg-primary/5 hover:text-foreground"
					>
						{prompt}
					</button>
				))}
			</div>
		</div>
	);
}

export function AgentChatPanel({
	conversation,
	promptPresets,
	isStreaming,
	chatInput,
	onChatInputChange,
	onSubmit,
	inputPlaceholder = "Ask the assistant…",
	inputDisabled = false,
	onQuickPrompt,
	renderMessageText,
	suggestionsSection,
}: AgentChatPanelProps) {
	const { chatContextFiles, removeDragContextFile } = useWorkspaceStore();
	const { isOver, setNodeRef } = useDroppable({ id: "chat-drop-zone" });
	const [suggestionsOpen, setSuggestionsOpen] = useState(true);
	const canSubmit = chatInput.trim().length > 0 && !inputDisabled && !isStreaming;

	return (
		<div className="flex flex-1 min-h-0 flex-col overflow-hidden">
			<div className="flex-1 min-h-0 overflow-y-auto px-4 py-4">
				<div className="space-y-4">
					{conversation.messages.length === 0 ? (
						<EmptyState promptPresets={promptPresets} onQuickPrompt={onQuickPrompt} />
					) : (
						conversation.messages.map((message) => {
							const isAssistant = message.role === "assistant";

							return (
								<MotionDiv
									key={message.id}
									initial={{ opacity: 0, y: 10 }}
									animate={{ opacity: 1, y: 0 }}
									transition={{ duration: 0.2, ease: [0.23, 1, 0.32, 1] }}
									className={cn("flex gap-3", isAssistant ? "justify-start" : "justify-end")}
								>
									{isAssistant ? (
										<div className="mt-1 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-2xl border border-primary/20 bg-primary/10 text-primary">
											<Bot className="h-4 w-4" />
										</div>
									) : null}

									<div className={cn("max-w-[88%] space-y-2", isAssistant ? "mr-8" : "ml-8 items-end")}>
										<div
											className={cn(
												"rounded-3xl border px-4 py-3 shadow-sm",
												isAssistant
													? "border-border/60 bg-muted/35 text-foreground"
													: "border-primary/30 bg-primary text-primary-foreground"
											)}
										>
											<div className="mb-2 flex items-center gap-2">
												<span className="text-[11px] font-semibold uppercase tracking-[0.18em] opacity-70">
													{isAssistant ? "Assistant" : "You"}
												</span>
												{isAssistant && message.status === "streaming" ? (
													<Badge variant="secondary" className="rounded-full border-0 bg-primary/15 text-primary">
														Live
													</Badge>
												) : null}
												{isAssistant && message.status === "error" ? (
													<Badge variant="secondary" className="rounded-full border-0 bg-destructive/15 text-destructive">
														Error
													</Badge>
												) : null}
											</div>

											<div className="whitespace-pre-wrap text-sm leading-relaxed break-words">
												{message.text ? renderMessageText(message.text) : isAssistant && message.status === "streaming" ? (
													<span className="inline-flex items-center gap-2 text-muted-foreground">
														<Loader2 className="h-4 w-4 animate-spin" />
														Thinking…
													</span>
												) : null}
												{isAssistant && message.status === "streaming" && message.text ? (
													<span className="ml-1 inline-flex h-4 w-2 translate-y-1 rounded-full bg-primary/60 align-middle animate-pulse" />
												) : null}
											</div>
										</div>

										{isAssistant && message.toolEvents?.length ? (
											<div className="space-y-2 pl-2">
												{message.toolEvents.map((event) => (
													<ToolEventCard key={event.id} event={event} />
												))}
											</div>
										) : null}
									</div>

									{!isAssistant ? (
										<div className="mt-1 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-2xl border border-border/60 bg-background text-muted-foreground">
											<User2 className="h-4 w-4" />
										</div>
									) : null}
								</MotionDiv>
							);
						})
					)}

					{isStreaming && conversation.messages.length > 0 ? (
						<div className="pl-11 text-[11px] font-medium uppercase tracking-[0.2em] text-muted-foreground">
							Streaming agent response…
						</div>
					) : null}
				</div>
			</div>

			{suggestionsSection ? (
			  <div className="border-t border-border/60 bg-background">
			    <button
			      type="button"
			      aria-label="Toggle suggestions"
			      className="flex w-full items-center justify-between px-4 py-2.5 transition-colors hover:bg-muted/30"
			      onClick={() => setSuggestionsOpen((v) => !v)}
			    >
			      <span className="text-[11px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
			        Suggestions · {suggestionsSection.suggestions.length} total
			      </span>
			      <ChevronDown
			        className={cn(
			          "h-3.5 w-3.5 text-muted-foreground transition-transform duration-200",
			          suggestionsOpen ? "" : "-rotate-90"
			        )}
			      />
			    </button>
			    {suggestionsOpen ? (
			      <div className="h-56 space-y-1.5 overflow-y-auto px-4 pb-3">
			        {suggestionsSection.isLoading ? (
			          <div className="flex items-center gap-2 rounded-xl border border-border/60 px-3 py-2 text-xs text-muted-foreground">
			            <Loader2 className="h-3.5 w-3.5 animate-spin" />
			            Loading suggestions…
			          </div>
			        ) : suggestionsSection.error ? (
			          <div className="rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
			            {suggestionsSection.error}
			          </div>
			        ) : !suggestionsSection.hasJobData ? (
			          <div className="rounded-xl border border-border/60 px-3 py-3 text-xs text-muted-foreground">
			            No job data yet — still processing?
			          </div>
			        ) : suggestionsSection.suggestions.length === 0 && suggestionsSection.jobStatus === "complete" ? (
			          <div className="rounded-xl border border-border/60 px-3 py-3 text-xs text-muted-foreground">
			            No suggestions found.
			          </div>
			        ) : suggestionsSection.suggestions.length === 0 ? (
			          <div className="flex items-center gap-2 rounded-xl border border-border/60 px-3 py-3 text-xs text-muted-foreground">
			            <Sparkles className="h-4 w-4" />
			            Waiting for analysis…
			          </div>
			        ) : (
			          suggestionsSection.suggestions.map((suggestion) => {
			            const isSelected = suggestionsSection.selectedSuggestionId === suggestion.id;
			            return (
			              <div
			                key={suggestion.id}
			                onClick={() => suggestionsSection.onSuggestionSelect(suggestion)}
			                onKeyDown={(event) => {
			                  if (event.key === "Enter" || event.key === " ") {
			                    event.preventDefault();
			                    suggestionsSection.onSuggestionSelect(suggestion);
			                  }
			                }}
			                role="button"
			                tabIndex={0}
			                className={cn(
			                  "group w-full rounded-xl border px-2.5 py-2 text-left text-[11px] transition-colors",
			                  isSelected
			                    ? "border-primary/30 bg-primary/5"
			                    : "border-border/60 hover:bg-muted/40"
			                )}
			              >
			                <div className="flex items-start gap-2">
			                  <Checkbox
			                    checked={suggestion.approved}
			                    onCheckedChange={(checked) =>
			                      suggestionsSection.onApprovalChange(suggestion.id, checked === true)
			                    }
			                    onClick={(event) => event.stopPropagation()}
			                    className="mt-0.5 flex-shrink-0"
			                  />
			                  <div className="min-w-0 flex-1">
			                    <div className="truncate font-medium text-foreground">
			                      {suggestion.text || "Manual redaction"}
			                    </div>
			                    <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[10px] text-muted-foreground">
			                      <span>{suggestionsSection.getSuggestionPageLabel(suggestion)}</span>
			                      <Badge
			                        variant="outline"
			                        className="rounded-full border-border/60 px-1.5 py-0 text-[10px] capitalize"
			                      >
			                        {suggestion.category}
			                      </Badge>
			                    </div>
			                    {suggestion.reasoning ? (
			                      <div className="mt-1 line-clamp-2 text-muted-foreground">
			                        {suggestion.reasoning}
			                      </div>
			                    ) : null}
			                  </div>
			                  <button
			                    type="button"
			                    onClick={(event) => {
			                      event.stopPropagation();
			                      suggestionsSection.onDelete(suggestion.id);
			                    }}
			                    className="ml-auto flex-shrink-0 rounded p-0.5 text-muted-foreground opacity-0 transition-opacity hover:text-destructive group-hover:opacity-100"
			                    aria-label="Delete suggestion"
			                  >
			                    <Trash2 className="h-3 w-3" />
			                  </button>
			                </div>
			              </div>
			            );
			          })
			        )}
			      </div>
			    ) : null}
			  </div>
			) : null}

			{chatContextFiles.length > 0 ? (
				<div className="flex flex-wrap gap-1.5 border-t border-border/60 px-3 py-2">
					{chatContextFiles.map((file) => (
						<div
							key={file.jobId}
							className="inline-flex items-center gap-1 rounded-full border border-border/60 bg-muted/40 px-2.5 py-1 text-xs text-foreground"
						>
							<span>{file.filename}</span>
							<button
								type="button"
								onClick={() => removeDragContextFile(file.jobId)}
								className="rounded-full p-0.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
								aria-label={`Remove ${file.filename}`}
							>
								<X className="h-3 w-3" />
							</button>
						</div>
					))}
				</div>
			) : null}

			<div
				ref={setNodeRef}
				className={cn(
					"border-t border-border/60 p-3 transition-colors",
					isOver && "ring-primary bg-accent/20 ring-2 ring-inset"
				)}
			>
				<PromptInput
					value={chatInput}
					onValueChange={onChatInputChange}
					onSubmit={onSubmit}
					isLoading={isStreaming}
					disabled={inputDisabled}
					className="rounded-xl border-border/70 bg-muted/30"
				>
					<PromptInputTextarea placeholder={inputPlaceholder} className="min-h-[44px] text-sm" />
					<PromptInputActions className="justify-end px-1 pb-1">
						<PromptInputAction tooltip="Send message" side="top">
							<button
								type="button"
								onClick={onSubmit}
								disabled={!canSubmit}
								className={cn(
									"flex h-8 w-8 items-center justify-center rounded-lg transition-colors",
									canSubmit
										? "bg-primary text-primary-foreground hover:bg-primary/90"
										: "bg-muted text-muted-foreground cursor-not-allowed"
								)}
							>
								{isStreaming ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
							</button>
						</PromptInputAction>
					</PromptInputActions>
				</PromptInput>
			</div>
		</div>
	);
}

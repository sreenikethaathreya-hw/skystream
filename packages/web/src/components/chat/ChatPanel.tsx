import { useEffect, useRef, useState, type FormEvent } from "react";
import { Loader2, MapPin, MessageSquarePlus, Send, Trash2, X } from "lucide-react";
import { ChatMessage } from "@/components/chat/ChatMessage";
import { Button } from "@/components/ui/button";
import { ConfirmButton } from "@/components/ui/confirm-button";
import { useCreateChatSession, useDeleteChatSession, useSendChatMessage } from "@/hooks/mutations";
import { useChatSession, useChatSessions } from "@/hooks/queries";
import { describeContext, type ChatRequest } from "@/hooks/useChat";
import { toolLabel } from "@/lib/chatActions";
import type { ChatMessage as ChatMessageData, PageContext, Role, Scope } from "@/lib/types";
import { cn } from "@/lib/utils";
const STARTERS: Record<Role, string[]> = {
  rep: [
    "What needs my attention?",
    "Which segments can I ask about?",
    "Which of my entries were flagged?",
    "How accurate has my track record been?",
  ],
  lead: [
    "Is this month ready to close?",
    "Which exceptions are still open?",
    "Which lead rules are active?",
    "Which competitor has the largest share?",
  ],
  admin: [
    "Which segments can I ask about?",
    "What was uploaded recently?",
    "Which lead rules are active?",
    "Which competitor has the largest share?",
  ],
};

const PAGE_STARTERS: Record<string, Partial<Record<Role, string[]>>> = {
  capture: {
    rep: ["Why is this number flagged?", "What do the market notes say for this segment?", "Across my segments, how far am I from plan?"],
  },
  consensus: {
    lead: ["Which segments have no entry yet this month?", "Where does the rep entry differ most from plan?", "What drivers are reps citing this month?"],
    admin: ["Which segments have no entry yet this month?", "Where does the rep entry differ most from plan?"],
  },
  ledger: {
    rep: ["Which of my claims are still pending?", "What happened when last month closed?"],
    lead: ["Which claims were contradicted last month?", "What happened when last month closed?"],
    admin: ["Which claims were contradicted last month?"],
  },
  rules: {
    lead: ["Which rules fire most and how often were they right?"],
    admin: ["Which rules fire most and how often were they right?"],
    rep: ["Which lead rules apply to my segments?"],
  },
  reps: {
    rep: ["How have my last months gone?", "What is range coverage?"],
    lead: ["Who overestimates?", "Has Rep B's bias changed over the last months?"],
    admin: ["Who overestimates?"],
  },
};

const MAX_LENGTH = 1000;
const MAX_STARTERS = 5;

function startersFor(role: Role, page: string | undefined): string[] {
  const pageStarters = (page && PAGE_STARTERS[page]?.[role]) || [];
  return [...new Set([...pageStarters, ...STARTERS[role]])].slice(0, MAX_STARTERS);
}

export function ChatPanel({
  role,
  scope,
  offline,
  writesAllowed,
  pageContext,
  request,
  onRequestHandled,
  segmentLabel,
  sessionId,
  onSessionChange,
}: {
  role: Role;
  scope: Scope | null;
  offline: boolean;
  writesAllowed: boolean;
  pageContext: PageContext | null;
  request: (ChatRequest & { id: number }) | null;
  onRequestHandled: (id: number) => void;
  segmentLabel?: (id: number) => string | undefined;
  sessionId: string | null;
  onSessionChange: (id: string | null) => void;
}) {
  const setSessionId = onSessionChange;
  const handled = useRef<number | null>(null);
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const [progress, setProgress] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [dismissedKey, setDismissedKey] = useState<string | null>(null);
  // An "Ask" button's context, kept only while the user stays on the page it came from.
  const [override, setOverride] = useState<{ context: PageContext; pageKey: string } | null>(null);
  const sessions = useChatSessions();
  const history = useChatSession(sessionId);
  const createSession = useCreateChatSession();
  const sendMessage = useSendChatMessage();
  const deleteSession = useDeleteChatSession();
  const bottom = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);

  const messages: ChatMessageData[] = history.data?.messages ?? [];
  const busy = sendMessage.isPending || createSession.isPending;
  const pageKey = JSON.stringify(pageContext);
  const baseContext = override && override.pageKey === pageKey ? override.context : pageContext;
  const contextKey = JSON.stringify(baseContext);
  const context = baseContext && dismissedKey !== contextKey ? baseContext : null;
  const contextLabel = describeContext(context, segmentLabel);

  useEffect(() => {
    input.current?.focus();
  }, []);

  useEffect(() => {
    bottom.current?.scrollIntoView?.({ block: "end" });
  }, [messages.length, pending, progress.length]);

  async function ask(text: string, askContext: PageContext | null = context) {
    const question = text.trim();
    if (!question || busy) return;
    setError(null);
    setPending(question);
    setProgress([]);
    setDraft("");
    try {
      const id = sessionId ?? (await createSession.mutateAsync()).id;
      setSessionId(id);
      await sendMessage.mutateAsync({
        sessionId: id,
        text: question,
        scope,
        pageContext: askContext,
        onProgress: (event, data) => {
          if (event === "tool_started") setProgress((p) => [...p, toolLabel(data.tool)]);
        },
      });
    } catch (err) {
      const reason = err instanceof Error ? err.message : "The question could not be answered.";
      setError(`${reason} Your question is back in the box; try again or rephrase it.`);
      setDraft(question);
    } finally {
      setPending(null);
      setProgress([]);
    }
  }

  useEffect(() => {
    if (!request || handled.current === request.id) return;
    handled.current = request.id;
    onRequestHandled(request.id);
    if (request.context) {
      setOverride({ context: request.context, pageKey });
      setDismissedKey(null);
    }
    if (!request.question) return;
    if (request.send) void ask(request.question, request.context ?? context);
    else {
      setDraft(request.question);
      input.current?.focus();
    }
    // Each request is handled once, keyed by its id.
  }, [request?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void ask(draft);
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center gap-2 border-b border-line px-4 py-2">
        <select
          aria-label="Conversation"
          className="h-8 min-w-0 flex-1 rounded-lg border border-line bg-surface px-2 text-xs text-ink"
          value={sessionId ?? ""}
          onChange={(e) => setSessionId(e.target.value || null)}
        >
          <option value="">New conversation</option>
          {(sessions.data ?? []).map((s) => (
            <option key={s.id} value={s.id}>
              {s.title}
            </option>
          ))}
        </select>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => setSessionId(null)}
          title="New conversation"
          aria-label="New conversation"
        >
          <MessageSquarePlus size={14} aria-hidden="true" />
        </Button>
        <ConfirmButton
          size="sm"
          variant="ghost"
          disabled={!sessionId || deleteSession.isPending}
          title="Delete conversation"
          aria-label="Delete conversation"
          confirmLabel="Delete?"
          onConfirm={() => {
            if (!sessionId) return;
            deleteSession.mutate(sessionId, { onSuccess: () => setSessionId(null) });
          }}
        >
          <Trash2 size={14} aria-hidden="true" />
        </ConfirmButton>
      </div>

      {offline && (
        <p className="border-b border-line bg-warn-50 px-4 py-2 text-xs text-warn-700" data-testid="chat-offline">
          Limited answers (offline): Gemini is off, so answers come from fixed templates, one table per question, and the
          assistant cannot make changes.
        </p>
      )}

      <div
        role="log"
        aria-live="polite"
        className="min-h-0 flex-1 space-y-3 overflow-y-auto overscroll-contain px-4 py-3"
        data-testid="chat-thread"
      >
        {!messages.length && !pending && (
          <div className="space-y-3 text-sm text-muted">
            <p>
              Ask about share, plan, year-to-go, actuals, entries and flags, claims, track records, competitors or lead
              rules. Answers only quote figures from the data; the app never forecasts.
              {writesAllowed &&
                (role === "rep"
                  ? " You can also ask me to submit or justify your own number, using exactly the figures and words you type."
                  : " You can also ask me to approve, discuss or challenge an entry, leave a note, or draft and activate a rule.")}
            </p>
            <div className="flex flex-col items-start gap-2">
              {startersFor(role, context?.page ?? pageContext?.page).map((starter) => (
                <button
                  key={starter}
                  type="button"
                  onClick={() => void ask(starter)}
                  className="rounded-full border border-line bg-surface px-3 py-1 text-left text-xs text-ink hover:bg-canvas"
                >
                  {starter}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((message, index) => (
          <ChatMessage key={`${message.createdAt}-${index}`} message={message} />
        ))}
        {pending && (
          <>
            <ChatMessage
              message={{
                role: "user",
                text: pending,
                createdAt: "",
                numbersRedacted: false,
                provider: null,
                sources: [],
                links: [],
                actions: [],
                downloads: [],
              }}
            />
            <div className="space-y-1 text-xs text-muted" data-testid="chat-progress">
              {progress.map((step, index) => (
                <p key={`${step}-${index}`} className="flex items-center gap-2">
                  <span className="size-1.5 rounded-full bg-brand-500" /> {step}
                </p>
              ))}
              <p className="flex items-center gap-2">
                <Loader2 size={12} className="animate-spin" /> Checking the data…
              </p>
            </div>
          </>
        )}
        <div ref={bottom} />
      </div>

      {error && (
        <p className="border-t border-line bg-crit-50 px-4 py-2 text-xs text-crit-700" role="alert">
          {error}
        </p>
      )}
      {context && contextLabel && (
        <div className="flex items-center gap-2 border-t border-line px-4 pt-2 text-xs text-muted" data-testid="chat-context">
          <MapPin size={12} />
          <span className="min-w-0 flex-1 truncate">About: {contextLabel}</span>
          <button
            type="button"
            className="rounded p-0.5 hover:bg-canvas"
            aria-label="Ask without the page context"
            onClick={() => setDismissedKey(contextKey)}
          >
            <X size={12} />
          </button>
        </div>
      )}
      <form onSubmit={onSubmit} className={cn("flex items-end gap-2 px-4 py-3", !(context && contextLabel) && "border-t border-line")}>
        <textarea
          ref={input}
          data-autofocus
          name="question"
          aria-label="Ask a question about the data"
          className="min-h-10 flex-1 resize-none rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink"
          rows={2}
          maxLength={MAX_LENGTH}
          placeholder={role === "rep" ? "e.g. What needs my attention?" : "e.g. Is this month ready to close?"}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              void ask(draft);
            }
          }}
        />
        <Button type="submit" disabled={busy || !draft.trim()} aria-label="Send">
          {busy ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
        </Button>
      </form>
    </div>
  );
}

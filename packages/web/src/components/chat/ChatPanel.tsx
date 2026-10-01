import { useEffect, useRef, useState, type FormEvent } from "react";
import { Loader2, MessageSquarePlus, Send, Trash2 } from "lucide-react";
import { ChatMessage } from "@/components/chat/ChatMessage";
import { Button } from "@/components/ui/button";
import { useCreateChatSession, useDeleteChatSession, useSendChatMessage } from "@/hooks/mutations";
import { useChatSession, useChatSessions } from "@/hooks/queries";
import type { ChatMessage as ChatMessageData, Role, Scope } from "@/lib/types";
import { cn } from "@/lib/utils";

const STARTERS: Record<Role, string[]> = {
  rep: [
    "Which segments can I ask about?",
    "Which of my entries were flagged?",
    "How accurate has my track record been?",
  ],
  lead: [
    "Which exceptions are still open?",
    "Which lead rules are active?",
    "Which competitor has the largest share?",
  ],
  admin: [
    "Which segments can I ask about?",
    "Which lead rules are active?",
    "Which competitor has the largest share?",
  ],
};

const MAX_LENGTH = 1000;

export function ChatPanel({
  role,
  scope,
  offline,
}: {
  role: Role;
  scope: Scope | null;
  offline: boolean;
}) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const sessions = useChatSessions();
  const history = useChatSession(sessionId);
  const createSession = useCreateChatSession();
  const sendMessage = useSendChatMessage();
  const deleteSession = useDeleteChatSession();
  const bottom = useRef<HTMLDivElement>(null);

  const messages: ChatMessageData[] = history.data?.messages ?? [];
  const busy = sendMessage.isPending || createSession.isPending;

  useEffect(() => {
    bottom.current?.scrollIntoView?.({ block: "end" });
  }, [messages.length, pending]);

  async function ask(text: string) {
    const question = text.trim();
    if (!question || busy) return;
    setError(null);
    setPending(question);
    setDraft("");
    try {
      const id = sessionId ?? (await createSession.mutateAsync()).id;
      setSessionId(id);
      await sendMessage.mutateAsync({ sessionId: id, text: question, scope });
    } catch (err) {
      setError(err instanceof Error ? err.message : "The question could not be answered");
      setDraft(question);
    } finally {
      setPending(null);
    }
  }

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
        <Button size="sm" variant="ghost" onClick={() => setSessionId(null)} title="New conversation">
          <MessageSquarePlus size={14} />
        </Button>
        <Button
          size="sm"
          variant="ghost"
          disabled={!sessionId || deleteSession.isPending}
          title="Delete conversation"
          onClick={() => {
            if (!sessionId) return;
            deleteSession.mutate(sessionId, { onSuccess: () => setSessionId(null) });
          }}
        >
          <Trash2 size={14} />
        </Button>
      </div>

      {offline && (
        <p className="border-b border-line bg-warn-50 px-4 py-2 text-xs text-warn-700" data-testid="chat-offline">
          Limited answers (offline): Gemini is off, so answers come from fixed templates, one table per question.
        </p>
      )}

      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto px-4 py-3" data-testid="chat-thread">
        {!messages.length && !pending && (
          <div className="space-y-3 text-sm text-muted">
            <p>
              Ask about share, plan, year-to-go, actuals, entries and flags, claims, track records, competitors or
              lead rules. Answers only quote figures from the data; the app never forecasts.
            </p>
            <div className="flex flex-col items-start gap-2">
              {STARTERS[role].map((starter) => (
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
              }}
            />
            <p className="flex items-center gap-2 text-xs text-muted">
              <Loader2 size={12} className="animate-spin" /> Checking the data…
            </p>
          </>
        )}
        <div ref={bottom} />
      </div>

      {error && (
        <p className="border-t border-line bg-crit-50 px-4 py-2 text-xs text-crit-700" role="alert">
          {error}
        </p>
      )}
      <form onSubmit={onSubmit} className="flex items-end gap-2 border-t border-line px-4 py-3">
        <textarea
          aria-label="Ask a question about the data"
          className={cn(
            "min-h-10 flex-1 resize-none rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink",
            "focus:outline-none focus:ring-2 focus:ring-brand-500/40",
          )}
          rows={2}
          maxLength={MAX_LENGTH}
          placeholder="e.g. How is 2482 tracking against plan?"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
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

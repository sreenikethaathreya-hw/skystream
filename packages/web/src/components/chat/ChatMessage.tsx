import { ShieldAlert } from "lucide-react";
import { ChatSources } from "@/components/chat/ChatSources";
import { Badge } from "@/components/ui/badge";
import type { ChatMessage as ChatMessageData } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Answers are rendered as plain text; model output is never interpreted as HTML or markdown. */
export function ChatMessage({ message }: { message: ChatMessageData }) {
  const mine = message.role === "user";
  return (
    <div className={cn("flex", mine ? "justify-end" : "justify-start")} data-testid={`chat-message-${message.role}`}>
      <div
        className={cn(
          "max-w-[92%] rounded-xl px-3 py-2 text-sm",
          mine ? "bg-brand-600 text-white" : "border border-line bg-surface text-ink",
        )}
      >
        <p className="whitespace-pre-wrap break-words" data-testid="chat-text">
          {message.text}
        </p>
        {!mine && (
          <>
            {message.numbersRedacted && (
              <p className="mt-2 flex items-center gap-1 text-xs text-warn-700" data-testid="chat-redacted">
                <ShieldAlert size={12} />
                Numbers the data could not confirm were removed. See the tables for the figures.
              </p>
            )}
            <ChatSources sources={message.sources} links={message.links} />
            {message.provider && (
              <Badge className="mt-2" tone="neutral">
                {message.provider}
              </Badge>
            )}
          </>
        )}
      </div>
    </div>
  );
}

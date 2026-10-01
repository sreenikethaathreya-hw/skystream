import { MessageSquare } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useOptionalChat } from "@/hooks/useChat";
import type { PageContext } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Opens the assistant with a question about the thing next to it. Hidden when the chat is off. */
export function AskButton({
  question,
  context,
  label = "Ask",
  send = true,
  className,
  testId,
}: {
  question: string;
  context?: PageContext;
  label?: string;
  send?: boolean;
  className?: string;
  testId?: string;
}) {
  const chat = useOptionalChat();
  if (!chat?.enabled) return null;
  return (
    <Button
      size="sm"
      variant="ghost"
      className={cn("h-7 gap-1 px-2 text-xs text-brand-700", className)}
      title={question}
      data-testid={testId ?? "ask-button"}
      onClick={() => chat.openChat({ question, context, send })}
    >
      <MessageSquare size={12} />
      {label}
    </Button>
  );
}

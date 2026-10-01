import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { PageContext } from "@/lib/types";

export interface ChatRequest {
  question?: string;
  /** Send the question straight away (an "Ask" button) instead of only filling the box. */
  send?: boolean;
  /** Overrides the page context for this question, e.g. one exception card on the Consensus page. */
  context?: PageContext;
}

interface ChatState {
  open: boolean;
  openChat: (request?: ChatRequest) => void;
  closeChat: () => void;
  pageContext: PageContext | null;
  setPageContext: (context: PageContext | null) => void;
  request: (ChatRequest & { id: number }) | null;
  consumeRequest: (id: number) => void;
  /** The open conversation, kept while the drawer is closed so reopening continues it. */
  sessionId: string | null;
  setSessionId: (id: string | null) => void;
  /** Whether "Ask" buttons show: the chat is on for this user. Set by the header's Ask the data control. */
  enabled: boolean;
  setEnabled: (enabled: boolean) => void;
}

const ChatContext = createContext<ChatState | null>(null);

export function ChatProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [pageContext, setPageContext] = useState<PageContext | null>(null);
  const [request, setRequest] = useState<(ChatRequest & { id: number }) | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [enabled, setEnabled] = useState(false);
  const counter = useRef(0);

  const openChat = useCallback((next?: ChatRequest) => {
    if (next && (next.question || next.context)) setRequest({ ...next, id: ++counter.current });
    setOpen(true);
  }, []);
  const closeChat = useCallback(() => setOpen(false), []);
  const consumeRequest = useCallback(
    (id: number) => setRequest((current) => (current && current.id === id ? null : current)),
    [],
  );

  const value = useMemo(
    () => ({
      open,
      openChat,
      closeChat,
      pageContext,
      setPageContext,
      request,
      consumeRequest,
      sessionId,
      setSessionId,
      enabled,
      setEnabled,
    }),
    [open, openChat, closeChat, pageContext, request, consumeRequest, sessionId, enabled],
  );
  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

export function useChat(): ChatState {
  const state = useContext(ChatContext);
  if (!state) throw new Error("useChat must be used inside ChatProvider");
  return state;
}

/** For components that also render outside the app shell (tests, previews): null when there is no chat. */
export function useOptionalChat(): ChatState | null {
  return useContext(ChatContext);
}

/** Tells the assistant what this page shows, so "this entry" and "here" resolve. Ids only, never figures. */
export function usePageContext(context: PageContext | null): void {
  const setPageContext = useOptionalChat()?.setPageContext;
  const key = JSON.stringify(context);
  useEffect(() => {
    setPageContext?.(context);
    // The serialized key is the dependency; the object identity changes on every render.
  }, [key, setPageContext]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => setPageContext?.(null), [setPageContext]);
}

export function describeContext(context: PageContext | null, segmentLabel?: (id: number) => string | undefined) {
  if (!context) return "";
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const parts: string[] = [];
  if (context.segmentId) parts.push(segmentLabel?.(context.segmentId) ?? `Segment ${context.segmentId}`);
  if (context.month) parts.push(months[context.month - 1]);
  if (context.entryId) parts.push("this entry");
  if (context.ruleId) parts.push(`Rule ${context.ruleId}`);
  if (!parts.length && context.page) parts.push(context.page.charAt(0).toUpperCase() + context.page.slice(1));
  return parts.join(", ");
}

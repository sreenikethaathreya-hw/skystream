import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ApiError, api, scopeQuery } from "@/lib/api";
import { queryKeysFor } from "@/lib/chatActions";
import type {
  AdminUser,
  AdvanceResult,
  AnalyzeResult,
  AppSettings,
  ChatSession,
  ChatTurn,
  Entry,
  EntryNote,
  EntryPayload,
  LeadRule,
  PageContext,
  Rtb,
  RuleDraft,
  RuleRequest,
  RuleSlots,
  Scope,
  UploadBatch,
} from "@/lib/types";

function useInvalidateAll() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries();
}

export const useAnalyze = () =>
  useMutation({ mutationFn: (body: EntryPayload) => api.post<AnalyzeResult>("/justifications/analyze", body) });

export function useSubmitEntry() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (body: EntryPayload) => api.post<Entry>("/entries", body),
    onSuccess: invalidate,
  });
}

export function useJustifyEntry() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: ({ entryId, ...body }: { entryId: string; justification: string | null; low: number; high: number }) =>
      api.post<Entry>(`/entries/${entryId}/justify`, body),
    onSuccess: invalidate,
  });
}

export function useAdvanceMonth() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: () => api.post<AdvanceResult>("/demo/advance"), onSuccess: invalidate });
}

export function useResetDemo() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: () => api.post<void>("/demo/reset"), onSuccess: invalidate });
}

export function useBulkApprove() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (scope: Scope | null) => api.post<{ approved: number }>(`/consensus/bulk-approve?${scopeQuery(scope)}`),
    onSuccess: invalidate,
  });
}

export function useDecide() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: ({ entryId, decision }: { entryId: string; decision: string }) =>
      api.post<void>(`/consensus/entries/${entryId}/decision`, { decision }),
    onSuccess: invalidate,
  });
}

export const useDraftRtb = () =>
  useMutation({
    mutationFn: ({ countryCode, segmentId }: { countryCode: string; segmentId: number }) =>
      api.post<Rtb>("/consensus/rtb", { countryCode, segmentId }),
  });

export function useUpload() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: ({ kind, file }: { kind: string; file: File }) => {
      const form = new FormData();
      form.append("kind", kind);
      form.append("file", file);
      return api.upload<UploadBatch>("/admin/uploads", form);
    },
    onSuccess: invalidate,
  });
}

export function useBatchAction() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: ({ id, action }: { id: string; action: "commit" | "discard" }) =>
      api.post<UploadBatch>(`/admin/uploads/${id}/${action}`),
    onSuccess: invalidate,
  });
}

export function useSaveUser() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (user: Omit<AdminUser, "lastSeenAt">) => api.put<AdminUser[]>("/admin/users", user),
    onSuccess: invalidate,
  });
}

export const useCompileRule = () =>
  useMutation({ mutationFn: (body: RuleRequest) => api.post<RuleDraft>("/rules/compile", body) });

export function useCreateRule() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (body: RuleRequest & { slots: RuleSlots; provider: string; decisions: Record<string, string> }) =>
      api.post<LeadRule>("/rules", body),
    onSuccess: invalidate,
  });
}

export function useRetireRule() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (id: number) => api.post<void>(`/rules/${id}/retire`), onSuccess: invalidate });
}

function useInvalidateChat() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ["chat"] });
}

export function useCreateChatSession() {
  const invalidate = useInvalidateChat();
  return useMutation({ mutationFn: () => api.post<ChatSession>("/chat/sessions"), onSuccess: invalidate });
}

export interface ChatProgress {
  tool: string;
  status?: string;
}

interface SendChat {
  sessionId: string;
  text: string;
  scope: Scope | null;
  pageContext?: PageContext | null;
  onProgress?: (event: "tool_started" | "tool_done", progress: ChatProgress) => void;
}

/** Streams one turn: tool progress arrives while the agent works, the checked answer arrives once at the end. */
export function useSendChatMessage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ sessionId, text, scope, pageContext, onProgress }: SendChat) => {
      const out: { turn?: ChatTurn; error?: string } = {};
      await api.stream(
        `/chat/sessions/${sessionId}/messages/stream`,
        { text, countryCode: scope?.countryCode, megaSegmentId: scope?.megaSegmentId, pageContext: pageContext ?? null },
        ({ event, data }) => {
          if (event === "final") out.turn = data as ChatTurn;
          else if (event === "error") out.error = (data as { detail?: string }).detail ?? "The question could not be answered";
          else if (event === "tool_started" || event === "tool_done") onProgress?.(event, data as ChatProgress);
        },
      );
      if (out.error) throw new ApiError(500, out.error);
      if (!out.turn) throw new ApiError(500, "The answer did not arrive; please ask again");
      return out.turn;
    },
    onSuccess: (turn) => {
      void queryClient.invalidateQueries({ queryKey: ["chat"] });
      if (!turn.actions.length) return;
      const keys = queryKeysFor(turn.actions);
      if (keys === "all") void queryClient.invalidateQueries();
      else for (const queryKey of keys) void queryClient.invalidateQueries({ queryKey });
    },
  });
}

export function useAddNote() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ entryId, body }: { entryId: string; body: string }) =>
      api.post<EntryNote>(`/entries/${entryId}/notes`, { body }),
    onSuccess: () => {
      for (const queryKey of [["/entries"], ["/consensus/queue"], ["entry-notes"]]) {
        void queryClient.invalidateQueries({ queryKey });
      }
    },
  });
}

export function useDeleteChatSession() {
  const invalidate = useInvalidateChat();
  return useMutation({ mutationFn: (id: string) => api.delete<void>(`/chat/sessions/${id}`), onSuccess: invalidate });
}

export function useSaveSettings() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (patch: Partial<AppSettings>) => api.put<AppSettings>("/admin/settings", patch),
    onSuccess: invalidate,
  });
}

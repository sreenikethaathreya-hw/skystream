import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, scopeQuery } from "@/lib/api";
import type {
  AdminUser,
  AdvanceResult,
  AnalyzeResult,
  AppSettings,
  Entry,
  EntryPayload,
  LeadRule,
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

export function useSaveSettings() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (patch: Partial<AppSettings>) => api.put<AppSettings>("/admin/settings", patch),
    onSuccess: invalidate,
  });
}

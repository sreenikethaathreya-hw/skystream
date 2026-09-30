import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { AdvanceResult, AnalyzeResult, Entry, EntryPayload, Rtb } from "@/lib/types";

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
    mutationFn: () => api.post<{ approved: number }>("/consensus/bulk-approve"),
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
  useMutation({ mutationFn: (segmentId: number) => api.post<Rtb>("/consensus/rtb", { segmentId }) });

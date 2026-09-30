import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Cube, DataQuality, Entry, Meta, Queue, TrackRecord } from "@/lib/types";

export const useMeta = () => useQuery({ queryKey: ["/meta"], queryFn: () => api.get<Meta>("/meta") });

export const useCube = () =>
  useQuery({ queryKey: ["/segments/cube"], queryFn: () => api.get<Cube>("/segments/cube"), staleTime: 60_000 });

export function useEntries(filters: { segmentId?: number; userId?: string } = {}) {
  const params = new URLSearchParams();
  if (filters.segmentId) params.set("segmentId", String(filters.segmentId));
  if (filters.userId) params.set("userId", filters.userId);
  const query = params.toString();
  return useQuery({
    queryKey: ["/entries", filters],
    queryFn: () => api.get<Entry[]>(`/entries${query ? `?${query}` : ""}`),
  });
}

export const useQueue = () =>
  useQuery({ queryKey: ["/consensus/queue"], queryFn: () => api.get<Queue>("/consensus/queue") });

export const useReps = () => useQuery({ queryKey: ["/reps"], queryFn: () => api.get<TrackRecord[]>("/reps") });

export const useDataQuality = () =>
  useQuery({ queryKey: ["/data-quality"], queryFn: () => api.get<DataQuality>("/data-quality") });

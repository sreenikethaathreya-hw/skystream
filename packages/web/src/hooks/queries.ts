import { useQuery } from "@tanstack/react-query";
import { api, scopeQuery } from "@/lib/api";
import type {
  AdminUser,
  AppConfig,
  AppSettings,
  Cube,
  DataQuality,
  Entry,
  Meta,
  Queue,
  Scope,
  ScopeOption,
  TrackRecord,
  UploadBatch,
  UploadKind,
} from "@/lib/types";

export const useConfig = () =>
  useQuery({ queryKey: ["/config"], queryFn: () => api.get<AppConfig>("/config"), staleTime: Infinity });

export const useMeta = (enabled = true) =>
  useQuery({ queryKey: ["/meta"], queryFn: () => api.get<Meta>("/meta"), enabled, retry: false });

export const useScopes = (enabled = true) =>
  useQuery({ queryKey: ["/scopes"], queryFn: () => api.get<ScopeOption[]>("/scopes"), enabled });

export const useCube = (scope: Scope | null) =>
  useQuery({
    queryKey: ["/segments/cube", scope],
    queryFn: () => api.get<Cube>(`/segments/cube?${scopeQuery(scope)}`),
    enabled: scope !== null,
    staleTime: 60_000,
  });

export function useEntries(filters: { scope?: Scope | null; segmentId?: number; userId?: string } = {}) {
  const params = new URLSearchParams(filters.scope ? scopeQuery(filters.scope) : "");
  if (filters.segmentId) params.set("segmentId", String(filters.segmentId));
  if (filters.userId) params.set("userId", filters.userId);
  const query = params.toString();
  return useQuery({
    queryKey: ["/entries", filters],
    queryFn: () => api.get<Entry[]>(`/entries${query ? `?${query}` : ""}`),
  });
}

export const useQueue = (scope: Scope | null) =>
  useQuery({
    queryKey: ["/consensus/queue", scope],
    queryFn: () => api.get<Queue>(`/consensus/queue?${scopeQuery(scope)}`),
    enabled: scope !== null,
  });

export const useReps = () => useQuery({ queryKey: ["/reps"], queryFn: () => api.get<TrackRecord[]>("/reps") });

export const useDataQuality = () =>
  useQuery({ queryKey: ["/data-quality"], queryFn: () => api.get<DataQuality>("/data-quality") });

export const useUploadKinds = () =>
  useQuery({ queryKey: ["/admin/upload-kinds"], queryFn: () => api.get<UploadKind[]>("/admin/upload-kinds") });

export const useUploads = () =>
  useQuery({ queryKey: ["/admin/uploads"], queryFn: () => api.get<UploadBatch[]>("/admin/uploads") });

export const useAdminUsers = () =>
  useQuery({ queryKey: ["/admin/users"], queryFn: () => api.get<AdminUser[]>("/admin/users") });

export const useAdminSettings = () =>
  useQuery({ queryKey: ["/admin/settings"], queryFn: () => api.get<AppSettings>("/admin/settings") });

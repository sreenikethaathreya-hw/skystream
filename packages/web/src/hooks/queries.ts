import { useQuery } from "@tanstack/react-query";
import { api, scopeQuery } from "@/lib/api";
import type {
  AdminUser,
  AppConfig,
  AppSettings,
  ChatHistory,
  ChatSession,
  Cube,
  DataQuality,
  Entry,
  EntryNote,
  LeadRule,
  Meta,
  Queue,
  Scope,
  ScopeOption,
  TrackRecord,
  UploadBatch,
  WidgetRun,
  WidgetsState,
  UploadKind,
} from "@/lib/types";

export const useConfig = () =>
  useQuery({ queryKey: ["/config"], queryFn: () => api.get<AppConfig>("/config"), staleTime: Infinity });

export const useMeta = (enabled = true) =>
  useQuery({ queryKey: ["/meta"], queryFn: () => api.get<Meta>("/meta"), enabled, retry: false });

export const useScopes = (enabled = true) =>
  useQuery({ queryKey: ["/scopes"], queryFn: () => api.get<ScopeOption[]>("/scopes"), enabled });

export const useRules = (scope: Scope | null) =>
  useQuery({
    queryKey: ["/rules", scope],
    queryFn: () => api.get<LeadRule[]>(`/rules?${scopeQuery(scope)}`),
    enabled: scope !== null,
  });

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

export const useChatSessions = (enabled = true) =>
  useQuery({ queryKey: ["chat", "sessions"], queryFn: () => api.get<ChatSession[]>("/chat/sessions"), enabled });

export const useChatSession = (id: string | null) =>
  useQuery({
    queryKey: ["chat", "session", id],
    queryFn: () => api.get<ChatHistory>(`/chat/sessions/${id}`),
    enabled: id !== null,
  });

export const useEntryNotes = (entryId: string | null | undefined) =>
  useQuery({
    queryKey: ["entry-notes", entryId],
    queryFn: () => api.get<EntryNote[]>(`/entries/${entryId}/notes`),
    enabled: !!entryId,
  });

export const useAdminSettings = () =>
  useQuery({ queryKey: ["/admin/settings"], queryFn: () => api.get<AppSettings>("/admin/settings") });

export const WIDGETS_KEY = ["me", "widgets"] as const;

export const useWidgets = () =>
  useQuery({ queryKey: WIDGETS_KEY, queryFn: () => api.get<WidgetsState>("/me/widgets"), staleTime: Infinity });

/** Re-runs a pinned widget's tool on the server; nothing about its figures is stored. */
export const useWidgetRun = (id: number) =>
  useQuery({
    queryKey: [...WIDGETS_KEY, "run", id],
    queryFn: () => api.get<WidgetRun>(`/me/widgets/${id}/run`),
    staleTime: 60_000,
  });

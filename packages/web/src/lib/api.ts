import { parseSseBlock, splitSse, type SseEvent } from "@/lib/sse";

const USER_KEY = "skystream.demoUser";

type TokenProvider = () => Promise<string | null>;
let tokenProvider: TokenProvider | null = null;

/** Real mode registers a Firebase ID-token provider; demo mode sends the role-switcher header instead. */
export function setTokenProvider(provider: TokenProvider | null): void {
  tokenProvider = provider;
}

export function getStoredUserId(): string {
  return localStorage.getItem(USER_KEY) ?? "rep-a";
}

export function storeUserId(id: string): void {
  localStorage.setItem(USER_KEY, id);
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function authHeaders(): Promise<Record<string, string>> {
  if (tokenProvider) {
    const token = await tokenProvider();
    return token ? { Authorization: `Bearer ${token}` } : {};
  }
  return { "X-Demo-User": getStoredUserId() };
}

async function send(method: string, path: string, body?: BodyInit, json = true): Promise<Response> {
  const headers: Record<string, string> = { ...(await authHeaders()) };
  if (json && body !== undefined) headers["Content-Type"] = "application/json";
  const response = await fetch(`/api${path}`, { method, headers, body });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const payload = await response.json();
      detail = typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail);
    } catch {
      // non-JSON error body
    }
    throw new ApiError(response.status, detail);
  }
  return response;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const response = await send(method, path, body === undefined ? undefined : JSON.stringify(body));
  if (response.status === 204) return undefined as T;
  const type = response.headers.get("content-type") ?? "";
  return (type.includes("application/json") ? response.json() : response.text()) as Promise<T>;
}

async function stream(path: string, body: unknown, onEvent: (event: SseEvent) => void): Promise<void> {
  const response = await send("POST", path, JSON.stringify(body));
  const reader = response.body?.getReader();
  if (!reader) throw new ApiError(500, "This browser cannot read streamed answers");
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const { blocks, rest } = splitSse(done ? `${buffer}\n\n` : buffer);
    buffer = rest;
    for (const block of blocks) {
      const event = parseSseBlock(block);
      if (event) onEvent(event);
    }
    if (done) return;
  }
}

export const api = {
  /** POST that answers with server-sent events, read through fetch so it can carry the auth header. */
  stream,
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, body),
  delete: <T>(path: string) => request<T>("DELETE", path),
  upload: async <T>(path: string, form: FormData): Promise<T> => (await send("POST", path, form, false)).json(),
  /** Authenticated file download (a plain link cannot carry the bearer token). */
  download: async (path: string, filename: string): Promise<void> => {
    const blob = await (await send("GET", path)).blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  },
};

export function scopeQuery(scope: { countryCode: string; megaSegmentId: string } | null): string {
  return scope ? `country=${scope.countryCode}&mega=${encodeURIComponent(scope.megaSegmentId)}` : "";
}

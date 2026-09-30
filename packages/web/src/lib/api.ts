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

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, body),
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

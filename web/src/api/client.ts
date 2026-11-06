import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";
import type { TokenResponse } from "./types";

export const API_URL = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") || "http://localhost:8000";

const ACCESS_KEY = "ara_access";
const REFRESH_KEY = "ara_refresh";

export const tokens = {
  get access() {
    return localStorage.getItem(ACCESS_KEY);
  },
  get refresh() {
    return localStorage.getItem(REFRESH_KEY);
  },
  set(access: string, refresh: string) {
    localStorage.setItem(ACCESS_KEY, access);
    localStorage.setItem(REFRESH_KEY, refresh);
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

/** The secret each interview gives the browser it was started on. Sent back so a second device is refused. */
const memoryTokens = new Map<string, string>();
export const deviceTokens = {
  get: (sessionId: string) => {
    try { return localStorage.getItem(`ara_device_${sessionId}`) ?? memoryTokens.get(sessionId) ?? null; } catch { return memoryTokens.get(sessionId) ?? null; }
  },
  set: (sessionId: string, token: string) => {
    memoryTokens.set(sessionId, token);
    try { localStorage.setItem(`ara_device_${sessionId}`, token); } catch { /* private mode: kept for this tab only */ }
  },
};

export const api = axios.create({ baseURL: `${API_URL}/api` });

// Attach the JWT to every request, and the interview device key to interview requests.
api.interceptors.request.use((config) => {
  const token = tokens.access;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  const interview = /^\/interviews\/([0-9a-f-]{36})/.exec(config.url ?? "");
  const device = interview && deviceTokens.get(interview[1]);
  if (device) config.headers["X-Interview-Device"] = device;
  return config;
});

// On 401, try ONE refresh (shared by all concurrent requests), then retry the original request.
let refreshing: Promise<string | null> | null = null;
let onSessionExpired: () => void = () => {};
export function setSessionExpiredHandler(fn: () => void) {
  onSessionExpired = fn;
}

async function refreshAccessToken(): Promise<string | null> {
  const refresh = tokens.refresh;
  if (!refresh) return null;
  try {
    const { data } = await axios.post<TokenResponse>(`${API_URL}/api/auth/refresh`, { refresh_token: refresh });
    tokens.set(data.access_token, data.refresh_token);
    return data.access_token;
  } catch {
    return null;
  }
}

api.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
    const original = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined;
    const isAuthCall = original?.url?.startsWith("/auth/login") || original?.url?.startsWith("/auth/refresh");
    if (error.response?.status === 401 && original && !original._retried && !isAuthCall) {
      original._retried = true;
      refreshing = refreshing ?? refreshAccessToken().finally(() => (refreshing = null));
      const newToken = await refreshing;
      if (newToken) {
        original.headers.Authorization = `Bearer ${newToken}`;
        return api(original);
      }
      tokens.clear();
      onSessionExpired();
    }
    return Promise.reject(error);
  },
);

/** Turn any API error into a friendly message for toasts / inline errors. */
export function errorMessage(err: unknown, fallback = "Something went wrong. Please try again."): string {
  if (axios.isAxiosError(err)) {
    if (!err.response) return "Cannot reach the server. Check your connection (the server may be waking up).";
    const detail = (err.response.data as { detail?: unknown } | undefined)?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length) {
      const first = detail[0] as { msg?: string; loc?: string[] };
      const field = first.loc?.[first.loc.length - 1];
      return `${field ? `${field}: ` : ""}${(first.msg || "Invalid value").replace(/^Value error, /, "")}`;
    }
    if (err.response.status === 429) return "Too many requests. Please wait and try again.";
  }
  return fallback;
}

/** Fetch a protected file (resume / audio) with the JWT and return an object URL. */
export async function fetchBlobUrl(path: string): Promise<string> {
  const res = await api.get(path, { responseType: "blob" });
  return URL.createObjectURL(res.data as Blob);
}

/** Download a protected file and save it with the filename the server suggests. */
export async function downloadFile(path: string, params: Record<string, unknown>, fallbackName: string) {
  const res = await api.get(path, { params, responseType: "blob" });
  const disposition = (res.headers["content-disposition"] as string | undefined) ?? "";
  const name = /filename="?([^"]+)"?/.exec(disposition)?.[1] ?? fallbackName;
  const url = URL.createObjectURL(res.data as Blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

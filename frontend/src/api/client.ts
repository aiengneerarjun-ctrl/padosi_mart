import { API_BASE_URL, API_PREFIX } from "../config";
import { clearTokens, loadTokens, saveTokens, loadLang, Tokens } from "../lib/storage";

// Backend ka error format: { detail: { code, message, request_id, errors? } }
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public fieldErrors?: { field: string; message: string }[],
    public requestId?: string | null,
  ) {
    super(message);
  }
}

type Opts = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined | null>;
  auth?: boolean; // default true
  headers?: Record<string, string>;
  timeoutMs?: number; // photo upload jaise bade kaam ke liye zyada samay
};

// Login screen ko batane ke liye: session khatam ho gaya.
let onSessionExpired: (() => void) | null = null;
export function setSessionExpiredHandler(fn: () => void) {
  onSessionExpired = fn;
}

// Ek hi refresh ek samay par chale, chahe 5 requests ek saath fail hon.
let refreshing: Promise<Tokens | null> | null = null;

async function doRefresh(): Promise<Tokens | null> {
  const current = await loadTokens();
  if (!current) return null;
  const res = await fetch(`${API_BASE_URL}${API_PREFIX}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: current.refresh_token }),
  });
  if (!res.ok) {
    await clearTokens();
    return null;
  }
  const pair = (await res.json()) as Tokens;
  await saveTokens(pair);
  return pair;
}

async function send(path: string, opts: Opts, accessToken?: string) {
  const qs = opts.query
    ? "?" +
      Object.entries(opts.query)
        .filter(([, v]) => v !== undefined && v !== null && v !== "")
        .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
        .join("&")
    : "";
  const headers: Record<string, string> = {
    "Accept-Language": await loadLang(), // backend isi se en/hi/bho tay karta hai
  };
  Object.assign(headers, opts.headers);
  const isForm = typeof FormData !== "undefined" && opts.body instanceof FormData;
  // FormData (photo upload) me Content-Type khud lagta hai (boundary ke saath), isliye hum nahi lagate
  if (opts.body !== undefined && !isForm) headers["Content-Type"] = "application/json";
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), opts.timeoutMs ?? 8000);
  try {
    return await fetch(`${API_BASE_URL}${API_PREFIX}${path}${qs}`, {
      method: opts.method ?? "GET",
      headers,
      body: opts.body === undefined ? undefined : isForm ? (opts.body as FormData) : JSON.stringify(opts.body),
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timer);
  }
}

async function toError(res: Response): Promise<ApiError> {
  try {
    const j = await res.json();
    const d = j?.detail;
    if (d && typeof d === "object") {
      return new ApiError(res.status, d.code ?? `HTTP_${res.status}`, d.message ?? "Kuch gadbad hui", d.errors, d.request_id);
    }
    return new ApiError(res.status, `HTTP_${res.status}`, typeof d === "string" ? d : "Kuch gadbad hui");
  } catch {
    return new ApiError(res.status, `HTTP_${res.status}`, "Server se jawab nahi mila");
  }
}

export async function api<T = unknown>(path: string, opts: Opts = {}): Promise<T> {
  const useAuth = opts.auth !== false;
  let tokens = useAuth ? await loadTokens() : null;
  let res = await send(path, opts, tokens?.access_token);

  if (res.status === 401 && useAuth && tokens) {
    refreshing ??= doRefresh().finally(() => (refreshing = null));
    tokens = await refreshing;
    if (!tokens) {
      onSessionExpired?.();
      throw await toError(res);
    }
    res = await send(path, opts, tokens.access_token);
  }

  if (!res.ok) throw await toError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  const msg = e instanceof Error ? e.message : "";
  const isNetwork =
    e instanceof Error && (e.name === "AbortError" || /network request failed|fetch failed|timed out|timeout|aborted/i.test(msg));
  // Asli internet/server ki dikkat ho tabhi ye message; warna asli wajah dikhao (galat batane se dikkat chhup jaati hai)
  if (isNetwork || !msg) return "Server se connection nahi hua. Internet aur server check karein.";
  return `Kuch gadbad hui: ${msg}`;
}

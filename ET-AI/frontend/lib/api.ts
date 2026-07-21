"use client";

import { useCallback, useEffect, useState } from "react";
import type { User } from "./types";
import { googleLogout } from "@react-oauth/google";
export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

const TOKEN_KEY = "intelliplant_token";
const USER_KEY = "intelliplant_user";

export class ApiError extends Error {
  status: number;
  backendDown: boolean;
  constructor(message: string, status = 0, backendDown = false) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.backendDown = backendDown;
  }
}

export const BACKEND_DOWN_MESSAGE =
  "Backend not running — start it with `uvicorn app.main:app`";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function getStoredUser(): User | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as User;
  } catch {
    return null;
  }
}

export function storeSession(token: string, user: User) {
  window.localStorage.setItem(TOKEN_KEY, token);
  window.localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession() {
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(USER_KEY);
}

export function logout() {
  googleLogout();      // Signs out of Google session
  clearSession();      // Clears JWT and user
  window.location.href = "/login";
}

interface Envelope<T> {
  success: boolean;
  data: T | null;
  error: string | null;
  timestamp: string;
}

interface FetchOptions {
  method?: string;
  body?: unknown;
  formData?: FormData;
  auth?: boolean;
}

/**
 * Shared fetch wrapper: adds the Bearer token, unwraps the
 * { success, data, error, timestamp } envelope, and redirects to
 * /login on a 401.
 */
export async function apiFetch<T>(
  path: string,
  opts: FetchOptions = {}
): Promise<T> {
  const { method = "GET", body, formData, auth = true } = opts;

  const headers: Record<string, string> = {};
  if (auth) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }
  if (body !== undefined) headers["Content-Type"] = "application/json";

  let res: Response;
  try {
    res = await fetch(API_BASE + path, {
      method,
      headers,
      body: formData ?? (body !== undefined ? JSON.stringify(body) : undefined),
    });
  } catch {
    throw new ApiError(BACKEND_DOWN_MESSAGE, 0, true);
  }

  if (res.status === 401 && path !== "/auth/login") {
    clearSession();
    if (typeof window !== "undefined") window.location.href = "/login";
    throw new ApiError("Session expired — please log in again.", 401);
  }

  let json: Envelope<T>;
  try {
    json = (await res.json()) as Envelope<T>;
  } catch {
    throw new ApiError(`Unexpected response from server (${res.status})`, res.status);
  }

  if (!json.success || !res.ok) {
    throw new ApiError(json.error ?? `Request failed (${res.status})`, res.status);
  }
  return json.data as T;
}

export const api = {
  get: <T>(path: string) => apiFetch<T>(path),
  post: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, { method: "POST", body }),
  upload: <T>(path: string, formData: FormData) =>
    apiFetch<T>(path, { method: "POST", formData }),
};

/** Simple fetch-on-mount hook with loading / error / reload. */
export function useApi<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(path !== null);
  const [error, setError] = useState<ApiError | null>(null);

  const load = useCallback(() => {
    if (!path) return;
    setLoading(true);
    setError(null);
    api
      .get<T>(path)
      .then((d) => setData(d))
      .catch((e: unknown) => {
        setError(
          e instanceof ApiError ? e : new ApiError("Something went wrong")
        );
      })
      .finally(() => setLoading(false));
  }, [path]);

  useEffect(() => {
    load();
  }, [load]);

  return { data, loading, error, reload: load };
}

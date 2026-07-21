import { useCallback, useEffect, useRef, useState } from 'react';
import { Platform } from 'react-native';
import {
  clearSession,
  emitUnauthorized,
  getCachedToken,
  loadSession,
  saveSession,
} from './auth';
import type { User } from './types';

// Android emulators can't reach "localhost" (that's the emulator itself) —
// 10.0.2.2 is the documented loopback alias to the host machine. iOS
// simulator can use localhost directly. Override with API_BASE_URL for a
// real device pointed at your machine's LAN IP.

export const API_BASE = __DEV__
  ? 'http://10.107.180.120:8000/api/v1'
  : 'https://aegis-smart-intelliplant.onrender.com/api/v1';

export class ApiError extends Error {
  status: number;
  backendDown: boolean;
  constructor(message: string, status = 0, backendDown = false) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.backendDown = backendDown;
  }
}

export const BACKEND_DOWN_MESSAGE =
  'Network Error!';

export async function storeSession(token: string, user: User) {
  await saveSession(token, user);
}

export async function logoutSession() {
  await clearSession();
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
 * Shared fetch wrapper: adds the Bearer token from the secure keychain,
 * unwraps the { success, data, error, timestamp } envelope, and fires the
 * unauthorized event on a 401 so AuthContext can navigate to Login.
 */
export async function apiFetch<T>(
  path: string,
  opts: FetchOptions = {},
): Promise<T> {
  const { method = 'GET', body, formData, auth = true } = opts;

  const headers: Record<string, string> = {};
  if (auth) {
    const token = getCachedToken() ?? (await loadSession())?.token ?? null;
    if (token) headers.Authorization = `Bearer ${token}`;
  }
  if (body !== undefined) headers['Content-Type'] = 'application/json';

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

if (
  res.status === 401 &&
  path !== '/auth/login' &&
  path !== '/auth/google'
) {
  await clearSession();
  emitUnauthorized();
  throw new ApiError('Session expired — please log in again.', 401);
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
    apiFetch<T>(path, { method: 'POST', body }),
  upload: <T>(path: string, formData: FormData) =>
    apiFetch<T>(path, { method: 'POST', formData }),
};

/** Simple fetch-on-mount hook with loading / error / reload, same shape as web. */
export function useApi<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(path !== null);
  const [error, setError] = useState<ApiError | null>(null);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const load = useCallback(() => {
    if (!path) return;
    setLoading(true);
    setError(null);
    api
      .get<T>(path)
      .then((d) => {
        if (mounted.current) setData(d);
      })
      .catch((e: unknown) => {
        if (mounted.current) {
          setError(e instanceof ApiError ? e : new ApiError('Something went wrong'));
        }
      })
      .finally(() => {
        if (mounted.current) setLoading(false);
      });
  }, [path]);

  useEffect(() => {
    load();
  }, [load]);

  return { data, loading, error, reload: load };
}

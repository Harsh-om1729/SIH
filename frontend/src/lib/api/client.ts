import { API_CONFIG } from './config';

// The backend fails closed on IBVAP_API_TOKEN (see integration/api.py), so
// every /api/v1 route except /health needs this header or answers 401.
//
// A Vite env var is compiled into the bundle, so this token is readable by
// anyone who can open the dashboard. That is acceptable only because the
// dashboard and the API are both meant to sit inside the same trusted
// network. Do not reuse the operator-facing token here if the API is ever
// exposed beyond it — issue the browser its own scoped credential instead.
function authHeaders(): Record<string, string> {
  const token = import.meta.env.VITE_API_TOKEN as string | undefined;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export interface ApiResponse<T> {
  data: T | null;
  error: string | null;
  isFallback: boolean;
  // HTTP status when the server answered, null when it could not be reached.
  // Lets a caller tell "backend offline" apart from "backend said no".
  status: number | null;
}

export async function safeFetch<T>(
  endpoint: string,
  options?: RequestInit,
  fallbackData?: T
): Promise<ApiResponse<T>> {
  const url = `${API_CONFIG.baseUrl}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), API_CONFIG.timeoutMs);

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        ...authHeaders(),
        ...(options?.headers || {}),
      },
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      // FastAPI puts the useful message in `detail` ("No face found in that
      // photo", "reason must be one of ..."). statusText alone just said
      // "Unprocessable Entity".
      let detail = response.statusText;
      try {
        const body = await response.json();
        if (body && typeof body.detail === 'string') detail = body.detail;
      } catch {
        // non-JSON error body; keep statusText
      }
      return {
        data: fallbackData !== undefined ? fallbackData : null,
        error: `HTTP ${response.status}: ${detail}`,
        isFallback: true,
        status: response.status,
      };
    }

    const data = (await response.json()) as T;
    return { data, error: null, isFallback: false, status: response.status };
  } catch (err: unknown) {
    clearTimeout(timeoutId);
    const message = err instanceof Error ? err.message : 'Network request failed';
    return {
      data: fallbackData !== undefined ? fallbackData : null,
      error: message,
      isFallback: true,
      status: null,
    };
  }
}

let cachedHealthStatus: boolean | null = null;
let lastHealthCheckTime = 0;

export async function checkBackendHealth(): Promise<boolean> {
  const now = Date.now();
  if (cachedHealthStatus !== null && now - lastHealthCheckTime < 10000) {
    return cachedHealthStatus;
  }

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 2000);
    const res = await fetch(`${API_CONFIG.baseUrl}/health`, {
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    cachedHealthStatus = res.ok;
    lastHealthCheckTime = now;
    return cachedHealthStatus;
  } catch {
    cachedHealthStatus = false;
    lastHealthCheckTime = now;
    return false;
  }
}

import { API_CONFIG } from './config';

export interface ApiResponse<T> {
  data: T | null;
  error: string | null;
  isFallback: boolean;
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
        ...(options?.headers || {}),
      },
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const data = (await response.json()) as T;
    return { data, error: null, isFallback: false };
  } catch (err: unknown) {
    clearTimeout(timeoutId);
    const message = err instanceof Error ? err.message : 'Network request failed';
    return {
      data: fallbackData !== undefined ? fallbackData : null,
      error: message,
      isFallback: true,
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

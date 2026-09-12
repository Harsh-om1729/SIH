// Opened on a phone at http://192.168.1.5:5173, a hardcoded 127.0.0.1 would
// point the API calls at the *phone*, not at the machine running the backend.
// Deriving the host from the page means one build works on localhost and
// across the LAN, with no rebuild. An explicit VITE_API_BASE_URL still wins.
function sameHost(port: number, scheme: 'http' | 'ws'): string {
  if (typeof window === 'undefined') return `${scheme}://127.0.0.1:${port}`;
  const secure = window.location.protocol === 'https:';
  const proto = scheme === 'ws' ? (secure ? 'wss' : 'ws') : secure ? 'https' : 'http';
  return `${proto}://${window.location.hostname}:${port}`;
}

// A browser WebSocket cannot set an Authorization header either, so the
// token goes in the query string exactly as it does for the MJPEG stream.
// The server rejects a bad token during the handshake, before accept().
function withToken(url: string): string {
  const token = import.meta.env.VITE_API_TOKEN as string | undefined;
  if (!token) return url;
  return `${url}${url.includes('?') ? '&' : '?'}token=${encodeURIComponent(token)}`;
}

export const API_CONFIG = {
  baseUrl: (import.meta.env.VITE_API_BASE_URL as string) || `${sameHost(8000, 'http')}/api/v1`,
  wsUrl: withToken(
    (import.meta.env.VITE_WS_URL as string) || `${sameHost(8000, 'ws')}/ws/alerts`
  ),
  timeoutMs: 4000,
  maxReconnectAttempts: 5,
  reconnectIntervalMs: 5000,
};

/**
 * Absolute URL for a camera's MJPEG feed, for use as an <img src>.
 *
 * The token rides in the query string because an <img> tag cannot set an
 * Authorization header. That is no more exposed than the header would be —
 * VITE_API_TOKEN is compiled into this bundle either way — but it does mean
 * the token appears in server access logs and browser history.
 */
export function cameraStreamUrl(cameraId: string): string {
  const token = import.meta.env.VITE_API_TOKEN as string | undefined;
  const base = `${API_CONFIG.baseUrl}/cameras/${encodeURIComponent(cameraId)}/stream`;
  return token ? `${base}?token=${encodeURIComponent(token)}` : base;
}

/**
 * Absolute, authenticated URL for an API-served asset used in an <img> —
 * e.g. an incident's snapshotUrl ("/incidents/12/evidence/snapshot").
 * Returns undefined for a missing path so it can go straight into `src`.
 */
export function apiAssetUrl(path: string | null | undefined): string | undefined {
  if (!path) return undefined;
  return withToken(`${API_CONFIG.baseUrl}${path.startsWith('/') ? path : `/${path}`}`);
}

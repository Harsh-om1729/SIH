export const API_CONFIG = {
  baseUrl: (import.meta.env.VITE_API_BASE_URL as string) || 'http://127.0.0.1:8000/api/v1',
  wsUrl: (import.meta.env.VITE_WS_URL as string) || 'ws://127.0.0.1:8000/ws/alerts',
  timeoutMs: 4000,
  maxReconnectAttempts: 5,
  reconnectIntervalMs: 5000,
};

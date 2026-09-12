import { API_CONFIG } from './config';
import { Incident } from '@/lib/mockIncidents';

export type WsConnectionStatus = 'connecting' | 'connected' | 'offline-fallback';

type AlertListener = (alert: Incident) => void;
type StatusListener = (status: WsConnectionStatus) => void;

class AlertWebSocketClient {
  private ws: WebSocket | null = null;
  private alertListeners: Set<AlertListener> = new Set();
  private statusListeners: Set<StatusListener> = new Set();
  private status: WsConnectionStatus = 'offline-fallback';
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private isIntentionalClose = false;

  public connect(): void {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.isIntentionalClose = false;
    this.setStatus('connecting');

    try {
      this.ws = new WebSocket(API_CONFIG.wsUrl);

      this.ws.onopen = () => {
        this.reconnectAttempts = 0;
        this.setStatus('connected');
      };

      this.ws.onmessage = (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data);
          if (data && data.type === 'alert' && data.payload) {
            this.notifyAlert(data.payload as Incident);
          } else if (data && data.tier && data.cameraName) {
            this.notifyAlert(data as Incident);
          }
        } catch {
          // ignore non-JSON or heartbeat frames
        }
      };

      this.ws.onerror = () => {
        // Quietly fail over to offline-fallback
        this.setStatus('offline-fallback');
      };

      this.ws.onclose = () => {
        if (!this.isIntentionalClose) {
          this.setStatus('offline-fallback');
          this.scheduleReconnect();
        }
      };
    } catch {
      this.setStatus('offline-fallback');
      this.scheduleReconnect();
    }
  }

  public disconnect(): void {
    this.isIntentionalClose = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.setStatus('offline-fallback');
  }

  public subscribeAlert(listener: AlertListener): () => void {
    this.alertListeners.add(listener);
    return () => {
      this.alertListeners.delete(listener);
    };
  }

  public subscribeStatus(listener: StatusListener): () => void {
    this.statusListeners.add(listener);
    listener(this.status);
    return () => {
      this.statusListeners.delete(listener);
    };
  }

  public getStatus(): WsConnectionStatus {
    return this.status;
  }

  private setStatus(status: WsConnectionStatus): void {
    if (this.status !== status) {
      this.status = status;
      this.statusListeners.forEach((fn) => fn(status));
    }
  }

  private notifyAlert(alert: Incident): void {
    this.alertListeners.forEach((fn) => fn(alert));
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= API_CONFIG.maxReconnectAttempts) {
      return;
    }
    if (this.reconnectTimer) return;

    this.reconnectAttempts++;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, API_CONFIG.reconnectIntervalMs);
  }
}

export const alertWebSocketClient = new AlertWebSocketClient();

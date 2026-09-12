import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import type { Incident } from '@/lib/mockIncidents';
import { alertWebSocketClient, incidentsApi, WsConnectionStatus } from '@/lib/api';
import { playYellowChime, playRedSiren } from '@/lib/audioAlerts';

interface AlertContextType {
  alerts: Incident[];
  unreadCount: number;
  activeToasts: Incident[];
  backendStatus: WsConnectionStatus;
  soundEnabled: boolean;
  popupsMuted: boolean;
  toggleSound: () => void;
  toggleMutePopups: () => void;
  dismissToast: (id: number) => void;
  acknowledgeAlert: (id: number) => void;
  markAllAsRead: () => void;
}

const AlertContext = createContext<AlertContextType | undefined>(undefined);

const LOCAL_STORAGE_KEY = 'ibvap_alerts_data';
const SOUND_STORAGE_KEY = 'ibvap_sound_enabled';
const POPUPS_MUTED_STORAGE_KEY = 'ibvap_popups_muted';
const MAX_TOASTS = 4;

export const AlertProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  // Alerts that arrived over the WebSocket during this session. Starts empty:
  // it used to start from mockIncidents and reload whatever was saved in
  // localStorage — including simulated alerts — and IncidentsPage merged this
  // list into the real incident table, where sample rows then sat under a
  // "Live data" badge. The database is the history; this is only the feed.
  const [alerts, setAlerts] = useState<Incident[]>([]);

  const [activeToasts, setActiveToasts] = useState<Incident[]>([]);
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [backendStatus, setBackendStatus] = useState<WsConnectionStatus>('offline-fallback');

  const [soundEnabled, setSoundEnabled] = useState<boolean>(() => {
    try {
      const saved = localStorage.getItem(SOUND_STORAGE_KEY);
      return saved !== null ? JSON.parse(saved) : true;
    } catch {
      return true;
    }
  });

  const [popupsMuted, setPopupsMuted] = useState<boolean>(() => {
    try {
      const saved = localStorage.getItem(POPUPS_MUTED_STORAGE_KEY);
      return saved !== null ? JSON.parse(saved) : false;
    } catch {
      return false;
    }
  });

  const toggleSound = useCallback(() => {
    setSoundEnabled((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(SOUND_STORAGE_KEY, JSON.stringify(next));
      } catch {
        // ignore
      }
      return next;
    });
  }, []);

  const toggleMutePopups = useCallback(() => {
    setPopupsMuted((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(POPUPS_MUTED_STORAGE_KEY, JSON.stringify(next));
      } catch {
        // ignore
      }
      if (next) {
        setActiveToasts([]);
      }
      return next;
    });
  }, []);

  // One-time cleanup: drop the alert list older builds persisted, which can
  // hold simulated incidents that would otherwise never go away.
  useEffect(() => {
    try {
      localStorage.removeItem(LOCAL_STORAGE_KEY);
    } catch {
      // storage unavailable; nothing to clean
    }
  }, []);

  // Dismiss a toast
  const dismissToast = useCallback((id: number) => {
    setActiveToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  // Acknowledge an alert: records it in incidents.db (so every other screen
  // and operator sees it as acknowledged), then clears it from the toast
  // stack and the unread count. It used to only hide the toast locally.
  const acknowledgeAlert = useCallback((id: number) => {
    dismissToast(id);
    setUnreadCount((prev) => Math.max(0, prev - 1));
    incidentsApi.acknowledgeIncident(id).then((res) => {
      if (res.isFallback) {
        console.warn(`Acknowledge failed for incident ${id}: ${res.error}`);
        return;
      }
      setAlerts((prev) =>
        prev.map((a) => (a.id === id ? { ...a, status: 'acknowledged' } : a))
      );
    });
  }, [dismissToast]);

  // Mark all alerts as read
  const markAllAsRead = useCallback(() => {
    setUnreadCount(0);
    setActiveToasts([]);
  }, []);

  // Process a new incoming alert
  const handleIncomingAlert = useCallback(
    (incident: Incident) => {
      // Clean any accidental name field
      const sanitizedIncident = { ...incident, watchlistMatch: null };
      // Dedupe by id (a reconnect can redeliver) and cap the session list.
      setAlerts((prev) =>
        [sanitizedIncident, ...prev.filter((a) => a.id !== sanitizedIncident.id)].slice(0, 200)
      );

      // Green tier: silent logging (no toast, no unread badge increment, no audio)
      if (sanitizedIncident.tier === 'green') {
        return;
      }

      // Yellow & Red tiers play synthesized tones only if sound is enabled AND popups aren't muted
      if (soundEnabled && !popupsMuted) {
        if (sanitizedIncident.tier === 'yellow') {
          playYellowChime();
        } else if (sanitizedIncident.tier === 'red') {
          playRedSiren();
        }
      }

      // Yellow & Red tiers increment unread count
      setUnreadCount((prev) => prev + 1);

      // Add to active toasts ONLY IF POPUPS ARE NOT MUTED
      if (!popupsMuted) {
        setActiveToasts((prev) => {
          const updated = [sanitizedIncident, ...prev.filter((t) => t.id !== sanitizedIncident.id)];
          return updated.slice(0, MAX_TOASTS);
        });

        // Yellow auto-dismisses after 6 seconds
        if (sanitizedIncident.tier === 'yellow') {
          setTimeout(() => {
            dismissToast(sanitizedIncident.id);
          }, 6000);
        }
      }
    },
    [dismissToast, soundEnabled, popupsMuted]
  );

  // Connect WebSocket & Listen to alerts / status
  useEffect(() => {
    alertWebSocketClient.connect();

    const unsubscribeAlert = alertWebSocketClient.subscribeAlert((incident) => {
      handleIncomingAlert(incident);
    });

    const unsubscribeStatus = alertWebSocketClient.subscribeStatus((status) => {
      setBackendStatus(status);
    });

    return () => {
      unsubscribeAlert();
      unsubscribeStatus();
    };
  }, [handleIncomingAlert]);

  // (Removed: a timer that invented a detection every 22s whenever the
  // WebSocket was not connected — including during every normal reconnect —
  // complete with siren and toast. When the feed is down the UI now says so;
  // it does not manufacture alerts.)

  return (
    <AlertContext.Provider
      value={{
        alerts,
        unreadCount,
        activeToasts,
        backendStatus,
        soundEnabled,
        popupsMuted,
        toggleSound,
        toggleMutePopups,
        dismissToast,
        acknowledgeAlert,
        markAllAsRead,
      }}
    >
      {children}
    </AlertContext.Provider>
  );
};

export const useAlerts = () => {
  const context = useContext(AlertContext);
  if (!context) {
    throw new Error('useAlerts must be used within an AlertProvider');
  }
  return context;
};

import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { Incident, mockIncidents } from '@/lib/mockIncidents';
import { generateSimulatedIncident } from '@/lib/simulateAlertStream';
import { alertWebSocketClient, WsConnectionStatus } from '@/lib/api';
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
  triggerDemoAlert: (tier?: 'green' | 'yellow' | 'red' | 'watchlist') => Incident;
}

const AlertContext = createContext<AlertContextType | undefined>(undefined);

const LOCAL_STORAGE_KEY = 'ibvap_alerts_data';
const SOUND_STORAGE_KEY = 'ibvap_sound_enabled';
const POPUPS_MUTED_STORAGE_KEY = 'ibvap_popups_muted';
const MAX_TOASTS = 4;

export const AlertProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  // Load initial alerts from localStorage (sanitizing any legacy watchlist names) or fallback to mockIncidents
  const [alerts, setAlerts] = useState<Incident[]>(() => {
    try {
      const saved = localStorage.getItem(LOCAL_STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed)) {
          return parsed.map((item: any) => ({ ...item, watchlistMatch: null }));
        }
      }
    } catch {
      // ignore JSON parse error
    }
    return mockIncidents;
  });

  const [activeToasts, setActiveToasts] = useState<Incident[]>([]);
  const [unreadCount, setUnreadCount] = useState<number>(() => {
    return Math.min(
      alerts.filter((i) => i.tier === 'red' || i.tier === 'yellow').length,
      5
    );
  });
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

  // Sync alerts to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(alerts.slice(0, 100)));
    } catch {
      // ignore storage quota errors
    }
  }, [alerts]);

  // Dismiss a toast
  const dismissToast = useCallback((id: number) => {
    setActiveToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  // Acknowledge an alert (removes from toast and decrements unread)
  const acknowledgeAlert = useCallback((id: number) => {
    dismissToast(id);
    setUnreadCount((prev) => Math.max(0, prev - 1));
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
      setAlerts((prev) => [sanitizedIncident, ...prev]);

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

  // Expose trigger for manual demo testing
  const triggerDemoAlert = useCallback(
    (tier?: 'green' | 'yellow' | 'red' | 'watchlist') => {
      const targetTier = tier === 'watchlist' ? 'red' : tier;
      const incident = generateSimulatedIncident(targetTier);
      incident.watchlistMatch = null;
      if (tier === 'watchlist') {
        incident.category = 'person';
        incident.score = 98.5;
        incident.tier = 'red';
      }
      handleIncomingAlert(incident);
      return incident;
    },
    [handleIncomingAlert]
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

  // Background stream: If backend is offline or disconnected, simulate detections every 22s
  useEffect(() => {
    if (backendStatus === 'connected') {
      return;
    }

    const interval = setInterval(() => {
      const newAlert = generateSimulatedIncident();
      handleIncomingAlert(newAlert);
    }, 22000);

    return () => clearInterval(interval);
  }, [backendStatus, handleIncomingAlert]);

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
        triggerDemoAlert,
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

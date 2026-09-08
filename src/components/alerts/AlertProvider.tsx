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
  toggleSound: () => void;
  dismissToast: (id: number) => void;
  acknowledgeAlert: (id: number) => void;
  markAllAsRead: () => void;
  triggerDemoAlert: (tier?: 'green' | 'yellow' | 'red' | 'watchlist') => Incident;
}

const AlertContext = createContext<AlertContextType | undefined>(undefined);

const LOCAL_STORAGE_KEY = 'ibvap_alerts_data';
const SOUND_STORAGE_KEY = 'ibvap_sound_enabled';
const MAX_TOASTS = 4;

export const AlertProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  // Load initial alerts from localStorage or fallback to mockIncidents
  const [alerts, setAlerts] = useState<Incident[]>(() => {
    try {
      const saved = localStorage.getItem(LOCAL_STORAGE_KEY);
      if (saved) {
        return JSON.parse(saved);
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
      setAlerts((prev) => [incident, ...prev]);

      // Green tier: silent logging (no toast, no unread badge increment, no audio)
      if (incident.tier === 'green') {
        return;
      }

      // Yellow & Red tiers play synthesized tones (880Hz chime or 1200Hz siren)
      if (soundEnabled) {
        if (incident.tier === 'yellow') {
          playYellowChime();
        } else if (incident.tier === 'red') {
          playRedSiren();
        }
      }

      // Yellow & Red tiers increment unread count
      setUnreadCount((prev) => prev + 1);

      // Add to active toasts (capped at MAX_TOASTS)
      setActiveToasts((prev) => {
        const updated = [incident, ...prev.filter((t) => t.id !== incident.id)];
        return updated.slice(0, MAX_TOASTS);
      });

      // Yellow auto-dismisses after 6 seconds
      if (incident.tier === 'yellow') {
        setTimeout(() => {
          dismissToast(incident.id);
        }, 6000);
      }
    },
    [dismissToast, soundEnabled]
  );

  // Expose trigger for manual demo testing
  const triggerDemoAlert = useCallback(
    (tier?: 'green' | 'yellow' | 'red' | 'watchlist') => {
      const targetTier = tier === 'watchlist' ? 'red' : tier;
      const incident = generateSimulatedIncident(targetTier);
      if (tier === 'watchlist') {
        incident.watchlistMatch = 'Kashif Ali (W-8812)';
        incident.personId = 8812;
        incident.reidGalleryId = 'PG-W8812';
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
        toggleSound,
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

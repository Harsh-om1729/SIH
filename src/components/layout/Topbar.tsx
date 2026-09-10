import React, { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { Menu, Clock, Volume2, VolumeX, BellOff } from 'lucide-react';
import { AlertBell } from './AlertBell';
import { useAlerts } from '@/components/alerts/AlertProvider';

interface TopbarProps {
  onOpenMobileSidebar: () => void;
  systemStatus?: 'online' | 'air-gapped' | 'standby';
}

const routeTitles: Record<string, { title: string; subtitle: string }> = {
  '/': {
    title: 'Surveillance Dashboard',
    subtitle: 'Real-time border situational overview & critical alerts',
  },
  '/live': {
    title: 'Live Camera Feeds',
    subtitle: 'Multi-camera surveillance stream grid & telemetry',
  },
  '/detections': {
    title: 'Target Detections Feed',
    subtitle: 'Real-time Person, Vehicle, and Unknown target detections & direct camera links',
  },
  '/incidents': {
    title: 'Target Detections Feed',
    subtitle: 'Real-time Person, Vehicle, and Unknown target detections & direct camera links',
  },
  '/zones': {
    title: 'Zone Management',
    subtitle: 'Interactive virtual-fence polygon configuration & tier rules',
  },
  '/analytics': {
    title: 'Threat Intelligence Analytics',
    subtitle: 'Kinematics breakdown, peak curfew patterns, and sector metrics',
  },
};

export const Topbar: React.FC<TopbarProps> = ({
  onOpenMobileSidebar,
  systemStatus = 'online',
}) => {
  const { backendStatus, soundEnabled, toggleSound, popupsMuted, toggleMutePopups } = useAlerts();
  const location = useLocation();
  const [currentTime, setCurrentTime] = useState<string>('');

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      const timeStr = now.toLocaleTimeString('en-GB', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
      });
      const dateStr = now.toLocaleDateString('en-GB', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
      });
      setCurrentTime(`${dateStr} · ${timeStr}`);
    };

    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  const currentRouteInfo = routeTitles[location.pathname] || {
    title: 'Command Center',
    subtitle: 'Border surveillance intelligence console',
  };

  return (
    <header className="sticky top-0 z-30 h-16 bg-[#06080c]/95 backdrop-blur-xl border-b border-[#161924] px-4 lg:px-6 flex items-center justify-between">
      {/* Left: Mobile Toggle & Page Title */}
      <div className="flex items-center gap-3">
        <button
          onClick={onOpenMobileSidebar}
          aria-label="Open navigation menu"
          className="lg:hidden p-2 rounded-xl text-text-dim hover:text-white hover:bg-white/[0.04] transition-colors"
        >
          <Menu className="w-5 h-5" />
        </button>

        <div>
          <h1 className="text-base font-bold text-white tracking-tight flex items-center gap-2">
            <span>{currentRouteInfo.title}</span>
          </h1>
          <p className="hidden sm:block text-xs text-text-dim truncate max-w-md">
            {currentRouteInfo.subtitle}
          </p>
        </div>
      </div>

      {/* Center: Status Pill (Clean, no ping animation) */}
      <div className="hidden md:flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-[#0a0d14] border border-[#1d2232] text-xs font-semibold text-accent-green">
        <span className="inline-flex rounded-full h-2 w-2 bg-accent-green" />
        <span>
          {backendStatus === 'connected'
            ? 'Live Stream Pipeline · 4/4 Online'
            : systemStatus === 'online'
            ? 'Active Monitoring · 4 Cameras Online'
            : 'Standby Mode · Offline'}
        </span>
      </div>

      {/* Right: Quick Actions */}
      <div className="flex items-center gap-2 sm:gap-3">
        {/* 3D Clock */}
        <div className="hidden xl:flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-[#0a0d14] border border-[#161924] text-xs text-text-dim font-mono">
          <Clock className="w-3.5 h-3.5 text-accent-teal" />
          <span>{currentTime || 'Syncing...'}</span>
        </div>

        {/* Audio Alert Toggle */}
        <button
          onClick={toggleSound}
          aria-label={soundEnabled ? 'Mute alert sounds' : 'Enable alert sounds'}
          className={`p-2 rounded-xl transition-colors border ${
            soundEnabled
              ? 'text-accent-teal bg-accent-teal/10 border-accent-teal/30'
              : 'text-text-muted hover:text-white hover:bg-white/[0.04] border-transparent'
          }`}
          title={soundEnabled ? 'Alert Audio: Active' : 'Alert Audio: Muted'}
        >
          {soundEnabled ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
        </button>

        {/* Mute On-Screen Notification Popups Toggle */}
        <button
          onClick={toggleMutePopups}
          aria-label={popupsMuted ? 'Show on-screen popup notifications' : 'Mute on-screen popup notifications'}
          className={`px-2.5 py-1.5 rounded-xl transition-colors border flex items-center gap-1.5 ${
            popupsMuted
              ? 'text-accent-yellow bg-accent-yellow/10 border-accent-yellow/30'
              : 'text-text-muted hover:text-white hover:bg-white/[0.04] border-[#161924]'
          }`}
          title={popupsMuted ? 'Screen Popups Muted (Click to show on screen)' : 'Mute screen popups (Alerts stay silent in background)'}
        >
          <BellOff className="w-4 h-4" />
          <span className="hidden md:inline text-[11px] font-mono font-medium">
            {popupsMuted ? 'Popups Muted' : 'Mute Popups'}
          </span>
        </button>


        {/* Alerts Notification Bell */}
        <AlertBell />
      </div>
    </header>
  );
};


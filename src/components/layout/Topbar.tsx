import React, { useState, useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { Menu, Clock, Activity, User, LogOut, ChevronDown, ShieldCheck, Volume2, VolumeX } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { AlertBell } from './AlertBell';
import { useAlerts } from '@/components/alerts/AlertProvider';
import { useAuth } from '@/components/auth/AuthProvider';

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
  '/incidents': {
    title: 'Incidents & Evidence Center',
    subtitle: 'Threat timeline, snapshots, burst logs, and event audits',
  },
  '/zones': {
    title: 'Zone Management',
    subtitle: 'Interactive virtual-fence polygon configuration & tier rules',
  },
  '/watchlist': {
    title: 'Watchlist Management',
    subtitle: 'Biometric face recognition database & identity verification',
  },
  '/analytics': {
    title: 'Threat Intelligence Analytics',
    subtitle: 'Kinematics breakdown, peak curfew patterns, and sector metrics',
  },
  '/settings': {
    title: 'System Settings & Health',
    subtitle: 'Hardware telemetry, threshold tuning, and C2 integrations',
  },
  '/design-system': {
    title: 'UI Design System & Primitives',
    subtitle: 'Tactical token reference & component test bench',
  },
};

export const Topbar: React.FC<TopbarProps> = ({
  onOpenMobileSidebar,
  systemStatus = 'online',
}) => {
  const { backendStatus, soundEnabled, toggleSound } = useAlerts();
  const { user, logout, switchRole } = useAuth();
  const location = useLocation();
  const [currentTime, setCurrentTime] = useState<string>('');
  const [operatorMenuOpen, setOperatorMenuOpen] = useState(false);
  const operatorMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (operatorMenuRef.current && !operatorMenuRef.current.contains(e.target as Node)) {
        setOperatorMenuOpen(false);
      }
    };
    if (operatorMenuOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [operatorMenuOpen]);

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      const timeStr = now.toLocaleTimeString('en-GB', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
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
    <header className="sticky top-0 z-30 h-16 bg-bg-surface/90 backdrop-blur-md border-b border-border-subtle px-4 lg:px-6 flex items-center justify-between">
      {/* Left: Mobile Toggle & Page Title */}
      <div className="flex items-center gap-3">
        <button
          onClick={onOpenMobileSidebar}
          aria-label="Open navigation menu"
          className="lg:hidden p-2 rounded-sm text-text-dim hover:text-text-primary hover:bg-bg-elevated transition-colors"
        >
          <Menu className="w-5 h-5" />
        </button>

        <div>
          <h1 className="text-sm lg:text-base font-semibold text-text-primary flex items-center gap-2">
            <span>{currentRouteInfo.title}</span>
          </h1>
          <p className="hidden sm:block text-[11px] text-text-dim truncate max-w-md">
            {currentRouteInfo.subtitle}
          </p>
        </div>
      </div>

      {/* Right: Telemetry & Live Status */}
      <div className="flex items-center gap-2.5 sm:gap-3">
        {/* Real-time Client-side Clock */}
        <div className="hidden md:flex items-center gap-2 px-2.5 py-1 rounded-sm bg-bg-elevated border border-border-subtle font-mono text-xs text-text-dim">
          <Clock className="w-3.5 h-3.5 text-accent-teal" />
          <span>{currentTime || 'SYNCHRONIZING...'}</span>
        </div>

        {/* Pipeline Telemetry Pill */}
        <div className="hidden xl:flex items-center gap-2 px-2.5 py-1 rounded-sm bg-bg-surface border border-border-subtle font-mono text-xs text-text-dim">
          <Activity className="w-3.5 h-3.5 text-accent-green" />
          <span>FPS: 30.0 · AI: YOLO+DEEPSORT</span>
        </div>

        {/* Backend / Air-Gap Link Status */}
        {backendStatus === 'connected' ? (
          <Badge variant="green" dot size="md" className="hidden lg:inline-flex font-mono">
            C2 LIVE
          </Badge>
        ) : backendStatus === 'connecting' ? (
          <Badge variant="yellow" dot pulse size="md" className="hidden lg:inline-flex font-mono">
            CONNECTING...
          </Badge>
        ) : (
          <Badge variant="teal" dot size="md" className="hidden lg:inline-flex font-mono">
            AIR-GAPPED SIM
          </Badge>
        )}

        {/* Live System Status Pill */}
        {systemStatus === 'online' && (
          <Badge variant="green" dot pulse size="md">
            <span className="hidden sm:inline">SYSTEM: </span>ONLINE
          </Badge>
        )}

        {/* Tactical Sound Synthesizer Toggle */}
        <button
          onClick={toggleSound}
          aria-label={soundEnabled ? 'Mute tactical alert tones' : 'Enable tactical alert tones'}
          className={`p-2 rounded-sm transition-colors border ${
            soundEnabled
              ? 'text-accent-teal hover:bg-bg-elevated border-border-subtle'
              : 'text-text-muted hover:text-text-primary hover:bg-bg-elevated border-transparent'
          }`}
          title={
            soundEnabled
              ? 'Tactical Audio: 880Hz Chime & 1200Hz Siren Active'
              : 'Tactical Audio: Muted'
          }
        >
          {soundEnabled ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
        </button>

        {/* Real-time Alerts Notification Bell */}
        <AlertBell />

        {/* Operator Profile & Role Switcher */}
        {user && (
          <div className="relative" ref={operatorMenuRef}>
            <button
              onClick={() => setOperatorMenuOpen((prev) => !prev)}
              className="flex items-center gap-2 py-1 px-2.5 rounded-sm bg-bg-elevated hover:bg-bg-surface border border-border-subtle text-xs font-mono transition-colors"
              title="Operator clearance & session controls"
            >
              <User className="w-3.5 h-3.5 text-accent-teal" />
              <span className="hidden sm:inline text-text-primary font-medium truncate max-w-[120px]">
                {user.name}
              </span>
              <Badge
                variant={user.role === 'commander' ? 'teal' : 'green'}
                size="sm"
                className="text-[10px] py-0"
              >
                {user.role.toUpperCase()}
              </Badge>
              <ChevronDown className="w-3 h-3 text-text-dim" />
            </button>

            {/* Operator Menu Dropdown */}
            {operatorMenuOpen && (
              <div className="absolute right-0 mt-2 w-72 rounded-md bg-[#111917] border border-border-subtle shadow-2xl z-50 p-3 space-y-3 font-mono animate-fadeIn">
                <div className="border-b border-border-subtle pb-2.5 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-text-primary flex items-center gap-1.5">
                      <ShieldCheck className="w-4 h-4 text-accent-teal" />
                      {user.name}
                    </span>
                    <Badge variant={user.role === 'commander' ? 'teal' : 'green'} size="sm">
                      {user.role.toUpperCase()}
                    </Badge>
                  </div>
                  <p className="text-[10px] text-text-dim">{user.email}</p>
                  <p className="text-[10px] text-accent-teal font-semibold pt-0.5">
                    {user.clearanceLevel}
                  </p>
                  <p className="text-[10px] text-text-muted">{user.sector}</p>
                </div>

                {/* Quick Role Switcher */}
                <div className="space-y-1">
                  <span className="text-[10px] text-text-muted uppercase">Switch Access Role:</span>
                  <div className="grid grid-cols-2 gap-1.5">
                    <button
                      onClick={() => {
                        switchRole('commander');
                        setOperatorMenuOpen(false);
                      }}
                      className={`p-1.5 rounded text-[11px] border transition-all ${
                        user.role === 'commander'
                          ? 'bg-accent-teal/20 border-accent-teal text-accent-teal font-bold'
                          : 'bg-bg-elevated border-border-subtle text-text-dim hover:text-text-primary'
                      }`}
                    >
                      Commander
                    </button>
                    <button
                      onClick={() => {
                        switchRole('operator');
                        setOperatorMenuOpen(false);
                      }}
                      className={`p-1.5 rounded text-[11px] border transition-all ${
                        user.role === 'operator'
                          ? 'bg-accent-green/20 border-accent-green text-accent-green font-bold'
                          : 'bg-bg-elevated border-border-subtle text-text-dim hover:text-text-primary'
                      }`}
                    >
                      Operator
                    </button>
                  </div>
                </div>

                {/* Logout Button */}
                <div className="pt-2 border-t border-border-subtle">
                  <button
                    onClick={() => {
                      setOperatorMenuOpen(false);
                      logout();
                    }}
                    className="w-full flex items-center justify-center gap-2 p-1.5 rounded bg-accent-red/15 hover:bg-accent-red/25 border border-accent-red/30 text-accent-red text-xs font-semibold transition-colors"
                  >
                    <LogOut className="w-3.5 h-3.5" />
                    <span>Disconnect & Logout</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </header>
  );
};


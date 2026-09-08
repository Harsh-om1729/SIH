import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAlerts } from '@/components/alerts/AlertProvider';
import {
  Bell,
  CheckCheck,
  ShieldAlert,
  Radio,
  ExternalLink,
  User,
  Car,
  HelpCircle,
  Zap,
} from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';

export const AlertBell: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const { alerts, unreadCount, markAllAsRead, acknowledgeAlert, triggerDemoAlert } = useAlerts();
  const dropdownRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  // Close dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  // Relative timestamp formatting
  const formatTimeAgo = (timestampSec: number) => {
    const nowSec = Math.floor(Date.now() / 1000);
    const diff = Math.max(0, nowSec - timestampSec);

    if (diff < 15) return 'Just now';
    if (diff < 60) return `${diff}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    return new Date(timestampSec * 1000).toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const recentAlerts = alerts.slice(0, 10);

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Bell Trigger Button */}
      <button
        onClick={() => setIsOpen((prev) => !prev)}
        aria-label="Open notifications center"
        className={`relative p-2 rounded-sm text-text-dim hover:text-text-primary hover:bg-bg-elevated transition-colors border ${
          isOpen
            ? 'bg-bg-elevated text-text-primary border-border'
            : 'border-transparent'
        }`}
      >
        <Bell className="w-4 h-4" />

        {/* Pulsing indicator & Badge when unread > 0 */}
        {unreadCount > 0 && (
          <>
            <span className="absolute -top-1 -right-1 flex h-4 min-w-4 px-1 items-center justify-center rounded-full bg-accent-red text-white text-[10px] font-mono font-bold shadow-md">
              {unreadCount > 9 ? '9+' : unreadCount}
            </span>
            <span className="absolute -top-1 -right-1 flex h-4 w-4 rounded-full bg-accent-red/50 animate-ping pointer-events-none" />
          </>
        )}
      </button>

      {/* Dropdown Panel */}
      {isOpen && (
        <div className="absolute right-0 mt-2 w-80 sm:w-96 rounded-md bg-[#111917] border border-border-subtle shadow-2xl z-50 overflow-hidden animate-fadeIn">
          {/* Header */}
          <div className="p-3.5 bg-bg-surface border-b border-border-subtle flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs font-bold tracking-wider text-text-primary flex items-center gap-1.5">
                <Radio className="w-3.5 h-3.5 text-accent-teal animate-pulse" />
                TACTICAL ALERTS
              </span>
              {unreadCount > 0 && (
                <Badge variant="red" size="sm">
                  {unreadCount} NEW
                </Badge>
              )}
            </div>

            {unreadCount > 0 && (
              <button
                onClick={markAllAsRead}
                className="flex items-center gap-1 text-[11px] font-mono text-text-dim hover:text-accent-teal transition-colors"
                title="Mark all alerts as read"
              >
                <CheckCheck className="w-3.5 h-3.5" />
                Clear All
              </button>
            )}
          </div>

          {/* Quick Demo Simulator Bar */}
          <div className="px-3 py-2 bg-bg-elevated/60 border-b border-border-subtle/70 flex items-center justify-between text-[11px]">
            <span className="font-mono text-text-dim flex items-center gap-1">
              <Zap className="w-3 h-3 text-accent-yellow" />
              TEST TRIGGER:
            </span>
            <div className="flex items-center gap-1.5">
              <button
                onClick={() => triggerDemoAlert('yellow')}
                className="px-2 py-0.5 rounded bg-accent-yellow/15 text-accent-yellow hover:bg-accent-yellow/25 border border-accent-yellow/30 font-mono text-[10px] font-semibold transition-colors"
              >
                + Caution
              </button>
              <button
                onClick={() => triggerDemoAlert('red')}
                className="px-2 py-0.5 rounded bg-accent-red/15 text-accent-red hover:bg-accent-red/25 border border-accent-red/30 font-mono text-[10px] font-semibold transition-colors"
              >
                + High Threat
              </button>
            </div>
          </div>

          {/* Alert List */}
          <div className="max-h-72 overflow-y-auto divide-y divide-border-subtle/40">
            {recentAlerts.length === 0 ? (
              <div className="p-6 text-center text-text-dim text-xs">
                No telemetry alerts recorded yet.
              </div>
            ) : (
              recentAlerts.map((alert) => {
                const isRed = alert.tier === 'red';
                const isYellow = alert.tier === 'yellow';

                return (
                  <div
                    key={alert.id}
                    onClick={() => {
                      acknowledgeAlert(alert.id);
                      setIsOpen(false);
                      navigate('/incidents');
                    }}
                    className={`p-3 hover:bg-bg-elevated/70 transition-colors cursor-pointer flex items-start gap-2.5 ${
                      isRed ? 'bg-accent-red/5' : ''
                    }`}
                  >
                    {/* Category / Alert Icon */}
                    <div
                      className={`p-1.5 rounded-sm mt-0.5 shrink-0 ${
                        isRed
                          ? 'bg-accent-red/20 text-accent-red'
                          : isYellow
                          ? 'bg-accent-yellow/20 text-accent-yellow'
                          : 'bg-accent-green/20 text-accent-green'
                      }`}
                    >
                      {alert.category === 'person' && <User className="w-3.5 h-3.5" />}
                      {alert.category === 'vehicle' && <Car className="w-3.5 h-3.5" />}
                      {alert.category === 'unknown' && <HelpCircle className="w-3.5 h-3.5" />}
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-1">
                        <div className="flex items-center gap-1.5">
                          <span className="font-mono text-xs font-semibold text-text-primary uppercase">
                            {alert.cameraName}
                          </span>
                          <Badge
                            variant={
                              alert.tier === 'red'
                                ? 'red'
                                : alert.tier === 'yellow'
                                ? 'yellow'
                                : 'green'
                            }
                            size="sm"
                          >
                            {alert.tier.toUpperCase()}
                          </Badge>
                        </div>
                        <span className="font-mono text-[10px] text-text-dim shrink-0">
                          {formatTimeAgo(alert.timestamp)}
                        </span>
                      </div>

                      <div className="text-[11px] text-text-dim mt-0.5 flex items-center justify-between">
                        <span className="capitalize">
                          {alert.category} · Zone {alert.zoneTier || alert.tier}
                        </span>
                        <span
                          className={`font-mono font-medium ${
                            isRed
                              ? 'text-accent-red'
                              : isYellow
                              ? 'text-accent-yellow'
                              : 'text-text-dim'
                          }`}
                        >
                          SCORE: {alert.score}
                        </span>
                      </div>

                      {/* Threat S/T/K/C formula breakdown */}
                      {alert.breakdown && (
                        <div className="text-[10px] font-mono text-text-muted mt-0.5 flex items-center justify-between">
                          <span>
                            S:{alert.breakdown.sectorRisk} T:{alert.breakdown.timeRisk} K:{alert.breakdown.kinematicsRisk} C:{alert.breakdown.classConfidence}
                          </span>
                          <span className="text-accent-teal">#{alert.reidGalleryId}</span>
                        </div>
                      )}

                      {/* Watchlist match pill */}
                      {alert.watchlistMatch && (
                        <div className="mt-1 inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-accent-red/20 border border-accent-red/40 text-accent-red text-[10px] font-mono font-bold">
                          <ShieldAlert className="w-3 h-3" />
                          <span>MATCH: {alert.watchlistMatch}</span>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Footer */}
          <div className="p-2.5 bg-bg-surface border-t border-border-subtle flex items-center justify-center">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setIsOpen(false);
                navigate('/incidents');
              }}
              className="w-full text-xs text-text-dim hover:text-accent-teal justify-center"
            >
              <span>View All in Evidence Center</span>
              <ExternalLink className="w-3 h-3 ml-1.5" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};

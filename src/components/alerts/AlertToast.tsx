import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAlerts } from './AlertProvider';
import {
  AlertTriangle,
  ShieldAlert,
  X,
  Eye,
  CheckCircle2,
  User,
  Car,
  HelpCircle,
} from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';

export const AlertToastContainer: React.FC = () => {
  const { activeToasts, dismissToast, acknowledgeAlert, unreadCount } = useAlerts();
  const navigate = useNavigate();

  if (activeToasts.length === 0) {
    return null;
  }

  const overflowCount = Math.max(0, unreadCount - activeToasts.length);

  return (
    <div
      aria-live="assertive"
      className="fixed top-20 right-4 sm:right-6 z-50 flex flex-col gap-3 max-w-sm sm:max-w-md w-full pointer-events-none transition-all"
    >
      {activeToasts.map((toast) => {
        const isRed = toast.tier === 'red';

        return (
          <div
            key={toast.id}
            className={`pointer-events-auto rounded-r-md transition-all duration-300 transform translate-y-0 ${
              isRed
                ? 'bg-[#181012]/95 border-l-4 border-l-accent-red border border-accent-red/40 shadow-[0_0_25px_rgba(229,72,77,0.35)] backdrop-blur-md'
                : 'bg-bg-surface/95 border-l-4 border-l-accent-yellow border border-border-subtle shadow-xl backdrop-blur-md'
            } p-4 relative overflow-hidden`}
          >
            {/* Countdown bar for yellow alerts (6s) */}
            {!isRed && (
              <div className="absolute bottom-0 left-0 right-0 h-1 bg-border-subtle overflow-hidden">
                <div
                  className="h-full bg-accent-yellow transition-all linear"
                  style={{
                    animation: 'shrinkBar 6s linear forwards',
                  }}
                />
              </div>
            )}

            {/* Header: Tier + Camera + Close Button */}
            <div className="flex items-center justify-between gap-2 mb-2">
              <div className="flex items-center gap-2">
                {isRed ? (
                  <span className="flex items-center gap-1.5 px-2 py-0.5 rounded-sm bg-accent-red/20 text-accent-red font-mono text-[11px] font-bold tracking-wider animate-pulse">
                    <ShieldAlert className="w-3.5 h-3.5" />
                    HIGH THREAT
                  </span>
                ) : (
                  <span className="flex items-center gap-1.5 px-2 py-0.5 rounded-sm bg-accent-yellow/20 text-accent-yellow font-mono text-[11px] font-medium tracking-wider">
                    <AlertTriangle className="w-3.5 h-3.5" />
                    CAUTION DETECTED
                  </span>
                )}

                <span className="font-mono text-xs font-semibold text-text-primary uppercase">
                  {toast.cameraName}
                </span>
              </div>

              <button
                onClick={() => dismissToast(toast.id)}
                aria-label="Dismiss alert"
                className="p-1 rounded text-text-dim hover:text-text-primary hover:bg-bg-elevated transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Main content body */}
            <div className="flex items-start gap-3 my-2">
              {/* Category Icon */}
              <div
                className={`p-2 rounded-sm shrink-0 ${
                  isRed
                    ? 'bg-accent-red/15 text-accent-red'
                    : 'bg-accent-yellow/15 text-accent-yellow'
                }`}
              >
                {toast.category === 'person' && <User className="w-4 h-4" />}
                {toast.category === 'vehicle' && <Car className="w-4 h-4" />}
                {toast.category === 'unknown' && <HelpCircle className="w-4 h-4" />}
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-text-primary font-medium capitalize">
                    {toast.category} detected in {toast.zoneTier || toast.tier} zone
                  </span>
                  <span
                    className={`font-mono font-bold ${
                      isRed ? 'text-accent-red' : 'text-accent-yellow'
                    }`}
                  >
                    SCORE: {toast.score}
                  </span>
                </div>

                {/* S/T/K/C Threat Formula breakdown */}
                {toast.breakdown && (
                  <div className="mt-1 font-mono text-[10px] text-text-dim flex items-center justify-between">
                    <span>
                      S:{toast.breakdown.sectorRisk} T:{toast.breakdown.timeRisk} K:{toast.breakdown.kinematicsRisk} C:{toast.breakdown.classConfidence}
                    </span>
                    <span className="text-accent-teal font-semibold">
                      #{toast.reidGalleryId}
                    </span>
                  </div>
                )}

                {/* Watchlist Match callout if present */}
                {toast.watchlistMatch && (
                  <div className="mt-1.5 flex items-center gap-1.5 p-1.5 rounded bg-accent-red/20 border border-accent-red/40 text-accent-red font-mono text-xs font-bold">
                    <ShieldAlert className="w-3.5 h-3.5 shrink-0" />
                    <span className="truncate">⚠ MATCH: {toast.watchlistMatch} (Overridden to Red)</span>
                  </div>
                )}
              </div>
            </div>

            {/* Red Action Buttons Footer */}
            {isRed && (
              <div className="mt-3 pt-2.5 border-t border-accent-red/20 flex items-center justify-end gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => acknowledgeAlert(toast.id)}
                  className="text-xs text-text-dim hover:text-text-primary"
                >
                  <CheckCircle2 className="w-3.5 h-3.5 mr-1" />
                  Acknowledge
                </Button>
                <Button
                  variant="danger"
                  size="sm"
                  onClick={() => {
                    acknowledgeAlert(toast.id);
                    navigate('/incidents');
                  }}
                  className="text-xs font-semibold shadow-sm"
                >
                  <Eye className="w-3.5 h-3.5 mr-1" />
                  View Evidence
                </Button>
              </div>
            )}
          </div>
        );
      })}

      {/* Overflow indicator */}
      {overflowCount > 0 && (
        <div className="pointer-events-auto self-end">
          <Badge
            variant="neutral"
            size="sm"
            onClick={() => navigate('/incidents')}
            className="cursor-pointer hover:bg-bg-elevated transition-colors border border-border-subtle font-mono text-[11px]"
          >
            +{overflowCount} more unread alerts →
          </Badge>
        </div>
      )}

      {/* Embedded CSS animation for countdown bar */}
      <style>{`
        @keyframes shrinkBar {
          from { width: 100%; }
          to { width: 0%; }
        }
      `}</style>
    </div>
  );
};

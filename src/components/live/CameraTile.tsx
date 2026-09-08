import React, { useState } from 'react';
import { Video, Maximize2, Minimize2, Info, Trash2 } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface CameraTileProps {
  cameraName: string;
  label?: string;
  streamUrl?: string;
  isActive?: boolean;
  fps?: string | number;
  activity?: string;
  activityGate?: 'HIGH' | 'LOW';
  lowLightBoost?: boolean;
  tamperStatus?: 'ok' | 'occluded' | 'frozen';
  isFocused?: boolean;
  onToggleFocus?: () => void;
  onRemove?: () => void;
  className?: string;
}

export const CameraTile: React.FC<CameraTileProps> = ({
  cameraName,
  label,
  streamUrl,
  isActive = true,
  fps = '0.0',
  activity = '—',
  activityGate = 'HIGH',
  lowLightBoost = false,
  tamperStatus = 'ok',
  isFocused = false,
  onToggleFocus,
  onRemove,
  className,
}) => {
  const [showTooltip, setShowTooltip] = useState(false);

  return (
    <div
      className={cn(
        'group relative rounded-sm border border-border-subtle bg-bg-surface overflow-hidden transition-all duration-200 shadow-sm',
        isFocused ? 'ring-1 ring-accent-teal/60' : 'hover:border-text-muted/60',
        className
      )}
    >
      {/* 16:9 Video Canvas / Placeholder Area */}
      <div className="relative aspect-video w-full bg-bg-primary/95 flex items-center justify-center overflow-hidden">
        {/* Subtle tactical corner markings */}
        <div className="absolute top-2 left-2 w-3 h-3 border-t-2 border-l-2 border-border-subtle group-hover:border-accent-teal/40 pointer-events-none transition-colors" />
        <div className="absolute top-2 right-2 w-3 h-3 border-t-2 border-r-2 border-border-subtle group-hover:border-accent-teal/40 pointer-events-none transition-colors" />
        <div className="absolute bottom-2 left-2 w-3 h-3 border-b-2 border-l-2 border-border-subtle group-hover:border-accent-teal/40 pointer-events-none transition-colors" />
        <div className="absolute bottom-2 right-2 w-3 h-3 border-b-2 border-r-2 border-border-subtle group-hover:border-accent-teal/40 pointer-events-none transition-colors" />

        {/* Center Crosshair / Scanline Overlay */}
        <div className="absolute inset-0 bg-tactical-grid opacity-30 pointer-events-none" />

        {streamUrl ? (
          <img
            src={streamUrl}
            alt={`Live feed from ${cameraName}`}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="flex flex-col items-center justify-center text-center p-4 z-10 space-y-2 select-none">
            <div className="p-3 rounded-full bg-bg-surface border border-border-subtle text-text-muted group-hover:text-accent-teal group-hover:border-accent-teal/30 transition-all">
              <Video className="w-6 h-6 sm:w-8 sm:h-8" />
            </div>
            <div className="space-y-0.5">
              <div className="font-mono text-xs sm:text-sm font-semibold tracking-wider text-text-dim uppercase">
                Awaiting stream: <span className="text-accent-teal">{cameraName}</span>
              </div>
              {label && (
                <div className="text-[11px] font-mono text-text-muted">
                  {label}
                </div>
              )}
            </div>
          </div>
        )}

        {/* TOP-LEFT OVERLAY: Camera Name & Live Status Dot */}
        <div className="absolute top-3 left-3 z-20 flex items-center gap-2 px-2.5 py-1 rounded-sm bg-bg-surface/85 backdrop-blur-sm border border-border-subtle/80 shadow-sm">
          <span className="relative flex h-2 w-2">
            {isActive ? (
              <>
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent-green opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-accent-green" />
              </>
            ) : (
              <span className="relative inline-flex rounded-full h-2 w-2 bg-text-muted" />
            )}
          </span>
          <span className="font-mono text-xs font-semibold text-text-primary tracking-wider uppercase">
            {cameraName}
          </span>
          {label && (
            <span className="hidden sm:inline font-mono text-[10px] text-text-dim border-l border-border-subtle pl-1.5">
              {label}
            </span>
          )}

          {/* Activity Gate Status (activity_gate/gate.py) */}
          <span
            className={`hidden md:inline-block font-mono text-[9px] px-1 py-0.5 rounded border ${
              activityGate === 'HIGH'
                ? 'bg-accent-teal/15 text-accent-teal border-accent-teal/30'
                : 'bg-accent-yellow/15 text-accent-yellow border-accent-yellow/30'
            }`}
          >
            {activityGate === 'HIGH' ? 'GATE: 30FPS' : 'GATE: IDLE'}
          </span>

          {/* Low-Light Boost Status (preprocessing/enhance.py) */}
          {lowLightBoost && (
            <span className="hidden md:inline-block font-mono text-[9px] px-1 py-0.5 rounded bg-accent-yellow/15 text-accent-yellow border border-accent-yellow/30">
              CLAHE BOOST
            </span>
          )}

          {/* Optical Tamper Status (Section 19 #13 & 20) */}
          <span
            className={`hidden lg:inline-block font-mono text-[9px] px-1 py-0.5 rounded border ${
              tamperStatus === 'ok'
                ? 'bg-accent-green/10 text-accent-green border-accent-green/30'
                : 'bg-accent-red/20 text-accent-red border-accent-red/40 animate-pulse'
            }`}
          >
            {tamperStatus === 'ok' ? 'OPTICAL: OK' : 'TAMPER DETECTED'}
          </span>
        </div>

        {/* TOP-RIGHT OVERLAY: Tier-Legend Badge + Controls */}
        <div className="absolute top-3 right-3 z-20 flex items-center gap-1.5">
          {/* Optional Remove button */}
          {onRemove && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onRemove();
              }}
              title="Remove camera from grid"
              className="p-1.5 rounded-sm bg-bg-surface/85 backdrop-blur-sm border border-border-subtle text-text-muted hover:text-accent-red hover:border-accent-red/40 transition-colors"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          )}

          {/* Focus Toggle Button */}
          {onToggleFocus && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onToggleFocus();
              }}
              title={isFocused ? 'Return to grid view' : 'Focus camera feed'}
              className="p-1.5 rounded-sm bg-bg-surface/85 backdrop-blur-sm border border-border-subtle text-text-dim hover:text-text-primary hover:bg-bg-elevated transition-colors"
            >
              {isFocused ? (
                <Minimize2 className="w-3.5 h-3.5 text-accent-teal" />
              ) : (
                <Maximize2 className="w-3.5 h-3.5" />
              )}
            </button>
          )}

          {/* Tier-Legend Indicator */}
          <div
            className="relative"
            onMouseEnter={() => setShowTooltip(true)}
            onMouseLeave={() => setShowTooltip(false)}
          >
            <div className="flex items-center gap-1.5 px-2 py-1 rounded-sm bg-bg-surface/85 backdrop-blur-sm border border-border-subtle/80 cursor-help">
              <span className="flex items-center gap-1 font-mono text-[10px] tracking-wider font-semibold">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-accent-green" />
                <span className="hidden sm:inline text-accent-green">G</span>
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-accent-yellow" />
                <span className="hidden sm:inline text-accent-yellow">Y</span>
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-accent-red" />
                <span className="hidden sm:inline text-accent-red">R</span>
              </span>
              <Info className="w-3 h-3 text-text-muted" />
            </div>

            {/* Hover Tooltip */}
            {showTooltip && (
              <div className="absolute right-0 top-8 z-30 w-56 p-2 rounded-sm bg-bg-surface border border-border-subtle shadow-xl text-left animate-in fade-in duration-100">
                <div className="text-[10px] font-mono text-text-dim uppercase tracking-wider mb-1 border-b border-border-subtle/60 pb-1">
                  Zone Threat Tiers
                </div>
                <div className="space-y-1 text-[11px] font-sans">
                  <div className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-accent-green shrink-0" />
                    <span className="text-text-primary">
                      <strong className="text-accent-green">Green:</strong> Normal activity
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-accent-yellow shrink-0" />
                    <span className="text-text-primary">
                      <strong className="text-accent-yellow">Yellow:</strong> Caution zone
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-accent-red shrink-0" />
                    <span className="text-text-primary">
                      <strong className="text-accent-red">High threat intrusion</strong>
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* BOTTOM OVERLAY STRIP: Monospace Telemetry */}
        <div className="absolute bottom-0 left-0 right-0 z-20 px-3 py-1.5 bg-bg-surface/90 backdrop-blur-sm border-t border-border-subtle/80 flex items-center justify-between font-mono text-[11px] text-text-dim">
          <div className="flex items-center gap-3">
            <span>
              FPS: <span className="text-accent-teal font-semibold">{fps}</span>
            </span>
            <span className="text-border-subtle">|</span>
            <span>
              ACTIVITY: <span className="text-text-primary">{activity}</span>
            </span>
          </div>

          <div className="flex items-center gap-2 text-[10px] text-text-muted">
            <span className="hidden sm:inline">RESOLUTION: 1920x1080</span>
            <span className="hidden sm:inline text-border-subtle">|</span>
            <span>AI: ACTIVE</span>
          </div>
        </div>
      </div>
    </div>
  );
};

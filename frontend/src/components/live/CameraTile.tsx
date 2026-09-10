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
  fps = '30.0',
  activity = 'ACTIVE',
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
        'card-3d group relative rounded-2xl border border-white/10 bg-[#07070c] overflow-hidden transition-colors duration-100 shadow-md',
        isFocused ? 'ring-1 ring-accent-teal border-accent-teal' : 'hover:border-white/20',
        className
      )}
    >
      {/* 16:9 Video Canvas / Stream or Tactical Awaiting Placeholder */}
      <div className="relative aspect-video w-full bg-[#05070a] flex items-center justify-center overflow-hidden">
        {/* Subtle camera frame boundary accents */}
        <div className="absolute top-2.5 left-2.5 w-3 h-3 border-t border-l border-white/15 pointer-events-none z-20" />
        <div className="absolute top-2.5 right-2.5 w-3 h-3 border-t border-r border-white/15 pointer-events-none z-20" />
        <div className="absolute bottom-8 left-2.5 w-3 h-3 border-b border-l border-white/15 pointer-events-none z-20" />
        <div className="absolute bottom-8 right-2.5 w-3 h-3 border-b border-r border-white/15 pointer-events-none z-20" />

        {/* Center Crosshair / Scanline Overlay */}
        <div className="absolute inset-0 bg-tactical-grid opacity-25 pointer-events-none" />

        {streamUrl ? (
          <img
            src={streamUrl}
            alt={`Live feed from ${cameraName}`}
            className="w-full h-full object-cover select-none"
          />
        ) : (
          <div className="flex flex-col items-center justify-center text-center p-4 z-10 space-y-2.5 select-none">
            <div className="p-3.5 rounded-2xl bg-[#0b0e17] border border-white/10 text-text-muted group-hover:text-accent-teal group-hover:border-accent-teal/30 transition-colors shadow-inner">
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
        <div className="absolute top-3 left-3 z-20 flex items-center gap-2">
          <div className="flex items-center gap-2 px-2.5 py-1 rounded bg-black/85 border border-white/10 shadow-sm">
            <span
              className={cn(
                'inline-flex rounded-full h-1.5 w-1.5',
                isActive ? 'bg-accent-green' : 'bg-text-muted'
              )}
            />

            <span className="font-mono text-xs font-bold text-white tracking-wider uppercase">
              {cameraName}
            </span>

            {label && (
              <span className="hidden sm:inline font-mono text-[10px] text-text-dim border-l border-white/15 pl-1.5">
                {label}
              </span>
            )}
          </div>

          {/* Activity Gate Status */}
          <span
            className={`hidden md:inline-block font-mono text-[9px] px-1.5 py-0.5 rounded border font-semibold ${
              activityGate === 'HIGH'
                ? 'bg-accent-teal/15 text-accent-teal border-accent-teal/30'
                : 'bg-accent-yellow/15 text-accent-yellow border-accent-yellow/30'
            }`}
          >
            {activityGate === 'HIGH' ? 'GATE: 30FPS' : 'GATE: IDLE'}
          </span>

          {/* Low-Light Boost Status */}
          {lowLightBoost && (
            <span className="hidden md:inline-block font-mono text-[9px] px-1.5 py-0.5 rounded bg-accent-yellow/15 text-accent-yellow border border-accent-yellow/30 font-semibold">
              CLAHE BOOST
            </span>
          )}

          {/* Optical Tamper Status */}
          <span
            className={`hidden lg:inline-block font-mono text-[9px] px-1.5 py-0.5 rounded border font-semibold ${
              tamperStatus === 'ok'
                ? 'bg-accent-green/10 text-accent-green border-accent-green/30'
                : 'bg-accent-red/20 text-accent-red border-accent-red/40'
            }`}
          >
            {tamperStatus === 'ok' ? 'OPTICAL: OK' : 'TAMPER DETECTED'}
          </span>
        </div>

        {/* TOP-RIGHT OVERLAY: Controls + Tier-Legend */}
        <div className="absolute top-3 right-3 z-20 flex items-center gap-1.5">
          {/* Optional Remove button */}
          {onRemove && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onRemove();
              }}
              title="Remove camera channel"
              className="p-1.5 rounded bg-black/85 border border-white/10 text-text-muted hover:text-accent-red hover:border-accent-red/40 hover:bg-accent-red/10 transition-colors"
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
              className="p-1.5 rounded bg-black/85 border border-white/10 text-text-dim hover:text-white hover:border-accent-teal/40 transition-colors"
            >
              {isFocused ? (
                <Minimize2 className="w-3.5 h-3.5 text-accent-teal" />
              ) : (
                <Maximize2 className="w-3.5 h-3.5" />
              )}
            </button>
          )}

          {/* Tier-Legend Tooltip */}
          <div
            className="relative hidden sm:block"
            onMouseEnter={() => setShowTooltip(true)}
            onMouseLeave={() => setShowTooltip(false)}
          >
            <div className="flex items-center gap-1 px-1.5 py-1 rounded bg-black/85 border border-white/10 cursor-help">
              <span className="flex items-center gap-1 font-mono text-[9px] tracking-wider font-semibold">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-accent-green" />
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-accent-yellow" />
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-accent-red" />
              </span>
              <Info className="w-3 h-3 text-text-muted" />
            </div>

            {showTooltip && (
              <div className="absolute right-0 top-8 z-30 w-52 p-2.5 rounded-lg bg-[#090c12] border border-white/10 shadow-xl text-left">
                <div className="text-[10px] font-mono text-text-dim uppercase tracking-wider mb-1.5 border-b border-white/10 pb-1 font-semibold">
                  Zone Threat Tiers
                </div>
                <div className="space-y-1.5 text-[11px] font-sans">
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
        <div className="absolute bottom-0 left-0 right-0 z-20 px-3.5 py-2 bg-gradient-to-t from-black via-black/90 to-black/60 backdrop-blur-md border-t border-white/10 flex items-center justify-between font-mono text-[11px] text-text-dim">
          <div className="flex items-center gap-3">
            <span>
              FPS: <span className="text-accent-teal font-semibold">{fps}</span>
            </span>
            <span className="text-white/20">|</span>
            <span>
              ACTIVITY: <span className="text-text-primary font-semibold">{activity}</span>
            </span>
          </div>

          <div className="flex items-center gap-2 text-[10px] text-text-muted">
            <span className="hidden sm:inline">RESOLUTION: 1920x1080</span>
            <span className="hidden sm:inline text-white/20">|</span>
            <span className="text-accent-green font-semibold">AI: ACTIVE</span>
          </div>
        </div>
      </div>
    </div>
  );
};

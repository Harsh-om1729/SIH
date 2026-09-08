import React, { useState, useRef } from 'react';
import { Zone } from '@/lib/mockZones';
import { Button } from '@/components/ui/Button';
import {
  Check,
  X,
  Crosshair,
  Pencil,
  Trash2,
} from 'lucide-react';

export interface ZoneCanvasProps {
  cameraName: string;
  zones: Zone[];
  selectedZoneId: string | null;
  onSelectZone: (id: string | null) => void;
  onEditZone: (zone: Zone) => void;
  onDeleteZone: (id: string) => void;
  isDrawing: boolean;
  onStartDrawing: () => void;
  onCancelDrawing: () => void;
  onFinishDrawing: (points: { x: number; y: number }[]) => void;
}

export const ZoneCanvas: React.FC<ZoneCanvasProps> = ({
  cameraName,
  zones,
  selectedZoneId,
  onSelectZone,
  onEditZone,
  onDeleteZone,
  isDrawing,
  onStartDrawing,
  onCancelDrawing,
  onFinishDrawing,
}) => {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [currentPoints, setCurrentPoints] = useState<{ x: number; y: number }[]>([]);
  const [mousePos, setMousePos] = useState<{ x: number; y: number } | null>(null);
  const [hoveredZoneId, setHoveredZoneId] = useState<string | null>(null);

  // SVG dimensions for 16:9 aspect ratio
  const VIEW_WIDTH = 1000;
  const VIEW_HEIGHT = 562.5;

  // Calculate normalized coordinate (0.0 to 1.0) from mouse event
  const getNormalizedCoordinates = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!svgRef.current) return { x: 0, y: 0 };
    const rect = svgRef.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const y = Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height));
    return {
      x: Number(x.toFixed(4)),
      y: Number(y.toFixed(4)),
    };
  };

  const handleCanvasClick = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!isDrawing) return;
    const pt = getNormalizedCoordinates(e);
    setCurrentPoints((prev) => [...prev, pt]);
  };

  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const pt = getNormalizedCoordinates(e);
    setMousePos(pt);
  };

  const handleDoubleClick = () => {
    if (isDrawing && currentPoints.length >= 3) {
      handleCompletePolygon();
    }
  };

  const handleCompletePolygon = () => {
    if (currentPoints.length >= 3) {
      onFinishDrawing(currentPoints);
      setCurrentPoints([]);
    }
  };

  const handleCancel = () => {
    setCurrentPoints([]);
    onCancelDrawing();
  };

  // Convert normalized points array to SVG polygon points string
  const toSvgPoints = (points: { x: number; y: number }[]) => {
    return points
      .map((p) => `${p.x * VIEW_WIDTH},${p.y * VIEW_HEIGHT}`)
      .join(' ');
  };

  // Compute centroid of polygon for label placement
  const getCentroid = (points: { x: number; y: number }[]) => {
    if (points.length === 0) return { x: 500, y: 281 };
    const sumX = points.reduce((acc, p) => acc + p.x, 0);
    const sumY = points.reduce((acc, p) => acc + p.y, 0);
    return {
      x: (sumX / points.length) * VIEW_WIDTH,
      y: (sumY / points.length) * VIEW_HEIGHT,
    };
  };

  const tierColors = {
    red: {
      fill: 'rgba(229, 72, 77, 0.25)',
      stroke: '#e5484d',
      highlight: '#ff757a',
    },
    yellow: {
      fill: 'rgba(230, 195, 74, 0.25)',
      stroke: '#e6c34a',
      highlight: '#ffdb6b',
    },
    green: {
      fill: 'rgba(79, 191, 122, 0.25)',
      stroke: '#4fbf7a',
      highlight: '#71d498',
    },
  };

  return (
    <div className="space-y-3">
      {/* Editor Canvas Toolbar Overlay */}
      <div className="flex items-center justify-between px-3 py-2 bg-bg-surface border border-border-subtle rounded-sm font-mono text-xs">
        <div className="flex items-center gap-2">
          <Crosshair className="w-4 h-4 text-accent-teal" />
          <span className="text-text-primary font-semibold uppercase">
            {cameraName} // REFERENCE FRAME CANVAS
          </span>
          <span className="text-border-subtle">|</span>
          <span className="text-text-dim">
            {zones.length} {zones.length === 1 ? 'ZONE' : 'ZONES'} DEFINED
          </span>
        </div>

        <div className="flex items-center gap-3">
          {mousePos && (
            <span className="hidden sm:inline text-text-muted text-[11px]">
              X: {mousePos.x} · Y: {mousePos.y}
            </span>
          )}

          {isDrawing ? (
            <div className="flex items-center gap-2">
              <span className="text-accent-teal font-semibold">
                {currentPoints.length} VERTICES PLACED
              </span>
              <Button
                variant="primary"
                size="sm"
                disabled={currentPoints.length < 3}
                leftIcon={<Check className="w-3.5 h-3.5" />}
                onClick={handleCompletePolygon}
              >
                Finish Zone
              </Button>
              <Button
                variant="ghost"
                size="sm"
                leftIcon={<X className="w-3.5 h-3.5" />}
                onClick={handleCancel}
              >
                Cancel
              </Button>
            </div>
          ) : (
            <Button
              variant="primary"
              size="sm"
              leftIcon={<Crosshair className="w-3.5 h-3.5" />}
              onClick={onStartDrawing}
            >
              Draw New Zone
            </Button>
          )}
        </div>
      </div>

      {/* Main 16:9 Canvas Area */}
      <div className="relative aspect-video w-full rounded-sm border border-border-subtle bg-bg-primary overflow-hidden select-none">
        {/* Synthetic Background Reference Frame */}
        <div className="absolute inset-0 bg-tactical-grid opacity-40 pointer-events-none" />

        {/* Tactical Crosshair Watermark in Center */}
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="w-24 h-24 border border-border-subtle/50 rounded-full flex items-center justify-center">
            <div className="w-1.5 h-1.5 rounded-full bg-accent-teal/40" />
          </div>
        </div>

        {/* Camera OSD Label */}
        <div className="absolute top-3 left-3 pointer-events-none px-2.5 py-1 bg-bg-surface/80 backdrop-blur-sm border border-border-subtle rounded-sm font-mono text-xs text-accent-teal">
          CAM: {cameraName.toUpperCase()} · 1920x1080 REF FRAME
        </div>

        {/* Drawing Prompt Banner */}
        {isDrawing && (
          <div className="absolute top-3 right-3 z-30 pointer-events-none px-3 py-1 bg-accent-teal/15 border border-accent-teal/40 text-accent-teal rounded-sm font-mono text-xs animate-pulse">
            CLICK TO ADD VERTEX · DOUBLE CLICK TO COMPLETE
          </div>
        )}

        {/* SVG Drawing & Polygon Overlay */}
        <svg
          ref={svgRef}
          viewBox={`0 0 ${VIEW_WIDTH} ${VIEW_HEIGHT}`}
          className={`absolute inset-0 w-full h-full ${
            isDrawing ? 'cursor-crosshair' : 'cursor-default'
          }`}
          onClick={handleCanvasClick}
          onMouseMove={handleMouseMove}
          onDoubleClick={handleDoubleClick}
        >
          {/* 1. Render Existing Configured Zones */}
          {zones.map((zone) => {
            const colors = tierColors[zone.tier];
            const isSelected = selectedZoneId === zone.id;
            const isHovered = hoveredZoneId === zone.id;
            const centroid = getCentroid(zone.points);

            return (
              <g
                key={zone.id}
                className="transition-all duration-150"
                onMouseEnter={() => !isDrawing && setHoveredZoneId(zone.id)}
                onMouseLeave={() => !isDrawing && setHoveredZoneId(null)}
                onClick={(e) => {
                  if (!isDrawing) {
                    e.stopPropagation();
                    onSelectZone(isSelected ? null : zone.id);
                  }
                }}
              >
                {/* Filled Polygon */}
                <polygon
                  points={toSvgPoints(zone.points)}
                  fill={colors.fill}
                  stroke={isSelected || isHovered ? colors.highlight : colors.stroke}
                  strokeWidth={isSelected || isHovered ? 2.5 : 1.5}
                  strokeDasharray={isSelected ? '6 3' : undefined}
                  className="cursor-pointer transition-colors"
                />

                {/* Vertices indicator dots on hover/select */}
                {(isSelected || isHovered) &&
                  zone.points.map((pt, idx) => (
                    <circle
                      key={idx}
                      cx={pt.x * VIEW_WIDTH}
                      cy={pt.y * VIEW_HEIGHT}
                      r={4}
                      fill={colors.highlight}
                      stroke="#0a0f0d"
                      strokeWidth={1.5}
                    />
                  ))}

                {/* Centered Zone Label */}
                <g transform={`translate(${centroid.x}, ${centroid.y})`}>
                  <rect
                    x="-85"
                    y="-14"
                    width="170"
                    height="28"
                    rx="3"
                    fill="#111917"
                    fillOpacity="0.9"
                    stroke={colors.stroke}
                    strokeWidth="1"
                  />
                  <text
                    x="0"
                    y="4"
                    textAnchor="middle"
                    fill="#e6ece9"
                    fontFamily="Inter, sans-serif"
                    fontSize="11"
                    fontWeight="600"
                  >
                    {zone.label.length > 22
                      ? `${zone.label.substring(0, 20)}...`
                      : zone.label}
                  </text>

                  {/* Direction Vector Indicator for Yellow Zones */}
                  {zone.direction && (
                    <text
                      x="0"
                      y="23"
                      textAnchor="middle"
                      fill={colors.stroke}
                      fontFamily="monospace"
                      fontSize="9"
                      fontWeight="bold"
                    >
                      [{zone.direction.toUpperCase()} VECTOR]
                    </text>
                  )}
                </g>
              </g>
            );
          })}

          {/* 2. Render In-Progress Polygon While Drawing */}
          {isDrawing && currentPoints.length > 0 && (
            <g>
              {/* Completed edges so far */}
              <polyline
                points={toSvgPoints(currentPoints)}
                fill="none"
                stroke="#5fd6c4"
                strokeWidth="2"
                strokeDasharray="4 2"
              />

              {/* Dynamic guide line from last vertex to current mouse cursor */}
              {mousePos && (
                <line
                  x1={currentPoints[currentPoints.length - 1].x * VIEW_WIDTH}
                  y1={currentPoints[currentPoints.length - 1].y * VIEW_HEIGHT}
                  x2={mousePos.x * VIEW_WIDTH}
                  y2={mousePos.y * VIEW_HEIGHT}
                  stroke="#5fd6c4"
                  strokeWidth="1.5"
                  strokeDasharray="2 2"
                />
              )}

              {/* Loop closing indicator line if >= 3 points */}
              {mousePos && currentPoints.length >= 3 && (
                <line
                  x1={mousePos.x * VIEW_WIDTH}
                  y1={mousePos.y * VIEW_HEIGHT}
                  x2={currentPoints[0].x * VIEW_WIDTH}
                  y2={currentPoints[0].y * VIEW_HEIGHT}
                  stroke="#5c6f68"
                  strokeWidth="1"
                  strokeDasharray="4 4"
                />
              )}

              {/* Placed Vertex Dots */}
              {currentPoints.map((pt, idx) => (
                <g key={idx}>
                  <circle
                    cx={pt.x * VIEW_WIDTH}
                    cy={pt.y * VIEW_HEIGHT}
                    r={5}
                    fill="#5fd6c4"
                    stroke="#0a0f0d"
                    strokeWidth={2}
                  />
                  <text
                    x={pt.x * VIEW_WIDTH + 8}
                    y={pt.y * VIEW_HEIGHT + 4}
                    fill="#5fd6c4"
                    fontFamily="monospace"
                    fontSize="10"
                    fontWeight="bold"
                  >
                    P{idx + 1}
                  </text>
                </g>
              ))}
            </g>
          )}
        </svg>

        {/* Hover Action Popover near selected/hovered zone */}
        {hoveredZoneId && !isDrawing && (
          <div className="absolute bottom-3 right-3 z-30 flex items-center gap-1.5 p-1.5 bg-bg-surface/95 backdrop-blur-sm border border-border-subtle rounded-sm shadow-xl">
            {(() => {
              const zone = zones.find((z) => z.id === hoveredZoneId);
              if (!zone) return null;
              return (
                <>
                  <span className="font-mono text-xs text-text-dim px-2">
                    {zone.label}
                  </span>
                  <button
                    onClick={() => onEditZone(zone)}
                    title="Edit zone metadata"
                    className="p-1 rounded-sm text-text-muted hover:text-accent-teal hover:bg-bg-elevated transition-colors"
                  >
                    <Pencil className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => onDeleteZone(zone.id)}
                    title="Delete zone"
                    className="p-1 rounded-sm text-text-muted hover:text-accent-red hover:bg-bg-elevated transition-colors"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </>
              );
            })()}
          </div>
        )}
      </div>
    </div>
  );
};

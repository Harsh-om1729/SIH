import React, { useState, useEffect, useMemo } from 'react';
import { Zone, initialMockZones } from '@/lib/mockZones';
import { ZoneCanvas } from '@/components/zones';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { Card } from '@/components/ui/Card';
import {
  Shield,
  ShieldAlert,
  Compass,
  Trash2,
  Pencil,
  Save,
  CheckCircle2,
  AlertTriangle,
  Layers,
  ArrowDownRight,
  ArrowUpRight,
  RotateCcw,
  Zap,
  Clock,
  Activity,
} from 'lucide-react';

const ZONES_STORAGE_KEY = 'ibvap_zones_data';

const loadStoredZones = (): Zone[] => {
  try {
    const saved = localStorage.getItem(ZONES_STORAGE_KEY);
    if (saved) {
      const parsed = JSON.parse(saved);
      if (Array.isArray(parsed) && parsed.length > 0) {
        return parsed;
      }
    }
  } catch (e) {
    console.error('Failed to load zones from storage', e);
  }
  return initialMockZones;
};

export const ZonesPage: React.FC = () => {
  const [allZones, setAllZones] = useState<Zone[]>(loadStoredZones);
  const [selectedCamera, setSelectedCamera] = useState<string>('cam0');
  const [selectedZoneId, setSelectedZoneId] = useState<string | null>(null);
  const [isDrawing, setIsDrawing] = useState(false);

  // Automatically persist zones across routes and browser sessions
  useEffect(() => {
    try {
      localStorage.setItem(ZONES_STORAGE_KEY, JSON.stringify(allZones));
    } catch (e) {
      console.error('Failed to persist zones to storage', e);
    }
  }, [allZones]);

  // Form Modal State (for Creating or Editing Zone Metadata)
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editingZone, setEditingZone] = useState<Zone | null>(null);
  const [inProgressPoints, setInProgressPoints] = useState<{ x: number; y: number }[]>([]);

  // Form Fields
  const [formTier, setFormTier] = useState<'green' | 'yellow' | 'red'>('red');
  const [formLabel, setFormLabel] = useState('');
  const [formDirection, setFormDirection] = useState<'inward' | 'outward'>('inward');
  const [formTripwire, setFormTripwire] = useState(false);
  const [formLoitering, setFormLoitering] = useState<number>(0);
  const [formClimbing, setFormClimbing] = useState(false);
  const [tripwireBreachCount, setTripwireBreachCount] = useState(0);
  const [formError, setFormError] = useState('');

  // Confirmation & Toast Feedback
  const [isClearModalOpen, setIsClearModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [zoneToDeleteId, setZoneToDeleteId] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  // Zones belonging to current camera
  const cameraZones = allZones.filter((z) => z.cameraName === selectedCamera);

  // Finished polygon drawing callback -> opens metadata modal
  const handleFinishDrawing = (points: { x: number; y: number }[]) => {
    setIsDrawing(false);
    setInProgressPoints(points);
    setEditingZone(null);
    setFormTier('red');
    setFormLabel(`Priority Zone ${cameraZones.length + 1}`);
    setFormDirection('inward');
    setFormTripwire(false);
    setFormLoitering(0);
    setFormClimbing(false);
    setFormError('');
    setIsFormOpen(true);
  };

  // Open Edit Metadata Modal
  const handleOpenEditZone = (zone: Zone) => {
    setEditingZone(zone);
    setFormTier(zone.tier);
    setFormLabel(zone.label);
    setFormDirection(zone.direction || 'inward');
    setFormTripwire(zone.tripwireEnabled ?? false);
    setFormLoitering(zone.loiteringThresholdSeconds ?? 0);
    setFormClimbing(zone.climbingDetection ?? false);
    setFormError('');
    setIsFormOpen(true);
  };

  // Save Zone Form (Add or Edit)
  const handleSaveZoneForm = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formLabel.trim()) {
      setFormError('Zone label is required');
      return;
    }

    if (editingZone) {
      // Update existing zone metadata
      const updated = allZones.map((z) => {
        if (z.id === editingZone.id) {
          return {
            ...z,
            tier: formTier,
            label: formLabel.trim(),
            direction: formTier === 'yellow' ? formDirection : undefined,
            tripwireEnabled: formTripwire,
            loiteringThresholdSeconds: formLoitering > 0 ? formLoitering : undefined,
            climbingDetection: formClimbing,
          };
        }
        return z;
      });
      setAllZones(updated);
      showToast(`Zone "${formLabel}" updated successfully`);
    } else {
      // Create new zone from inProgressPoints
      const newZone: Zone = {
        id: `zone-${selectedCamera}-${Date.now()}`,
        cameraName: selectedCamera,
        tier: formTier,
        label: formLabel.trim(),
        points: inProgressPoints,
        direction: formTier === 'yellow' ? formDirection : undefined,
        tripwireEnabled: formTripwire,
        loiteringThresholdSeconds: formLoitering > 0 ? formLoitering : undefined,
        climbingDetection: formClimbing,
      };
      setAllZones((prev) => [...prev, newZone]);
      setSelectedZoneId(newZone.id);
      showToast(`New ${formTier.toUpperCase()} zone registered on ${selectedCamera.toUpperCase()}`);
    }

    setIsFormOpen(false);
    setInProgressPoints([]);
    setEditingZone(null);
  };

  // Delete single zone confirmation
  const handlePromptDeleteZone = (id: string) => {
    setZoneToDeleteId(id);
    setIsDeleteModalOpen(true);
  };

  const handleConfirmDelete = () => {
    if (zoneToDeleteId) {
      setAllZones((prev) => prev.filter((z) => z.id !== zoneToDeleteId));
      if (selectedZoneId === zoneToDeleteId) setSelectedZoneId(null);
      showToast('Zone removed from camera profile');
    }
    setIsDeleteModalOpen(false);
    setZoneToDeleteId(null);
  };

  // Clear all zones for current camera
  const handleConfirmClearAll = () => {
    setAllZones((prev) => prev.filter((z) => z.cameraName !== selectedCamera));
    setSelectedZoneId(null);
    setIsClearModalOpen(false);
    showToast(`All zones cleared for ${selectedCamera.toUpperCase()}`);
  };

  const handleSaveZonesProfile = () => {
    try {
      localStorage.setItem(ZONES_STORAGE_KEY, JSON.stringify(allZones));
    } catch (e) {
      console.error(e);
    }
    showToast('Zones saved to tactical storage — persists across navigation');
  };

  const handleResetDefaults = () => {
    setAllZones(initialMockZones);
    setSelectedZoneId(null);
    setIsClearModalOpen(false);
    try {
      localStorage.setItem(ZONES_STORAGE_KEY, JSON.stringify(initialMockZones));
    } catch (e) {
      console.error(e);
    }
    showToast('Zones restored to default factory layout');
  };

  const availableCameras = useMemo(() => {
    const baseCams = ['cam0', 'cam1', 'cam2', 'cam3'];
    const zoneCams = allZones.map((z) => z.cameraName);
    let registeredCams: string[] = [];
    try {
      const storedCams = localStorage.getItem('ibvap_cameras_data');
      if (storedCams) {
        const parsed = JSON.parse(storedCams);
        if (Array.isArray(parsed)) {
          registeredCams = parsed.map((c: { id: string }) => c.id);
        }
      }
    } catch {
      // ignore
    }
    const combined = Array.from(new Set([...baseCams, ...zoneCams, ...registeredCams]));
    return combined.sort();
  }, [allZones]);

  return (
    <div className="space-y-5">
      {/* Toast Feedback */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 flex items-center gap-2 px-4 py-2.5 bg-bg-surface border border-accent-teal/50 rounded-sm shadow-2xl font-mono text-xs text-text-primary animate-in fade-in slide-in-from-bottom-2">
          <CheckCircle2 className="w-4 h-4 text-accent-teal" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Top Toolbar: Camera Selector & Global Zone Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3.5 bg-bg-surface border border-border-subtle rounded-sm">
        {/* Camera Selector Tabs */}
        <div className="flex items-center gap-2 overflow-x-auto pb-1 sm:pb-0">
          <span className="font-mono text-xs text-text-dim uppercase tracking-wider shrink-0 mr-1">
            Active Camera:
          </span>
          {availableCameras.map((cam) => {
            const count = allZones.filter((z) => z.cameraName === cam).length;
            const isSelected = selectedCamera === cam;
            return (
              <button
                key={cam}
                onClick={() => {
                  setSelectedCamera(cam);
                  setSelectedZoneId(null);
                  setIsDrawing(false);
                }}
                className={`px-3 py-1.5 text-xs font-mono rounded-sm transition-all flex items-center gap-2 border shrink-0 ${
                  isSelected
                    ? 'bg-accent-teal/20 text-accent-teal border-accent-teal/50 font-semibold shadow-sm'
                    : 'bg-bg-elevated text-text-dim border-border-subtle hover:text-text-primary'
                }`}
              >
                <span className="w-1.5 h-1.5 rounded-full bg-accent-green" />
                <span>{cam.toUpperCase()}</span>
                <span className="text-[10px] text-text-muted">({count})</span>
              </button>
            );
          })}
        </div>

        {/* Global Action Buttons */}
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            disabled={cameraZones.length === 0}
            leftIcon={<Trash2 className="w-3.5 h-3.5 text-accent-red" />}
            onClick={() => setIsClearModalOpen(true)}
          >
            Clear Zones
          </Button>

          <Button
            variant="primary"
            size="sm"
            leftIcon={<Save className="w-3.5 h-3.5" />}
            onClick={handleSaveZonesProfile}
          >
            Save Zones
          </Button>
        </div>
      </div>

      {/* Main 2-Column Command Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Interactive Polygon Canvas Editor (8 Cols) */}
        <div className="lg:col-span-8 space-y-4">
          <ZoneCanvas
            cameraName={selectedCamera}
            zones={cameraZones}
            selectedZoneId={selectedZoneId}
            onSelectZone={setSelectedZoneId}
            onEditZone={handleOpenEditZone}
            onDeleteZone={handlePromptDeleteZone}
            isDrawing={isDrawing}
            onStartDrawing={() => setIsDrawing(true)}
            onCancelDrawing={() => setIsDrawing(false)}
            onFinishDrawing={handleFinishDrawing}
          />
        </div>

        {/* Right Column: Zone List Panel & Tier Rules Legend (4 Cols) */}
        <div className="lg:col-span-4 space-y-5">
          {/* Active Camera Zones List Panel */}
          <Card
            title={
              <div className="flex items-center justify-between w-full">
                <span className="font-semibold text-sm">Configured Zones</span>
                <Badge variant="teal" size="sm">
                  {cameraZones.length} ACTIVE
                </Badge>
              </div>
            }
            subtitle={`Defined perimeter boundaries for ${selectedCamera.toUpperCase()}`}
            variant="default"
          >
            <div className="space-y-2.5 max-h-[340px] overflow-y-auto pr-1">
              {cameraZones.length > 0 ? (
                cameraZones.map((zone) => {
                  const isSelected = selectedZoneId === zone.id;
                  const borderTierColor =
                    zone.tier === 'red'
                      ? 'border-l-accent-red'
                      : zone.tier === 'yellow'
                      ? 'border-l-accent-yellow'
                      : 'border-l-accent-green';

                  return (
                    <div
                      key={zone.id}
                      onClick={() =>
                        setSelectedZoneId(isSelected ? null : zone.id)
                      }
                      className={`p-3 rounded-sm border bg-bg-surface hover:bg-bg-elevated/70 transition-all cursor-pointer border-l-4 ${borderTierColor} ${
                        isSelected
                          ? 'border-accent-teal/50 ring-1 ring-accent-teal/40 bg-bg-elevated'
                          : 'border-border-subtle'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <Badge variant={zone.tier} size="sm">
                          {zone.tier} TIER
                        </Badge>
                        <div className="flex items-center gap-1">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleOpenEditZone(zone);
                            }}
                            title="Edit metadata"
                            className="p-1 rounded-sm text-text-muted hover:text-accent-teal hover:bg-bg-surface transition-colors"
                          >
                            <Pencil className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handlePromptDeleteZone(zone.id);
                            }}
                            title="Delete zone"
                            className="p-1 rounded-sm text-text-muted hover:text-accent-red hover:bg-bg-surface transition-colors"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>

                      <div className="font-semibold text-xs text-text-primary tracking-wide">
                        {zone.label}
                      </div>

                      <div className="flex items-center justify-between font-mono text-[11px] text-text-dim mt-2 pt-1.5 border-t border-border-subtle/50">
                        <span>{zone.points.length} vertices</span>
                        {zone.direction && (
                          <span className="text-accent-yellow font-semibold flex items-center gap-1">
                            <Compass className="w-3 h-3" />
                            {zone.direction.toUpperCase()} VECTOR
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })
              ) : (
                <div className="p-6 border border-dashed border-border-subtle rounded-sm text-center">
                  <Layers className="w-6 h-6 text-text-muted mx-auto mb-2" />
                  <span className="font-mono text-xs text-text-dim block">
                    No Zones Configured
                  </span>
                  <span className="text-[11px] text-text-muted block mt-1">
                    Click "Draw New Zone" above to define an alert polygon.
                  </span>
                </div>
              )}
            </div>
          </Card>

          {/* Operational Tier Rule Legend */}
          <Card
            title="Border Tier Rules & Logic"
            subtitle="Autonomous threat scoring behavior"
            variant="default"
          >
            <div className="space-y-2.5 font-mono text-xs">
              <div className="p-2.5 bg-accent-red/10 border border-accent-red/30 rounded-sm space-y-1">
                <div className="flex items-center gap-1.5 text-accent-red font-bold">
                  <ShieldAlert className="w-3.5 h-3.5" />
                  <span>RED ZONE (CRITICAL TIER 1)</span>
                </div>
                <p className="text-[11px] font-sans text-text-dim leading-relaxed">
                  Zero-tolerance intrusion perimeter. Any movement instantly triggers continuous alarms, snapshot bursts, and intercept dispatch.
                </p>
              </div>

              <div className="p-2.5 bg-accent-yellow/10 border border-accent-yellow/30 rounded-sm space-y-1">
                <div className="flex items-center gap-1.5 text-accent-yellow font-bold">
                  <Compass className="w-3.5 h-3.5" />
                  <span>YELLOW ZONE (CAUTION TIER 2)</span>
                </div>
                <p className="text-[11px] font-sans text-text-dim leading-relaxed">
                  Direction-sensitive buffer zone. Evaluates trajectory kinematics: <strong>Inward</strong> breaches trigger caution alerts; outward movements remain logged.
                </p>
              </div>

              <div className="p-2.5 bg-accent-green/10 border border-accent-green/30 rounded-sm space-y-1">
                <div className="flex items-center gap-1.5 text-accent-green font-bold">
                  <Shield className="w-3.5 h-3.5" />
                  <span>GREEN ZONE (NORMAL TIER 3)</span>
                </div>
                <p className="text-[11px] font-sans text-text-dim leading-relaxed">
                  Authorized access corridors. Silently logs telemetry during daylight, automatically re-tiered to <strong>Yellow</strong> during curfew hours (21:00–05:00).
                </p>
              </div>
            </div>
          </Card>

          {/* Section 20 Roadmap: Behaviour Anomaly Detection & Virtual Tripwires */}
          <Card
            title={
              <div className="flex items-center justify-between w-full">
                <span className="font-semibold text-sm flex items-center gap-1.5">
                  <Zap className="w-4 h-4 text-accent-teal" />
                  <span>Behaviour Anomaly Engine</span>
                </span>
                <Badge variant="teal" size="sm">
                  SEC 20 ROADMAP
                </Badge>
              </div>
            }
            subtitle="Kinematic behaviour analysis & virtual tripwire beams"
            variant="default"
          >
            <div className="space-y-3 font-mono text-xs">
              <div className="p-2.5 rounded bg-bg-surface border border-border-subtle space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-text-primary font-bold flex items-center gap-1.5">
                    <Zap className="w-3.5 h-3.5 text-accent-red" /> Virtual Tripwire Beam
                  </span>
                  <Badge variant={tripwireBreachCount > 0 ? 'red' : 'green'} size="sm">
                    {tripwireBreachCount > 0 ? `${tripwireBreachCount} BREACHES` : 'ARMED / SECURE'}
                  </Badge>
                </div>
                <p className="text-[11px] font-sans text-text-dim">
                  Zero-tolerance crossing threshold across perimeter fence line.
                </p>
                <div className="pt-1 flex items-center justify-between">
                  <button
                    onClick={() => {
                      setTripwireBreachCount((c) => c + 1);
                      showToast('⚠ Virtual Tripwire Beam Breached! Alarm Escalated to Red.');
                    }}
                    className="px-2 py-1 text-[11px] rounded bg-accent-red/15 hover:bg-accent-red/25 border border-accent-red/30 text-accent-red font-semibold transition-colors"
                  >
                    Simulate Beam Breach
                  </button>
                  {tripwireBreachCount > 0 && (
                    <button
                      onClick={() => setTripwireBreachCount(0)}
                      className="text-[10px] text-text-muted hover:text-text-primary underline"
                    >
                      Reset Counter
                    </button>
                  )}
                </div>
              </div>

              <div className="p-2.5 rounded bg-bg-surface border border-border-subtle space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-text-primary font-bold flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5 text-accent-yellow" /> Loitering Watchdog
                  </span>
                  <Badge variant="yellow" size="sm">45s DWELL LIMIT</Badge>
                </div>
                <p className="text-[11px] font-sans text-text-dim">
                  Dwell time tracker flags stationary targets remaining in buffer zone without crossing.
                </p>
              </div>

              <div className="p-2.5 rounded bg-bg-surface border border-border-subtle space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-text-primary font-bold flex items-center gap-1.5">
                    <Activity className="w-3.5 h-3.5 text-accent-purple" /> Fence Climbing Detector
                  </span>
                  <Badge variant="purple" size="sm">ASPECT RATIO ON</Badge>
                </div>
                <p className="text-[11px] font-sans text-text-dim">
                  Monitors vertical bounding-box elongation & elevation shifts over fence barrier.
                </p>
              </div>
            </div>
          </Card>
        </div>
      </div>

      {/* ZONE CONFIGURATION MODAL (FOR NEW OR EDIT) */}
      <Modal
        isOpen={isFormOpen}
        onClose={() => {
          setIsFormOpen(false);
          setInProgressPoints([]);
          setEditingZone(null);
        }}
        title={editingZone ? 'Edit Zone Configuration' : 'Configure New Priority Zone'}
        description={`Set detection tier, label, and directional sensitivity for ${selectedCamera.toUpperCase()}`}
        size="md"
        footer={
          <>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setIsFormOpen(false);
                setInProgressPoints([]);
                setEditingZone(null);
              }}
            >
              Cancel
            </Button>
            <Button variant="primary" size="sm" onClick={handleSaveZoneForm}>
              {editingZone ? 'Save Changes' : 'Confirm & Create Zone'}
            </Button>
          </>
        }
      >
        <form onSubmit={handleSaveZoneForm} className="space-y-4">
          {formError && (
            <div className="p-2 bg-accent-red/15 border border-accent-red/40 text-accent-red rounded-sm text-xs font-mono">
              {formError}
            </div>
          )}

          {/* Tier Selection Radio Tiles */}
          <div>
            <label className="block text-xs font-mono uppercase text-text-dim mb-2">
              Zone Priority Tier:
            </label>
            <div className="grid grid-cols-3 gap-2.5">
              {/* Red Tier */}
              <label
                className={`flex flex-col p-3 rounded-sm border cursor-pointer transition-all ${
                  formTier === 'red'
                    ? 'bg-accent-red/15 border-accent-red ring-1 ring-accent-red'
                    : 'bg-bg-elevated border-border-subtle hover:border-accent-red/40'
                }`}
              >
                <input
                  type="radio"
                  name="tier"
                  value="red"
                  checked={formTier === 'red'}
                  onChange={() => setFormTier('red')}
                  className="sr-only"
                />
                <span className="w-2.5 h-2.5 rounded-full bg-accent-red mb-1" />
                <span className="font-mono text-xs font-bold text-accent-red">RED</span>
                <span className="text-[10px] text-text-dim">Critical Breach</span>
              </label>

              {/* Yellow Tier */}
              <label
                className={`flex flex-col p-3 rounded-sm border cursor-pointer transition-all ${
                  formTier === 'yellow'
                    ? 'bg-accent-yellow/15 border-accent-yellow ring-1 ring-accent-yellow'
                    : 'bg-bg-elevated border-border-subtle hover:border-accent-yellow/40'
                }`}
              >
                <input
                  type="radio"
                  name="tier"
                  value="yellow"
                  checked={formTier === 'yellow'}
                  onChange={() => setFormTier('yellow')}
                  className="sr-only"
                />
                <span className="w-2.5 h-2.5 rounded-full bg-accent-yellow mb-1" />
                <span className="font-mono text-xs font-bold text-accent-yellow">YELLOW</span>
                <span className="text-[10px] text-text-dim">Direction Caution</span>
              </label>

              {/* Green Tier */}
              <label
                className={`flex flex-col p-3 rounded-sm border cursor-pointer transition-all ${
                  formTier === 'green'
                    ? 'bg-accent-green/15 border-accent-green ring-1 ring-accent-green'
                    : 'bg-bg-elevated border-border-subtle hover:border-accent-green/40'
                }`}
              >
                <input
                  type="radio"
                  name="tier"
                  value="green"
                  checked={formTier === 'green'}
                  onChange={() => setFormTier('green')}
                  className="sr-only"
                />
                <span className="w-2.5 h-2.5 rounded-full bg-accent-green mb-1" />
                <span className="font-mono text-xs font-bold text-accent-green">GREEN</span>
                <span className="text-[10px] text-text-dim">Normal / Curfew</span>
              </label>
            </div>
          </div>

          {/* Zone Label Input */}
          <div>
            <label className="block text-xs font-mono uppercase text-text-dim mb-1">
              Zone Identifier / Description Label <span className="text-accent-red">*</span>
            </label>
            <input
              type="text"
              value={formLabel}
              onChange={(e) => setFormLabel(e.target.value)}
              placeholder="e.g. North Barrier Line, Outpost Vehicle Bay"
              className="w-full px-3 py-2 bg-bg-elevated border border-border-subtle rounded-sm text-sm text-text-primary focus:outline-none focus:border-accent-teal"
            />
          </div>

          {/* Direction Toggle (Active only for Yellow zones) */}
          {formTier === 'yellow' && (
            <div className="p-3 bg-bg-elevated border border-accent-yellow/30 rounded-sm space-y-2">
              <div className="flex items-center gap-2 text-xs font-mono text-accent-yellow font-semibold">
                <Compass className="w-4 h-4" />
                <span>DIRECTION KINEMATICS SENSITIVITY</span>
              </div>
              <p className="text-[11px] text-text-dim">
                Yellow zones trigger alerts depending on breach vector trajectory:
              </p>
              <div className="grid grid-cols-2 gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => setFormDirection('inward')}
                  className={`px-3 py-2 rounded-sm border text-xs font-mono flex items-center justify-center gap-1.5 ${
                    formDirection === 'inward'
                      ? 'bg-accent-yellow/20 text-accent-yellow border-accent-yellow font-bold'
                      : 'bg-bg-surface text-text-dim border-border-subtle hover:text-text-primary'
                  }`}
                >
                  <ArrowDownRight className="w-3.5 h-3.5" />
                  <span>INWARD VECTOR</span>
                </button>
                <button
                  type="button"
                  onClick={() => setFormDirection('outward')}
                  className={`px-3 py-2 rounded-sm border text-xs font-mono flex items-center justify-center gap-1.5 ${
                    formDirection === 'outward'
                      ? 'bg-accent-yellow/20 text-accent-yellow border-accent-yellow font-bold'
                      : 'bg-bg-surface text-text-dim border-border-subtle hover:text-text-primary'
                  }`}
                >
                  <ArrowUpRight className="w-3.5 h-3.5" />
                  <span>OUTWARD VECTOR</span>
                </button>
              </div>
            </div>
          )}

          {/* Behaviour Anomaly Configuration (Section 20 Roadmap) */}
          <div className="p-3 bg-bg-elevated border border-border-subtle rounded-sm space-y-3 font-mono text-xs">
            <span className="font-bold text-text-primary uppercase tracking-wider block">
              Advanced Behaviour Triggers (Section 20)
            </span>
            <div className="space-y-2 text-[11px]">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formTripwire}
                  onChange={(e) => setFormTripwire(e.target.checked)}
                  className="w-3.5 h-3.5 accent-accent-teal rounded"
                />
                <span className="text-text-primary font-medium">Virtual Tripwire Beam</span>
                <span className="text-text-muted">(Instant escalation upon crossing)</span>
              </label>

              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formClimbing}
                  onChange={(e) => setFormClimbing(e.target.checked)}
                  className="w-3.5 h-3.5 accent-accent-teal rounded"
                />
                <span className="text-text-primary font-medium">Fence Climbing Anomaly</span>
                <span className="text-text-muted">(Monitors vertical bbox shift)</span>
              </label>

              <div className="space-y-1 pt-1">
                <div className="flex items-center justify-between text-text-dim">
                  <span>Loitering Dwell Limit:</span>
                  <span className="text-accent-yellow font-bold">
                    {formLoitering > 0 ? `${formLoitering}s` : 'Disabled'}
                  </span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="120"
                  step="15"
                  value={formLoitering}
                  onChange={(e) => setFormLoitering(Number(e.target.value))}
                  className="w-full accent-accent-yellow cursor-pointer"
                />
                <div className="flex justify-between text-[9px] text-text-muted">
                  <span>0 (Off)</span>
                  <span>45s (Standard)</span>
                  <span>120s (Extended)</span>
                </div>
              </div>
            </div>
          </div>
        </form>
      </Modal>

      {/* DELETE SINGLE ZONE CONFIRMATION MODAL */}
      <Modal
        isOpen={isDeleteModalOpen}
        onClose={() => setIsDeleteModalOpen(false)}
        title="Delete Virtual Zone"
        description="Are you sure you want to delete this zone from the camera profile?"
        size="sm"
        footer={
          <>
            <Button variant="ghost" size="sm" onClick={() => setIsDeleteModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="danger" size="sm" onClick={handleConfirmDelete}>
              Confirm Delete
            </Button>
          </>
        }
      >
        <p className="text-xs text-text-dim">
          This will remove the polygon detection rules for this sector. The AI pipeline will no longer evaluate threat scores for this specific zone.
        </p>
      </Modal>

      {/* CLEAR ALL ZONES CONFIRMATION MODAL */}
      <Modal
        isOpen={isClearModalOpen}
        onClose={() => setIsClearModalOpen(false)}
        title={`Clear All Zones on ${selectedCamera.toUpperCase()}`}
        description="Are you sure you want to remove all configured polygon zones for this camera?"
        size="sm"
        footer={
          <div className="flex items-center justify-between w-full">
            <Button
              variant="ghost"
              size="sm"
              leftIcon={<RotateCcw className="w-3.5 h-3.5 text-accent-teal" />}
              onClick={handleResetDefaults}
            >
              Reset to Defaults
            </Button>
            <div className="flex items-center gap-2">
              <Button variant="ghost" size="sm" onClick={() => setIsClearModalOpen(false)}>
                Cancel
              </Button>
              <Button variant="danger" size="sm" onClick={handleConfirmClearAll}>
                Clear All Zones
              </Button>
            </div>
          </div>
        }
      >
        <div className="p-3 bg-accent-red/10 border border-accent-red/30 rounded-sm text-xs text-text-primary flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 text-accent-red shrink-0 mt-0.5" />
          <span>
            This action will delete all {cameraZones.length} zones defined on {selectedCamera.toUpperCase()}. You will need to redraw or reload them.
          </span>
        </div>
      </Modal>
    </div>
  );
};

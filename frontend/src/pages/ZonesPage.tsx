import React, { useState, useEffect, useMemo } from 'react';
import { Zone, initialMockZones } from '@/lib/mockZones';
import { zonesApi } from '@/lib/api';
import { DataSourceBadge } from '@/components/ui/DataSourceBadge';
import { ZONE_PRESETS, ZonePreset } from '@/lib/zonePresets';
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
  Copy,
  Sparkles,
  ChevronDown,
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
  const [isMock, setIsMock] = useState(true);
  const [saveError, setSaveError] = useState<string | null>(null);
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

  // Pull the zones the backend actually has. config/zones_<cam>.json is what
  // ZoneEngine reads at pipeline startup, so it — not localStorage — is the
  // real store. localStorage stays only as the offline seed.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const res = await zonesApi.getZones({});
      if (cancelled) return;
      setIsMock(res.isFallback);
      if (res.isFallback || !res.data) return;
      const flat = Object.values(res.data).flat() as Zone[];
      setAllZones(flat);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Form Modal State (for Creating or Editing Zone Metadata)
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editingZone, setEditingZone] = useState<Zone | null>(null);
  const [inProgressPoints, setInProgressPoints] = useState<{ x: number; y: number }[]>([]);

  // Form Fields
  const [formTier, setFormTier] = useState<'green' | 'yellow' | 'red'>('red');
  const [formLabel, setFormLabel] = useState('');
  const [formDirection, setFormDirection] = useState<'inward' | 'outward'>('inward');
  const [formError, setFormError] = useState('');

  // Confirmation & Toast Feedback
  const [isClearModalOpen, setIsClearModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [zoneToDeleteId, setZoneToDeleteId] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Quick Presets & Clone State
  const [isPresetMenuOpen, setIsPresetMenuOpen] = useState(false);
  const [isCloneModalOpen, setIsCloneModalOpen] = useState(false);
  const [selectedCloneTargets, setSelectedCloneTargets] = useState<string[]>([]);
  const [cloneOverwrite, setCloneOverwrite] = useState(true);

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
    setFormError('');
    setIsFormOpen(true);
  };

  // Open Edit Metadata Modal
  const handleOpenEditZone = (zone: Zone) => {
    setEditingZone(zone);
    setFormTier(zone.tier);
    setFormLabel(zone.label);
    setFormDirection(zone.direction || 'inward');
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

  const handleSaveZonesProfile = async () => {
    try {
      localStorage.setItem(ZONES_STORAGE_KEY, JSON.stringify(allZones));
    } catch (e) {
      console.error(e);
    }

    // The API groups zones per camera and writes config/zones_<cam>.json in
    // ZoneEngine's own format. Saving only to localStorage (as this did) left
    // the pipeline with no zones at all, so no sector/direction/loiter risk
    // was ever scored and a RED tier could not be reached.
    const grouped: Record<string, Zone[]> = {};
    for (const cam of availableCameras) grouped[cam] = [];
    for (const z of allZones) {
      (grouped[z.cameraName] ||= []).push(z);
    }

    const res = await zonesApi.saveZones(grouped);
    if (res.isFallback) {
      setSaveError(res.error);
      showToast('Saved locally only — backend unreachable, pipeline will NOT see these zones');
      return;
    }
    setSaveError(null);
    setIsMock(false);
    showToast('Zones written to the backend — restart the pipeline to apply them');
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

  // Other cameras that currently have at least 1 zone configured
  const otherCamerasWithZones = useMemo(() => {
    return availableCameras.filter(
      (cam) => cam !== selectedCamera && allZones.some((z) => z.cameraName === cam)
    );
  }, [availableCameras, selectedCamera, allZones]);

  // 1-Click Zone Preset Application
  const handleApplyPreset = (preset: ZonePreset, overwrite: boolean = true) => {
    const newZones = preset.createZones(selectedCamera);
    setAllZones((prev) => {
      const filtered = overwrite ? prev.filter((z) => z.cameraName !== selectedCamera) : prev;
      return [...filtered, ...newZones];
    });
    setSelectedZoneId(newZones[0]?.id || null);
    setIsPresetMenuOpen(false);
    showToast(`Applied "${preset.name}" preset to ${selectedCamera.toUpperCase()} (${newZones.length} zones active)`);
  };

  // Open Clone Modal
  const handleOpenCloneModal = () => {
    const others = availableCameras.filter((c) => c !== selectedCamera);
    setSelectedCloneTargets(others);
    setIsCloneModalOpen(true);
  };

  // Execute Bulk Camera Cloning
  const handleConfirmClone = () => {
    if (cameraZones.length === 0) {
      showToast('No zones on active camera to clone');
      return;
    }
    if (selectedCloneTargets.length === 0) {
      showToast('Select at least one destination camera');
      return;
    }

    const clonedZones: Zone[] = [];
    selectedCloneTargets.forEach((targetCam) => {
      cameraZones.forEach((sourceZone, idx) => {
        clonedZones.push({
          ...sourceZone,
          id: `zone-${targetCam}-${Date.now()}-${idx}`,
          cameraName: targetCam,
          points: sourceZone.points.map((p) => ({ ...p })),
        });
      });
    });

    setAllZones((prev) => {
      let filtered = prev;
      if (cloneOverwrite) {
        filtered = prev.filter((z) => !selectedCloneTargets.includes(z.cameraName));
      }
      return [...filtered, ...clonedZones];
    });

    setIsCloneModalOpen(false);
    showToast(`Cloned ${cameraZones.length} zones to ${selectedCloneTargets.length} camera(s) (${selectedCloneTargets.map((c) => c.toUpperCase()).join(', ')})`);
  };

  // Copy zones from a specific reference camera into active camera
  const handleCopyFromCamera = (sourceCamera: string) => {
    const sourceZones = allZones.filter((z) => z.cameraName === sourceCamera);
    if (sourceZones.length === 0) {
      showToast(`No zones found on ${sourceCamera.toUpperCase()}`);
      return;
    }
    const cloned = sourceZones.map((z, idx) => ({
      ...z,
      id: `zone-${selectedCamera}-${Date.now()}-${idx}`,
      cameraName: selectedCamera,
      points: z.points.map((p) => ({ ...p })),
    }));
    setAllZones((prev) => {
      const filtered = prev.filter((z) => z.cameraName !== selectedCamera);
      return [...filtered, ...cloned];
    });
    setSelectedZoneId(cloned[0]?.id || null);
    showToast(`Copied ${cloned.length} zones from ${sourceCamera.toUpperCase()} to ${selectedCamera.toUpperCase()}`);
  };

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
      <div className="card-3d flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 bg-gradient-to-b from-[#0c0c14] to-[#06060a] border border-white/10 rounded-2xl shadow-[0_15px_35px_rgba(0,0,0,0.8)]">
        {/* Camera Selector Tabs */}
        <div className="flex items-center gap-2 overflow-x-auto pb-1 sm:pb-0">
          <span className="font-mono text-xs font-semibold text-text-dim uppercase tracking-wider shrink-0 mr-1">
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
                className={`px-3.5 py-1.5 text-xs font-mono rounded-xl transition-all flex items-center gap-2 border shrink-0 ${
                  isSelected
                    ? 'bg-accent-teal/20 text-accent-teal border-accent-teal/50 font-bold shadow-[0_0_12px_rgba(0,240,255,0.25)]'
                    : 'bg-black/60 text-text-dim border-white/10 hover:text-white hover:border-white/20'
                }`}
              >
                <span className="w-1.5 h-1.5 rounded-full bg-accent-green shadow-[0_0_6px_#00ff88]" />
                <span>{cam.toUpperCase()}</span>
                <span className="text-[10px] text-text-muted">({count})</span>
              </button>
            );
          })}
        </div>

        {/* Global Action Buttons */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* Quick Presets Dropdown */}
          <div className="relative">
            <Button
              variant="secondary"
              size="sm"
              leftIcon={<Sparkles className="w-3.5 h-3.5 text-accent-teal" />}
              rightIcon={<ChevronDown className="w-3 h-3 text-text-muted" />}
              onClick={() => setIsPresetMenuOpen((prev) => !prev)}
            >
              Presets
            </Button>

            {isPresetMenuOpen && (
              <>
                <div
                  className="fixed inset-0 z-40"
                  onClick={() => setIsPresetMenuOpen(false)}
                />
                <div className="absolute right-0 mt-1.5 w-72 bg-[#080c14] border border-white/15 rounded-xl shadow-2xl p-2 z-50 space-y-1 font-mono text-xs backdrop-blur-xl animate-in fade-in zoom-in-95 duration-150">
                  <div className="px-2.5 py-1.5 text-[10px] text-text-muted uppercase font-bold border-b border-white/10 flex items-center justify-between">
                    <span>1-Click Zone Presets</span>
                    <span className="text-accent-teal">AUTO-TIER</span>
                  </div>
                  {ZONE_PRESETS.map((preset) => (
                    <button
                      key={preset.id}
                      onClick={() => handleApplyPreset(preset, true)}
                      className="w-full p-2.5 rounded-lg hover:bg-white/[0.06] text-left transition-colors flex flex-col gap-0.5 group"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-white font-bold group-hover:text-accent-teal transition-colors">
                          {preset.name}
                        </span>
                        <span className="text-[9px] px-1.5 py-0.2 rounded bg-accent-teal/15 text-accent-teal font-semibold">
                          {preset.badge}
                        </span>
                      </div>
                      <span className="text-[11px] font-sans text-text-dim leading-snug">
                        {preset.description}
                      </span>
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>

          {/* Clone to Cameras */}
          <Button
            variant="secondary"
            size="sm"
            disabled={cameraZones.length === 0}
            leftIcon={<Copy className="w-3.5 h-3.5 text-accent-yellow" />}
            onClick={handleOpenCloneModal}
            title={cameraZones.length === 0 ? 'Configure at least one zone to clone' : 'Clone zones to other cameras'}
          >
            Clone to Cameras...
          </Button>

          {/* Clear Zones */}
          <Button
            variant="secondary"
            size="sm"
            disabled={cameraZones.length === 0}
            leftIcon={<Trash2 className="w-3.5 h-3.5 text-accent-red" />}
            onClick={() => setIsClearModalOpen(true)}
          >
            Clear Zones
          </Button>

          {/* Save Zones */}
          <Button
            variant="primary"
            size="sm"
            leftIcon={<Save className="w-3.5 h-3.5" />}
            onClick={handleSaveZonesProfile}
          >
            Save Zones
          </Button>

          <DataSourceBadge isMock={isMock} error={saveError} />
        </div>
      </div>

      {/* Zones live in config/zones_<cam>.json, which the pipeline reads once
          at startup — there is no live reload channel, so say so rather than
          letting a saved zone look immediately active. */}
      {!isMock && (
        <p className="text-[11px] font-mono text-text-dim">
          Saved zones apply on the next pipeline start (./run.sh).
        </p>
      )}

      {/* Main 2-Column Command Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Interactive Polygon Canvas Editor & Aligned Tier Rules (8 Cols) */}
        <div className="lg:col-span-8 space-y-5">
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

          {/* Operational Tier Rule Legend - Perfectly aligned with the Map Canvas */}
          <Card
            title="Border Tier Rules & Logic"
            subtitle="Autonomous perimeter threat scoring behavior & boundary classifications"
            variant="default"
          >
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5 font-mono text-xs">
              <div className="p-3.5 bg-accent-red/10 border border-accent-red/30 rounded-xl space-y-2 flex flex-col justify-between">
                <div className="flex items-center gap-1.5 text-accent-red font-bold">
                  <ShieldAlert className="w-4 h-4 shrink-0" />
                  <span className="tracking-wide">RED ZONE (CRITICAL)</span>
                </div>
                <p className="text-[11px] font-sans text-text-dim leading-relaxed">
                  Zero-tolerance perimeter line. Any movement immediately escalates threat alarms, captures high-rate snapshots, and dispatches rapid response.
                </p>
                <div className="pt-2 border-t border-accent-red/20 flex items-center justify-between text-[10px] text-accent-red uppercase tracking-wider font-semibold">
                  <span>TIER 1</span>
                  <span>ZERO TOLERANCE</span>
                </div>
              </div>

              <div className="p-3.5 bg-accent-yellow/10 border border-accent-yellow/30 rounded-xl space-y-2 flex flex-col justify-between">
                <div className="flex items-center gap-1.5 text-accent-yellow font-bold">
                  <Compass className="w-4 h-4 shrink-0" />
                  <span className="tracking-wide">YELLOW ZONE (CAUTION)</span>
                </div>
                <p className="text-[11px] font-sans text-text-dim leading-relaxed">
                  Direction-sensitive perimeter buffer. Trajectory vectors toward border trigger caution alerts, while verified outward movement remains logged.
                </p>
                <div className="pt-2 border-t border-accent-yellow/20 flex items-center justify-between text-[10px] text-accent-yellow uppercase tracking-wider font-semibold">
                  <span>TIER 2</span>
                  <span>VECTOR AWARE</span>
                </div>
              </div>

              <div className="p-3.5 bg-accent-green/10 border border-accent-green/30 rounded-xl space-y-2 flex flex-col justify-between">
                <div className="flex items-center gap-1.5 text-accent-green font-bold">
                  <Shield className="w-4 h-4 shrink-0" />
                  <span className="tracking-wide">GREEN ZONE (NORMAL)</span>
                </div>
                <p className="text-[11px] font-sans text-text-dim leading-relaxed">
                  Authorized access and patrol corridors. Logs background activity during standard hours; automatically escalates to <strong>Yellow</strong> during curfew (21:00–05:00).
                </p>
                <div className="pt-2 border-t border-accent-green/20 flex items-center justify-between text-[10px] text-accent-green uppercase tracking-wider font-semibold">
                  <span>TIER 3</span>
                  <span>CURFEW AWARE</span>
                </div>
              </div>
            </div>
          </Card>
        </div>

        {/* Right Column: Zone List Panel (4 Cols) */}
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
            <div className="space-y-2.5 max-h-[580px] overflow-y-auto pr-1">
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
                      className={`p-3.5 rounded-xl border bg-black/60 hover:bg-white/[0.04] transition-all cursor-pointer border-l-4 ${borderTierColor} shadow-md ${
                        isSelected
                          ? 'border-accent-teal/70 ring-2 ring-accent-teal/40 bg-accent-teal/10 shadow-[0_0_15px_rgba(0,240,255,0.15)]'
                          : 'border-white/10'
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
                <div className="p-4 rounded-xl border border-accent-yellow/30 bg-accent-yellow/5 space-y-3.5">
                  <div className="flex items-start gap-2.5">
                    <div className="p-2 rounded-lg bg-accent-yellow/15 text-accent-yellow border border-accent-yellow/30 shrink-0 mt-0.5">
                      <Shield className="w-5 h-5" />
                    </div>
                    <div className="space-y-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-bold text-accent-yellow uppercase tracking-wide">
                          Autonomous Fallback Active
                        </span>
                        <span className="w-2 h-2 rounded-full bg-accent-yellow animate-pulse" />
                      </div>
                      <p className="text-[11px] text-text-dim leading-relaxed font-sans">
                        Manual zones are <strong>optional</strong>. With 0 configured zones, the autonomous AI matrix monitors this camera automatically:
                      </p>
                    </div>
                  </div>

                  <div className="p-3 bg-black/60 rounded-xl border border-white/10 space-y-2 font-mono text-[11px]">
                    <div className="flex items-center justify-between text-text-dim">
                      <span className="flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-accent-yellow" />
                        Daylight (05:00 - 21:00)
                      </span>
                      <span className="text-accent-yellow font-bold">Caution (Tier 2)</span>
                    </div>
                    <div className="flex items-center justify-between text-text-dim">
                      <span className="flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-accent-red" />
                        Curfew (21:00 - 05:00)
                      </span>
                      <span className="text-accent-red font-bold">Critical (Tier 1)</span>
                    </div>
                    <div className="flex items-center justify-between text-text-dim">
                      <span className="flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-accent-red" />
                        Rapid Approach / Sprint
                      </span>
                      <span className="text-accent-red font-bold">Instant Escalation</span>
                    </div>
                  </div>

                  {/* 1-Click Zone Setup Options */}
                  <div className="space-y-2 pt-1 border-t border-white/10">
                    <span className="text-[10px] font-mono text-text-muted uppercase tracking-wider block font-bold">
                      1-Click Zone Setup (Optional):
                    </span>
                    <div className="grid grid-cols-1 gap-2">
                      <button
                        onClick={() => handleApplyPreset(ZONE_PRESETS[0], true)}
                        className="w-full px-3 py-2 rounded-lg bg-accent-teal/15 hover:bg-accent-teal/25 text-accent-teal border border-accent-teal/30 text-xs font-mono font-semibold flex items-center justify-between transition-all group"
                      >
                        <span className="flex items-center gap-1.5">
                          <Sparkles className="w-3.5 h-3.5 group-hover:rotate-12 transition-transform" />
                          Apply 3-Tier Horizon
                        </span>
                        <span className="text-[10px] bg-accent-teal/20 px-1.5 py-0.5 rounded">3 Zones</span>
                      </button>

                      <button
                        onClick={() => handleApplyPreset(ZONE_PRESETS[1], true)}
                        className="w-full px-3 py-2 rounded-lg bg-white/[0.05] hover:bg-white/[0.1] text-text-dim hover:text-white border border-white/10 text-xs font-mono font-semibold flex items-center justify-between transition-all"
                      >
                        <span className="flex items-center gap-1.5">
                          <Layers className="w-3.5 h-3.5" />
                          Apply Gate Funnel
                        </span>
                        <span className="text-[10px] bg-white/10 px-1.5 py-0.5 rounded">4 Zones</span>
                      </button>

                      {otherCamerasWithZones.length > 0 && (
                        <button
                          onClick={() => handleCopyFromCamera(otherCamerasWithZones[0])}
                          className="w-full px-3 py-2 rounded-lg bg-white/[0.05] hover:bg-white/[0.1] text-text-dim hover:text-white border border-white/10 text-xs font-mono font-semibold flex items-center justify-between transition-all"
                        >
                          <span className="flex items-center gap-1.5">
                            <Copy className="w-3.5 h-3.5" />
                            Copy Zones from {otherCamerasWithZones[0].toUpperCase()}
                          </span>
                          <span className="text-[10px] bg-white/10 px-1.5 py-0.5 rounded">Mirror</span>
                        </button>
                      )}

                      <button
                        onClick={() => setIsDrawing(true)}
                        className="w-full px-3 py-2 rounded-lg bg-white/[0.03] hover:bg-white/[0.08] text-text-muted hover:text-text-primary border border-white/10 text-xs font-mono flex items-center justify-center gap-1.5 transition-all"
                      >
                        <Pencil className="w-3 h-3" />
                        <span>Draw Custom Polygon</span>
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Bottom Quick Clone Action if camera has zones */}
            {cameraZones.length > 0 && (
              <div className="pt-3 border-t border-white/10">
                <button
                  onClick={handleOpenCloneModal}
                  className="w-full py-2 px-3 rounded-lg bg-white/[0.04] hover:bg-accent-teal/15 text-text-dim hover:text-accent-teal border border-white/10 hover:border-accent-teal/30 transition-all font-mono text-xs flex items-center justify-center gap-1.5 font-semibold"
                >
                  <Copy className="w-3.5 h-3.5" />
                  <span>Clone {cameraZones.length} Zones to Other Cameras</span>
                </button>
              </div>
            )}
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

      {/* CLONE TO OTHER CAMERAS MODAL */}
      <Modal
        isOpen={isCloneModalOpen}
        onClose={() => setIsCloneModalOpen(false)}
        title={
          <div className="flex items-center gap-2">
            <Copy className="w-4 h-4 text-accent-yellow" />
            <span>Clone Zones Across Cameras</span>
          </div>
        }
        description={`Duplicate ${cameraZones.length} configured zone(s) from ${selectedCamera.toUpperCase()} to other sector cameras.`}
        size="md"
        footer={
          <div className="flex items-center justify-between w-full">
            <span className="text-xs font-mono text-text-dim">
              {selectedCloneTargets.length} camera(s) selected
            </span>
            <div className="flex items-center gap-2">
              <Button variant="ghost" size="sm" onClick={() => setIsCloneModalOpen(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                disabled={selectedCloneTargets.length === 0}
                leftIcon={<Copy className="w-3.5 h-3.5" />}
                onClick={handleConfirmClone}
              >
                Clone to {selectedCloneTargets.length} Camera(s)
              </Button>
            </div>
          </div>
        }
      >
        <div className="space-y-4 font-mono text-xs">
          <div className="p-3 bg-white/[0.03] border border-white/10 rounded-xl space-y-1">
            <span className="text-text-muted text-[10px] block uppercase">Source Camera</span>
            <div className="flex items-center justify-between">
              <span className="text-white font-bold">{selectedCamera.toUpperCase()}</span>
              <Badge variant="teal" size="sm">
                {cameraZones.length} ZONES
              </Badge>
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-text-dim uppercase text-[11px] font-bold">
                Select Destination Cameras:
              </span>
              <button
                type="button"
                onClick={() => {
                  const others = availableCameras.filter((c) => c !== selectedCamera);
                  if (selectedCloneTargets.length === others.length) {
                    setSelectedCloneTargets([]);
                  } else {
                    setSelectedCloneTargets(others);
                  }
                }}
                className="text-accent-teal hover:underline text-[11px]"
              >
                {selectedCloneTargets.length === availableCameras.filter((c) => c !== selectedCamera).length
                  ? 'Deselect All'
                  : 'Select All'}
              </button>
            </div>

            <div className="grid grid-cols-2 gap-2">
              {availableCameras
                .filter((c) => c !== selectedCamera)
                .map((cam) => {
                  const isChecked = selectedCloneTargets.includes(cam);
                  const existingCount = allZones.filter((z) => z.cameraName === cam).length;
                  return (
                    <label
                      key={cam}
                      className={`flex items-center justify-between p-3 rounded-xl border cursor-pointer transition-all ${
                        isChecked
                          ? 'bg-accent-teal/15 border-accent-teal text-white'
                          : 'bg-black/50 border-white/10 text-text-dim hover:border-white/20'
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedCloneTargets((prev) => [...prev, cam]);
                            } else {
                              setSelectedCloneTargets((prev) => prev.filter((c) => c !== cam));
                            }
                          }}
                          className="w-4 h-4 rounded accent-accent-teal"
                        />
                        <span className="font-bold">{cam.toUpperCase()}</span>
                      </div>
                      <span className="text-[10px] text-text-muted">
                        ({existingCount} existing)
                      </span>
                    </label>
                  );
                })}
            </div>
          </div>

          <div className="pt-2 border-t border-white/10">
            <label className="flex items-center gap-2 cursor-pointer text-[11px] text-text-dim">
              <input
                type="checkbox"
                checked={cloneOverwrite}
                onChange={(e) => setCloneOverwrite(e.target.checked)}
                className="w-3.5 h-3.5 accent-accent-teal rounded"
              />
              <span>Overwrite existing zones on destination cameras</span>
            </label>
            <p className="text-[10px] text-text-muted pl-5 mt-0.5 font-sans">
              If checked, replaces target cameras' zones with source zones. If unchecked, appends to them.
            </p>
          </div>
        </div>
      </Modal>
    </div>
  );
};

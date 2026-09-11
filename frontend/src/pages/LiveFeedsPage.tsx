import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { camerasApi, cameraStreamUrl } from '@/lib/api';
import { CameraTile } from '@/components/live';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Modal } from '@/components/ui/Modal';
import {
  Grid2X2,
  Maximize2,
  ArrowLeft,
  Video,
  Radio,
  Layers,
  Plus,
  Tv,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';

export interface CameraItem {
  id: string;
  name: string;
  location: string;
  sector: string;
  streamUrl?: string;
  fps: string;
  activity: string;
  isActive: boolean;
  resolution?: string;
  activityGate?: 'HIGH' | 'LOW';
  lowLightBoost?: boolean;
}

const initialCameras: CameraItem[] = [
  {
    id: 'cam0',
    name: 'cam0',
    location: 'North Perimeter Gate',
    sector: 'North Border Sector',
    fps: '29.8',
    activity: 'MOTION',
    isActive: true,
    resolution: '1920x1080',
    activityGate: 'HIGH',
    lowLightBoost: false,
  },
  {
    id: 'cam1',
    name: 'cam1',
    location: 'East Checkpoint Bravo',
    sector: 'East Border Sector',
    fps: '30.0',
    activity: 'STANDBY',
    isActive: true,
    resolution: '1920x1080',
    activityGate: 'LOW',
    lowLightBoost: false,
  },
  {
    id: 'cam2',
    name: 'cam2',
    location: 'South Fence Line',
    sector: 'South Perimeter',
    fps: '28.4',
    activity: 'ACTIVE',
    isActive: true,
    resolution: '1920x1080',
    activityGate: 'HIGH',
    lowLightBoost: false,
  },
  {
    id: 'cam3',
    name: 'cam3',
    location: 'West Watchtower Alpha',
    sector: 'West Mountain Sector',
    fps: '29.5',
    activity: 'NIGHT_IR',
    isActive: true,
    resolution: '1920x1080',
    activityGate: 'HIGH',
    lowLightBoost: true,
  },
];

const CAMERAS_STORAGE_KEY = 'ibvap_cameras_data_v3';

const loadStoredCameras = (): CameraItem[] => {
  try {
    const saved = localStorage.getItem(CAMERAS_STORAGE_KEY);
    if (saved) {
      const parsed = JSON.parse(saved);
      if (Array.isArray(parsed) && parsed.length > 0) {
        return parsed.map((cam: any, idx: number) => ({
          ...cam,
          resolution: cam.resolution || '1920x1080',
          activityGate: cam.activityGate || (idx === 1 ? 'LOW' : 'HIGH'),
          lowLightBoost: cam.lowLightBoost ?? (idx === 3),
        }));
      }
    }
  } catch (e) {
    console.error('Failed to load cameras from storage', e);
  }
  return initialCameras;
};


export const LiveFeedsPage: React.FC = () => {
  const [cameras, setCameras] = useState<CameraItem[]>(loadStoredCameras);
  const [viewMode, setViewMode] = useState<'grid' | 'focus'>('grid');
  const [gridColumns, setGridColumns] = useState<'2' | '3'>('2');
  const [focusedCameraId, setFocusedCameraId] = useState<string>('cam0');
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);

  const [searchParams] = useSearchParams();
  const urlCamera = searchParams.get('camera');

  // Replace the seeded demo tiles with whatever the backend actually has on
  // CAMERA_SOURCES. Guarded on isFallback: safeFetch resolves successfully
  // with mock data when the API is down, and overwriting real tiles with
  // that would be worse than leaving the last known list in place.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const res = await camerasApi.getCameras([]);
      if (cancelled || res.isFallback || !res.data || res.data.length === 0) return;
      setCameras(
        res.data.map((c) => ({
          id: c.id,
          name: c.name,
          location: c.location,
          sector: c.sector,
          streamUrl: cameraStreamUrl(c.id),
          fps: c.fps,
          activity: c.activity,
          isActive: c.isActive,
          resolution: c.resolution,
        }))
      );
      setFocusedCameraId(res.data[0].id);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Automatically sync cameras to localStorage across routes and sessions
  useEffect(() => {
    try {
      localStorage.setItem(CAMERAS_STORAGE_KEY, JSON.stringify(cameras));
    } catch (e) {
      console.error('Failed to persist cameras', e);
    }
  }, [cameras]);

  // Auto-focus camera when requested via query parameter (e.g. from Detections / View Evidence)
  useEffect(() => {
    if (urlCamera) {
      const match = cameras.find((c) => c.id.toLowerCase() === urlCamera.toLowerCase());
      if (match) {
        setFocusedCameraId(match.id);
        setViewMode('focus');
      }
    }
  }, [urlCamera, cameras]);

  // Form State for Adding a Camera
  const [newCamId, setNewCamId] = useState(`cam${cameras.length}`);
  const [newCamLocation, setNewCamLocation] = useState('');
  const [newCamSector, setNewCamSector] = useState('North Border Sector');
  const [sourceType, setSourceType] = useState<'local' | 'rtsp'>('local');
  const [localCamIndex, setLocalCamIndex] = useState('0');
  const [newCamStreamUrl, setNewCamStreamUrl] = useState('');
  const [formError, setFormError] = useState('');
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  const handleTileClick = (camId: string) => {
    setFocusedCameraId(camId);
    setViewMode('focus');
  };


  const handleRemoveCamera = async (camId: string) => {
    if (cameras.length <= 1) {
      showToast('Cannot remove last remaining surveillance feed');
      return;
    }
    
    try {
      await camerasApi.deleteCamera(camId);
      const updated = cameras.filter((c) => c.id !== camId);
      setCameras(updated);
      if (focusedCameraId === camId) {
        setFocusedCameraId(updated[0]?.id || 'cam0');
      }
      showToast(`Removed camera channel ${camId.toUpperCase()}`);
    } catch (err) {
      // Surface the reason: a delete refused because the camera comes from
      // CAMERA_SOURCES in .env reads very differently from a network failure.
      showToast(
        `Failed to remove camera ${camId}: ${err instanceof Error ? err.message : 'unknown error'}`
      );
    }
  };

  const handleOpenAddModal = () => {
    setNewCamId(`cam${cameras.length}`);
    setNewCamLocation('');
    setNewCamStreamUrl('');
    setFormError('');
    setIsAddModalOpen(true);
  };

  const handleAddCameraSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanId = newCamId.trim().toLowerCase();
    const cleanLocation = newCamLocation.trim();

    if (!cleanId) {
      setFormError('Camera ID is required (e.g. cam4)');
      return;
    }

    if (cameras.some((c) => c.id.toLowerCase() === cleanId)) {
      setFormError(`Camera ID "${cleanId}" already exists. Use a unique channel ID.`);
      return;
    }

    if (!cleanLocation) {
      setFormError('Location or post name is required');
      return;
    }
    
    const finalStreamUrl = sourceType === 'local' ? localCamIndex : newCamStreamUrl.trim();

    const newCamera: CameraItem = {
      id: cleanId,
      name: cleanId,
      location: cleanLocation,
      sector: newCamSector,
      streamUrl: finalStreamUrl || undefined,
      fps: '0.0',
      activity: '—',
      isActive: true,
      resolution: '1920x1080',
    };

    try {
      const res = await camerasApi.addCamera(newCamera);
      if (!res.isFallback && res.data) {
        newCamera.id = res.data.id || newCamera.id;
        // finalStreamUrl is what the BACKEND needs to open the device (a
        // device index like "0", or an rtsp:// URL). What the tile needs is
        // the MJPEG endpoint. Leaving the former here renders <img src="0">,
        // i.e. a broken image on the freshly added camera.
        newCamera.streamUrl = cameraStreamUrl(newCamera.id);
      }
      const updated = [...cameras, newCamera];
      setCameras(updated);
      setIsAddModalOpen(false);
      showToast(`Camera ${cleanId.toUpperCase()} (${cleanLocation}) added successfully`);
    } catch (err) {
      setFormError(
        `Failed to integrate camera with the backend API: ${
          err instanceof Error ? err.message : 'unknown error'
        }`
      );
    }
  };

  // Quick batch add preset: adds 2 tactical outpost cameras at once
  const handleBatchAddPreset = async () => {
    const nextIdx = cameras.length;
    const batch: CameraItem[] = [
      {
        id: `cam${nextIdx}`,
        name: `cam${nextIdx}`,
        location: `Checkpost ${String.fromCharCode(65 + nextIdx)} - Riverbank`,
        sector: 'Riverine Border Zone',
        fps: '0.0',
        activity: '—',
        isActive: true,
        resolution: '1920x1080',
      },
      {
        id: `cam${nextIdx + 1}`,
        name: `cam${nextIdx + 1}`,
        location: `BOP Echo - Road Intersection`,
        sector: 'Highway Corridor Sector',
        fps: '0.0',
        activity: '—',
        isActive: true,
        resolution: '1920x1080',
      },
    ];

    try {
      for (const cam of batch) {
        await camerasApi.addCamera(cam);
      }
      setCameras((prev) => [...prev, ...batch]);
      setIsAddModalOpen(false);
      showToast(`Batch added 2 outpost cameras: ${batch[0].id}, ${batch[1].id}`);
    } catch (err) {
      showToast(
        `Failed to integrate batch cameras: ${err instanceof Error ? err.message : 'unknown error'}`
      );
    }
  };

  const focusedCamera =
    cameras.find((c) => c.id === focusedCameraId) || cameras[0] || initialCameras[0];

  const onlineCount = cameras.filter((c) => c.isActive).length;

  return (
    <div className="space-y-5">
      {/* Dynamic Toast Feedback */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 flex items-center gap-2 px-4 py-2.5 bg-bg-surface border border-accent-teal/50 rounded-sm shadow-xl font-mono text-xs text-text-primary animate-in fade-in slide-in-from-bottom-2">
          <CheckCircle2 className="w-4 h-4 text-accent-teal" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Top Toolbar / Filter Row */}
      <div className="card-3d flex flex-col lg:flex-row lg:items-center justify-between gap-3 p-4 rounded-2xl border border-white/10 bg-gradient-to-b from-[#0c0c14] to-[#06060a] shadow-[0_15px_35px_rgba(0,0,0,0.8)]">
        {/* Left: Camera Count Indicator & Status */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <Video className="w-4 h-4 text-accent-teal" />
            <span className="font-mono text-xs font-bold text-white uppercase tracking-wider">
              Surveillance Grid
            </span>
          </div>

          <span className="text-white/20">|</span>

          <Badge variant="green" dot size="sm">
            {cameras.length} CAMERAS · {onlineCount} ONLINE
          </Badge>

          <span className="hidden sm:inline font-mono text-[11px] text-text-dim">
            AUTO-RELOAD · RTSP POOL
          </span>
        </div>

        {/* Right: Actions & Layout Controls */}
        <div className="flex flex-wrap items-center gap-2.5">
          {/* Add Camera Button */}
          <Button
            variant="primary"
            size="sm"
            leftIcon={<Plus className="w-4 h-4" />}
            onClick={handleOpenAddModal}
          >
            Add Camera
          </Button>

          {/* Back to Grid Button (when in focus mode) */}
          {viewMode === 'focus' && (
            <Button
              variant="secondary"
              size="sm"
              leftIcon={<ArrowLeft className="w-3.5 h-3.5" />}
              onClick={() => setViewMode('grid')}
            >
              Back to Grid
            </Button>
          )}

          {/* Grid Columns Switcher (when in grid mode) */}
          {viewMode === 'grid' && cameras.length >= 4 && (
            <div className="hidden sm:inline-flex p-1 bg-black/60 border border-white/10 rounded-xl shadow-inner">
              <button
                onClick={() => setGridColumns('2')}
                title="2 Columns Grid"
                className={`px-2.5 py-1 text-[11px] font-mono rounded-lg transition-all ${
                  gridColumns === '2'
                    ? 'bg-accent-teal/15 text-accent-teal font-bold border border-accent-teal/40'
                    : 'text-text-dim hover:text-white'
                }`}
              >
                2 COL
              </button>
              <button
                onClick={() => setGridColumns('3')}
                title="3 Columns Grid"
                className={`px-2.5 py-1 text-[11px] font-mono rounded-lg transition-all ${
                  gridColumns === '3'
                    ? 'bg-accent-teal/15 text-accent-teal font-bold border border-accent-teal/40'
                    : 'text-text-dim hover:text-white'
                }`}
              >
                3 COL
              </button>
            </div>
          )}

          {/* Layout Mode Toggle Buttons */}
          <div className="inline-flex p-1 bg-black/60 border border-white/10 rounded-xl shadow-inner">
            <button
              onClick={() => setViewMode('grid')}
              title="Grid View"
              className={`flex items-center gap-1.5 px-3 py-1 text-xs font-mono font-semibold rounded-lg transition-all ${
                viewMode === 'grid'
                  ? 'bg-accent-teal/15 text-accent-teal border border-accent-teal/40'
                  : 'text-text-dim hover:text-white'
              }`}
            >
              <Grid2X2 className="w-3.5 h-3.5" />
              <span>GRID</span>
            </button>

            <button
              onClick={() => setViewMode('focus')}
              title="Focus View (Single Camera Enlarged)"
              className={`flex items-center gap-1.5 px-3 py-1 text-xs font-mono font-semibold rounded-lg transition-all ${
                viewMode === 'focus'
                  ? 'bg-accent-teal/15 text-accent-teal border border-accent-teal/40'
                  : 'text-text-dim hover:text-white'
              }`}
            >
              <Maximize2 className="w-3.5 h-3.5" />
              <span>FOCUS</span>
            </button>
          </div>
        </div>
      </div>

      {/* Main Surveillance View Area */}
      {viewMode === 'grid' ? (
        /* Responsive Camera Grid */
        <div
          className={`grid gap-4 ${
            gridColumns === '3'
              ? 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3'
              : 'grid-cols-1 md:grid-cols-2'
          }`}
        >
          {cameras.map((camera) => (
            <div
              key={camera.id}
              onClick={() => handleTileClick(camera.id)}
              className="cursor-pointer group/card focus:outline-none"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  handleTileClick(camera.id);
                }
              }}
            >
              <CameraTile
                cameraName={camera.name}
                label={camera.location}
                streamUrl={camera.streamUrl}
                isActive={camera.isActive}
                fps={camera.fps}
                activity={camera.activity}
                activityGate={camera.activityGate}
                lowLightBoost={camera.lowLightBoost}
                onToggleFocus={() => handleTileClick(camera.id)}
                onRemove={() => handleRemoveCamera(camera.id)}
              />
            </div>
          ))}
        </div>
      ) : (

        /* Single Camera Focus View */
        <div className="space-y-4">
          {/* Channel Selector Bar */}
          <div className="flex items-center gap-2 overflow-x-auto pb-1.5">
            <span className="font-mono text-xs text-text-dim uppercase tracking-wider shrink-0 mr-1">
              Select Camera:
            </span>
            {cameras.map((cam) => (
              <button
                key={cam.id}
                onClick={() => setFocusedCameraId(cam.id)}
                className={`px-3 py-1 text-xs font-mono rounded-sm transition-all flex items-center gap-2 border shrink-0 ${
                  focusedCameraId === cam.id
                    ? 'bg-accent-teal/20 text-accent-teal border-accent-teal/50 font-semibold shadow-sm'
                    : 'bg-bg-surface text-text-dim border-border-subtle hover:text-text-primary hover:bg-bg-elevated'
                }`}
              >
                <span className="w-1.5 h-1.5 rounded-full bg-accent-green" />
                <span>{cam.name}</span>
                <span className="text-[10px] text-text-muted hidden sm:inline">
                  ({cam.location})
                </span>
              </button>
            ))}
          </div>

          {/* Large Focused Tile */}
          <div className="max-w-5xl mx-auto">
            <CameraTile
              cameraName={focusedCamera.name}
              label={focusedCamera.location}
              streamUrl={focusedCamera.streamUrl}
              isActive={focusedCamera.isActive}
              fps={focusedCamera.fps}
              activity={focusedCamera.activity}
              activityGate={focusedCamera.activityGate}
              lowLightBoost={focusedCamera.lowLightBoost}
              isFocused={true}
              onToggleFocus={() => setViewMode('grid')}
              onRemove={() => handleRemoveCamera(focusedCamera.id)}
              className="shadow-2xl"
            />
          </div>

          {/* Quick Diagnostics Strip for Focused Camera */}
          <div className="card-3d max-w-5xl mx-auto p-3.5 bg-[#090c12] border border-white/10 rounded-2xl grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-xs shadow-lg">
            <div>
              <span className="text-text-muted block text-[10px] uppercase">
                Hardware Health
              </span>
              <span className="text-accent-green font-semibold flex items-center gap-1">
                ONLINE · RTSP LIVE
              </span>
              <span className="text-[10px] text-text-dim">
                Stream Latency: ~42ms
              </span>
            </div>
            <div>
              <span className="text-text-muted block text-[10px] uppercase">
                Activity Gating
              </span>
              <span
                className={`font-semibold flex items-center gap-1 ${
                  focusedCamera.activityGate === 'HIGH'
                    ? 'text-accent-green'
                    : 'text-accent-yellow'
                }`}
              >
                GATE: {focusedCamera.activityGate || 'HIGH'}
              </span>
              <span className="text-[10px] text-text-muted truncate block">
                {focusedCamera.activityGate === 'HIGH'
                  ? '30 FPS In-Motion'
                  : 'Low FPS Keep-Alive (1/10)'}
              </span>
            </div>
            <div>
              <span className="text-text-muted block text-[10px] uppercase">
                Preprocessing
              </span>
              <span
                className={`flex items-center gap-1 ${
                  focusedCamera.lowLightBoost
                    ? 'text-accent-yellow font-medium'
                    : 'text-text-dim'
                }`}
              >
                {focusedCamera.lowLightBoost ? 'CLAHE BOOST ON' : 'STANDARD LUX'}
              </span>
              <span className="text-[10px] text-text-muted">
                {focusedCamera.lowLightBoost ? 'Lux < 90 Boost' : 'Direct Sensor'}
              </span>
            </div>
            <div>
              <span className="text-text-muted block text-[10px] uppercase">
                Threat Detection
              </span>
              <span className="text-text-dim flex items-center gap-1">
                <Layers className="w-3 h-3 text-accent-yellow" /> 3 ZONES ACTIVE
              </span>
              <span className="text-[10px] text-accent-green flex items-center gap-1">
                <Radio className="w-2.5 h-2.5" /> RTSP POOL OK
              </span>
            </div>
          </div>
        </div>
      )}


      {/* Add Camera Modal Dialog */}
      <Modal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        title="Add Surveillance Camera Channel"
        description="Register a new CCTV IP stream / BOP outpost camera into the IBVAP surveillance grid."
        size="md"
        footer={
          <div className="flex items-center justify-between w-full">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleBatchAddPreset}
              leftIcon={<Tv className="w-3.5 h-3.5 text-accent-teal" />}
            >
              + Quick Add 2 Outposts
            </Button>

            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setIsAddModalOpen(false)}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                leftIcon={<Plus className="w-3.5 h-3.5" />}
                onClick={handleAddCameraSubmit}
              >
                Register Camera
              </Button>
            </div>
          </div>
        }
      >
        <form onSubmit={handleAddCameraSubmit} className="space-y-4">
          {formError && (
            <div className="p-2.5 bg-accent-red/15 border border-accent-red/40 rounded-sm flex items-center gap-2 text-xs text-accent-red">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{formError}</span>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-mono uppercase text-text-dim mb-1">
                Camera ID <span className="text-accent-red">*</span>
              </label>
              <input
                type="text"
                value={newCamId}
                onChange={(e) => setNewCamId(e.target.value)}
                placeholder="e.g. cam4"
                className="w-full px-3 py-2 bg-bg-elevated border border-border-subtle rounded-sm text-sm text-text-primary focus:outline-none focus:border-accent-teal font-mono"
              />
              <span className="text-[10px] text-text-muted mt-0.5 block font-mono">
                Identifier used in AI pipelines
              </span>
            </div>

            <div>
              <label className="block text-xs font-mono uppercase text-text-dim mb-1">
                Sector / Area
              </label>
              <select
                value={newCamSector}
                onChange={(e) => setNewCamSector(e.target.value)}
                className="w-full px-3 py-2 bg-bg-elevated border border-border-subtle rounded-sm text-sm text-text-primary focus:outline-none focus:border-accent-teal"
              >
                <option value="North Border Sector">North Border Sector</option>
                <option value="East Border Sector">East Border Sector</option>
                <option value="South Perimeter">South Perimeter</option>
                <option value="West Mountain Sector">West Mountain Sector</option>
                <option value="Checkpost Bravo Corridor">Checkpost Corridor</option>
                <option value="Riverine Border Zone">Riverine Border Zone</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-mono uppercase text-text-dim mb-1">
              Camera Location / Post Name <span className="text-accent-red">*</span>
            </label>
            <input
              type="text"
              value={newCamLocation}
              onChange={(e) => setNewCamLocation(e.target.value)}
              placeholder="e.g. Outpost Delta Watchtower, Gate 3 Checkpoint"
              className="w-full px-3 py-2 bg-bg-elevated border border-border-subtle rounded-sm text-sm text-text-primary focus:outline-none focus:border-accent-teal"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-mono uppercase text-text-dim mb-1">
                Source Type
              </label>
              <select
                value={sourceType}
                onChange={(e) => setSourceType(e.target.value as 'local' | 'rtsp')}
                className="w-full px-3 py-2 bg-bg-elevated border border-border-subtle rounded-sm text-sm text-text-primary focus:outline-none focus:border-accent-teal"
              >
                <option value="local">Local USB/Front Camera</option>
                <option value="rtsp">RTSP / IP Stream</option>
              </select>
            </div>

            {sourceType === 'local' ? (
              <div>
                <label className="block text-xs font-mono uppercase text-text-dim mb-1">
                  Device Index
                </label>
                <select
                  value={localCamIndex}
                  onChange={(e) => setLocalCamIndex(e.target.value)}
                  className="w-full px-3 py-2 bg-bg-elevated border border-border-subtle rounded-sm text-sm text-text-primary focus:outline-none focus:border-accent-teal font-mono"
                >
                  <option value="0">Camera 0 (Default Front)</option>
                  <option value="1">Camera 1 (External)</option>
                  <option value="2">Camera 2</option>
                  <option value="3">Camera 3</option>
                </select>
              </div>
            ) : (
              <div>
                <label className="block text-xs font-mono uppercase text-text-dim mb-1">
                  RTSP URL
                </label>
                <input
                  type="text"
                  value={newCamStreamUrl}
                  onChange={(e) => setNewCamStreamUrl(e.target.value)}
                  placeholder="rtsp://192.168.1.104:554/h264/ch1/main"
                  className="w-full px-3 py-2 bg-bg-elevated border border-border-subtle rounded-sm text-sm text-text-primary focus:outline-none focus:border-accent-teal font-mono text-xs"
                />
              </div>
            )}

            {/* Full-width helper row inside the same grid: it was previously
                emitted after the grid's closing tag, with a stray </div>
                after it, which left two adjacent JSX roots and failed to
                parse. col-span-2 keeps it spanning both columns. */}
            <span className="text-[10px] text-text-muted mt-0.5 block col-span-2">
              {sourceType === 'local'
                ? 'Select the hardware device index of the local camera.'
                : 'Enter the RTSP link for the IP camera.'}
            </span>
          </div>
        </form>
      </Modal>
    </div>
  );
};

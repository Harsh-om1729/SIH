import React, { useState, useEffect, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { ApiCamera, camerasApi, cameraStreamUrl } from '@/lib/api';
import { describeCamera, useSystemHealth } from '@/components/system/SystemHealthProvider';
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
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';

export interface CameraItem extends Omit<ApiCamera, 'activityGate' | 'lowLightBoost'> {
  activityGate?: 'HIGH' | 'LOW';
  lowLightBoost?: boolean;
}

const LEGACY_CAMERAS_STORAGE_KEY = 'ibvap_cameras_data_v3';


export const LiveFeedsPage: React.FC = () => {
  // One source of truth for cameras and their live status, shared with the
  // topbar, sidebar and dashboard (components/system/SystemHealthProvider).
  const { cameras: apiCameras, health, reachable, refresh } = useSystemHealth();
  const cameras: CameraItem[] = useMemo(
    () =>
      apiCameras.map((c) => ({
        ...c,
        streamUrl: cameraStreamUrl(c.id),
        activityGate: c.activityGate ?? undefined,
        lowLightBoost: c.lowLightBoost ?? undefined,
      })),
    [apiCameras]
  );
  const serverNow = health?.checkedAt ?? null;
  const [viewMode, setViewMode] = useState<'grid' | 'focus'>('grid');
  const [gridColumns, setGridColumns] = useState<'2' | '3'>('2');
  const [focusedCameraId, setFocusedCameraId] = useState<string>('cam0');
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);

  const [searchParams] = useSearchParams();
  const urlCamera = searchParams.get('camera');

  // Drop the camera list older builds cached, which held the invented tiles.
  useEffect(() => {
    try {
      localStorage.removeItem(LEGACY_CAMERAS_STORAGE_KEY);
    } catch {
      // storage unavailable
    }
  }, []);

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
      const res = await camerasApi.deleteCamera(camId);
      if (res.isFallback) {
        // e.g. 409 for a camera defined in .env — it was removed from the
        // grid anyway before, and came back on the next reload.
        showToast(`Could not remove ${camId.toUpperCase()}: ${res.error ?? 'backend unreachable'}`);
        return;
      }
      await refresh();
      if (focusedCameraId === camId) {
        setFocusedCameraId(cameras.find((c) => c.id !== camId)?.id || 'cam0');
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
      // newCamera.streamUrl carries what the BACKEND opens (a device index
      // like "0", or an rtsp:// URL); the tile's MJPEG URL is derived from
      // the id once the backend lists the camera.
      const res = await camerasApi.addCamera(newCamera);
      if (res.isFallback) {
        // Previously the tile was added locally even when this failed, so
        // the camera "appeared" and then vanished on the next reload.
        setFormError(`Could not add the camera: ${res.error ?? 'backend unreachable'}`);
        return;
      }
      await refresh();
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

  const focusedCamera =
    cameras.find((c) => c.id === focusedCameraId) || cameras[0];

  const onlineCount = cameras.filter((c) => c.health === 'online' && c.source !== 'idle').length;

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

          <Badge
            variant={cameras.length > 0 && onlineCount === cameras.length ? 'green' : 'yellow'}
            dot
            size="sm"
          >
            {cameras.length} CAMERAS · {onlineCount} LIVE
          </Badge>

          <span className="hidden sm:inline font-mono text-[11px] text-text-dim">
            {health?.pipeline.running ? 'AI PIPELINE RUNNING' : 'AI PIPELINE STOPPED — PREVIEW ONLY'}
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

      {/* Main Surveillance View Area — with no-camera / offline / loading states */}
      {reachable === null && cameras.length === 0 ? (
        <div role="status" className="card-3d p-10 border border-white/10 rounded-2xl text-center text-xs font-mono text-text-dim">
          Loading cameras…
        </div>
      ) : reachable === false && cameras.length === 0 ? (
        <div role="alert" className="card-3d p-10 border border-accent-red/40 bg-accent-red/5 rounded-2xl text-center space-y-2">
          <AlertCircle className="w-6 h-6 text-accent-red mx-auto" />
          <h3 className="text-sm font-semibold text-white">Backend unreachable</h3>
          <p className="text-xs text-text-dim">Start it with ./run.sh up — this page reconnects on its own.</p>
          <Button variant="secondary" size="sm" onClick={() => refresh()}>
            Retry now
          </Button>
        </div>
      ) : cameras.length === 0 ? (
        <div className="card-3d p-10 border border-dashed border-white/15 rounded-2xl text-center space-y-2">
          <Video className="w-6 h-6 text-text-muted mx-auto" />
          <h3 className="text-sm font-semibold text-white">No cameras configured</h3>
          <p className="text-xs text-text-dim">
            Set CAMERA_SOURCES in .env (e.g. cam0=0 for the built-in webcam) or add one here.
          </p>
          <Button variant="primary" size="sm" leftIcon={<Plus className="w-4 h-4" />} onClick={handleOpenAddModal}>
            Add Camera
          </Button>
        </div>
      ) : viewMode === 'grid' ? (
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
                source={camera.source}
                health={camera.health}
                zones={camera.zones}
                detections={camera.detections}
                maxTier={camera.maxTier}
                resolution={camera.resolution}
                lastFrameAt={camera.lastFrameAt}
                serverNow={serverNow}
                onToggleFocus={() => handleTileClick(camera.id)}
                onRemove={() => handleRemoveCamera(camera.id)}
              />
            </div>
          ))}
        </div>
      ) : !focusedCamera ? null : (

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
                <span
                  className={`w-1.5 h-1.5 rounded-full ${
                    cam.health === 'online' ? 'bg-accent-green' : cam.health === 'offline' ? 'bg-accent-red' : 'bg-accent-yellow'
                  }`}
                />
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
              source={focusedCamera.source}
              health={focusedCamera.health}
              zones={focusedCamera.zones}
              detections={focusedCamera.detections}
              maxTier={focusedCamera.maxTier}
              resolution={focusedCamera.resolution}
              lastFrameAt={focusedCamera.lastFrameAt}
              serverNow={serverNow}
              isFocused={true}
              onToggleFocus={() => setViewMode('grid')}
              onRemove={() => handleRemoveCamera(focusedCamera.id)}
              className="shadow-2xl"
            />
          </div>

          {/* Diagnostics for the focused camera — measured values only. This
              strip used to state "~42ms latency", "3 ZONES ACTIVE" and
              "RTSP POOL OK" for every camera. */}
          {(() => {
            const st = describeCamera(focusedCamera, reachable);
            const tone = {
              green: 'text-accent-green',
              yellow: 'text-accent-yellow',
              red: 'text-accent-red',
              muted: 'text-text-dim',
            }[st.tone];
            const age =
              serverNow != null && focusedCamera.lastFrameAt != null
                ? serverNow - focusedCamera.lastFrameAt
                : null;
            return (
              <div className="card-3d max-w-5xl mx-auto p-3.5 bg-[#090c12] border border-white/10 rounded-2xl grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-xs shadow-lg">
                <div>
                  <span className="text-text-muted block text-[10px] uppercase">Status</span>
                  <span className={`font-semibold ${tone}`}>{st.label}</span>
                  <span className="text-[10px] text-text-dim block">
                    {age != null
                      ? `Last frame ${Math.max(0, age).toFixed(1)}s ago`
                      : focusedCamera.source === 'pipeline'
                      ? 'Waiting for frames'
                      : 'Not being analysed'}
                  </span>
                </div>
                <div>
                  <span className="text-text-muted block text-[10px] uppercase">Activity gate</span>
                  <span className="text-text-primary font-semibold">
                    {focusedCamera.activityGate === 'HIGH'
                      ? 'MOTION · full pipeline'
                      : focusedCamera.activityGate === 'LOW'
                      ? 'IDLE · keep-alive rate'
                      : '—'}
                  </span>
                  <span className="text-[10px] text-text-muted block">Reported by the AI pipeline</span>
                </div>
                <div>
                  <span className="text-text-muted block text-[10px] uppercase">Low-light</span>
                  <span className={focusedCamera.lowLightBoost ? 'text-accent-yellow font-semibold' : 'text-text-dim'}>
                    {focusedCamera.lowLightBoost == null ? '—' : focusedCamera.lowLightBoost ? 'BOOST ON' : 'Off'}
                  </span>
                  <span className="text-[10px] text-text-muted block">
                    {focusedCamera.brightness != null ? `Brightness ${focusedCamera.brightness}` : 'Pipeline only'}
                  </span>
                </div>
                <div>
                  <span className="text-text-muted block text-[10px] uppercase">Border scoring</span>
                  <span className={`flex items-center gap-1 ${focusedCamera.zones ? 'text-text-primary' : 'text-accent-yellow'}`}>
                    <Layers className="w-3 h-3" /> {focusedCamera.zones ?? 0} zone{focusedCamera.zones === 1 ? '' : 's'}
                  </span>
                  <span className="text-[10px] text-text-muted flex items-center gap-1">
                    <Radio className="w-2.5 h-2.5" />
                    {focusedCamera.zones ? `${focusedCamera.detections ?? 0} target(s) in view` : 'Inactive — draw zones'}
                  </span>
                </div>
              </div>
            );
          })()}
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
            <span />

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

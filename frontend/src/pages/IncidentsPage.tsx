import React, { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Incident } from '@/lib/mockIncidents';
import { incidentsApi } from '@/lib/api';
import { useBackendData } from '@/lib/useBackendData';
import { DataSourceBadge } from '@/components/ui/DataSourceBadge';
import { useAlerts } from '@/components/alerts/AlertProvider';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/Table';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import {
  User,
  Car,
  HelpCircle,
  Video,
  Clock,
  Search,
  ArrowUp,
  ArrowDown,
  FilterX,
  Maximize2,
  Eye,
} from 'lucide-react';

const CAMERA_LOCATIONS: Record<string, string> = {
  cam0: 'North Perimeter Gate',
  cam1: 'East Checkpoint Bravo',
  cam2: 'South Fence Line',
  cam3: 'West Watchtower Alpha',
};

export const IncidentsPage: React.FC = () => {
  const navigate = useNavigate();
  const { alerts } = useAlerts();

  // Stored incidents from incidents.db. `alerts` holds what arrived over the
  // WebSocket since this tab opened; those rows are also in the database, so
  // merge by id rather than concatenating or a just-fired alert appears twice.
  const {
    data: stored,
    isMock,
    error,
  } = useBackendData<Incident[]>(() => incidentsApi.getIncidents(), []);

  const incidentsData = useMemo(() => {
    const byId = new Map<number, Incident>();
    for (const i of stored) byId.set(i.id, i);
    for (const a of alerts) byId.set(a.id, a);
    return Array.from(byId.values()).sort((a, b) => b.id - a.id);
  }, [stored, alerts]);

  // Filter States - centered around Detection Types (Person, Vehicle, Unknown)
  const [selectedCategory, setSelectedCategory] = useState<'all' | 'person' | 'vehicle' | 'unknown'>('all');
  const [selectedCamera, setSelectedCamera] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [sortDirection, setSortDirection] = useState<'desc' | 'asc'>('desc');

  // Evidence Preview Modal State
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);

  // Category counts
  const personCount = incidentsData.filter((i) => i.category === 'person').length;
  const vehicleCount = incidentsData.filter((i) => i.category === 'vehicle').length;
  const unknownCount = incidentsData.filter((i) => i.category === 'unknown').length;

  // Extract unique cameras from data
  const availableCameras = useMemo(() => {
    const cams = Array.from(new Set(incidentsData.map((i) => i.cameraName)));
    return cams.sort();
  }, [incidentsData]);

  // Filtered & Sorted Detections
  const filteredIncidents = useMemo(() => {
    return incidentsData
      .filter((incident) => {
        // Category filter (Person / Vehicle / Unknown)
        if (selectedCategory !== 'all' && incident.category !== selectedCategory) {
          return false;
        }
        // Camera filter
        if (selectedCamera !== 'all' && incident.cameraName !== selectedCamera) {
          return false;
        }
        // Search query (Track ID or Camera)
        if (searchQuery.trim()) {
          const q = searchQuery.trim().toLowerCase();
          const trackMatch = incident.trackId.toString().includes(q);
          const camMatch = incident.cameraName.toLowerCase().includes(q);
          const locationMatch = (CAMERA_LOCATIONS[incident.cameraName] || '').toLowerCase().includes(q);
          if (!trackMatch && !camMatch && !locationMatch) {
            return false;
          }
        }
        return true;
      })
      .sort((a, b) => {
        return sortDirection === 'desc'
          ? b.timestamp - a.timestamp
          : a.timestamp - b.timestamp;
      });
  }, [selectedCategory, selectedCamera, searchQuery, sortDirection, incidentsData]);

  // Navigate directly to the camera where target is detected
  const handleGoToCamera = (cameraName: string) => {
    navigate(`/live?camera=${cameraName}`);
  };

  const handleResetFilters = () => {
    setSelectedCategory('all');
    setSelectedCamera('all');
    setSearchQuery('');
  };

  const formatTime = (ts: number) => {
    const d = new Date(ts * 1000);
    return d.toLocaleTimeString('en-GB', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  return (
    <div className="space-y-6">
      {/* Where these rows came from. Without it a page served from
          mockIncidents.ts looks identical to one served from incidents.db. */}
      <div className="flex items-center justify-between">
        <span className="text-xs font-mono uppercase tracking-wider text-text-dim">
          {incidentsData.length} incident{incidentsData.length === 1 ? '' : 's'}
        </span>
        <DataSourceBadge isMock={isMock} error={error} />
      </div>

      {/* 1. Category KPI Cards: Person Detect / Vehicle Detect / Unknown Detect */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {/* Person Detect */}
        <div
          onClick={() => setSelectedCategory(selectedCategory === 'person' ? 'all' : 'person')}
          className={`card-3d p-4 rounded-2xl border transition-all cursor-pointer select-none ${
            selectedCategory === 'person'
              ? 'border-accent-teal ring-1 ring-accent-teal/50 bg-accent-teal/10'
              : 'border-white/10 hover:border-white/20'
          }`}
        >
          <div className="flex items-start justify-between">
            <div className="space-y-1">
              <span className="text-xs font-bold text-accent-teal uppercase tracking-wider block">
                Person Detect
              </span>
              <span className="text-3xl font-extrabold text-white block">
                {personCount}
              </span>
              <span className="text-[11px] text-text-dim">
                Human & foot intrusions
              </span>
            </div>
            <div className="w-10 h-10 rounded-xl bg-accent-teal/15 border border-accent-teal/30 text-accent-teal flex items-center justify-center">
              <User className="w-5 h-5" />
            </div>
          </div>
        </div>

        {/* Vehicle Detect */}
        <div
          onClick={() => setSelectedCategory(selectedCategory === 'vehicle' ? 'all' : 'vehicle')}
          className={`card-3d p-4 rounded-2xl border transition-all cursor-pointer select-none ${
            selectedCategory === 'vehicle'
              ? 'border-accent-yellow ring-1 ring-accent-yellow/50 bg-accent-yellow/10'
              : 'border-white/10 hover:border-white/20'
          }`}
        >
          <div className="flex items-start justify-between">
            <div className="space-y-1">
              <span className="text-xs font-bold text-accent-yellow uppercase tracking-wider block">
                Vehicle Detect
              </span>
              <span className="text-3xl font-extrabold text-white block">
                {vehicleCount}
              </span>
              <span className="text-[11px] text-text-dim">
                Automobile & perimeter transport
              </span>
            </div>
            <div className="w-10 h-10 rounded-xl bg-accent-yellow/15 border border-accent-yellow/30 text-accent-yellow flex items-center justify-center">
              <Car className="w-5 h-5" />
            </div>
          </div>
        </div>

        {/* Unknown Detect */}
        <div
          onClick={() => setSelectedCategory(selectedCategory === 'unknown' ? 'all' : 'unknown')}
          className={`card-3d p-4 rounded-2xl border transition-all cursor-pointer select-none ${
            selectedCategory === 'unknown'
              ? 'border-accent-green ring-1 ring-accent-green/50 bg-accent-green/10'
              : 'border-white/10 hover:border-white/20'
          }`}
        >
          <div className="flex items-start justify-between">
            <div className="space-y-1">
              <span className="text-xs font-bold text-accent-green uppercase tracking-wider block">
                Unknown Detect
              </span>
              <span className="text-3xl font-extrabold text-white block">
                {unknownCount}
              </span>
              <span className="text-[11px] text-text-dim">
                Thermal & unidentified shapes
              </span>
            </div>
            <div className="w-10 h-10 rounded-xl bg-accent-green/15 border border-accent-green/30 text-accent-green flex items-center justify-center">
              <HelpCircle className="w-5 h-5" />
            </div>
          </div>
        </div>
      </div>

      {/* 2. Target Category Filter Bar & Search */}
      <div className="card-3d p-4 bg-gradient-to-b from-[#0c0c14] to-[#06060a] border border-white/10 rounded-2xl shadow-[0_15px_35px_rgba(0,0,0,0.8)] space-y-4">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
          {/* Category Filter Pills */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs font-semibold text-text-dim uppercase tracking-wider mr-1">
              Category:
            </span>

            <button
              onClick={() => setSelectedCategory('all')}
              className={`px-3 py-1.5 text-xs font-mono rounded-xl transition-all border ${
                selectedCategory === 'all'
                  ? 'bg-accent-teal/20 text-accent-teal border-accent-teal/50 font-bold shadow-[0_0_12px_rgba(0,240,255,0.25)]'
                  : 'bg-black/60 text-text-dim border-white/10 hover:text-white'
              }`}
            >
              ALL DETECTIONS ({incidentsData.length})
            </button>

            <button
              onClick={() => setSelectedCategory('person')}
              className={`px-3 py-1.5 text-xs font-mono rounded-xl transition-all border flex items-center gap-1.5 ${
                selectedCategory === 'person'
                  ? 'bg-accent-teal/20 text-accent-teal border-accent-teal/50 font-bold shadow-[0_0_12px_rgba(0,240,255,0.25)]'
                  : 'bg-black/60 text-text-dim border-white/10 hover:text-accent-teal'
              }`}
            >
              <User className="w-3.5 h-3.5" />
              PERSON DETECT ({personCount})
            </button>

            <button
              onClick={() => setSelectedCategory('vehicle')}
              className={`px-3 py-1.5 text-xs font-mono rounded-xl transition-all border flex items-center gap-1.5 ${
                selectedCategory === 'vehicle'
                  ? 'bg-accent-yellow/20 text-accent-yellow border-accent-yellow/50 font-bold shadow-[0_0_12px_rgba(255,170,0,0.25)]'
                  : 'bg-black/60 text-text-dim border-white/10 hover:text-accent-yellow'
              }`}
            >
              <Car className="w-3.5 h-3.5" />
              VEHICLE DETECT ({vehicleCount})
            </button>

            <button
              onClick={() => setSelectedCategory('unknown')}
              className={`px-3 py-1.5 text-xs font-mono rounded-xl transition-all border flex items-center gap-1.5 ${
                selectedCategory === 'unknown'
                  ? 'bg-accent-green/20 text-accent-green border-accent-green/50 font-bold shadow-[0_0_12px_rgba(0,255,136,0.25)]'
                  : 'bg-black/60 text-text-dim border-white/10 hover:text-accent-green'
              }`}
            >
              <HelpCircle className="w-3.5 h-3.5" />
              UNKNOWN DETECT ({unknownCount})
            </button>
          </div>

          {/* Quick Reset Filters */}
          {(selectedCategory !== 'all' || selectedCamera !== 'all' || searchQuery) && (
            <button
              onClick={handleResetFilters}
              className="flex items-center gap-1.5 text-xs font-mono text-text-dim hover:text-accent-teal transition-colors"
            >
              <FilterX className="w-3.5 h-3.5" />
              <span>Reset Filters</span>
            </button>
          )}
        </div>

        {/* Camera Filter & Search Row */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2 border-t border-white/10">
          <div className="sm:col-span-2 relative">
            <Search className="w-4 h-4 text-text-muted absolute left-3 top-2.5" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by Track ID (#TRK-...), camera ID, or location..."
              className="w-full pl-9 pr-3 py-2 bg-[#0a0a10] border border-white/10 rounded-xl text-xs text-white placeholder:text-text-muted focus:outline-none focus:border-accent-teal focus:ring-1 focus:ring-accent-teal font-mono transition-all"
            />
          </div>

          <div>
            <select
              value={selectedCamera}
              onChange={(e) => setSelectedCamera(e.target.value)}
              className="w-full px-3 py-2 bg-[#0a0a10] border border-white/10 rounded-xl text-xs text-white focus:outline-none focus:border-accent-teal focus:ring-1 focus:ring-accent-teal font-mono transition-all"
            >
              <option value="all">All Cameras ({availableCameras.length})</option>
              {availableCameras.map((cam) => (
                <option key={cam} value={cam}>
                  {cam.toUpperCase()} - {CAMERA_LOCATIONS[cam] || 'Perimeter'}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* 3. Detections Table with Direct "Go to Camera" Action */}
      {filteredIncidents.length > 0 ? (
        <Table>
          <TableHeader>
            <TableRow isHoverable={false}>
              <TableHead>
                <button
                  onClick={() =>
                    setSortDirection((prev) => (prev === 'desc' ? 'asc' : 'desc'))
                  }
                  className="flex items-center gap-1.5 text-text-dim hover:text-white transition-colors select-none font-mono"
                  title="Toggle sort direction by timestamp"
                >
                  <span>TIMESTAMP</span>
                  {sortDirection === 'desc' ? (
                    <ArrowDown className="w-3.5 h-3.5 text-accent-teal" />
                  ) : (
                    <ArrowUp className="w-3.5 h-3.5 text-accent-teal" />
                  )}
                </button>
              </TableHead>
              <TableHead>DETECTION TYPE</TableHead>
              <TableHead>CAMERA LOCATION</TableHead>
              <TableHead>TRACK ID</TableHead>
              <TableHead>THREAT LEVEL</TableHead>
              <TableHead>SNAPSHOT</TableHead>
              <TableHead className="text-right">VIEW EVIDENCE</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredIncidents.map((incident) => {
              const isPerson = incident.category === 'person';
              const isVehicle = incident.category === 'vehicle';
              const isRed = incident.tier === 'red';
              const isYellow = incident.tier === 'yellow';

              return (
                <TableRow
                  key={incident.id}
                  className={isRed ? 'bg-accent-red/[0.03]' : ''}
                >
                  {/* Timestamp */}
                  <TableCell className="font-mono text-xs text-text-dim font-medium">
                    <div className="flex items-center gap-1.5">
                      <Clock className="w-3 h-3 text-text-muted" />
                      <span>{formatTime(incident.timestamp)}</span>
                    </div>
                  </TableCell>

                  {/* Detection Type: Person Detect / Vehicle Detect / Unknown Detect */}
                  <TableCell>
                    {isPerson ? (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-accent-teal/15 text-accent-teal border border-accent-teal/40 font-mono text-xs font-bold shadow-[0_0_8px_rgba(0,240,255,0.2)]">
                        <User className="w-3.5 h-3.5" />
                        PERSON DETECT
                      </span>
                    ) : isVehicle ? (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-accent-yellow/15 text-accent-yellow border border-accent-yellow/40 font-mono text-xs font-bold">
                        <Car className="w-3.5 h-3.5" />
                        VEHICLE DETECT
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-accent-green/15 text-accent-green border border-accent-green/40 font-mono text-xs font-bold">
                        <HelpCircle className="w-3.5 h-3.5" />
                        UNKNOWN DETECT
                      </span>
                    )}
                  </TableCell>

                  {/* Camera Location */}
                  <TableCell>
                    <div className="space-y-0.5">
                      <div className="font-mono text-xs font-bold text-white uppercase flex items-center gap-1.5">
                        <Video className="w-3 h-3 text-accent-teal" />
                        <span>{incident.cameraName}</span>
                      </div>
                      <div className="text-[11px] text-text-dim">
                        {CAMERA_LOCATIONS[incident.cameraName] || 'Perimeter Line'}
                      </div>
                    </div>
                  </TableCell>

                  {/* Track ID */}
                  <TableCell className="font-mono text-xs text-accent-teal font-semibold">
                    #TRK-{incident.trackId}
                  </TableCell>

                  {/* Threat Level */}
                  <TableCell>
                    <Badge
                      variant={isRed ? 'red' : isYellow ? 'yellow' : 'green'}
                      dot
                      pulse={isRed}
                      size="sm"
                    >
                      {incident.tier.toUpperCase()} ({incident.score.toFixed(0)})
                    </Badge>
                  </TableCell>

                  {/* Snapshot Thumbnail Preview */}
                  <TableCell>
                    <button
                      onClick={() => setSelectedIncident(incident)}
                      title="Inspect snapshot frame"
                      className="w-14 h-9 rounded-lg border border-white/15 bg-black overflow-hidden hover:border-accent-teal transition-all group relative block"
                    >
                      <img
                        src={incident.snapshotUrl}
                        alt="Evidence snapshot thumbnail"
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                      />
                      <div className="absolute inset-0 bg-black/30 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                        <Maximize2 className="w-3 h-3 text-accent-teal" />
                      </div>
                    </button>
                  </TableCell>

                  {/* View Evidence -> Sleek dashboard-styled button */}
                  <TableCell className="text-right">
                    <button
                      onClick={() => handleGoToCamera(incident.cameraName)}
                      className="px-2.5 py-1 rounded-lg bg-white/[0.06] hover:bg-accent-teal/20 text-text-dim hover:text-accent-teal border border-white/10 hover:border-accent-teal/40 transition-all font-mono text-[10px] font-semibold inline-flex items-center gap-1 shadow-sm"
                      title={`Go to live camera feed of ${incident.cameraName.toUpperCase()}`}
                    >
                      <Eye className="w-3 h-3" />
                      <span>View Evidence</span>
                    </button>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      ) : (
        /* Empty State */
        <div className="card-3d p-12 bg-black/60 border border-dashed border-white/15 rounded-2xl text-center space-y-3">
          <div className="p-3 bg-black border border-white/10 rounded-full w-12 h-12 flex items-center justify-center mx-auto text-text-muted">
            <FilterX className="w-6 h-6" />
          </div>
          <h3 className="text-sm font-semibold text-white">No Detections Found</h3>
          <p className="text-xs text-text-dim max-w-sm mx-auto">
            No targets match the active category and camera filters.
          </p>
          <Button variant="secondary" size="sm" onClick={handleResetFilters}>
            Reset Filters
          </Button>
        </div>
      )}

      {/* Snapshot Preview Modal with direct "Open Live Camera Feed" CTA */}
      {selectedIncident && (
        <Modal
          isOpen={Boolean(selectedIncident)}
          onClose={() => setSelectedIncident(null)}
          title={
            <div className="flex items-center gap-2">
              {selectedIncident.category === 'person' ? (
                <User className="w-5 h-5 text-accent-teal" />
              ) : selectedIncident.category === 'vehicle' ? (
                <Car className="w-5 h-5 text-accent-yellow" />
              ) : (
                <HelpCircle className="w-5 h-5 text-accent-green" />
              )}
              <span>
                Evidence Frame: {selectedIncident.category.toUpperCase()} DETECT (#TRK-{selectedIncident.trackId})
              </span>
            </div>
          }
          description={`Captured at ${CAMERA_LOCATIONS[selectedIncident.cameraName] || 'Perimeter'} (${selectedIncident.cameraName.toUpperCase()})`}
          size="xl"
          footer={
            <div className="flex items-center justify-between w-full">
              <span className="font-mono text-xs text-text-dim">
                Captured: {formatTime(selectedIncident.timestamp)}
              </span>
              <div className="flex items-center gap-2">
                <Button variant="ghost" size="sm" onClick={() => setSelectedIncident(null)}>
                  Close
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  leftIcon={<Video className="w-4 h-4" />}
                  onClick={() => {
                    const cam = selectedIncident.cameraName;
                    setSelectedIncident(null);
                    handleGoToCamera(cam);
                  }}
                >
                  Go to Live Camera Feed ({selectedIncident.cameraName.toUpperCase()})
                </Button>
              </div>
            </div>
          }
        >
          <div className="space-y-4">
            <div className="relative aspect-video w-full rounded-xl overflow-hidden border border-white/15 bg-black shadow-2xl">
              <img
                src={selectedIncident.snapshotUrl}
                alt="Full evidence frame"
                className="w-full h-full object-contain"
              />
            </div>

            <div className="grid grid-cols-3 gap-3 p-3 bg-black/60 rounded-xl border border-white/10 font-mono text-xs">
              <div>
                <span className="text-[10px] text-text-dim block uppercase">Target Type</span>
                <span className="text-white font-bold uppercase">{selectedIncident.category} DETECT</span>
              </div>
              <div>
                <span className="text-[10px] text-text-dim block uppercase">Camera Sector</span>
                <span className="text-accent-teal font-bold uppercase">{selectedIncident.cameraName}</span>
              </div>
              <div>
                <span className="text-[10px] text-text-dim block uppercase">Threat Score</span>
                <span className="text-white font-bold">{selectedIncident.score.toFixed(1)} / 100</span>
              </div>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};

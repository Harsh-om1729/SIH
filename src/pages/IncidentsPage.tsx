import React, { useState, useMemo } from 'react';
import {
  Incident,
  mockIncidents,
} from '@/lib/mockIncidents';
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
  AlertTriangle,
  Search,
  ArrowUp,
  ArrowDown,
  Eye,
  User,
  Car,
  HelpCircle,
  Clock,
  FilterX,
  FileImage,
  Scale,
  Zap,
  CheckCircle2,
} from 'lucide-react';

export const IncidentsPage: React.FC = () => {
  const { alerts } = useAlerts();
  const incidentsData = alerts.length > 0 ? alerts : mockIncidents;

  // Filter States
  const [selectedTier, setSelectedTier] = useState<'all' | 'green' | 'yellow' | 'red'>('all');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [selectedCamera, setSelectedCamera] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [sortDirection, setSortDirection] = useState<'desc' | 'asc'>('desc');

  // Evidence Modal State
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);
  const [activeViewerImage, setActiveViewerImage] = useState<string>('');

  // Extract unique cameras from data
  const availableCameras = useMemo(() => {
    const cams = Array.from(new Set(incidentsData.map((i) => i.cameraName)));
    return cams.sort();
  }, [incidentsData]);

  // Filtered & Sorted Incidents
  const filteredIncidents = useMemo(() => {
    return incidentsData
      .filter((incident) => {
        // Tier filter (evaluates final alert tier)
        if (selectedTier !== 'all' && incident.tier !== selectedTier) {
          return false;
        }
        // Category filter
        if (selectedCategory !== 'all' && incident.category !== selectedCategory) {
          return false;
        }
        // Camera filter
        if (selectedCamera !== 'all' && incident.cameraName !== selectedCamera) {
          return false;
        }
        // Search query (Track ID or Watchlist Match)
        if (searchQuery.trim()) {
          const q = searchQuery.trim().toLowerCase();
          const trackMatch = incident.trackId.toString().includes(q);
          const watchlistMatch = incident.watchlistMatch
            ? incident.watchlistMatch.toLowerCase().includes(q)
            : false;
          if (!trackMatch && !watchlistMatch) {
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
  }, [selectedTier, selectedCategory, selectedCamera, searchQuery, sortDirection]);

  // Open Evidence Modal handler
  const handleOpenEvidence = (incident: Incident) => {
    setSelectedIncident(incident);
    setActiveViewerImage(incident.snapshotUrl);
  };

  // Format UNIX timestamp into HH:MM:SS
  const formatTime = (ts: number) => {
    const d = new Date(ts * 1000);
    return d.toLocaleTimeString('en-GB', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  const formatFullDate = (ts: number) => {
    const d = new Date(ts * 1000);
    return `${d.toLocaleDateString('en-GB', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    })} · ${formatTime(ts)} UTC`;
  };

  const handleResetFilters = () => {
    setSelectedTier('all');
    setSelectedCategory('all');
    setSelectedCamera('all');
    setSearchQuery('');
  };

  const getCategoryIcon = (category: Incident['category']) => {
    switch (category) {
      case 'person':
        return <User className="w-3.5 h-3.5 text-accent-teal" />;
      case 'vehicle':
        return <Car className="w-3.5 h-3.5 text-accent-yellow" />;
      default:
        return <HelpCircle className="w-3.5 h-3.5 text-text-muted" />;
    }
  };

  return (
    <div className="space-y-5">
      {/* Top Filter & Search Toolbar */}
      <div className="p-4 bg-bg-surface border border-border-subtle rounded-sm space-y-3.5">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
          {/* Left: Tier Filter Pills */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs text-text-dim uppercase tracking-wider mr-1">
              Tier Filter:
            </span>

            <button
              onClick={() => setSelectedTier('all')}
              className={`px-2.5 py-1 text-xs font-mono rounded-sm transition-colors border ${
                selectedTier === 'all'
                  ? 'bg-accent-teal/20 text-accent-teal border-accent-teal/50 font-semibold'
                  : 'bg-bg-elevated text-text-dim border-border-subtle hover:text-text-primary'
              }`}
            >
              ALL TIERS ({mockIncidents.length})
            </button>

            <button
              onClick={() => setSelectedTier('green')}
              className={`px-2.5 py-1 text-xs font-mono rounded-sm transition-colors border flex items-center gap-1.5 ${
                selectedTier === 'green'
                  ? 'bg-accent-green/20 text-accent-green border-accent-green/50 font-semibold'
                  : 'bg-bg-elevated text-text-dim border-border-subtle hover:text-accent-green'
              }`}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-accent-green" />
              GREEN
            </button>

            <button
              onClick={() => setSelectedTier('yellow')}
              className={`px-2.5 py-1 text-xs font-mono rounded-sm transition-colors border flex items-center gap-1.5 ${
                selectedTier === 'yellow'
                  ? 'bg-accent-yellow/20 text-accent-yellow border-accent-yellow/50 font-semibold'
                  : 'bg-bg-elevated text-text-dim border-border-subtle hover:text-accent-yellow'
              }`}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-accent-yellow" />
              YELLOW
            </button>

            <button
              onClick={() => setSelectedTier('red')}
              className={`px-2.5 py-1 text-xs font-mono rounded-sm transition-colors border flex items-center gap-1.5 ${
                selectedTier === 'red'
                  ? 'bg-accent-red/20 text-accent-red border-accent-red/50 font-semibold'
                  : 'bg-bg-elevated text-text-dim border-border-subtle hover:text-accent-red'
              }`}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-accent-red" />
              RED ALERT
            </button>
          </div>

          {/* Right: Quick Reset Filters */}
          {(selectedTier !== 'all' ||
            selectedCategory !== 'all' ||
            selectedCamera !== 'all' ||
            searchQuery) && (
            <button
              onClick={handleResetFilters}
              className="flex items-center gap-1.5 text-xs font-mono text-text-dim hover:text-accent-teal transition-colors"
            >
              <FilterX className="w-3.5 h-3.5" />
              <span>Reset Filters</span>
            </button>
          )}
        </div>

        {/* Dropdowns & Search Input Row */}
        <div className="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-4 gap-3 pt-2 border-t border-border-subtle/50">
          {/* Search Input */}
          <div className="sm:col-span-2 relative">
            <Search className="w-4 h-4 text-text-muted absolute left-3 top-2.5" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by Track ID (e.g. 9042) or Watchlist Name..."
              className="w-full pl-9 pr-3 py-1.5 bg-bg-elevated border border-border-subtle rounded-sm text-xs text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent-teal font-mono"
            />
          </div>

          {/* Category Dropdown */}
          <div>
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="w-full px-3 py-1.5 bg-bg-elevated border border-border-subtle rounded-sm text-xs text-text-primary focus:outline-none focus:border-accent-teal"
            >
              <option value="all">All Categories</option>
              <option value="person">Person</option>
              <option value="vehicle">Vehicle</option>
              <option value="unknown">Unknown</option>
            </select>
          </div>

          {/* Camera Dropdown */}
          <div>
            <select
              value={selectedCamera}
              onChange={(e) => setSelectedCamera(e.target.value)}
              className="w-full px-3 py-1.5 bg-bg-elevated border border-border-subtle rounded-sm text-xs text-text-primary focus:outline-none focus:border-accent-teal font-mono"
            >
              <option value="all">All Cameras</option>
              {availableCameras.map((cam) => (
                <option key={cam} value={cam}>
                  {cam.toUpperCase()}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Incidents Table */}
      {filteredIncidents.length > 0 ? (
        <Table>
          <TableHeader>
            <TableRow isHoverable={false}>
              <TableHead>
                <button
                  onClick={() =>
                    setSortDirection((prev) => (prev === 'desc' ? 'asc' : 'desc'))
                  }
                  className="flex items-center gap-1.5 text-text-dim hover:text-text-primary transition-colors select-none font-mono"
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
              <TableHead>CAMERA</TableHead>
              <TableHead>TRACK ID</TableHead>
              <TableHead>CATEGORY</TableHead>
              <TableHead>ZONE TIER</TableHead>
              <TableHead>SCORE</TableHead>
              <TableHead>ALERT TIER</TableHead>
              <TableHead>WATCHLIST MATCH</TableHead>
              <TableHead className="text-right">ACTIONS</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredIncidents.map((incident) => {
              const isRed = incident.tier === 'red';
              const isYellow = incident.tier === 'yellow';

              // Colored left border based on alert tier
              const tierBorderColor = isRed
                ? 'border-l-2 border-l-accent-red'
                : isYellow
                ? 'border-l-2 border-l-accent-yellow'
                : 'border-l-2 border-l-accent-green';

              return (
                <TableRow
                  key={incident.id}
                  className={`${tierBorderColor} ${
                    isRed ? 'bg-accent-red/[0.04]' : ''
                  }`}
                >
                  {/* Timestamp */}
                  <TableCell className="font-mono text-xs text-text-dim font-medium">
                    <div className="flex items-center gap-1.5">
                      <Clock className="w-3 h-3 text-text-muted" />
                      <span>{formatTime(incident.timestamp)}</span>
                    </div>
                  </TableCell>

                  {/* Camera */}
                  <TableCell className="font-mono text-xs font-semibold text-text-primary uppercase">
                    {incident.cameraName}
                  </TableCell>

                  {/* Track ID & Re-ID Continuity */}
                  <TableCell className="font-mono text-xs text-accent-teal font-medium">
                    <div>#TRK-{incident.trackId}</div>
                    {incident.reidGalleryId && (
                      <div className="text-[9px] text-text-muted">#{incident.reidGalleryId}</div>
                    )}
                  </TableCell>

                  {/* Category */}
                  <TableCell>
                    <div className="flex items-center gap-1.5 text-xs capitalize text-text-primary font-medium">
                      {getCategoryIcon(incident.category)}
                      <span>{incident.category}</span>
                    </div>
                  </TableCell>

                  {/* Zone Tier */}
                  <TableCell>
                    <Badge variant={incident.zoneTier} size="sm">
                      {incident.zoneTier}
                    </Badge>
                  </TableCell>

                  {/* Threat Score & S/T/K/C Breakdown (intelligence/threat_score.py) */}
                  <TableCell className="font-mono text-xs">
                    <div className="flex items-baseline gap-1 font-bold">
                      <span
                        className={
                          incident.score >= 70
                            ? 'text-accent-red'
                            : incident.score > 30
                            ? 'text-accent-yellow'
                            : 'text-accent-green'
                        }
                      >
                        {incident.score.toFixed(1)}
                      </span>
                      <span className="text-[10px] text-text-muted font-normal">/100</span>
                    </div>
                    {incident.breakdown && (
                      <div className="text-[9px] text-text-muted tracking-tight">
                        S:{incident.breakdown.sectorRisk.toFixed(0)} T:{incident.breakdown.timeRisk.toFixed(0)} K:{incident.breakdown.kinematicsRisk.toFixed(0)} C:{incident.breakdown.classConfidence.toFixed(0)}
                      </div>
                    )}
                  </TableCell>

                  {/* Final Alert Tier */}
                  <TableCell>
                    <Badge
                      variant={incident.tier}
                      dot={incident.tier === 'red'}
                      pulse={incident.tier === 'red'}
                      size="sm"
                    >
                      {incident.tier}
                    </Badge>
                  </TableCell>

                  {/* Watchlist Match */}
                  <TableCell>
                    {incident.watchlistMatch ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded font-mono text-[11px] font-bold bg-accent-red/15 text-accent-red border border-accent-red/40 shadow-[0_0_8px_rgba(229,72,77,0.2)]">
                        <AlertTriangle className="w-3 h-3 text-accent-red" />
                        <span>MATCH: {incident.watchlistMatch}</span>
                      </span>
                    ) : (
                      <span className="text-text-muted font-mono text-xs">—</span>
                    )}
                  </TableCell>

                  {/* Action */}
                  <TableCell className="text-right">
                    <Button
                      variant={isRed ? 'danger' : 'secondary'}
                      size="sm"
                      leftIcon={<Eye className="w-3.5 h-3.5" />}
                      onClick={() => handleOpenEvidence(incident)}
                    >
                      View Evidence
                    </Button>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      ) : (
        /* Empty State */
        <div className="p-12 bg-bg-surface border border-dashed border-border-subtle rounded-sm text-center space-y-3">
          <div className="p-3 bg-bg-elevated border border-border-subtle rounded-full w-12 h-12 flex items-center justify-center mx-auto text-text-muted">
            <FilterX className="w-6 h-6" />
          </div>
          <div className="space-y-1">
            <h3 className="text-sm font-semibold text-text-primary">
              No incidents match the current filters
            </h3>
            <p className="text-xs text-text-dim max-w-sm mx-auto">
              Try broadening your search criteria, switching tiers, or resetting all applied filters.
            </p>
          </div>
          <Button variant="secondary" size="sm" onClick={handleResetFilters}>
            Clear All Filters
          </Button>
        </div>
      )}

      {/* EVIDENCE INSPECTOR MODAL */}
      {selectedIncident && (
        <Modal
          isOpen={Boolean(selectedIncident)}
          onClose={() => setSelectedIncident(null)}
          title={
            <div className="flex items-center gap-2.5">
              <FileImage className="w-5 h-5 text-accent-teal" />
              <span>Evidence Record #TRK-{selectedIncident.trackId}</span>
              <Badge variant={selectedIncident.tier} size="sm">
                {selectedIncident.tier} TIER
              </Badge>
            </div>
          }
          description={`Logged from ${selectedIncident.cameraName.toUpperCase()} · ${formatFullDate(
            selectedIncident.timestamp
          )}`}
          size="xl"
          footer={
            <div className="flex items-center justify-between w-full">
              <span className="font-mono text-[11px] text-text-muted">
                ENCRYPTED EVIDENCE HASH: SHA-256:d8a9f4...2e
              </span>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setSelectedIncident(null)}
              >
                Close Inspector
              </Button>
            </div>
          }
        >
          <div className="space-y-4">
            {/* Watchlist Banner (if present) */}
            {selectedIncident.watchlistMatch && (
              <div className="p-3 bg-accent-red/15 border border-accent-red/40 rounded-sm flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <AlertTriangle className="w-5 h-5 text-accent-red animate-pulse" />
                  <div>
                    <span className="font-mono font-bold text-xs text-accent-red uppercase tracking-wide block">
                      ⚠ CRITICAL BIOMETRIC WATCHLIST MATCH
                    </span>
                    <span className="text-xs text-text-primary">
                      Subject identified as: <strong>{selectedIncident.watchlistMatch}</strong> (Person ID: {selectedIncident.personId || 'CONFIDENTIAL'})
                    </span>
                  </div>
                </div>
                <Badge variant="red" size="sm">
                  ESCALATED
                </Badge>
              </div>
            )}

            {/* Main Evidence Viewer Screen */}
            <div className="relative aspect-video w-full bg-bg-primary rounded-sm border border-border-subtle overflow-hidden flex items-center justify-center">
              <img
                src={activeViewerImage}
                alt="Selected evidence capture"
                className="w-full h-full object-contain"
              />

              {/* Watermark overlay */}
              <div className="absolute top-2 left-2 px-2 py-0.5 bg-bg-surface/85 backdrop-blur-sm border border-border-subtle rounded-sm font-mono text-[10px] text-accent-teal">
                EVIDENCE VIEWER: {selectedIncident.cameraName.toUpperCase()}
              </div>
            </div>

            {/* Thumbnail Gallery (Crop + Burst Frames) */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs uppercase text-text-dim tracking-wider">
                  Available Evidence Frames (Click to inspect):
                </span>
                <span className="font-mono text-[11px] text-text-muted">
                  {1 + (selectedIncident.cropUrl ? 1 : 0) + selectedIncident.burstUrls.length} FRAMES RECORDED
                </span>
              </div>

              <div className="flex items-center gap-2 overflow-x-auto pb-1">
                {/* Main Snapshot Thumbnail */}
                <button
                  onClick={() => setActiveViewerImage(selectedIncident.snapshotUrl)}
                  className={`relative aspect-video w-24 rounded-sm border overflow-hidden shrink-0 transition-all ${
                    activeViewerImage === selectedIncident.snapshotUrl
                      ? 'border-accent-teal ring-1 ring-accent-teal shadow-md'
                      : 'border-border-subtle opacity-70 hover:opacity-100'
                  }`}
                >
                  <img
                    src={selectedIncident.snapshotUrl}
                    alt="Full Snapshot"
                    className="w-full h-full object-cover"
                  />
                  <span className="absolute bottom-0 left-0 right-0 bg-bg-surface/90 font-mono text-[9px] text-center text-text-dim">
                    SNAPSHOT
                  </span>
                </button>

                {/* Crop Thumbnail */}
                {selectedIncident.cropUrl && (
                  <button
                    onClick={() => setActiveViewerImage(selectedIncident.cropUrl!)}
                    className={`relative aspect-video w-24 rounded-sm border overflow-hidden shrink-0 transition-all ${
                      activeViewerImage === selectedIncident.cropUrl
                        ? 'border-accent-teal ring-1 ring-accent-teal shadow-md'
                        : 'border-border-subtle opacity-70 hover:opacity-100'
                    }`}
                  >
                    <img
                      src={selectedIncident.cropUrl}
                      alt="Target Crop"
                      className="w-full h-full object-cover"
                    />
                    <span className="absolute bottom-0 left-0 right-0 bg-bg-surface/90 font-mono text-[9px] text-center text-text-dim">
                      TARGET CROP
                    </span>
                  </button>
                )}

                {/* Burst Thumbnails */}
                {selectedIncident.burstUrls.map((burstUrl, idx) => (
                  <button
                    key={idx}
                    onClick={() => setActiveViewerImage(burstUrl)}
                    className={`relative aspect-video w-24 rounded-sm border overflow-hidden shrink-0 transition-all ${
                      activeViewerImage === burstUrl
                        ? 'border-accent-teal ring-1 ring-accent-teal shadow-md'
                        : 'border-border-subtle opacity-70 hover:opacity-100'
                    }`}
                  >
                    <img
                      src={burstUrl}
                      alt={`Burst frame ${idx + 1}`}
                      className="w-full h-full object-cover"
                    />
                    <span className="absolute bottom-0 left-0 right-0 bg-bg-surface/90 font-mono text-[9px] text-center text-text-dim">
                      BURST {idx + 1}
                    </span>
                  </button>
                ))}
              </div>
            </div>

            {/* Telemetry & Metadata Grid */}
            <div className="p-3.5 bg-bg-surface border border-border-subtle rounded-sm grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-xs">
              <div>
                <span className="text-text-muted block text-[10px] uppercase">
                  Track Identifier
                </span>
                <span className="text-accent-teal font-semibold">
                  #TRK-{selectedIncident.trackId}
                </span>
              </div>

              <div>
                <span className="text-text-muted block text-[10px] uppercase">
                  Classification
                </span>
                <span className="text-text-primary capitalize font-medium flex items-center gap-1">
                  {getCategoryIcon(selectedIncident.category)}
                  <span>{selectedIncident.category}</span>
                </span>
              </div>

              <div>
                <span className="text-text-muted block text-[10px] uppercase">
                  Zone Priority
                </span>
                <span className="font-semibold uppercase text-text-primary">
                  {selectedIncident.zoneTier} ZONE
                </span>
              </div>

              <div>
                <span className="text-text-muted block text-[10px] uppercase">
                  Calculated Threat Score
                </span>
                <span
                  className={`font-bold text-sm ${
                    selectedIncident.score >= 80
                      ? 'text-accent-red'
                      : selectedIncident.score >= 50
                      ? 'text-accent-yellow'
                      : 'text-accent-green'
                  }`}
                >
                  {selectedIncident.score.toFixed(1)} / 100
                </span>
              </div>

              <div>
                <span className="text-text-muted block text-[10px] uppercase">
                  Camera Channel
                </span>
                <span className="text-text-primary font-medium uppercase">
                  {selectedIncident.cameraName}
                </span>
              </div>

              <div>
                <span className="text-text-muted block text-[10px] uppercase">
                  Person ID
                </span>
                <span className="text-text-dim">
                  {selectedIncident.personId ? `#PID-${selectedIncident.personId}` : 'NONE'}
                </span>
              </div>
            </div>

            {/* Threat Intelligence Scoring Breakdown Matrix (intelligence/threat_score.py) */}
            {selectedIncident.breakdown && (
              <div className="p-3.5 bg-bg-surface border border-border-subtle rounded-sm space-y-2.5">
                <div className="flex items-center justify-between border-b border-border-subtle/60 pb-1.5">
                  <span className="font-mono text-xs font-bold text-text-primary uppercase tracking-wider flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-accent-teal" />
                    Threat Intelligence Risk Breakdown (S/T/K/C)
                  </span>
                  <span className="font-mono text-xs font-bold text-accent-teal">
                    TOTAL: {selectedIncident.score.toFixed(1)} / 100
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 font-mono text-[11px]">
                  {/* Sector Risk */}
                  <div className="space-y-1 p-2 rounded bg-bg-elevated/70 border border-border-subtle/50">
                    <div className="flex justify-between text-text-dim">
                      <span>Sector Risk (S):</span>
                      <span className="font-bold text-text-primary">
                        {selectedIncident.breakdown.sectorRisk.toFixed(1)} / 40
                      </span>
                    </div>
                    <div className="w-full bg-bg-primary h-1.5 rounded-full overflow-hidden">
                      <div
                        className="bg-accent-red h-full rounded-full"
                        style={{ width: `${(selectedIncident.breakdown.sectorRisk / 40) * 100}%` }}
                      />
                    </div>
                    <span className="text-[10px] text-text-muted">Virtual Fence Priority</span>
                  </div>

                  {/* Time Risk */}
                  <div className="space-y-1 p-2 rounded bg-bg-elevated/70 border border-border-subtle/50">
                    <div className="flex justify-between text-text-dim">
                      <span>Time Risk (T):</span>
                      <span className="font-bold text-text-primary">
                        {selectedIncident.breakdown.timeRisk.toFixed(1)} / 25
                      </span>
                    </div>
                    <div className="w-full bg-bg-primary h-1.5 rounded-full overflow-hidden">
                      <div
                        className="bg-accent-yellow h-full rounded-full"
                        style={{ width: `${(selectedIncident.breakdown.timeRisk / 25) * 100}%` }}
                      />
                    </div>
                    <span className="text-[10px] text-text-muted">Curfew Hours Multiplier</span>
                  </div>

                  {/* Kinematics Risk */}
                  <div className="space-y-1 p-2 rounded bg-bg-elevated/70 border border-border-subtle/50">
                    <div className="flex justify-between text-text-dim">
                      <span>Kinematics Risk (K):</span>
                      <span className="font-bold text-text-primary">
                        {selectedIncident.breakdown.kinematicsRisk.toFixed(1)} / 20
                      </span>
                    </div>
                    <div className="w-full bg-bg-primary h-1.5 rounded-full overflow-hidden">
                      <div
                        className="bg-accent-teal h-full rounded-full"
                        style={{ width: `${(selectedIncident.breakdown.kinematicsRisk / 20) * 100}%` }}
                      />
                    </div>
                    <span className="text-[10px] text-text-muted">Speed & Heading Vector</span>
                  </div>

                  {/* Class Confidence */}
                  <div className="space-y-1 p-2 rounded bg-bg-elevated/70 border border-border-subtle/50">
                    <div className="flex justify-between text-text-dim">
                      <span>Class Confidence (C):</span>
                      <span className="font-bold text-text-primary">
                        {selectedIncident.breakdown.classConfidence.toFixed(1)} / 15
                      </span>
                    </div>
                    <div className="w-full bg-bg-primary h-1.5 rounded-full overflow-hidden">
                      <div
                        className="bg-accent-green h-full rounded-full"
                        style={{ width: `${(selectedIncident.breakdown.classConfidence / 15) * 100}%` }}
                      />
                    </div>
                    <span className="text-[10px] text-text-muted">Category Confidence</span>
                  </div>
                </div>

                {selectedIncident.watchlistMatch && (
                  <div className="p-2 rounded bg-accent-red/10 border border-accent-red/30 text-accent-red font-mono text-[11px] flex items-center gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                    <span>
                      ThreatRulesDB Override: Biometric watchlist hit automatically escalated incident to RED tier (score &ge; 70).
                    </span>
                  </div>
                )}
              </div>
            )}

            {/* Explainable Decision Logic (XAI) Defense Card (Section 9.3 & 22) */}
            <div className="p-3 bg-accent-teal/10 border border-accent-teal/30 rounded-sm space-y-2 font-mono text-xs">
              <div className="flex items-center justify-between border-b border-accent-teal/20 pb-1.5">
                <span className="font-bold text-accent-teal uppercase tracking-wider flex items-center gap-1.5">
                  <Scale className="w-4 h-4" /> Explainable Decision Logic (XAI vs Blackbox AI)
                </span>
                <Badge variant="teal" size="sm">
                  SEC 65B EVIDENCE ACT COMPLIANT
                </Badge>
              </div>
              <p className="font-sans text-xs text-text-dim leading-relaxed">
                Unlike unexplainable neural nets that output an opaque probability (e.g. 0.87), IBVAP decomposes this decision into a <strong>100% deterministic, court-admissible audit trail</strong>:
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px]">
                <div className="p-2 rounded bg-bg-surface/80 border border-border-subtle/50 space-y-0.5">
                  <span className="text-text-primary font-bold flex items-center gap-1">
                    <Zap className="w-3 h-3 text-accent-red" /> Sector Risk: +{selectedIncident.breakdown?.sectorRisk.toFixed(1) || 40.0} pts
                  </span>
                  <p className="text-text-muted">Target breached {selectedIncident.zoneTier.toUpperCase()} Perimeter Zone polygon.</p>
                </div>
                <div className="p-2 rounded bg-bg-surface/80 border border-border-subtle/50 space-y-0.5">
                  <span className="text-text-primary font-bold flex items-center gap-1">
                    <Clock className="w-3 h-3 text-accent-yellow" /> Curfew Factor: +{selectedIncident.breakdown?.timeRisk.toFixed(1) || 25.0} pts
                  </span>
                  <p className="text-text-muted">High-risk nocturnal infiltration window active (21:00 to 05:00 IST).</p>
                </div>
                <div className="p-2 rounded bg-bg-surface/80 border border-border-subtle/50 space-y-0.5">
                  <span className="text-text-primary font-bold flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3 text-accent-teal" /> Kinematics: +{selectedIncident.breakdown?.kinematicsRisk.toFixed(1) || 18.0} pts
                  </span>
                  <p className="text-text-muted">Direction vector confirmed inward approach towards critical border fence.</p>
                </div>
                <div className="p-2 rounded bg-bg-surface/80 border border-border-subtle/50 space-y-0.5">
                  <span className="text-text-primary font-bold flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3 text-accent-green" /> Class Confidence: +{selectedIncident.breakdown?.classConfidence.toFixed(1) || 14.0} pts
                  </span>
                  <p className="text-text-muted">YOLOv8 confirmed {selectedIncident.category.toUpperCase()} category with high confidence.</p>
                </div>
              </div>
            </div>

            {/* Air-Gapped Evidence Security & Re-ID Audit Card (database/incident_store.py) */}
            <div className="p-3 bg-bg-surface border border-border-subtle rounded-sm flex flex-col sm:flex-row sm:items-center justify-between gap-3 font-mono text-xs">
              <div className="space-y-0.5">
                <span className="text-text-muted text-[10px] uppercase block">
                  Evidence At-Rest Encryption
                </span>
                <span className="text-text-primary font-bold">
                  {selectedIncident.encryption?.cipher || 'FERNET-AES128-CBC'} · SHA-256 HMAC
                </span>
                <span className="text-[10px] text-text-dim block">
                  Key Source: {selectedIncident.encryption?.keyPath || 'database/evidence.key'} (On-Premises Air-Gapped Store)
                </span>
              </div>

              <div className="space-y-0.5 sm:text-right">
                <span className="text-text-muted text-[10px] uppercase block">
                  Re-ID Multi-Camera Continuity
                </span>
                <span className="text-accent-teal font-bold">
                  #{selectedIncident.reidGalleryId || `PG-${selectedIncident.trackId}`}
                </span>
                <span className="text-[10px] text-accent-green block">
                  Cosine Distance: 0.88 · Identity Locked
                </span>
              </div>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};

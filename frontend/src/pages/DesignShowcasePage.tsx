import React, { useState } from 'react';
import {
  Button,
  Badge,
  Card,
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
  Modal,
  Tabs,
} from '@/components/ui';
import {
  Shield,
  ShieldAlert,
  ShieldCheck,
  Video,
  Activity,
  AlertTriangle,
  Radio,
  Layers,
  Terminal,
  Clock,
  Eye,
  Crosshair,
} from 'lucide-react';

export const DesignShowcasePage: React.FC = () => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('components');
  const [activePillTab, setActivePillTab] = useState('all');
  const [clickCount, setClickCount] = useState(0);

  const sampleTelemetry = [
    {
      id: 'TRK-9042',
      cam: 'cam0-sector-north',
      time: '14:22:08.412',
      category: 'PERSON',
      tier: 'red' as const,
      score: '94.2',
      status: 'CRITICAL INTRUSION',
    },
    {
      id: 'TRK-9041',
      cam: 'cam2-outpost-east',
      time: '14:21:45.109',
      category: 'VEHICLE',
      tier: 'yellow' as const,
      score: '68.0',
      status: 'PERIMETER CAUTION',
    },
    {
      id: 'TRK-9040',
      cam: 'cam1-checkpost-bravo',
      time: '14:19:12.875',
      category: 'PERSON',
      tier: 'green' as const,
      score: '12.5',
      status: 'AUTHORIZED PATROL',
    },
    {
      id: 'TRK-9039',
      cam: 'cam3-bop-delta',
      time: '14:15:30.004',
      category: 'UNKNOWN',
      tier: 'neutral' as const,
      score: '04.1',
      status: 'LOW-LIGHT SHADOW',
    },
  ];

  const palette = [
    { name: 'bg-primary', hex: '#0a0f0d', border: '#25322e', text: '#e6ece9' },
    { name: 'bg-surface', hex: '#111917', border: '#25322e', text: '#e6ece9' },
    { name: 'bg-elevated', hex: '#16201d', border: '#25322e', text: '#e6ece9' },
    { name: 'border-subtle', hex: '#25322e', border: '#5c6f68', text: '#8fa39b' },
    { name: 'text-muted', hex: '#5c6f68', border: '#25322e', text: '#0a0f0d' },
    { name: 'text-dim', hex: '#8fa39b', border: '#25322e', text: '#0a0f0d' },
    { name: 'text-primary', hex: '#e6ece9', border: '#25322e', text: '#0a0f0d' },
    { name: 'accent-teal', hex: '#5fd6c4', border: '#5fd6c4', text: '#0a0f0d' },
    { name: 'accent-green', hex: '#4fbf7a', border: '#4fbf7a', text: '#0a0f0d' },
    { name: 'accent-green-deep', hex: '#2f6e64', border: '#2f6e64', text: '#e6ece9' },
    { name: 'accent-yellow', hex: '#e6c34a', border: '#e6c34a', text: '#0a0f0d' },
    { name: 'accent-red', hex: '#e5484d', border: '#e5484d', text: '#e6ece9' },
  ];

  return (
    <div className="min-h-screen bg-bg-primary bg-tactical-grid text-text-primary p-6 md:p-10">
      <div className="max-w-7xl mx-auto space-y-8">
        {/* Top Tactical Banner */}
        <header className="border-b border-border-subtle pb-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-accent-teal/10 border border-accent-teal/30 rounded-sm text-accent-teal">
                <Shield className="w-6 h-6" />
              </div>
              <div>
                <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
                  <span>IBVAP</span>
                  <span className="text-text-muted font-normal text-lg">/</span>
                  <span className="text-accent-teal font-mono text-sm tracking-wider uppercase">
                    Command Center
                  </span>
                </h1>
                <p className="text-xs text-text-dim">
                  Intelligent Border Video Analytics Platform · Design System & UI Shell (Phase 0)
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Badge variant="green" dot pulse size="md">
              SYSTEM ONLINE
            </Badge>
            <Badge variant="neutral" size="md">
              <span className="text-text-dim font-mono">PHASE 0 · SCAFFOLD</span>
            </Badge>
            <div className="hidden lg:flex items-center gap-2 px-3 py-1 bg-bg-surface border border-border-subtle rounded-sm font-mono text-xs text-text-dim">
              <Clock className="w-3.5 h-3.5 text-accent-teal" />
              <span>AIR-GAPPED MODE READY</span>
            </div>
          </div>
        </header>

        {/* Navigation Tabs (Previewing Tabs primitive) */}
        <div className="space-y-4">
          <Tabs
            activeTab={activeTab}
            onChange={setActiveTab}
            items={[
              { id: 'components', label: 'UI Primitives Showcase', icon: <Layers className="w-3.5 h-3.5" /> },
              { id: 'palette', label: 'Color & Typography Tokens', icon: <Terminal className="w-3.5 h-3.5" /> },
              { id: 'telemetry', label: 'Tactical Telemetry Table', icon: <Crosshair className="w-3.5 h-3.5" /> },
            ]}
          />
        </div>

        {/* Tab 1: UI Primitives Showcase */}
        {activeTab === 'components' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Buttons Showcase */}
            <Card
              title="Button Component Variants"
              subtitle="Flat tactical style, 4 semantic variants, loading & icon states"
              variant="default"
              action={
                <span className="font-mono text-[10px] text-text-muted">
                  components/ui/Button.tsx
                </span>
              }
            >
              <div className="space-y-4">
                <div className="flex flex-wrap items-center gap-3">
                  <Button
                    variant="primary"
                    leftIcon={<ShieldCheck className="w-4 h-4" />}
                    onClick={() => setClickCount((c) => c + 1)}
                  >
                    Primary Action ({clickCount})
                  </Button>

                  <Button
                    variant="secondary"
                    leftIcon={<Video className="w-4 h-4" />}
                  >
                    Secondary
                  </Button>

                  <Button variant="ghost" leftIcon={<Radio className="w-4 h-4" />}>
                    Ghost Button
                  </Button>

                  <Button
                    variant="danger"
                    leftIcon={<ShieldAlert className="w-4 h-4" />}
                    onClick={() => setIsModalOpen(true)}
                  >
                    Danger Alert (Open Modal)
                  </Button>
                </div>

                <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-border-subtle/40">
                  <Button variant="primary" size="sm">
                    Small
                  </Button>
                  <Button variant="secondary" size="md">
                    Medium
                  </Button>
                  <Button variant="secondary" size="lg">
                    Large Size
                  </Button>
                  <Button variant="primary" size="sm" isLoading>
                    Processing
                  </Button>
                  <Button variant="secondary" size="sm" disabled>
                    Disabled State
                  </Button>
                </div>
              </div>
            </Card>

            {/* Badges Showcase */}
            <Card
              title="Badge Component (Zone Tiers & Status)"
              subtitle="Monospace security badges with pulsating live indicators"
              variant="default"
              action={
                <span className="font-mono text-[10px] text-text-muted">
                  components/ui/Badge.tsx
                </span>
              }
            >
              <div className="space-y-4">
                <div className="flex flex-wrap items-center gap-3">
                  <Badge variant="green" dot pulse>
                    GREEN ZONE / TIER 3
                  </Badge>
                  <Badge variant="yellow" dot pulse>
                    YELLOW ZONE / TIER 2
                  </Badge>
                  <Badge variant="red" dot pulse>
                    RED ZONE / TIER 1
                  </Badge>
                  <Badge variant="neutral" dot>
                    OFFLINE / STANDBY
                  </Badge>
                  <Badge variant="teal" dot>
                    AI PIPELINE ACTIVE
                  </Badge>
                </div>

                <div className="pt-3 border-t border-border-subtle/40 space-y-2">
                  <p className="text-xs text-text-dim">
                    Tier Meaning per IBVAP Spec:
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs font-mono">
                    <div className="p-2 bg-accent-green/5 border border-accent-green/20 rounded-sm">
                      <span className="text-accent-green font-bold block">GREEN</span>
                      <span className="text-text-dim text-[11px]">Normal activity / curfew sensitive</span>
                    </div>
                    <div className="p-2 bg-accent-yellow/5 border border-accent-yellow/20 rounded-sm">
                      <span className="text-accent-yellow font-bold block">YELLOW</span>
                      <span className="text-text-dim text-[11px]">Direction caution / perimeter alert</span>
                    </div>
                    <div className="p-2 bg-accent-red/5 border border-accent-red/20 rounded-sm">
                      <span className="text-accent-red font-bold block">RED</span>
                      <span className="text-text-dim text-[11px]">High threat / instant intrusion trigger</span>
                    </div>
                  </div>
                </div>
              </div>
            </Card>

            {/* Card & Modal Showcase */}
            <Card
              title="Tactical Cards & Modals"
              subtitle="Elevated container panels and focus-trapped dialog overlays"
              variant="elevated"
              action={
                <Button
                  variant="secondary"
                  size="sm"
                  leftIcon={<Eye className="w-3.5 h-3.5 text-accent-teal" />}
                  onClick={() => setIsModalOpen(true)}
                >
                  Test Modal
                </Button>
              }
              footer={
                <div className="flex items-center justify-between w-full font-mono text-[11px]">
                  <span>LAT: 32°43'12.4"N · LONG: 74°52'31.8"E</span>
                  <span className="text-accent-teal">SECTOR SECURE</span>
                </div>
              }
            >
              <div className="space-y-3">
                <p className="text-xs text-text-dim leading-relaxed">
                  IBVAP transforms conventional border CCTV cameras into an AI-powered surveillance network.
                  Edge pipelines perform human/vehicle detection, virtual fence intrusion analysis, and real-time
                  threat scoring directly on live streams.
                </p>

                <div className="p-3 bg-bg-surface border border-border-subtle rounded-sm flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <Activity className="w-4 h-4 text-accent-teal" />
                    <span className="text-xs font-mono text-text-primary">
                      Threat Score Engine: S_sector + T_time + K_kinematics + C_class
                    </span>
                  </div>
                  <Badge variant="teal" size="sm">0 - 100 PTS</Badge>
                </div>
              </div>
            </Card>

            {/* Tabs & Pill Filter Showcase */}
            <Card
              title="Interactive Filter Switcher (Tabs)"
              subtitle="Pill-style switcher used for category and tier filtering"
              variant="default"
              action={
                <span className="font-mono text-[10px] text-text-muted">
                  components/ui/Tabs.tsx
                </span>
              }
            >
              <div className="space-y-4">
                <div>
                  <label className="text-xs text-text-dim block mb-2 font-mono uppercase">
                    Filter by Category (Pill Variant):
                  </label>
                  <Tabs
                    variant="pill"
                    activeTab={activePillTab}
                    onChange={setActivePillTab}
                    items={[
                      { id: 'all', label: 'All Incidents', count: 18 },
                      { id: 'person', label: 'Persons', count: 12 },
                      { id: 'vehicle', label: 'Vehicles', count: 4 },
                      { id: 'unknown', label: 'Unknown', count: 2 },
                    ]}
                  />
                </div>

                <div className="p-3 bg-bg-elevated border border-border-subtle rounded-sm font-mono text-xs text-text-dim">
                  Selected Filter: <span className="text-accent-teal font-semibold">{activePillTab.toUpperCase()}</span>
                </div>
              </div>
            </Card>
          </div>
        )}

        {/* Tab 2: Color Palette & Typography Tokens */}
        {activeTab === 'palette' && (
          <div className="space-y-6">
            <Card
              title="Design Tokens Palette"
              subtitle="Semantic tokens configured in tailwind.config.js & src/styles/index.css"
            >
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
                {palette.map((item) => (
                  <div
                    key={item.name}
                    className="p-3 rounded-sm border border-border-subtle bg-bg-surface flex flex-col justify-between h-28"
                  >
                    <div
                      className="w-full h-8 rounded-sm border"
                      style={{
                        backgroundColor: item.hex,
                        borderColor: item.border,
                      }}
                    />
                    <div className="mt-2">
                      <div className="text-xs font-semibold text-text-primary truncate">
                        {item.name}
                      </div>
                      <div className="font-mono text-[11px] text-text-dim">
                        {item.hex}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </Card>

            <Card
              title="Typography System"
              subtitle="Inter for UI structure & JetBrains Mono for telemetry / coordinates"
            >
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-2 p-4 bg-bg-surface rounded-sm border border-border-subtle">
                  <span className="text-xs font-mono uppercase text-accent-teal tracking-wider">
                    UI Font: Inter
                  </span>
                  <div className="text-xl font-bold">Inter Bold (Headings & Page Titles)</div>
                  <div className="text-base font-semibold">Inter Semibold (Card Titles & Nav Links)</div>
                  <div className="text-sm font-normal text-text-dim leading-relaxed">
                    Inter Regular: High-legibility sans-serif optimized for tactical command consoles and dense surveillance dashboards.
                  </div>
                </div>

                <div className="space-y-2 p-4 bg-bg-surface rounded-sm border border-border-subtle font-mono">
                  <span className="text-xs uppercase text-accent-teal tracking-wider">
                    Telemetry Font: JetBrains Mono
                  </span>
                  <div className="text-lg font-bold text-accent-teal">
                    FPS: 29.8 · LATENCY: 34ms · THREAT: 89.2
                  </div>
                  <div className="text-xs text-text-dim">
                    TRACK_ID: #TK-84910 · PERSON_ID: 104 · BBOX: [142, 88, 320, 480]
                  </div>
                  <div className="text-xs text-accent-yellow">
                    TIMESTAMP: 2026-09-07T16:09:42.108Z · ZONE: RED-ALPHA
                  </div>
                </div>
              </div>
            </Card>
          </div>
        )}

        {/* Tab 3: Telemetry Table */}
        {activeTab === 'telemetry' && (
          <div className="space-y-4">
            <Card
              title="Surveillance Telemetry Feed"
              subtitle="Verified with components/ui/Table.tsx primitive (striped hover, monospace columns)"
              action={
                <Badge variant="teal" dot pulse>
                  LIVE LOGS
                </Badge>
              }
            >
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Track ID</TableHead>
                    <TableHead>Camera Source</TableHead>
                    <TableHead>Timestamp</TableHead>
                    <TableHead>Category</TableHead>
                    <TableHead>Threat Score</TableHead>
                    <TableHead>Zone Tier</TableHead>
                    <TableHead>Action Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sampleTelemetry.map((row) => (
                    <TableRow key={row.id}>
                      <TableCell className="font-mono font-semibold text-accent-teal">
                        {row.id}
                      </TableCell>
                      <TableCell className="font-mono text-text-dim">
                        {row.cam}
                      </TableCell>
                      <TableCell className="font-mono text-xs text-text-muted">
                        {row.time}
                      </TableCell>
                      <TableCell className="text-xs uppercase font-medium">
                        {row.category}
                      </TableCell>
                      <TableCell className="font-mono font-semibold">
                        <span
                          className={
                            Number(row.score) > 80
                              ? 'text-accent-red'
                              : Number(row.score) > 50
                              ? 'text-accent-yellow'
                              : 'text-accent-green'
                          }
                        >
                          {row.score} / 100
                        </span>
                      </TableCell>
                      <TableCell>
                        <Badge variant={row.tier} size="sm">
                          {row.tier}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-xs text-text-dim">
                        {row.status}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Card>
          </div>
        )}

        {/* Interactive Modal Primitive Test */}
        <Modal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          title="Tactical Alert Verification"
          description="High-priority border intrusion event simulation"
          footer={
            <>
              <Button variant="ghost" size="sm" onClick={() => setIsModalOpen(false)}>
                Dismiss
              </Button>
              <Button
                variant="danger"
                size="sm"
                leftIcon={<AlertTriangle className="w-4 h-4" />}
                onClick={() => setIsModalOpen(false)}
              >
                Acknowledge Threat
              </Button>
            </>
          }
        >
          <div className="space-y-3">
            <div className="p-3 bg-accent-red/10 border border-accent-red/30 rounded-sm">
              <div className="flex items-center gap-2 text-accent-red font-semibold text-sm">
                <AlertTriangle className="w-4 h-4" />
                <span>RED TIER ALERT · CAM0 (NORTH POST)</span>
              </div>
              <p className="text-xs text-text-dim mt-1">
                Virtual fence breach detected in restricted zone sector A-4. Real-time threat score: 94.2.
              </p>
            </div>
            <div className="font-mono text-xs text-text-dim space-y-1">
              <div>TRACK_ID: TRK-9042</div>
              <div>CLASSIFICATION: PERSON (UNAUTHORIZED)</div>
              <div>DIRECTION: INWARD (PERIMETER BREACH)</div>
            </div>
          </div>
        </Modal>

        {/* Phase 0 Completion Footer */}
        <footer className="border-t border-border-subtle pt-4 flex flex-col sm:flex-row sm:items-center justify-between text-xs text-text-dim gap-2">
          <div>
            IBVAP Frontend Phase 0: Scaffold & Design System Verified.
          </div>
          <div className="font-mono text-text-muted">
            READY FOR PHASE 1: APP SHELL (SIDEBAR, TOPBAR, ROUTING)
          </div>
        </footer>
      </div>
    </div>
  );
};

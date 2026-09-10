import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { mockIncidents } from '@/lib/mockIncidents';
import { useAlerts } from '@/components/alerts/AlertProvider';
import {
  getDashboardStats,
  getHourlyThreatTimeline,
  getRealtimeThreatStream,
} from '@/lib/analyticsUtils';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts';
import {
  Activity,
  ShieldAlert,
  AlertTriangle,
  Video,
  ArrowRight,
  Clock,
  Eye,
  User,
  Car,
  HelpCircle,
  Radio,
  Zap,
} from 'lucide-react';

// Custom Minimal Dark Tooltip for 24H Chart
const CustomDashboardTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="p-3 bg-[#080a10] border border-[#1a1e2b] rounded-xl shadow-xl text-xs space-y-2 min-w-[160px]">
        <div className="text-white font-bold border-b border-white/10 pb-1 flex items-center justify-between">
          <span>{label}</span>
          <span className="text-[10px] text-accent-teal font-mono uppercase">OBSERVATION</span>
        </div>
        <div className="space-y-1 font-medium font-mono text-[11px]">
          <div className="flex items-center justify-between text-accent-red">
            <span className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-accent-red" />
              Critical:
            </span>
            <span className="font-bold">{payload.find((p: any) => p.dataKey === 'red')?.value || 0}</span>
          </div>
          <div className="flex items-center justify-between text-accent-yellow">
            <span className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-accent-yellow" />
              Caution:
            </span>
            <span className="font-bold">{payload.find((p: any) => p.dataKey === 'yellow')?.value || 0}</span>
          </div>
          <div className="flex items-center justify-between text-accent-green">
            <span className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-accent-green" />
              Normal:
            </span>
            <span className="font-bold">{payload.find((p: any) => p.dataKey === 'green')?.value || 0}</span>
          </div>
        </div>
      </div>
    );
  }
  return null;
};

// Custom Minimal Dark Tooltip for Real-Time Alert Telemetry Stream
const CustomRealtimeTooltip = ({ active, payload }: any) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    const tierColor =
      data.tier === 'red'
        ? 'text-accent-red'
        : data.tier === 'yellow'
        ? 'text-accent-yellow'
        : 'text-accent-green';

    return (
      <div className="p-3 bg-[#080a10] border border-[#1a1e2b] rounded-xl shadow-xl text-xs space-y-1.5 min-w-[190px]">
        <div className="text-white font-bold border-b border-white/10 pb-1 flex items-center justify-between">
          <span className="font-mono text-accent-teal">#TRK-{data.trackId}</span>
          <span className="text-[10px] text-text-muted font-mono">{data.timeLabel}</span>
        </div>
        <div className="space-y-1 font-mono text-[11px]">
          <div className="flex items-center justify-between">
            <span className="text-text-dim">Camera:</span>
            <span className="font-bold text-white uppercase">{data.cameraName}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-text-dim">Category:</span>
            <span className="font-semibold text-white capitalize">{data.category}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-text-dim">Tier:</span>
            <span className={`font-bold ${tierColor}`}>{data.tier.toUpperCase()}</span>
          </div>
          <div className="flex items-center justify-between border-t border-white/10 pt-1">
            <span className="text-text-dim font-bold">Threat Score:</span>
            <span className={`font-bold text-xs ${tierColor}`}>
              {data.threatScore.toFixed(1)} / 100
            </span>
          </div>
        </div>
      </div>
    );
  }
  return null;
};

// Custom Dot to indicate exact alert tier on the real-time curve
const RenderRealtimeDot = (props: any) => {
  const { cx, cy, payload } = props;
  if (!cx || !cy) return null;

  const color =
    payload.tier === 'red'
      ? '#f02555'
      : payload.tier === 'yellow'
      ? '#f09f00'
      : '#00e077';

  return (
    <circle
      cx={cx}
      cy={cy}
      r={4}
      fill={color}
      stroke="#05070a"
      strokeWidth={1.5}
    />
  );
};

const mockCameras = [
  { id: 'cam0', name: 'Camera 01', location: 'North Perimeter Gate', fps: '30.0', status: 'online' },
  { id: 'cam1', name: 'Camera 02', location: 'East Checkpoint Bravo', fps: '30.0', status: 'online' },
  { id: 'cam2', name: 'Camera 03', location: 'South Fence Line', fps: '28.4', status: 'online' },
  { id: 'cam3', name: 'Camera 04', location: 'West Watchtower Alpha', fps: '30.2', status: 'online' },
];


export const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const { alerts, triggerDemoAlert } = useAlerts();
  const activeAlerts = alerts.length > 0 ? alerts : mockIncidents;

  // Chart view mode state: 'realtime' (stream per alert) or '24h' (hourly trend)
  const [chartMode, setChartMode] = useState<'realtime' | '24h'>('realtime');

  // Derived metrics from synchronized real-time alerts
  const stats = getDashboardStats(activeAlerts);
  const timelineData = getHourlyThreatTimeline(activeAlerts);
  const realtimeStream = getRealtimeThreatStream(activeAlerts, 14);
  const latestAlert = activeAlerts[0];

  // Top 5 most recent critical / high-threat alert detections, real-time synchronized
  const recentCriticalAlerts = activeAlerts
    .filter((i) => i.tier === 'red' || i.tier === 'yellow')
    .sort((a, b) => b.timestamp - a.timestamp)
    .slice(0, 5);

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
    <div className="space-y-5">
      {/* Top Header Row */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-1 border-b border-[#161924]">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            <span>Surveillance Overview</span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#101624] text-accent-teal border border-accent-teal/30">
              LIVE TELEMETRY
            </span>
          </h2>
          <p className="text-xs text-text-dim mt-0.5">
            Real-time perimeter telemetry & threat detection pipeline
          </p>
        </div>

        {/* Real-time alert synchronization indicator & Demo Test Controls */}
        <div className="flex flex-wrap items-center gap-2 self-start sm:self-auto">
          <div className="flex items-center gap-2 text-xs text-text-dim bg-[#0a0d14] px-3 py-1.5 rounded-lg border border-[#161924] font-mono">
            <span className="w-2 h-2 rounded-full bg-accent-green" />
            <span>REALTIME SYNC ACTIVE</span>
          </div>

          <div className="flex items-center gap-1 bg-[#0a0d14] p-1 rounded-lg border border-[#161924]">
            <span className="text-[10px] font-mono text-text-muted px-1.5 flex items-center gap-1">
              <Zap className="w-3 h-3 text-accent-yellow" />
              TEST SYNC:
            </span>
            <button
              onClick={() => triggerDemoAlert('yellow')}
              title="Trigger Caution Alert and watch graph update in real-time"
              className="px-2 py-0.5 rounded bg-accent-yellow/15 text-accent-yellow hover:bg-accent-yellow/25 border border-accent-yellow/30 font-mono text-[10px] font-semibold transition-colors"
            >
              + Caution
            </button>
            <button
              onClick={() => triggerDemoAlert('red')}
              title="Trigger Critical Alert and watch graph update in real-time"
              className="px-2 py-0.5 rounded bg-accent-red/15 text-accent-red hover:bg-accent-red/25 border border-accent-red/30 font-mono text-[10px] font-semibold transition-colors"
            >
              + Critical
            </button>
          </div>
        </div>
      </div>

      {/* 1. Row of 4 KPI Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Stat Card 1: Total Incidents */}
        <Card variant="default" className="border-t-2 border-t-accent-teal">
          <div className="flex items-start justify-between">
            <div className="space-y-1">
              <span className="text-xs font-semibold text-text-dim uppercase tracking-wider block">
                Total Events
              </span>
              <span className="text-3xl font-bold tracking-tight text-white block">
                {stats.totalIncidents}
              </span>
              <span className="text-[11px] text-text-muted flex items-center gap-1 font-medium">
                <span className="text-accent-teal font-semibold">Live</span> synchronized count
              </span>
            </div>
            <div className="w-10 h-10 rounded-xl bg-[#0e121c] border border-white/10 text-accent-teal flex items-center justify-center">
              <Activity className="w-5 h-5" />
            </div>
          </div>
        </Card>

        {/* Stat Card 2: Red Alerts */}
        <Card variant="default" className="border-t-2 border-t-accent-red">
          <div className="flex items-start justify-between">
            <div className="space-y-1">
              <span className="text-xs font-semibold text-text-dim uppercase tracking-wider block">
                Critical Threats
              </span>
              <span className="text-3xl font-bold tracking-tight text-accent-red block">
                {stats.redAlerts}
              </span>
              <span className="text-[11px] text-accent-red/80 font-medium">
                Immediate dispatch tier
              </span>
            </div>
            <div className="w-10 h-10 rounded-xl bg-[#0e121c] border border-white/10 text-accent-red flex items-center justify-center">
              <ShieldAlert className="w-5 h-5" />
            </div>
          </div>
        </Card>

        {/* Stat Card 3: Yellow Alerts */}
        <Card variant="default" className="border-t-2 border-t-accent-yellow">
          <div className="flex items-start justify-between">
            <div className="space-y-1">
              <span className="text-xs font-semibold text-text-dim uppercase tracking-wider block">
                Caution Alerts
              </span>
              <span className="text-3xl font-bold tracking-tight text-accent-yellow block">
                {stats.yellowAlerts}
              </span>
              <span className="text-[11px] text-text-muted font-medium">
                Active tracking in progress
              </span>
            </div>
            <div className="w-10 h-10 rounded-xl bg-[#0e121c] border border-white/10 text-accent-yellow flex items-center justify-center">
              <AlertTriangle className="w-5 h-5" />
            </div>
          </div>
        </Card>

        {/* Stat Card 4: Active Cameras */}
        <Card variant="default" className="border-t-2 border-t-accent-green">
          <div className="flex items-start justify-between">
            <div className="space-y-1">
              <span className="text-xs font-semibold text-text-dim uppercase tracking-wider block">
                Active Cameras
              </span>
              <span className="text-3xl font-bold tracking-tight text-accent-green block">
                {stats.activeCameras} / 4
              </span>
              <span className="text-[11px] text-accent-green font-medium flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-accent-green inline-block" />
                All channels live
              </span>
            </div>
            <div className="w-10 h-10 rounded-xl bg-[#0e121c] border border-white/10 text-accent-green flex items-center justify-center">
              <Video className="w-5 h-5" />
            </div>
          </div>
        </Card>
      </div>

      {/* 2. Real-Time Synchronized Threat Graph & Camera Feeds */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Threat Timeline Chart (8 cols) */}
        <Card
          className="lg:col-span-8"
          title={
            <div className="flex items-center gap-2">
              <Radio className="w-4 h-4 text-accent-teal" />
              <span>Threat Activity Graph</span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-accent-green/10 text-accent-green border border-accent-green/30">
                REAL-TIME SYNC
              </span>
            </div>
          }
          subtitle={
            chartMode === 'realtime'
              ? 'Synchronized live threat scores for each incoming alert stream detection'
              : 'Hourly threat density across perimeter observation zones'
          }
          action={
            <div className="flex items-center gap-3 text-xs">
              {/* Mode Toggle: Realtime vs 24H */}
              <div className="flex items-center p-0.5 rounded-lg bg-[#07090f] border border-[#161924]">
                <button
                  onClick={() => setChartMode('realtime')}
                  className={`px-2.5 py-1 rounded text-[11px] font-mono font-medium transition-colors ${
                    chartMode === 'realtime'
                      ? 'bg-[#141a29] text-white border border-white/10'
                      : 'text-text-muted hover:text-white'
                  }`}
                >
                  Live Stream
                </button>
                <button
                  onClick={() => setChartMode('24h')}
                  className={`px-2.5 py-1 rounded text-[11px] font-mono font-medium transition-colors ${
                    chartMode === '24h'
                      ? 'bg-[#141a29] text-white border border-white/10'
                      : 'text-text-muted hover:text-white'
                  }`}
                >
                  24H Trend
                </button>
              </div>

              {/* Legend */}
              <div className="hidden sm:flex items-center gap-2.5 font-semibold text-[11px]">
                <span className="flex items-center gap-1 text-accent-red">
                  <span className="w-2 h-2 rounded-full bg-accent-red" /> Critical
                </span>
                <span className="flex items-center gap-1 text-accent-yellow">
                  <span className="w-2 h-2 rounded-full bg-accent-yellow" /> Caution
                </span>
                <span className="flex items-center gap-1 text-accent-green">
                  <span className="w-2 h-2 rounded-full bg-accent-green" /> Normal
                </span>
              </div>
            </div>
          }
        >
          {/* Synchronized Alert Status Banner */}
          <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-1.5 mb-2 rounded-lg bg-[#07090f] border border-[#161924] text-xs font-mono">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-accent-green" />
              <span className="text-accent-green font-semibold">SYNCHRONIZED WITH ALERT PIPELINE</span>
              <span className="text-text-dim text-[11px]">
                ({activeAlerts.length} total events tracked)
              </span>
            </div>
            {latestAlert && (
              <div className="flex items-center gap-1.5 text-[11px] text-text-dim">
                <span>Latest Alert:</span>
                <span className="font-bold text-white uppercase">{latestAlert.cameraName}</span>
                <span
                  className={`font-bold px-1.5 py-0.2 rounded text-[10px] ${
                    latestAlert.tier === 'red'
                      ? 'bg-accent-red/20 text-accent-red border border-accent-red/30'
                      : latestAlert.tier === 'yellow'
                      ? 'bg-accent-yellow/20 text-accent-yellow border border-accent-yellow/30'
                      : 'bg-accent-green/20 text-accent-green border border-accent-green/30'
                  }`}
                >
                  {latestAlert.tier.toUpperCase()}
                </span>
                <span className="text-text-muted">#TRK-{latestAlert.trackId}</span>
                <span className="text-white font-bold">(Score: {latestAlert.score.toFixed(1)})</span>
              </div>
            )}
          </div>

          <div className="h-72 w-full pt-1">
            <ResponsiveContainer width="100%" height="100%">
              {chartMode === 'realtime' ? (
                /* REAL-TIME THREAT SCORE STREAM CHART (Synchronized with each incoming alert) */
                <AreaChart
                  data={realtimeStream}
                  margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
                >
                  <defs>
                    <linearGradient id="colorThreatScore" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#00d2df" stopOpacity={0.35} />
                      <stop offset="95%" stopColor="#00d2df" stopOpacity={0.0} />
                    </linearGradient>
                  </defs>

                  <CartesianGrid strokeDasharray="3 3" stroke="#131622" vertical={false} />
                  <XAxis
                    dataKey="timeLabel"
                    stroke="#4b5563"
                    tick={{ fill: '#8c98a8', fontSize: 10 }}
                    axisLine={{ stroke: '#161924' }}
                  />
                  <YAxis
                    domain={[0, 100]}
                    stroke="#4b5563"
                    tick={{ fill: '#8c98a8', fontSize: 10 }}
                    axisLine={{ stroke: '#161924' }}
                    allowDecimals={false}
                  />
                  <Tooltip content={<CustomRealtimeTooltip />} />

                  <Area
                    type="monotone"
                    dataKey="threatScore"
                    stroke="#00d2df"
                    strokeWidth={2}
                    fillOpacity={1}
                    fill="url(#colorThreatScore)"
                    isAnimationActive={false}
                    dot={<RenderRealtimeDot />}
                  />
                </AreaChart>
              ) : (
                /* 24-HOUR AGGREGATED OBSERVATION CHART */
                <AreaChart
                  data={timelineData}
                  margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
                >
                  <defs>
                    <linearGradient id="colorRed" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#f02555" stopOpacity={0.35} />
                      <stop offset="95%" stopColor="#f02555" stopOpacity={0.0} />
                    </linearGradient>
                    <linearGradient id="colorYellow" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#f09f00" stopOpacity={0.35} />
                      <stop offset="95%" stopColor="#f09f00" stopOpacity={0.0} />
                    </linearGradient>
                    <linearGradient id="colorGreen" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#00e077" stopOpacity={0.35} />
                      <stop offset="95%" stopColor="#00e077" stopOpacity={0.0} />
                    </linearGradient>
                  </defs>

                  <CartesianGrid strokeDasharray="3 3" stroke="#131622" vertical={false} />
                  <XAxis
                    dataKey="timeLabel"
                    stroke="#4b5563"
                    tick={{ fill: '#8c98a8', fontSize: 10 }}
                    axisLine={{ stroke: '#161924' }}
                  />
                  <YAxis
                    stroke="#4b5563"
                    tick={{ fill: '#8c98a8', fontSize: 10 }}
                    axisLine={{ stroke: '#161924' }}
                    allowDecimals={false}
                  />
                  <Tooltip content={<CustomDashboardTooltip />} />

                  <Area
                    type="monotone"
                    dataKey="red"
                    stroke="#f02555"
                    strokeWidth={2}
                    fillOpacity={1}
                    fill="url(#colorRed)"
                    isAnimationActive={false}
                  />
                  <Area
                    type="monotone"
                    dataKey="yellow"
                    stroke="#f09f00"
                    strokeWidth={2}
                    fillOpacity={1}
                    fill="url(#colorYellow)"
                    isAnimationActive={false}
                  />
                  <Area
                    type="monotone"
                    dataKey="green"
                    stroke="#00e077"
                    strokeWidth={2}
                    fillOpacity={1}
                    fill="url(#colorGreen)"
                    isAnimationActive={false}
                  />
                </AreaChart>
              )}
            </ResponsiveContainer>
          </div>
        </Card>

        {/* Camera Status Mini-Grid (4 cols) */}
        <Card
          className="lg:col-span-4 flex flex-col justify-between"
          title="Camera Feeds"
          subtitle="Real-time optical & IR sensor connectivity"
          action={
            <Badge variant="green" dot size="sm">
              4 Online
            </Badge>
          }
          footer={
            <Button
              variant="secondary"
              size="sm"
              className="w-full justify-between text-xs"
              rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
              onClick={() => navigate('/live')}
            >
              Open Live Multi-Grid
            </Button>
          }
        >
          <div className="space-y-2.5">
            {mockCameras.map((cam) => (
              <div
                key={cam.id}
                onClick={() => navigate(`/live?camera=${cam.id}`)}
                className="p-3 rounded-xl bg-[#090c12] border border-white/[0.06] hover:border-white/20 transition-colors flex items-center justify-between cursor-pointer group"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-8 h-8 rounded-lg bg-[#0e121c] border border-white/10 flex items-center justify-center text-accent-teal group-hover:text-white transition-colors shrink-0">
                    <Video className="w-4 h-4" />
                  </div>
                  <div className="min-w-0 space-y-0.5">
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs font-semibold text-white truncate">
                        {cam.name}
                      </span>
                    </div>
                    <span className="text-[11px] text-text-dim truncate block">
                      {cam.location}
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <span className="text-[11px] font-mono text-accent-teal font-semibold">
                    {cam.fps} FPS
                  </span>
                  <span className="inline-flex rounded-full h-2 w-2 bg-accent-green" />
                </div>
              </div>

            ))}
          </div>
        </Card>
      </div>

      {/* 3. Recent Critical Alerts (Synchronized Live Target Detections) */}
      <Card
        title={
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-accent-red" />
            <span className="text-sm font-bold tracking-tight">Recent Critical Alerts</span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-accent-teal/10 text-accent-teal border border-accent-teal/30">
              SYNCHRONIZED
            </span>
          </div>
        }
        subtitle="Priority target detections coordinated with live notification pipeline"
        action={
          <Button
            variant="secondary"
            size="sm"
            className="text-xs h-7 px-3 font-mono"
            rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
            onClick={() => navigate('/detections')}
          >
            All Detections
          </Button>
        }
      >
        <div className="space-y-2">
          {recentCriticalAlerts.length === 0 ? (
            <div className="p-6 text-center text-xs text-text-dim font-mono">
              No recent critical alerts detected.
            </div>
          ) : (
            recentCriticalAlerts.map((alert) => (
              <div
                key={alert.id}
                onClick={() => navigate(`/live?camera=${alert.cameraName}`)}
                className="p-3 bg-[#090c12] border border-white/[0.06] border-l-2 border-l-accent-red hover:border-white/20 transition-colors rounded-xl flex flex-col md:flex-row md:items-center justify-between gap-2.5 cursor-pointer group"
              >
                {/* Left: Status Badge, Time, Camera, Target Type Badge, Track ID */}
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={`px-1.5 py-0.5 rounded font-mono text-[10px] font-bold tracking-wider ${
                      alert.tier === 'red'
                        ? 'bg-accent-red/20 text-accent-red border border-accent-red/30'
                        : 'bg-accent-yellow/20 text-accent-yellow border border-accent-yellow/30'
                    }`}
                  >
                    {alert.tier === 'red' ? 'CRITICAL' : 'CAUTION'}
                  </span>

                  <div className="flex items-center gap-1 text-[11px] text-text-dim font-mono">
                    <Clock className="w-3 h-3 text-text-muted" />
                    <span>{formatTime(alert.timestamp)}</span>
                  </div>

                  <span className="text-[11px] font-mono font-bold text-white uppercase px-2 py-0.5 rounded bg-black/40 border border-white/10">
                    {alert.cameraName}
                  </span>

                  {/* Target Detection Badges */}
                  {alert.category === 'person' && (
                    <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-accent-teal bg-accent-teal/10 px-2 py-0.5 rounded border border-accent-teal/30">
                      <User className="w-3 h-3 text-accent-teal" />
                      <span>Person Detection</span>
                    </span>
                  )}
                  {alert.category === 'vehicle' && (
                    <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-accent-yellow bg-accent-yellow/10 px-2 py-0.5 rounded border border-accent-yellow/30">
                      <Car className="w-3 h-3 text-accent-yellow" />
                      <span>Vehicle Detection</span>
                    </span>
                  )}
                  {alert.category === 'unknown' && (
                    <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-text-muted bg-white/[0.04] px-2 py-0.5 rounded border border-white/10">
                      <HelpCircle className="w-3 h-3 text-text-muted" />
                      <span>Unknown Detection</span>
                    </span>
                  )}

                  <span className="text-[11px] font-mono text-accent-teal/80">
                    #TRK-{alert.trackId}
                  </span>
                </div>

                {/* Right: Threat Score + Direct View Evidence button */}
                <div className="flex items-center justify-between md:justify-end gap-3 shrink-0">
                  <span className="text-[11px] font-mono text-text-muted">
                    Score:{' '}
                    <span
                      className={`font-bold ${
                        alert.tier === 'red' ? 'text-accent-red' : 'text-accent-yellow'
                      }`}
                    >
                      {alert.score.toFixed(1)}
                    </span>
                  </span>

                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      navigate(`/live?camera=${alert.cameraName}`);
                    }}
                    className="px-2.5 py-1 rounded bg-white/[0.04] hover:bg-white/[0.08] text-text-dim hover:text-white border border-white/10 transition-colors font-mono text-[10px] font-semibold flex items-center gap-1"
                  >
                    <Eye className="w-3 h-3" />
                    <span>View Evidence</span>
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </Card>
    </div>
  );
};


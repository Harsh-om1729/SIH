import React from 'react';
import { useNavigate } from 'react-router-dom';
import { mockIncidents } from '@/lib/mockIncidents';
import {
  getDashboardStats,
  getHourlyThreatTimeline,
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
} from 'lucide-react';

export const DashboardPage: React.FC = () => {
  const navigate = useNavigate();

  // Derived metrics from mock data
  const stats = getDashboardStats(mockIncidents);
  const timelineData = getHourlyThreatTimeline(mockIncidents);

  // Top 5 most recent Red-tier incidents
  const recentRedAlerts = mockIncidents
    .filter((i) => i.tier === 'red')
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

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'person':
        return <User className="w-3.5 h-3.5 text-accent-teal" />;
      case 'vehicle':
        return <Car className="w-3.5 h-3.5 text-accent-yellow" />;
      default:
        return <HelpCircle className="w-3.5 h-3.5 text-text-muted" />;
    }
  };

  // Custom Tactical Tooltip for Recharts
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="p-3 bg-bg-surface border border-border-subtle rounded-sm shadow-xl font-mono text-xs space-y-1.5 min-w-[160px]">
          <div className="text-text-primary font-bold border-b border-border-subtle/70 pb-1 flex items-center justify-between">
            <span>{label}</span>
            <span className="text-[10px] text-text-dim">TIMELINE</span>
          </div>
          <div className="space-y-1">
            <div className="flex items-center justify-between text-accent-red font-semibold">
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-accent-red" />
                Red Alerts:
              </span>
              <span>{payload.find((p: any) => p.dataKey === 'red')?.value || 0}</span>
            </div>
            <div className="flex items-center justify-between text-accent-yellow font-semibold">
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-accent-yellow" />
                Yellow Alerts:
              </span>
              <span>{payload.find((p: any) => p.dataKey === 'yellow')?.value || 0}</span>
            </div>
            <div className="flex items-center justify-between text-accent-green font-semibold">
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-accent-green" />
                Green Tiers:
              </span>
              <span>{payload.find((p: any) => p.dataKey === 'green')?.value || 0}</span>
            </div>
          </div>
        </div>
      );
    }
    return null;
  };

  const mockCameras = [
    { id: 'cam0', name: 'cam0', location: 'North Perimeter Gate', fps: '30.0', status: 'online' },
    { id: 'cam1', name: 'cam1', location: 'East Checkpoint Bravo', fps: '29.8', status: 'online' },
    { id: 'cam2', name: 'cam2', location: 'South Fence Line', fps: '30.0', status: 'online' },
    { id: 'cam3', name: 'cam3', location: 'West Watchtower Alpha', fps: '30.2', status: 'online' },
  ];

  return (
    <div className="space-y-6">
      {/* Top Header Row with Data Range Disclaimer */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border-subtle pb-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-text-primary flex items-center gap-2">
            <span>Operational Situational Overview</span>
          </h2>
          <p className="text-xs text-text-dim">
            Consolidated threat intelligence & perimeter telemetry
          </p>
        </div>

        <div className="flex items-center gap-2 font-mono text-[11px] text-text-dim bg-bg-surface px-3 py-1.5 rounded-sm border border-border-subtle">
          <Clock className="w-3.5 h-3.5 text-accent-teal" />
          <span>Data range: Last 24 hours (mock data)</span>
        </div>
      </div>

      {/* 1. Row of 4 KPI Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Stat Card 1: Total Incidents */}
        <Card variant="default" className="border-l-4 border-l-accent-teal">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-xs font-mono uppercase text-text-dim tracking-wider block">
                Total Incidents (24h)
              </span>
              <span className="text-2xl font-bold font-mono text-accent-teal mt-1 block">
                {stats.totalIncidents}
              </span>
              <span className="text-[10px] text-text-muted mt-0.5 block font-mono">
                ALL PERIMETER SECTORS
              </span>
            </div>
            <div className="p-3 rounded-full bg-accent-teal/10 border border-accent-teal/30 text-accent-teal">
              <Activity className="w-5 h-5" />
            </div>
          </div>
        </Card>

        {/* Stat Card 2: Red Alerts */}
        <Card variant="default" className="border-l-4 border-l-accent-red">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-xs font-mono uppercase text-text-dim tracking-wider block">
                Red Alerts (Critical)
              </span>
              <span className="text-2xl font-bold font-mono text-accent-red mt-1 block">
                {stats.redAlerts}
              </span>
              <span className="text-[10px] text-accent-red/80 mt-0.5 block font-mono">
                IMMEDIATE DISPATCH
              </span>
            </div>
            <div className="p-3 rounded-full bg-accent-red/10 border border-accent-red/30 text-accent-red">
              <ShieldAlert className="w-5 h-5" />
            </div>
          </div>
        </Card>

        {/* Stat Card 3: Yellow Alerts */}
        <Card variant="default" className="border-l-4 border-l-accent-yellow">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-xs font-mono uppercase text-text-dim tracking-wider block">
                Yellow Alerts (Caution)
              </span>
              <span className="text-2xl font-bold font-mono text-accent-yellow mt-1 block">
                {stats.yellowAlerts}
              </span>
              <span className="text-[10px] text-text-muted mt-0.5 block font-mono">
                DIRECTION VECTORS
              </span>
            </div>
            <div className="p-3 rounded-full bg-accent-yellow/10 border border-accent-yellow/30 text-accent-yellow">
              <AlertTriangle className="w-5 h-5" />
            </div>
          </div>
        </Card>

        {/* Stat Card 4: Active Cameras */}
        <Card variant="default" className="border-l-4 border-l-accent-green">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-xs font-mono uppercase text-text-dim tracking-wider block">
                Active Cameras
              </span>
              <span className="text-2xl font-bold font-mono text-accent-green mt-1 block">
                {stats.activeCameras} / {stats.activeCameras}
              </span>
              <span className="text-[10px] text-accent-green/80 mt-0.5 block font-mono">
                ALL CHANNELS ONLINE
              </span>
            </div>
            <div className="p-3 rounded-full bg-accent-green/10 border border-accent-green/30 text-accent-green">
              <Video className="w-5 h-5" />
            </div>
          </div>
        </Card>
      </div>

      {/* 2. Threat Timeline Chart & Mini-Grid Section */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Threat Timeline Area Chart (8 cols) */}
        <Card
          className="lg:col-span-8"
          title="24-Hour Threat Activity Timeline"
          subtitle="Tier frequency distribution across rolling 24-hour observation window"
          action={
            <div className="flex items-center gap-3 font-mono text-[10px]">
              <span className="flex items-center gap-1 text-accent-red font-semibold">
                <span className="w-2 h-2 rounded-full bg-accent-red" /> RED
              </span>
              <span className="flex items-center gap-1 text-accent-yellow font-semibold">
                <span className="w-2 h-2 rounded-full bg-accent-yellow" /> YELLOW
              </span>
              <span className="flex items-center gap-1 text-accent-green font-semibold">
                <span className="w-2 h-2 rounded-full bg-accent-green" /> GREEN
              </span>
            </div>
          }
        >
          <div className="h-72 w-full pt-2">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart
                data={timelineData}
                margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
              >
                <defs>
                  <linearGradient id="colorRed" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#e5484d" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#e5484d" stopOpacity={0.0} />
                  </linearGradient>
                  <linearGradient id="colorYellow" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#e6c34a" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#e6c34a" stopOpacity={0.0} />
                  </linearGradient>
                  <linearGradient id="colorGreen" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#4fbf7a" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#4fbf7a" stopOpacity={0.0} />
                  </linearGradient>
                </defs>

                <CartesianGrid strokeDasharray="3 3" stroke="#25322e" vertical={false} />
                <XAxis
                  dataKey="timeLabel"
                  stroke="#5c6f68"
                  tick={{ fill: '#8fa39b', fontSize: 11, fontFamily: 'monospace' }}
                  axisLine={{ stroke: '#25322e' }}
                />
                <YAxis
                  stroke="#5c6f68"
                  tick={{ fill: '#8fa39b', fontSize: 11, fontFamily: 'monospace' }}
                  axisLine={{ stroke: '#25322e' }}
                  allowDecimals={false}
                />
                <Tooltip content={<CustomTooltip />} />

                <Area
                  type="monotone"
                  dataKey="red"
                  stroke="#e5484d"
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#colorRed)"
                />
                <Area
                  type="monotone"
                  dataKey="yellow"
                  stroke="#e6c34a"
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#colorYellow)"
                />
                <Area
                  type="monotone"
                  dataKey="green"
                  stroke="#4fbf7a"
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#colorGreen)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>

        {/* Camera Status Mini-Grid (4 cols) */}
        <Card
          className="lg:col-span-4 flex flex-col justify-between"
          title="Camera Channel Health"
          subtitle="Real-time RTSP stream sensor connectivity"
          action={
            <Badge variant="green" dot size="sm">
              4/4 ONLINE
            </Badge>
          }
          footer={
            <Button
              variant="ghost"
              size="sm"
              className="w-full justify-between text-xs"
              rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
              onClick={() => navigate('/live')}
            >
              Open Live Feeds Grid
            </Button>
          }
        >
          <div className="space-y-2.5">
            {mockCameras.map((cam) => (
              <div
                key={cam.id}
                onClick={() => navigate('/live')}
                className="p-2.5 rounded-sm bg-bg-surface border border-border-subtle hover:border-text-muted/60 transition-colors flex items-center justify-between cursor-pointer"
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <span className="relative flex h-2 w-2 shrink-0">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent-green opacity-75" />
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-accent-green" />
                  </span>
                  <div className="min-w-0">
                    <span className="font-mono text-xs font-semibold text-text-primary uppercase block">
                      {cam.name}
                    </span>
                    <span className="text-[10px] text-text-dim truncate block">
                      {cam.location}
                    </span>
                  </div>
                </div>

                <div className="text-right font-mono text-[11px] text-text-muted shrink-0">
                  <span className="text-accent-teal">{cam.fps}</span> FPS
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* 3. Recent Critical Alerts (Top 5 Red-Tier Incidents) */}
      <Card
        title={
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-accent-red" />
            <span>Recent Critical Red Alerts (Top 5)</span>
          </div>
        }
        subtitle="Priority boundary breaches requiring tactical response"
        action={
          <Button
            variant="secondary"
            size="sm"
            rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
            onClick={() => navigate('/incidents')}
          >
            View All Incidents
          </Button>
        }
      >
        <div className="space-y-2">
          {recentRedAlerts.map((alert) => (
            <div
              key={alert.id}
              onClick={() => navigate('/incidents')}
              className="p-3 bg-bg-surface border border-border-subtle border-l-4 border-l-accent-red hover:bg-bg-elevated/70 transition-all rounded-sm flex flex-col sm:flex-row sm:items-center justify-between gap-3 cursor-pointer group"
            >
              {/* Left: Time, Camera, Category, Track ID */}
              <div className="flex flex-wrap items-center gap-3">
                <div className="flex items-center gap-1.5 font-mono text-xs text-text-dim">
                  <Clock className="w-3.5 h-3.5 text-text-muted" />
                  <span>{formatTime(alert.timestamp)} UTC</span>
                </div>

                <span className="font-mono text-xs font-semibold uppercase text-text-primary">
                  {alert.cameraName}
                </span>

                <div className="flex items-center gap-1 text-xs text-text-dim capitalize">
                  {getCategoryIcon(alert.category)}
                  <span>{alert.category}</span>
                </div>

                <span className="font-mono text-xs text-accent-teal">
                  #TRK-{alert.trackId}
                </span>

                {/* Threat Score Pill */}
                <span className="font-mono text-xs font-bold text-accent-red bg-accent-red/10 px-2 py-0.5 rounded border border-accent-red/20">
                  SCORE: {alert.score.toFixed(1)}
                </span>
              </div>

              {/* Right: Watchlist Match Tag & Action */}
              <div className="flex items-center justify-between sm:justify-end gap-3">
                {alert.watchlistMatch ? (
                  <span className="inline-flex items-center gap-1 font-mono text-[11px] font-bold text-accent-red bg-accent-red/15 px-2 py-0.5 rounded border border-accent-red/40">
                    <AlertTriangle className="w-3 h-3 text-accent-red" />
                    <span>MATCH: {alert.watchlistMatch}</span>
                  </span>
                ) : (
                  <span className="font-mono text-[11px] text-text-muted">
                    PERIMETER INTRUSION
                  </span>
                )}

                <span className="text-text-muted group-hover:text-accent-teal transition-colors">
                  <Eye className="w-4 h-4" />
                </span>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
};

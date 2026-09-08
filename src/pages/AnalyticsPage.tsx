import React from 'react';
import { mockIncidents } from '@/lib/mockIncidents';
import {
  getCategoryDistribution,
  getCameraDistribution,
  getTierDistribution,
  getPeakHourlyActivity,
} from '@/lib/analyticsUtils';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from 'recharts';
import {
  BarChart3,
  Clock,
  PieChart as PieIcon,
  Video,
  Shield,
  Moon,
} from 'lucide-react';

export const AnalyticsPage: React.FC = () => {
  const categoryData = getCategoryDistribution(mockIncidents);
  const cameraData = getCameraDistribution(mockIncidents);
  const tierData = getTierDistribution(mockIncidents);
  const hourlyActivity = getPeakHourlyActivity(mockIncidents);

  // Custom Tooltip for Recharts
  const CustomAnalyticsTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="p-3 bg-bg-surface border border-border-subtle rounded-sm shadow-xl font-mono text-xs space-y-1 min-w-[140px]">
          <div className="text-text-primary font-bold border-b border-border-subtle/70 pb-1">
            {label || payload[0]?.name}
          </div>
          {payload.map((entry: any, index: number) => (
            <div
              key={index}
              className="flex items-center justify-between gap-3 text-xs"
              style={{ color: entry.color || entry.fill }}
            >
              <span className="capitalize">{entry.name || 'Count'}:</span>
              <span className="font-bold">{entry.value}</span>
            </div>
          ))}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="space-y-6">
      {/* Top Header Row */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border-subtle pb-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-text-primary flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-accent-teal" />
            <span>Threat Intelligence Analytics</span>
          </h2>
          <p className="text-xs text-text-dim">
            Deep multi-dimensional breakdown of border activity, sector distributions, and curfew patterns
          </p>
        </div>

        <div className="flex items-center gap-2 font-mono text-[11px] text-text-dim bg-bg-surface px-3 py-1.5 rounded-sm border border-border-subtle">
          <Clock className="w-3.5 h-3.5 text-accent-teal" />
          <span>Data range: Last 24 hours (mock data)</span>
        </div>
      </div>

      {/* Grid of 4 Core Analytical Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Chart 1: Incidents by Category (Donut Chart) */}
        <Card
          title={
            <div className="flex items-center gap-2">
              <PieIcon className="w-4 h-4 text-accent-teal" />
              <span>Incidents by Target Category</span>
            </div>
          }
          subtitle="Classification breakdown: Person vs. Vehicle vs. Unknown/Thermal"
          action={
            <Badge variant="teal" size="sm">
              CLASSIFIER
            </Badge>
          }
        >
          <div className="h-64 w-full flex flex-col sm:flex-row items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={categoryData}
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={85}
                  paddingAngle={4}
                  dataKey="value"
                  stroke="#111917"
                  strokeWidth={2}
                >
                  {categoryData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip content={<CustomAnalyticsTooltip />} />
                <Legend
                  formatter={(value) => (
                    <span className="font-mono text-xs text-text-dim">{value}</span>
                  )}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </Card>

        {/* Chart 2: Incidents by Camera Channel (Bar Chart) */}
        <Card
          title={
            <div className="flex items-center gap-2">
              <Video className="w-4 h-4 text-accent-teal" />
              <span>Incidents by Camera Sector</span>
            </div>
          }
          subtitle="Total detection distribution across surveillance channels"
          action={
            <Badge variant="green" size="sm">
              SECTOR LOAD
            </Badge>
          }
        >
          <div className="h-64 w-full pt-2">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={cameraData}
                margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#25322e" vertical={false} />
                <XAxis
                  dataKey="camera"
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
                <Tooltip content={<CustomAnalyticsTooltip />} />
                <Legend
                  formatter={(value) => (
                    <span className="font-mono text-xs text-text-dim capitalize">{value}</span>
                  )}
                />
                <Bar dataKey="red" name="Red (Critical)" fill="#e5484d" stackId="a" />
                <Bar dataKey="yellow" name="Yellow (Caution)" fill="#e6c34a" stackId="a" />
                <Bar dataKey="green" name="Green (Normal)" fill="#4fbf7a" stackId="a" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        {/* Chart 3: Incidents by Threat Tier (Bar Chart) */}
        <Card
          title={
            <div className="flex items-center gap-2">
              <Shield className="w-4 h-4 text-accent-teal" />
              <span>Volume by Alert Tier</span>
            </div>
          }
          subtitle="Comparative volume of Green, Yellow, and Red alerts"
          action={
            <Badge variant="yellow" size="sm">
              TIER SPLIT
            </Badge>
          }
        >
          <div className="h-64 w-full pt-2">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={tierData}
                margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#25322e" vertical={false} />
                <XAxis
                  dataKey="tier"
                  stroke="#5c6f68"
                  tick={{ fill: '#8fa39b', fontSize: 10, fontFamily: 'Inter' }}
                  axisLine={{ stroke: '#25322e' }}
                />
                <YAxis
                  stroke="#5c6f68"
                  tick={{ fill: '#8fa39b', fontSize: 11, fontFamily: 'monospace' }}
                  axisLine={{ stroke: '#25322e' }}
                  allowDecimals={false}
                />
                <Tooltip content={<CustomAnalyticsTooltip />} />
                <Bar dataKey="count" name="Incidents" radius={[4, 4, 0, 0]}>
                  {tierData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        {/* Chart 4: Peak Activity Hours (Curfew Histogram) */}
        <Card
          title={
            <div className="flex items-center gap-2">
              <Moon className="w-4 h-4 text-accent-yellow" />
              <span>Peak Activity Hours (Curfew Analysis)</span>
            </div>
          }
          subtitle="Activity distribution across 24 hours (Curfew hours: 21:00–05:00)"
          action={
            <Badge variant="yellow" size="sm">
              21:00 - 05:00 CURFEW
            </Badge>
          }
        >
          <div className="h-64 w-full pt-2">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={hourlyActivity}
                margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#25322e" vertical={false} />
                <XAxis
                  dataKey="hour"
                  stroke="#5c6f68"
                  tick={{ fill: '#8fa39b', fontSize: 9, fontFamily: 'monospace' }}
                  axisLine={{ stroke: '#25322e' }}
                  interval={2}
                />
                <YAxis
                  stroke="#5c6f68"
                  tick={{ fill: '#8fa39b', fontSize: 11, fontFamily: 'monospace' }}
                  axisLine={{ stroke: '#25322e' }}
                  allowDecimals={false}
                />
                <Tooltip content={<CustomAnalyticsTooltip />} />
                <Bar dataKey="count" name="Detections" radius={[2, 2, 0, 0]}>
                  {hourlyActivity.map((entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={entry.isCurfew ? '#e5484d' : '#5fd6c4'}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>
    </div>
  );
};

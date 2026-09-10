export interface Zone {
  id: string;
  cameraName: string;
  tier: 'green' | 'yellow' | 'red';
  points: { x: number; y: number }[]; // polygon vertices, normalized 0.0 to 1.0
  direction?: 'inward' | 'outward'; // only meaningful for yellow zones
  label: string;
  tripwireEnabled?: boolean; // Section 20: virtual tripwire crossing beam
  loiteringThresholdSeconds?: number; // Section 20: dwell time limit before alarm
  climbingDetection?: boolean; // Section 20: fence climbing aspect ratio shift
}

export const initialMockZones: Zone[] = [
  // cam0 Zones (North Perimeter Gate)
  {
    id: 'zone-cam0-1',
    cameraName: 'cam0',
    tier: 'red',
    label: 'Restricted Border Fence Line',
    tripwireEnabled: true,
    climbingDetection: true,
    points: [
      { x: 0.15, y: 0.2 },
      { x: 0.85, y: 0.22 },
      { x: 0.88, y: 0.45 },
      { x: 0.12, y: 0.42 },
    ],
  },
  {
    id: 'zone-cam0-2',
    cameraName: 'cam0',
    tier: 'yellow',
    direction: 'inward',
    label: 'North Buffer Zone (Inward Vector)',
    loiteringThresholdSeconds: 45,
    points: [
      { x: 0.1, y: 0.48 },
      { x: 0.9, y: 0.5 },
      { x: 0.86, y: 0.72 },
      { x: 0.14, y: 0.7 },
    ],
  },
  {
    id: 'zone-cam0-3',
    cameraName: 'cam0',
    tier: 'green',
    label: 'Internal Patrol Access Track',
    points: [
      { x: 0.2, y: 0.76 },
      { x: 0.8, y: 0.78 },
      { x: 0.75, y: 0.94 },
      { x: 0.25, y: 0.92 },
    ],
  },

  // cam1 Zones (East Checkpoint Bravo)
  {
    id: 'zone-cam1-1',
    cameraName: 'cam1',
    tier: 'red',
    label: 'East Barrier Zero-Line',
    points: [
      { x: 0.25, y: 0.15 },
      { x: 0.75, y: 0.18 },
      { x: 0.7, y: 0.4 },
      { x: 0.28, y: 0.38 },
    ],
  },
  {
    id: 'zone-cam1-2',
    cameraName: 'cam1',
    tier: 'yellow',
    direction: 'inward',
    label: 'Checkpoint Vehicle Queue Corridor',
    points: [
      { x: 0.3, y: 0.45 },
      { x: 0.7, y: 0.48 },
      { x: 0.65, y: 0.82 },
      { x: 0.35, y: 0.8 },
    ],
  },

  // cam2 Zones (South Fence Line)
  {
    id: 'zone-cam2-1',
    cameraName: 'cam2',
    tier: 'red',
    label: 'South Wall Perimeter Barrier',
    points: [
      { x: 0.1, y: 0.25 },
      { x: 0.9, y: 0.28 },
      { x: 0.85, y: 0.52 },
      { x: 0.15, y: 0.5 },
    ],
  },
  {
    id: 'zone-cam2-2',
    cameraName: 'cam2',
    tier: 'yellow',
    direction: 'outward',
    label: 'Buffer Strip (Outward Alert)',
    points: [
      { x: 0.18, y: 0.58 },
      { x: 0.82, y: 0.6 },
      { x: 0.78, y: 0.85 },
      { x: 0.22, y: 0.82 },
    ],
  },

  // cam3 Zones (West Watchtower Alpha)
  {
    id: 'zone-cam3-1',
    cameraName: 'cam3',
    tier: 'red',
    label: 'Riverbed Crossing Sector',
    points: [
      { x: 0.2, y: 0.3 },
      { x: 0.6, y: 0.25 },
      { x: 0.75, y: 0.55 },
      { x: 0.35, y: 0.6 },
    ],
  },
  {
    id: 'zone-cam3-2',
    cameraName: 'cam3',
    tier: 'green',
    label: 'Hillside Observation Track',
    points: [
      { x: 0.1, y: 0.65 },
      { x: 0.9, y: 0.68 },
      { x: 0.85, y: 0.92 },
      { x: 0.15, y: 0.9 },
    ],
  },
];

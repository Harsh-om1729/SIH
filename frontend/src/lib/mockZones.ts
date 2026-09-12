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

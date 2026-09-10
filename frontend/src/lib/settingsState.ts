export interface ThresholdSettings {
  redThreshold: number;
  yellowThreshold: number;
  biometricThreshold: number;
  reidThreshold: number;
  brightnessThreshold: number;
  motionThreshold: number;
  lowFpsInterval: number;
  detectionConfidence: number;
  alertCooldownSeconds: number;
  motionSensitivity: 'low' | 'medium' | 'high';
  curfewBoost: boolean;
  curfewHours: string;
}

export interface IntegrationSettings {
  capWebhookUrl: string;
  capEnabled: boolean;
  gpioSirenRelay: boolean;
  siemHost: string;
  siemPort: number;
  siemProtocol: 'UDP' | 'TCP';
  siemEnabled: boolean;
  fernetKeyPath?: string;
  audioToneSynth?: boolean;
}

export interface HardwareTelemetry {
  gpuUtilization: number;
  cpuUtilization: number;
  ramUsageGb: number;
  ramTotalGb: number;
  storageUsedGb: number;
  storageTotalGb: number;
  inferenceLatencyMs: number;
  pipelineFps: number;
  activePipelines: number;
  isAirGapped: boolean;
  temperatureC: number;
}

export const DEFAULT_THRESHOLDS: ThresholdSettings = {
  redThreshold: 70,
  yellowThreshold: 30,
  biometricThreshold: 60,
  reidThreshold: 65,
  brightnessThreshold: 90,
  motionThreshold: 2.0,
  lowFpsInterval: 10,
  detectionConfidence: 40,
  alertCooldownSeconds: 8.0,
  motionSensitivity: 'high',
  curfewBoost: true,
  curfewHours: '21:00 - 05:00',
};

export const DEFAULT_INTEGRATIONS: IntegrationSettings = {
  capWebhookUrl: 'https://c2-command.bop-alpha.mil/api/v1/alerts/cap',
  capEnabled: true,
  gpioSirenRelay: true,
  siemHost: '10.14.0.25',
  siemPort: 514,
  siemProtocol: 'UDP',
  siemEnabled: true,
};

export const DEFAULT_TELEMETRY: HardwareTelemetry = {
  gpuUtilization: 42,
  cpuUtilization: 38,
  ramUsageGb: 5.8,
  ramTotalGb: 16.0,
  storageUsedGb: 482,
  storageTotalGb: 1000,
  inferenceLatencyMs: 18.2,
  pipelineFps: 30.0,
  activePipelines: 4,
  isAirGapped: true,
  temperatureC: 48,
};

const THRESHOLDS_STORAGE_KEY = 'ibvap_settings_thresholds';
const INTEGRATIONS_STORAGE_KEY = 'ibvap_settings_integrations';

export function loadThresholdSettings(): ThresholdSettings {
  try {
    const saved = localStorage.getItem(THRESHOLDS_STORAGE_KEY);
    if (saved) {
      return { ...DEFAULT_THRESHOLDS, ...JSON.parse(saved) };
    }
  } catch {
    // ignore parse error
  }
  return DEFAULT_THRESHOLDS;
}

export function saveThresholdSettings(settings: ThresholdSettings): void {
  try {
    localStorage.setItem(THRESHOLDS_STORAGE_KEY, JSON.stringify(settings));
  } catch {
    // ignore
  }
}

export function loadIntegrationSettings(): IntegrationSettings {
  try {
    const saved = localStorage.getItem(INTEGRATIONS_STORAGE_KEY);
    if (saved) {
      return { ...DEFAULT_INTEGRATIONS, ...JSON.parse(saved) };
    }
  } catch {
    // ignore parse error
  }
  return DEFAULT_INTEGRATIONS;
}

export function saveIntegrationSettings(settings: IntegrationSettings): void {
  try {
    localStorage.setItem(INTEGRATIONS_STORAGE_KEY, JSON.stringify(settings));
  } catch {
    // ignore
  }
}

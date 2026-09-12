export const APP_NAME = 'IBVAP';
export const APP_FULL_NAME = 'Intelligent Border Video Analytics Platform';
export const APP_VERSION = 'v1.0.0-hackathon';

export const THEME_COLORS = {
  bgPrimary: '#0a0f0d',
  bgSurface: '#111917',
  bgElevated: '#16201d',
  borderSubtle: '#25322e',
  textMuted: '#5c6f68',
  textDim: '#8fa39b',
  textPrimary: '#e6ece9',
  accentTeal: '#5fd6c4',
  accentGreen: '#4fbf7a',
  accentGreenDeep: '#2f6e64',
  accentYellow: '#e6c34a',
  accentRed: '#e5484d',
} as const;

export type ZoneTier = 'green' | 'yellow' | 'red';

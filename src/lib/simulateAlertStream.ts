import { Incident } from './mockIncidents';

// Weighted simulation matching intelligence/threat_score.py (GREEN <= 30, YELLOW <= 69, RED >= 70)
export function generateSimulatedIncident(overrideTier?: 'green' | 'yellow' | 'red'): Incident {
  const rand = Math.random();
  let tier: 'green' | 'yellow' | 'red';

  if (overrideTier) {
    tier = overrideTier;
  } else if (rand < 0.6) {
    tier = 'green';
  } else if (rand < 0.9) {
    tier = 'yellow';
  } else {
    tier = 'red';
  }

  const cameras = ['cam0', 'cam1', 'cam2', 'cam3'];
  const camera = cameras[Math.floor(Math.random() * cameras.length)];

  const categories: ('person' | 'vehicle' | 'unknown')[] = ['person', 'vehicle', 'unknown'];
  const category =
    tier === 'red'
      ? Math.random() > 0.3
        ? 'person'
        : 'vehicle'
      : categories[Math.floor(Math.random() * categories.length)];

  const trackId = 9100 + Math.floor(Math.random() * 800);
  const now = Math.floor(Date.now() / 1000);

  // Derive realistic S, T, K, C components per intelligence/threat_score.py
  let sectorRisk = 0;
  let timeRisk = 0;
  let kinematicsRisk = 0;
  let classConfidence = 0;

  if (tier === 'green') {
    sectorRisk = Number((2 + Math.random() * 6).toFixed(1));
    timeRisk = Number((Math.random() * 5).toFixed(1));
    kinematicsRisk = Number((2 + Math.random() * 5).toFixed(1));
    classConfidence = Number((5 + Math.random() * 5).toFixed(1));
  } else if (tier === 'yellow') {
    sectorRisk = Number((18 + Math.random() * 8).toFixed(1));
    timeRisk = Number((12 + Math.random() * 8).toFixed(1));
    kinematicsRisk = Number((10 + Math.random() * 6).toFixed(1));
    classConfidence = Number((8 + Math.random() * 5).toFixed(1));
  } else {
    sectorRisk = Number((32 + Math.random() * 7).toFixed(1));
    timeRisk = Number((20 + Math.random() * 5).toFixed(1));
    kinematicsRisk = Number((16 + Math.random() * 4).toFixed(1));
    classConfidence = Number((12 + Math.random() * 3).toFixed(1));
  }

  let totalScore = Number((sectorRisk + timeRisk + kinematicsRisk + classConfidence).toFixed(1));

  // No person names - pure target detection
  const watchlistMatch: string | null = null;
  const personId: number | null = null;
  if (tier === 'red') {
    totalScore = Math.max(totalScore, 70.0);
  }

  // Tactical SVG snapshot with Fernet encryption badge
  const tierColor = tier === 'red' ? '#e5484d' : tier === 'yellow' ? '#e6c34a' : '#4fbf7a';
  const categoryLabel = category === 'person' ? 'PERSON DETECT' : category === 'vehicle' ? 'VEHICLE DETECT' : 'UNKNOWN DETECT';
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 360" width="640" height="360">
      <rect width="640" height="360" fill="#0a0f0d"/>
      <rect x="220" y="90" width="200" height="180" fill="${tierColor}" fill-opacity="0.1" stroke="${tierColor}" stroke-width="2"/>
      <text x="20" y="30" fill="#e6ece9" font-family="monospace" font-size="12">LIVE TARGET CAPTURE: ${camera.toUpperCase()}</text>
      <text x="20" y="50" fill="${tierColor}" font-family="monospace" font-size="11">TYPE: ${categoryLabel} · SCORE: ${totalScore} [S:${sectorRisk} T:${timeRisk} K:${kinematicsRisk} C:${classConfidence}]</text>
      <text x="20" y="68" fill="#5c6f68" font-family="monospace" font-size="10">STORAGE: FERNET-AES128-CBC ENCRYPTED (database/incidents.db)</text>
      <text x="20" y="86" fill="${tierColor}" font-family="monospace" font-size="11">CLASSIFICATION: ${categoryLabel} // SECTOR THREAT</text>
    </svg>
  `.trim();

  return {
    id: Date.now() + Math.floor(Math.random() * 1000),
    trackId,
    personId,
    category,
    zoneTier: tier === 'red' && Math.random() > 0.5 ? 'yellow' : tier,
    score: totalScore,
    tier,
    timestamp: now,
    cameraName: camera,
    snapshotUrl: `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`,
    cropUrl: null,
    burstUrls: [],
    watchlistMatch,
    breakdown: {
      sectorRisk,
      timeRisk,
      kinematicsRisk,
      classConfidence,
    },
    reidGalleryId: `PG-${trackId}`,
    encryption: {
      cipher: 'FERNET-AES128-CBC',
      keyPath: 'database/evidence.key',
      verified: true,
    },
  };
}

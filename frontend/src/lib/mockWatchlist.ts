export interface WatchlistPerson {
  id: number;
  name: string;
  notes?: string;
  photoUrl: string; // reference photo / biometric embedding source
  addedAt: number; // unix seconds
  lastMatchedAt: number | null; // last time this person was detected
  matchCount: number;
}

// Generate an air-gapped tactical SVG biometric portrait
export function generateBiometricAvatarSvg(name: string, subjectId: number, matchCount: number): string {
  const isFlagged = matchCount > 0;
  const accentColor = isFlagged ? '#e5484d' : '#5fd6c4';

  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="200" height="200">
      <defs>
        <linearGradient id="avatar-bg-${subjectId}" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#111917"/>
          <stop offset="100%" stop-color="#0a0f0d"/>
        </linearGradient>
      </defs>

      <!-- Background -->
      <rect width="200" height="200" fill="url(#avatar-bg-${subjectId})" rx="6"/>

      <!-- Biometric Mesh Network -->
      <circle cx="100" cy="85" r="42" fill="none" stroke="${accentColor}" stroke-width="1.5" stroke-dasharray="3 3" opacity="0.6"/>
      <ellipse cx="100" cy="90" rx="32" ry="40" fill="none" stroke="${accentColor}" stroke-width="1.5" opacity="0.8"/>

      <!-- Facial Landmarks & Nodes -->
      <circle cx="88" cy="80" r="3" fill="${accentColor}"/>
      <circle cx="112" cy="80" r="3" fill="${accentColor}"/>
      <line x1="88" y1="80" x2="112" y2="80" stroke="${accentColor}" stroke-width="1" opacity="0.7"/>

      <!-- Nose Bridge -->
      <line x1="100" y1="78" x2="100" y2="94" stroke="${accentColor}" stroke-width="1.2"/>
      <line x1="94" y1="94" x2="106" y2="94" stroke="${accentColor}" stroke-width="1.2"/>

      <!-- Mouth Axis -->
      <line x1="90" y1="108" x2="110" y2="108" stroke="${accentColor}" stroke-width="1.5"/>

      <!-- Jaw Contour -->
      <path d="M 68 85 Q 70 125, 100 134 Q 130 125, 132 85" fill="none" stroke="${accentColor}" stroke-width="1.5"/>

      <!-- Shoulder Contour -->
      <path d="M 40 185 C 45 150, 80 145, 100 145 C 120 145, 155 150, 160 185" fill="none" stroke="#25322e" stroke-width="2"/>

      <!-- Tactical Corner Targeting Reticle -->
      <path d="M 20 35 L 20 20 L 35 20" fill="none" stroke="${accentColor}" stroke-width="2"/>
      <path d="M 180 35 L 180 20 L 165 20" fill="none" stroke="${accentColor}" stroke-width="2"/>
      <path d="M 20 165 L 20 180 L 35 180" fill="none" stroke="${accentColor}" stroke-width="2"/>
      <path d="M 180 165 L 180 180 L 165 180" fill="none" stroke="${accentColor}" stroke-width="2"/>

      <!-- Biometric Vector ID Banner -->
      <rect x="20" y="166" width="160" height="18" fill="#16201d" rx="2" stroke="#25322e" stroke-width="0.75"/>
      <text x="100" y="179" fill="#8fa39b" font-family="monospace" font-size="8.5" text-anchor="middle">#FE-${subjectId} · ${name.toUpperCase().slice(0, 14)}</text>
    </svg>
  `.trim();

  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}


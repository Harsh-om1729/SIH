export interface ThreatScoreBreakdown {
  sectorRisk: number;       // S: Sector / Virtual Fence Risk (0-40)
  timeRisk: number;         // T: Time / Curfew Hours Risk (0-25)
  kinematicsRisk: number;   // K: Speed & Inward Vector Risk (0-20)
  classConfidence: number;  // C: Target Category & Detection Confidence (0-15)
}

export interface Incident {
  id: number;
  trackId: number;
  personId: number | null;
  category: "person" | "vehicle" | "unknown";
  zoneTier: "green" | "yellow" | "red";
  score: number;        // 0-100 threat score (total = S + T + K + C)
  tier: "green" | "yellow" | "red";  // final alert tier: Green <= 30, Yellow 31-69, Red >= 70
  timestamp: number;    // unix seconds
  cameraName: string;   // e.g. "cam0"
  snapshotUrl: string;
  cropUrl: string | null;
  burstUrls: string[];
  watchlistMatch: string | null; // matched person's name if any, else null
  breakdown: ThreatScoreBreakdown;
  reidGalleryId: string;        // Person Gallery Re-ID track continuity (e.g. "PG-101")
  encryption: {
    cipher: string;             // "FERNET-AES128-CBC"
    keyPath: string;            // "database/evidence.key"
    verified: boolean;
  };
}

// Tactical SVG generator for realistic air-gapped surveillance evidence frames
function generateEvidenceSvg(
  camera: string,
  timestampStr: string,
  label: string,
  tierColor: string,
  trackId: number,
  subtext: string,
  breakdownText = "S:35 T:25 K:19 C:15"
): string {
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 360" width="640" height="360">
      <defs>
        <pattern id="grid-${trackId}" width="20" height="20" patternUnits="userSpaceOnUse">
          <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#25322e" stroke-width="0.75"/>
        </pattern>
        <linearGradient id="scan-${trackId}" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stop-color="#0a0f0d" stop-opacity="0.95"/>
          <stop offset="50%" stop-color="#111917" stop-opacity="0.8"/>
          <stop offset="100%" stop-color="#0a0f0d" stop-opacity="0.95"/>
        </linearGradient>
      </defs>

      <!-- Background Screen -->
      <rect width="640" height="360" fill="url(#scan-${trackId})"/>
      <rect width="640" height="360" fill="url(#grid-${trackId})" opacity="0.6"/>

      <!-- Tactical Reticle & Crosshairs -->
      <circle cx="320" cy="180" r="90" fill="none" stroke="#25322e" stroke-dasharray="4 4" stroke-width="1.5"/>
      <line x1="210" y1="180" x2="430" y2="180" stroke="#25322e" stroke-width="1"/>
      <line x1="320" y1="70" x2="320" y2="290" stroke="#25322e" stroke-width="1"/>

      <!-- Detection Bounding Box -->
      <g transform="translate(240, 100)">
        <rect width="160" height="170" fill="${tierColor}" fill-opacity="0.1" stroke="${tierColor}" stroke-width="2"/>
        <!-- Corner brackets -->
        <path d="M 0 15 L 0 0 L 15 0" fill="none" stroke="${tierColor}" stroke-width="3"/>
        <path d="M 145 0 L 160 0 L 160 15" fill="none" stroke="${tierColor}" stroke-width="3"/>
        <path d="M 0 155 L 0 170 L 15 170" fill="none" stroke="${tierColor}" stroke-width="3"/>
        <path d="M 145 170 L 160 170 L 160 155" fill="none" stroke="${tierColor}" stroke-width="3"/>

        <!-- BBox Tag -->
        <rect x="0" y="-22" width="160" height="22" fill="${tierColor}"/>
        <text x="6" y="-6" fill="#0a0f0d" font-family="monospace" font-size="11" font-weight="bold">#TRK-${trackId} [${label}]</text>
      </g>

      <!-- Target Silhouette Symbol -->
      <circle cx="320" cy="150" r="18" fill="none" stroke="${tierColor}" stroke-width="2"/>
      <path d="M 290 220 C 290 185, 350 185, 350 220" fill="none" stroke="${tierColor}" stroke-width="2"/>

      <!-- OSD Telemetry Watermarks -->
      <text x="20" y="30" fill="#e6ece9" font-family="monospace" font-size="12" font-weight="bold">IBVAP CCTV EVIDENCE CAPTURE</text>
      <text x="20" y="48" fill="#5fd6c4" font-family="monospace" font-size="11">SOURCE: ${camera.toUpperCase()} // SECTOR-ALPHA</text>
      <text x="20" y="64" fill="#8fa39b" font-family="monospace" font-size="10">THREAT FORMULA: ${breakdownText}</text>

      <text x="620" y="30" text-anchor="end" fill="#e6c34a" font-family="monospace" font-size="12">${timestampStr}</text>
      <text x="620" y="48" text-anchor="end" fill="#5c6f68" font-family="monospace" font-size="10">ENCRYPTED AT REST: FERNET-AES128-CBC</text>

      <!-- Bottom Status Strip -->
      <rect x="0" y="332" width="640" height="28" fill="#111917" fill-opacity="0.9"/>
      <text x="20" y="351" fill="#8fa39b" font-family="monospace" font-size="11">STATUS: <tspan fill="${tierColor}" font-weight="bold">${subtext}</tspan></text>
      <text x="620" y="351" text-anchor="end" fill="#5fd6c4" font-family="monospace" font-size="11">FERNET SHA-256 HMAC VERIFIED</text>
    </svg>
  `.trim();

  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

// Generate realistic mock incidents over recent hours
const now = Math.floor(Date.now() / 1000);

export const mockIncidents: Incident[] = [
  {
    id: 101,
    trackId: 9042,
    personId: 104,
    category: "person",
    zoneTier: "red",
    score: 94.2,
    tier: "red",
    timestamp: now - 180, // 3 mins ago
    cameraName: "cam0",
    snapshotUrl: generateEvidenceSvg("cam0", "16:54:12 UTC", "PERSON // INTRUSION", "#e5484d", 9042, "CRITICAL VIRTUAL FENCE BREACH", "S:38.0 T:23.5 K:18.5 C:14.2"),
    cropUrl: generateEvidenceSvg("cam0", "16:54:12 UTC", "FACE CROP", "#e5484d", 9042, "FACIAL BIOMETRIC MATCH 96%"),
    burstUrls: [
      generateEvidenceSvg("cam0", "16:54:11 UTC", "BURST FRAME 1/3", "#e5484d", 9042, "APPROACHING PERIMETER"),
      generateEvidenceSvg("cam0", "16:54:12 UTC", "BURST FRAME 2/3", "#e5484d", 9042, "CROSSING FENCE LINE"),
      generateEvidenceSvg("cam0", "16:54:13 UTC", "BURST FRAME 3/3", "#e5484d", 9042, "INWARD VECTOR CONFIRMED"),
    ],
    watchlistMatch: "TARIQ AHMED",
    breakdown: { sectorRisk: 38.0, timeRisk: 23.5, kinematicsRisk: 18.5, classConfidence: 14.2 },
    reidGalleryId: "PG-9042",
    encryption: { cipher: "FERNET-AES128-CBC", keyPath: "database/evidence.key", verified: true },
  },
  {
    id: 102,
    trackId: 9041,
    personId: null,
    category: "vehicle",
    zoneTier: "yellow",
    score: 68.5,
    tier: "yellow",
    timestamp: now - 420, // 7 mins ago
    cameraName: "cam2",
    snapshotUrl: generateEvidenceSvg("cam2", "16:50:18 UTC", "VEHICLE // UNREGISTERED", "#e6c34a", 9041, "CAUTION PERIMETER ROAD MOVING SLOW", "S:24.0 T:18.0 K:16.5 C:10.0"),
    cropUrl: generateEvidenceSvg("cam2", "16:50:18 UTC", "ANPR PLATE", "#e6c34a", 9041, "PLATE DETECT: JK-02-AZ-4412"),
    burstUrls: [
      generateEvidenceSvg("cam2", "16:50:17 UTC", "BURST 1/2", "#e6c34a", 9041, "APPROACHING BUFFER ZONE"),
      generateEvidenceSvg("cam2", "16:50:19 UTC", "BURST 2/2", "#e6c34a", 9041, "STOPPED AT BUFFER BOUNDARY"),
    ],
    watchlistMatch: null,
    breakdown: { sectorRisk: 24.0, timeRisk: 18.0, kinematicsRisk: 16.5, classConfidence: 10.0 },
    reidGalleryId: "PG-9041",
    encryption: { cipher: "FERNET-AES128-CBC", keyPath: "database/evidence.key", verified: true },
  },
  {
    id: 103,
    trackId: 9038,
    personId: 211,
    category: "person",
    zoneTier: "yellow",
    score: 88.0,
    tier: "red", // Escalated to RED due to watchlist match!
    timestamp: now - 950, // 15 mins ago
    cameraName: "cam1",
    snapshotUrl: generateEvidenceSvg("cam1", "16:41:20 UTC", "PERSON // ESCALATED", "#e5484d", 9038, "WATCHLIST MATCH ESCALATED TO RED", "S:25.0 T:21.0 K:15.0 C:14.0 [OVERRIDE >=70]"),
    cropUrl: generateEvidenceSvg("cam1", "16:41:20 UTC", "FACE CROP", "#e5484d", 9038, "SIMILARITY 92.4%"),
    burstUrls: [
      generateEvidenceSvg("cam1", "16:41:19 UTC", "BURST 1/2", "#e5484d", 9038, "EAST CHECKPOST ENTRY"),
      generateEvidenceSvg("cam1", "16:41:21 UTC", "BURST 2/2", "#e5484d", 9038, "MONITORED SUBJECT"),
    ],
    watchlistMatch: "VIKRAM SINGH",
    breakdown: { sectorRisk: 25.0, timeRisk: 21.0, kinematicsRisk: 15.0, classConfidence: 14.0 },
    reidGalleryId: "PG-9038",
    encryption: { cipher: "FERNET-AES128-CBC", keyPath: "database/evidence.key", verified: true },
  },
  {
    id: 104,
    trackId: 9035,
    personId: null,
    category: "person",
    zoneTier: "green",
    score: 18.0,
    tier: "green",
    timestamp: now - 1800, // 30 mins ago
    cameraName: "cam3",
    snapshotUrl: generateEvidenceSvg("cam3", "16:27:10 UTC", "PERSON // AUTHORIZED", "#4fbf7a", 9035, "NORMAL PATROL ROUTE", "S:5.0 T:0.0 K:4.0 C:9.0"),
    cropUrl: null,
    burstUrls: [],
    watchlistMatch: null,
    breakdown: { sectorRisk: 5.0, timeRisk: 0.0, kinematicsRisk: 4.0, classConfidence: 9.0 },
    reidGalleryId: "PG-9035",
    encryption: { cipher: "FERNET-AES128-CBC", keyPath: "database/evidence.key", verified: true },
  },
  {
    id: 105,
    trackId: 9031,
    personId: null,
    category: "unknown",
    zoneTier: "yellow",
    score: 54.0,
    tier: "yellow",
    timestamp: now - 2400, // 40 mins ago
    cameraName: "cam0",
    snapshotUrl: generateEvidenceSvg("cam0", "16:17:05 UTC", "UNKNOWN // THERMAL BLOB", "#e6c34a", 9031, "LOW-LIGHT MOVING TARGET", "S:20.0 T:15.0 K:12.0 C:7.0"),
    cropUrl: null,
    burstUrls: [
      generateEvidenceSvg("cam0", "16:17:04 UTC", "BURST 1/2", "#e6c34a", 9031, "FENCE BOUNDARY MOVEMENT"),
      generateEvidenceSvg("cam0", "16:17:06 UTC", "BURST 2/2", "#e6c34a", 9031, "TARGET CLOUD COVER"),
    ],
    watchlistMatch: null,
    breakdown: { sectorRisk: 20.0, timeRisk: 15.0, kinematicsRisk: 12.0, classConfidence: 7.0 },
    reidGalleryId: "PG-9031",
    encryption: { cipher: "FERNET-AES128-CBC", keyPath: "database/evidence.key", verified: true },
  },
  {
    id: 106,
    trackId: 9028,
    personId: null,
    category: "vehicle",
    zoneTier: "red",
    score: 91.5,
    tier: "red",
    timestamp: now - 3200, // 53 mins ago
    cameraName: "cam2",
    snapshotUrl: generateEvidenceSvg("cam2", "16:03:40 UTC", "VEHICLE // HIGH SPEED", "#e5484d", 9028, "UNAUTHORIZED HEAVY VEHICLE AT GATE", "S:36.0 T:22.5 K:19.0 C:14.0"),
    cropUrl: generateEvidenceSvg("cam2", "16:03:40 UTC", "VEHICLE BBOX", "#e5484d", 9028, "TRUCK CHASSIS 4x4"),
    burstUrls: [
      generateEvidenceSvg("cam2", "16:03:38 UTC", "BURST 1/3", "#e5484d", 9028, "BREACHING BARRIER POINT"),
      generateEvidenceSvg("cam2", "16:03:40 UTC", "BURST 2/3", "#e5484d", 9028, "ACTIVE WARNING SIREN"),
      generateEvidenceSvg("cam2", "16:03:42 UTC", "BURST 3/3", "#e5484d", 9028, "INTERCEPT TEAM DISPATCHED"),
    ],
    watchlistMatch: null,
    breakdown: { sectorRisk: 36.0, timeRisk: 22.5, kinematicsRisk: 19.0, classConfidence: 14.0 },
    reidGalleryId: "PG-9028",
    encryption: { cipher: "FERNET-AES128-CBC", keyPath: "database/evidence.key", verified: true },
  },
  {
    id: 107,
    trackId: 9024,
    personId: 302,
    category: "person",
    zoneTier: "red",
    score: 97.0,
    tier: "red",
    timestamp: now - 4500, // 1h 15m ago
    cameraName: "cam3",
    snapshotUrl: generateEvidenceSvg("cam3", "15:42:15 UTC", "PERSON // RED SECTOR", "#e5484d", 9024, "HIGH PRIORITY SUSPECT DETECTED", "S:39.0 T:24.0 K:19.0 C:15.0"),
    cropUrl: generateEvidenceSvg("cam3", "15:42:15 UTC", "FACE CROP", "#e5484d", 9024, "INSIGHTFACE MATCH 98.1%"),
    burstUrls: [
      generateEvidenceSvg("cam3", "15:42:14 UTC", "BURST 1/2", "#e5484d", 9024, "COVERT CRAWL IN VEGETATION"),
      generateEvidenceSvg("cam3", "15:42:16 UTC", "BURST 2/2", "#e5484d", 9024, "CROSSING DRY RIVERBED"),
    ],
    watchlistMatch: "BILAL HUSSAIN",
    breakdown: { sectorRisk: 39.0, timeRisk: 24.0, kinematicsRisk: 19.0, classConfidence: 15.0 },
    reidGalleryId: "PG-9024",
    encryption: { cipher: "FERNET-AES128-CBC", keyPath: "database/evidence.key", verified: true },
  },
  {
    id: 108,
    trackId: 9019,
    personId: null,
    category: "vehicle",
    zoneTier: "green",
    score: 12.0,
    tier: "green",
    timestamp: now - 5600, // 1h 33m ago
    cameraName: "cam1",
    snapshotUrl: generateEvidenceSvg("cam1", "15:23:45 UTC", "VEHICLE // LOGISTICS", "#4fbf7a", 9019, "SUPPLY TRUCK AUTHORIZED PASS", "S:4.0 T:0.0 K:2.0 C:6.0"),
    cropUrl: null,
    burstUrls: [],
    watchlistMatch: null,
    breakdown: { sectorRisk: 4.0, timeRisk: 0.0, kinematicsRisk: 2.0, classConfidence: 6.0 },
    reidGalleryId: "PG-9019",
    encryption: { cipher: "FERNET-AES128-CBC", keyPath: "database/evidence.key", verified: true },
  },
  {
    id: 109,
    trackId: 9014,
    personId: null,
    category: "unknown",
    zoneTier: "green",
    score: 8.5,
    tier: "green",
    timestamp: now - 6800, // ~2 hrs ago
    cameraName: "cam0",
    snapshotUrl: generateEvidenceSvg("cam0", "15:03:20 UTC", "UNKNOWN // WILDLIFE", "#4fbf7a", 9014, "ANIMAL CROSSING OUTSIDE BUFFER", "S:2.0 T:0.0 K:2.5 C:4.0"),
    cropUrl: null,
    burstUrls: [],
    watchlistMatch: null,
    breakdown: { sectorRisk: 2.0, timeRisk: 0.0, kinematicsRisk: 2.5, classConfidence: 4.0 },
    reidGalleryId: "PG-9014",
    encryption: { cipher: "FERNET-AES128-CBC", keyPath: "database/evidence.key", verified: true },
  },
  {
    id: 110,
    trackId: 9008,
    personId: null,
    category: "person",
    zoneTier: "yellow",
    score: 64.0,
    tier: "yellow",
    timestamp: now - 8200, // ~2.2 hrs ago
    cameraName: "cam2",
    snapshotUrl: generateEvidenceSvg("cam2", "14:40:02 UTC", "PERSON // CAUTION ZONE", "#e6c34a", 9008, "WALKING ADJACENT TO PERIMETER", "S:22.0 T:17.0 K:14.0 C:11.0"),
    cropUrl: null,
    burstUrls: [
      generateEvidenceSvg("cam2", "14:40:01 UTC", "BURST 1/2", "#e6c34a", 9008, "APPROACH TRACK"),
      generateEvidenceSvg("cam2", "14:40:03 UTC", "BURST 2/2", "#e6c34a", 9008, "OUTWARD VECTOR CONFIRMED"),
    ],
    watchlistMatch: null,
    breakdown: { sectorRisk: 22.0, timeRisk: 17.0, kinematicsRisk: 14.0, classConfidence: 11.0 },
    reidGalleryId: "PG-9008",
    encryption: { cipher: "FERNET-AES128-CBC", keyPath: "database/evidence.key", verified: true },
  },
  {
    id: 111,
    trackId: 9003,
    personId: 104,
    category: "person",
    zoneTier: "red",
    score: 95.8,
    tier: "red",
    timestamp: now - 9800, // ~2.7 hrs ago
    cameraName: "cam0",
    snapshotUrl: generateEvidenceSvg("cam0", "14:13:22 UTC", "PERSON // RE-ENTRY ATTEMPT", "#e5484d", 9003, "PRIOR WATCHLIST SUBJECT SPOTTED", "S:38.0 T:24.0 K:19.0 C:14.8"),
    cropUrl: generateEvidenceSvg("cam0", "14:13:22 UTC", "FACE CROP", "#e5484d", 9003, "CONFIRMATION 94.7%"),
    burstUrls: [
      generateEvidenceSvg("cam0", "14:13:21 UTC", "BURST 1/3", "#e5484d", 9003, "SURVEILLANCE IDENTIFICATION"),
      generateEvidenceSvg("cam0", "14:13:23 UTC", "BURST 2/3", "#e5484d", 9003, "FENCE BREACH ATTEMPT"),
      generateEvidenceSvg("cam0", "14:13:24 UTC", "BURST 3/3", "#e5484d", 9003, "PATROL ALARM TRIGGERED"),
    ],
    watchlistMatch: "TARIQ AHMED",
    breakdown: { sectorRisk: 38.0, timeRisk: 24.0, kinematicsRisk: 19.0, classConfidence: 14.8 },
    reidGalleryId: "PG-9003",
    encryption: { cipher: "FERNET-AES128-CBC", keyPath: "database/evidence.key", verified: true },
  },
  {
    id: 112,
    trackId: 8997,
    personId: null,
    category: "vehicle",
    zoneTier: "yellow",
    score: 58.2,
    tier: "yellow",
    timestamp: now - 11400, // ~3.1 hrs ago
    cameraName: "cam1",
    snapshotUrl: generateEvidenceSvg("cam1", "13:46:11 UTC", "VEHICLE // UNKNOWN TRACTOR", "#e6c34a", 8997, "AGRICULTURAL VEHICLE IN BUFFER ZONE", "S:20.0 T:14.0 K:14.2 C:10.0"),
    cropUrl: null,
    burstUrls: [],
    watchlistMatch: null,
    breakdown: { sectorRisk: 20.0, timeRisk: 14.0, kinematicsRisk: 14.2, classConfidence: 10.0 },
    reidGalleryId: "PG-8997",
    encryption: { cipher: "FERNET-AES128-CBC", keyPath: "database/evidence.key", verified: true },
  },
  {
    id: 113,
    trackId: 8991,
    personId: null,
    category: "person",
    zoneTier: "green",
    score: 14.5,
    tier: "green",
    timestamp: now - 13200, // ~3.6 hrs ago
    cameraName: "cam3",
    snapshotUrl: generateEvidenceSvg("cam3", "13:16:40 UTC", "PERSON // BORDER PATROL", "#4fbf7a", 8991, "ROUTINE FENCE INSPECTION", "S:4.0 T:0.0 K:2.5 C:8.0"),
    cropUrl: null,
    burstUrls: [],
    watchlistMatch: null,
    breakdown: { sectorRisk: 4.0, timeRisk: 0.0, kinematicsRisk: 2.5, classConfidence: 8.0 },
    reidGalleryId: "PG-8991",
    encryption: { cipher: "FERNET-AES128-CBC", keyPath: "database/evidence.key", verified: true },
  },
  {
    id: 114,
    trackId: 8985,
    personId: null,
    category: "unknown",
    zoneTier: "yellow",
    score: 61.0,
    tier: "yellow",
    timestamp: now - 15000, // ~4.1 hrs ago
    cameraName: "cam2",
    snapshotUrl: generateEvidenceSvg("cam2", "12:46:33 UTC", "UNKNOWN // SHADOW BLOB", "#e6c34a", 8985, "MOTION AT PERIMETER CORNER", "S:22.0 T:16.0 K:14.0 C:9.0"),
    cropUrl: null,
    burstUrls: [],
    watchlistMatch: null,
    breakdown: { sectorRisk: 22.0, timeRisk: 16.0, kinematicsRisk: 14.0, classConfidence: 9.0 },
    reidGalleryId: "PG-8985",
    encryption: { cipher: "FERNET-AES128-CBC", keyPath: "database/evidence.key", verified: true },
  },
  {
    id: 115,
    trackId: 8979,
    personId: 405,
    category: "person",
    zoneTier: "yellow",
    score: 86.5,
    tier: "red", // Escalated to RED
    timestamp: now - 16800, // ~4.6 hrs ago
    cameraName: "cam1",
    snapshotUrl: generateEvidenceSvg("cam1", "12:16:21 UTC", "PERSON // FLAGGED SUSPECT", "#e5484d", 8979, "WATCHLIST PERSON ESCALATED", "S:24.0 T:20.0 K:16.5 C:14.0 [OVERRIDE >=70]"),
    cropUrl: generateEvidenceSvg("cam1", "12:16:21 UTC", "FACE CROP", "#e5484d", 8979, "MATCH CONFIRMED 89%"),
    burstUrls: [
      generateEvidenceSvg("cam1", "12:16:20 UTC", "BURST 1/2", "#e5484d", 8979, "APPROACHING CULVERT"),
      generateEvidenceSvg("cam1", "12:16:22 UTC", "BURST 2/2", "#e5484d", 8979, "SECTOR ALERT DISPATCHED"),
    ],
    watchlistMatch: "RASHID MALIK",
    breakdown: { sectorRisk: 24.0, timeRisk: 20.0, kinematicsRisk: 16.5, classConfidence: 14.0 },
    reidGalleryId: "PG-8979",
    encryption: { cipher: "FERNET-AES128-CBC", keyPath: "database/evidence.key", verified: true },
  },
];

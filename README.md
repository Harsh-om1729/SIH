# IBVAP — Intelligent Border Video Analytics Platform

Built phase by phase per `../Roadmap`. See that file for the full plan.

## Setup

```bash
cd ibvap
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

## Phase status

- [x] Phase 0 — Foundation
- [x] Phase 1 — Camera Input
- [x] Phase 2 — Multi-Camera Stream Management
- [x] Phase 3 — Weather / Low-Light Preprocessing
- [x] Phase 3A — Adaptive Activity Gate
- [x] Phase 4 — YOLO Detection
- [x] Phase 5 — ONNX + INT8 + OpenVINO (ONNX fp32 adopted; INT8/OpenVINO documented as Intel-hardware-dependent, see below)
- [x] Phase 6 — Tracking (ByteTrack)
- [x] Phase 7 — False-Alarm Filter (aspect-ratio check + ResNet-18 appearance-based Re-ID gallery for stable person IDs across brief disappearances)
- [x] Phase 7A — Vehicle Classification (already satisfied by YOLO's granular COCO classes — car/truck/bus/motorcycle/bicycle shown distinctly, verified against recorded footage; tractor class + Indian-vehicle fine-tuning remain future work, no labeled dataset available)
- [x] Phase 8 — 3-Zone Tactical Logic (interactive click-to-draw zones on the existing OpenCV window in place of the Phase 13 dashboard UI; Red/Yellow/Green priority, Yellow inward/outward direction, Green curfew re-tiering — all covered by unit tests, red zone also live-verified)
- [x] Phase 9 — Offline Threat Intelligence (SQLite `threat_rules.db`: sector/time/class-confidence lookups + movement config, seeded once and never overwritten so local tuning persists; unit tested, live-verified via diagnostic overlay)
- [x] Phase 10 — Threat Score / Decision Engine (T = S_sector + T_time + K_kinematics + C_class, 0-100, tiered Green/Yellow/Red; unit tested + live-verified)
- [x] Phase 11 — Alerting (Green=silent log, Yellow=synthesized chime+snapshot, Red=siren+snapshot burst+logged radio-metadata stub; per-track rate limiting with escalation bypass; unit tested + live-verified with audio)
- [x] Phase 12 — Incident DB + Evidence (SQLite `incidents.db` + Fernet-encrypted full/crop/burst evidence images, reusing Phase 11's alert firing/rate-limit decisions; unit tested + live-verified by directly querying the DB)
- [x] Phase 12A — Facial Recognition + Watchlist (face detection+embedding via InsightFace buffalo_s — since Phase 4 never added a separate YOLOv8-Face detector, this fills that gap too; SQLite watchlist.db, cosine match escalates to Red regardless of zone; unit tested + live-verified with a real photo. **DPDP Act caveat**: any real deployment of a watchlist DB of biometric face data needs authorized data-handling procedures under India's DPDP Act — not just a modeling detail)
- [x] Phase 13 — Local Dashboard (Streamlit prototype: live annotated feed + recent-incidents table, reusing the exact same pipeline as app.py; zone drawing stays in the OpenCV app's Phase 8 drawer, loaded read-only here; live-verified in browser)
- [x] Phase 14 — Offline / Air-Gapped Operation (live-verified with Wi-Fi fully disabled: detect→track→score→alert→DB all worked; also added encrypted USB-transfer bundle scripts for threat_rules.db/watchlist.db updates, unit tested)
- [x] Phase 15 — Cross-Camera Re-ID (single shared `PersonGallery` across all cameras, keyed by `(camera_name, track_id)` to prevent cross-camera ID collisions; unit tested + live-verified with 2 simultaneous streams — different people stayed on distinct IDs, no false merging)
- [x] Phase 16 — Command & Control Integration (FastAPI `/incidents` + `/status` JSON endpoints, outbound webhook, syslog-formatted UDP events — all fail-safe/non-blocking if unreachable; VHF/LoRa stays a logged stand-in per Phase 11, no real radio hardware; unit tested + live-verified)

## Phase 5 benchmark notes (measured on Apple M4, run via `scripts/benchmark_models.py`)

| Model | Avg latency | FPS |
|---|---|---|
| PyTorch (.pt) | 31.7 ms | 31.6 |
| ONNX (fp32) | 7.1 ms | 140.9 |
| ONNX (int8, dynamic quant) | 86.8 ms | 11.5 |

ONNX Runtime (fp32) is the default — it's dramatically faster here because it
auto-selects Apple's CoreML execution provider (Neural Engine/GPU). Dynamic
INT8 quantization made things *worse* on this hardware: the quantized graph
fragmented into many more CoreML/CPU partitions, adding overhead with no
compensating speedup. INT8's real benefit (via VNNI instructions + OpenVINO)
is expected on the target Intel i3/i5 field-deployment hardware, not verified
here — worth stating explicitly as a caveat in the SIH report rather than
claiming INT8 as a universal win.

Also found and fixed during this phase: the webcam was capturing at native
1080p by default, which inflated every pipeline stage. Camera capture is now
explicitly requested at 640x480 (`CAMERA_WIDTH`/`CAMERA_HEIGHT` in `.env`).

## Phase 7 Re-ID design notes

ByteTrack alone only matches detections frame-to-frame by motion/position, so
a person who leaves frame (or is occluded) longer than its internal track
buffer gets a brand-new `track_id` on return — worth stating plainly in the
report as a limitation of motion-based tracking, not a bug. `reid/reid.py`'s
`PersonGallery` closes that gap by matching appearance across track_ids.

Two embedding approaches were tried, in order:
1. **HSV color histogram** (roadmap's cheapest suggested option) — failed in
   practice: different people wearing similar neutral-toned (white/grey/beige)
   clothing produced near-identical histograms, since hue is close to
   meaningless for low-saturation pixels. Verified via live testing (multiple
   people got merged into the same ID), not just theorized.
2. **ResNet-18 embedding** (ImageNet-pretrained, classification head removed,
   512-d feature) — the roadmap's other named option for this phase. Captures
   shape/texture/pattern, not just color, and reliably separated people in
   similar clothing in testing. Adopted as the default.

Other measures that mattered in practice: deciding a new track's identity
from the *average* of its first few embeddings (not a single frame) to cancel
out noise from partial/edge-clipped boxes, and skipping embedding entirely for
boxes below a minimum size. Both configurable: `REID_SIMILARITY_THRESHOLD`,
`REID_TTL_SECONDS` in `.env`.

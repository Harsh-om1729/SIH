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
- [ ] Phase 7 — False-Alarm Filter
- [ ] Phase 7A — Vehicle Classification
- [ ] Phase 8 — 3-Zone Tactical Logic
- [ ] Phase 9 — Offline Threat Intelligence
- [ ] Phase 10 — Threat Score / Decision Engine
- [ ] Phase 11 — Alerting
- [ ] Phase 12 — Incident DB + Evidence
- [ ] Phase 12A — Facial Recognition + Watchlist
- [ ] Phase 13 — Local Dashboard
- [ ] Phase 14 — Offline / Air-Gapped Operation
- [ ] Phase 15 — Cross-Camera Re-ID
- [ ] Phase 16 — Command & Control Integration

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
# SIH

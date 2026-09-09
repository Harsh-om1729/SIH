"""Phase 1 baseline measurement harness.

Runs the REAL pipeline stages and reports per-stage latency, throughput and
process resource use. Nothing here is estimated: every number printed comes
from executing the actual code under `time.perf_counter`.

Input is a synthetic video built from a standard test image containing
people, panned to induce motion so tracking, scoring and alerting all run on
genuine detections. That is a deliberate choice: it is reproducible, needs no
live camera, and exposes no real footage. It is NOT a substitute for
measuring against a real RTSP feed — capture latency in particular is not
representative here, and that limitation is printed with the results.

Run from ibvap/:
    python scripts/measure_baseline.py --frames 120
"""

import argparse
import json
import os
import platform
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np

from activity_gate.gate import ActivityGate
from alerts.alert_manager import AlertManager
from alerts.dispatch import AlertDispatcher
from detection.draw import draw_detections
from filtering.false_alarm import FalseAlarmFilter
from intelligence.threat_rules import ThreatRulesDB
from intelligence.threat_score import ThreatScorer
from metrics import MetricsCollector, ResourceSampler
from preprocessing.enhance import Preprocessor
from tracking.tracker import Tracker
from zones.zone_engine import ZoneEngine

CAMERA = "bench0"


def build_synthetic_video(path: str, frames: int, width: int, height: int) -> str:
    """Writes a synthetic clip by panning a real test image containing people.

    Using a real photograph (ultralytics' bundled bus.jpg) rather than drawn
    rectangles matters: it produces genuine person detections, so tracking,
    scoring and alert dispatch are exercised on a realistic detection count
    instead of an empty frame.
    """
    import ultralytics

    source = os.path.join(os.path.dirname(ultralytics.__file__), "assets", "bus.jpg")
    if not os.path.exists(source):
        raise FileNotFoundError(f"test asset missing: {source}")
    image = cv2.imread(source)
    if image is None:
        raise RuntimeError(f"could not decode test asset: {source}")

    canvas_w = int(width * 1.4)
    image = cv2.resize(image, (canvas_w, height))
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 30.0, (width, height))
    if not writer.isOpened():
        raise RuntimeError("OpenCV could not open a VideoWriter for the synthetic clip")
    span = canvas_w - width
    for i in range(frames):
        # Ping-pong pan so objects move, stop, and reverse - this makes
        # ByteTrack actually track rather than re-detect a static scene.
        t = i / max(frames - 1, 1)
        offset = int(span * (1 - abs(2 * t - 1)))
        writer.write(image[:, offset:offset + width].copy())
    writer.release()
    return path


def environment() -> dict:
    env = {
        "platform": platform.platform(),
        "processor": platform.processor() or "unknown",
        "python": platform.python_version(),
        "cpu_count_logical": os.cpu_count(),
        "opencv": cv2.__version__,
    }
    try:
        import torch

        env["torch"] = torch.__version__
        env["cuda_available"] = bool(torch.cuda.is_available())
        env["device"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"
    except Exception:
        env["torch"] = "unavailable"
        env["cuda_available"] = False
        env["device"] = "cpu"
    try:
        import onnxruntime

        from detection.detector import (
            CPU_EXECUTION_PROVIDER,
            ONNX_PROVIDERS_AVAILABLE,
        )

        env["onnxruntime"] = onnxruntime.__version__
        # The build's true provider list, snapshotted before pinning, so this
        # record shows what was excluded rather than only what was used.
        env["onnx_providers_available"] = list(ONNX_PROVIDERS_AVAILABLE)
        env["onnx_provider_pinned"] = CPU_EXECUTION_PROVIDER
    except Exception:
        env["onnxruntime"] = "unavailable"
    return env


def measure_collector_overhead(iterations: int = 200_000) -> dict:
    """How much the instrumentation itself costs per stage-timing."""
    collector = MetricsCollector(window=512)
    start = time.perf_counter()
    for _ in range(iterations):
        with collector.stage(CAMERA, "overhead_probe"):
            pass
    elapsed = time.perf_counter() - start
    return {
        "iterations": iterations,
        "per_call_us": 1e6 * elapsed / iterations,
        "rings_created": collector.tracked_keys(),
    }


def run(args) -> int:
    model_path = args.model
    if not os.path.exists(model_path):
        print(f"BLOCKED: model weights not found at {model_path}", file=sys.stderr)
        return 2

    metrics = MetricsCollector(window=1024)
    resources = ResourceSampler(min_interval_s=1.0)

    print("=" * 74)
    print("IBVAP PHASE 1 - BASELINE MEASUREMENT")
    print("=" * 74)
    env = environment()
    for key, value in env.items():
        print(f"  {key:20} {value}")

    clip = os.path.join(args.workdir, "synthetic_baseline.mp4")
    os.makedirs(args.workdir, exist_ok=True)
    build_synthetic_video(clip, args.frames, args.width, args.height)
    print(f"\n  synthetic clip        {clip} ({args.frames} frames @ {args.width}x{args.height})")

    # ---- construct the real pipeline stages -------------------------------
    load_start = time.perf_counter()
    tracker = Tracker(model_path=model_path, confidence=args.confidence)
    model_load_s = time.perf_counter() - load_start

    preprocessor = Preprocessor(CAMERA)
    gate = ActivityGate()
    false_alarm = FalseAlarmFilter()
    zone_engine = ZoneEngine(config_path=os.path.join(args.workdir, "zones_bench.json"))
    threat_rules = ThreatRulesDB(db_path=os.path.join(args.workdir, "threat_rules.db"))
    scorer = ThreatScorer(threat_rules)
    dispatcher = AlertDispatcher(maxsize=64)
    alert_manager = AlertManager(
        snapshot_dir=os.path.join(args.workdir, "snapshots"),
        cooldown_seconds=8.0,
        dispatcher=dispatcher,
    )

    baseline_rss = resources.sample(force=True)
    capture = cv2.VideoCapture(clip)
    if not capture.isOpened():
        print("BLOCKED: could not reopen synthetic clip", file=sys.stderr)
        return 2

    # Warm-up frames are executed but NOT measured: the first inference pays
    # ONNX session construction and allocator warm-up (seconds), which would
    # otherwise dominate the mean and misrepresent steady-state latency.
    warmup_done = 0
    warmup_first_frame_s = None
    while warmup_done < args.warmup:
        ok, frame = capture.read()
        if not ok or frame is None:
            break
        t0 = time.perf_counter()
        tracker.track(preprocessor.process(frame))
        if warmup_done == 0:
            warmup_first_frame_s = time.perf_counter() - t0
        warmup_done += 1

    rss_series = []
    detection_counts = []
    e2e_samples = []
    frames_done = 0
    rss_after_warmup = resources.sample(force=True)

    loop_start = time.perf_counter()
    while frames_done < args.frames:
        with metrics.stage(CAMERA, "01_capture"):
            ok, frame = capture.read()
        if not ok or frame is None:
            break

        frame_t0 = time.perf_counter()

        with metrics.stage(CAMERA, "02_activity_gate"):
            active, motion_score = gate.is_active(frame)

        with metrics.stage(CAMERA, "03_preprocess"):
            processed = preprocessor.process(frame)

        with metrics.stage(CAMERA, "04_detect_track"):
            detections = tracker.track(processed)

        with metrics.stage(CAMERA, "05_false_alarm_filter"):
            detections = false_alarm.filter(detections)

        detection_counts.append(len(detections))

        with metrics.stage(CAMERA, "06_zone_classify"):
            for det in detections:
                x1, y1, x2, y2 = det.box
                result = zone_engine.classify(((x1 + x2) // 2, y2), det.direction)
                det.zone_tier = result["tier"]
                det.zone_direction = result["direction"]

        with metrics.stage(CAMERA, "07_threat_score"):
            scores = [
                scorer.score(
                    zone_tier=det.zone_tier,
                    hour=datetime.now().hour,
                    speed_px_per_frame=det.speed,
                    category=det.category(),
                )
                for det in detections
            ]

        with metrics.stage(CAMERA, "08_draw"):
            draw_detections(processed, detections)

        with metrics.stage(CAMERA, "09_alert_dispatch"):
            for det, score in zip(detections, scores):
                alert_manager.handle(det, score, [processed])

        e2e_samples.append(time.perf_counter() - frame_t0)
        frames_done += 1

        sample = resources.sample()
        if sample.get("available") and (not rss_series or sample is not rss_series[-1][1]):
            rss_series.append((frames_done, sample))

    wall = time.perf_counter() - loop_start
    capture.release()

    flushed = dispatcher.stop(timeout=10.0)
    dispatch_stats = dispatcher.stats()
    final_rss = resources.sample(force=True)
    threat_rules.close()

    # ---- report -----------------------------------------------------------
    snapshot = metrics.snapshot()
    e2e_sorted = sorted(e2e_samples)

    print(f"\n  model load            {model_load_s * 1000:.0f} ms  ({model_path})")
    print(f"  frames processed      {frames_done}")
    print(f"  wall time             {wall:.2f} s")
    print(f"  throughput            {frames_done / wall:.2f} FPS (single camera, this host)")
    if detection_counts:
        print(
            f"  detections/frame      mean {sum(detection_counts)/len(detection_counts):.2f}"
            f"  max {max(detection_counts)}"
        )

    print("\n  PER-STAGE LATENCY (ms)")
    print(f"    {'stage':<26}{'n':>6}{'mean':>10}{'p50':>10}{'p95':>10}{'max':>10}")
    for name in sorted(snapshot["stages"]):
        s = snapshot["stages"][name]
        if not s.get("count"):
            continue
        label = name.split("/", 1)[1]
        print(
            f"    {label:<26}{s['count']:>6}{s['mean_ms']:>10.2f}"
            f"{s['p50_ms']:>10.2f}{s['p95_ms']:>10.2f}{s['max_ms']:>10.2f}"
        )

    if e2e_sorted:
        def pct(f):
            return 1000 * e2e_sorted[min(len(e2e_sorted) - 1, round(f * (len(e2e_sorted) - 1)))]
        print("\n  END-TO-END per frame (gate -> dispatch handoff), ms")
        print(
            f"    mean {1000*sum(e2e_sorted)/len(e2e_sorted):.2f}   "
            f"p50 {pct(.50):.2f}   p95 {pct(.95):.2f}   max {pct(1.0):.2f}"
        )

    print("\n  PROCESS RESOURCES")
    if final_rss.get("available"):
        print(f"    RSS baseline        {baseline_rss['rss_mb']:.1f} MB (before model load)")
        if rss_after_warmup.get("available"):
            print(f"    RSS after warm-up   {rss_after_warmup['rss_mb']:.1f} MB (steady-state start)")
        print(f"    RSS final           {final_rss['rss_mb']:.1f} MB")
        print(f"    RSS delta           {final_rss['rss_mb'] - baseline_rss['rss_mb']:+.1f} MB")
        print(f"    threads             {final_rss['threads']}")
        print(f"    samples captured    {len(rss_series)}")
        if rss_after_warmup.get("available"):
            drift = final_rss['rss_mb'] - rss_after_warmup['rss_mb']
            print(f"    steady-state drift  {drift:+.1f} MB over {frames_done} measured frames")
        if len(rss_series) >= 2:
            trend = "  ".join(f"f{n}:{s['rss_mb']:.0f}MB" for n, s in rss_series[:8])
            print(f"    trend               {trend}")
    else:
        print("    UNAVAILABLE (psutil not installed)")

    print("\n  ALERT DISPATCH")
    print(f"    {dispatch_stats}  flushed_cleanly={flushed}")

    overhead = measure_collector_overhead()
    print("\n  INSTRUMENTATION OVERHEAD")
    print(
        f"    {overhead['per_call_us']:.3f} us per stage timing "
        f"({overhead['iterations']:,} iterations)"
    )
    print(f"    bounded ring keys   {metrics.tracked_keys()}")

    print("\n  LIMITATIONS OF THIS RUN")
    print("    - Synthetic clip from a still image; NOT real border footage.")
    print("    - Capture latency is file I/O, NOT representative of RTSP/USB.")
    print("    - Single camera; multi-camera contention not measured here.")
    print("    - Re-ID / face / watchlist stages NOT exercised (no face model loaded).")
    print("    - Short run; says nothing about multi-hour memory behaviour.")
    print("=" * 74)

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "environment": env,
                    "frames": frames_done,
                    "wall_s": wall,
                    "fps": frames_done / wall,
                    "model_load_ms": model_load_s * 1000,
                    "stages": snapshot["stages"],
                    "counters": snapshot["counters"],
                    "dispatch": dispatch_stats,
                    "rss_baseline_mb": baseline_rss.get("rss_mb"),
                    "rss_final_mb": final_rss.get("rss_mb"),
                    "rss_after_warmup_mb": rss_after_warmup.get("rss_mb"),
                    "warmup_frames": warmup_done,
                    "overhead_us_per_call": overhead["per_call_us"],
                },
                fh,
                indent=2,
            )
        print(f"  wrote {args.json}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="IBVAP Phase 1 baseline measurement")
    parser.add_argument("--frames", type=int, default=120)
    parser.add_argument("--warmup", type=int, default=10,
                        help="frames executed but excluded from measurement")
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--model", default="models/yolov8n.onnx")
    parser.add_argument("--confidence", type=float, default=0.4)
    parser.add_argument("--workdir", default="benchmark_out")
    parser.add_argument("--json", default=None)
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())

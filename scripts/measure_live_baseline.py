"""Phase 1 LIVE-CAMERA baseline measurement (single bounded run).

Companion to `scripts/measure_baseline.py`, which measures the same pipeline
against a synthetic clip built from a still image. This one drives the real
capture path: the real `StreamManager` producer thread, the real
`CameraSource`, and a configured local camera.

The two are NOT directly comparable and must never be reported as if they
were - different workload, different scene content, different capture
mechanism. See "COMPARABILITY" in the printed report.

What is measured here that the file-based baseline cannot measure:

- camera open latency and time-to-first-frame on a real device
- device-side capture latency (`cap.read()`, timed on the producer thread)
- consumer-side queue latency (what the app loop actually waits on)
- health/reconnect behaviour of a live source
- the real frame-drop ratio between a free-running camera and a slower
  pipeline (the newest-frame-only policy in `CameraStream`)

Instrumentation is non-invasive: no production module is modified. Device
timing is obtained through `CameraStream`'s existing `camera_factory` hook.

Privacy: every artefact this run can produce (evidence DB, encryption key,
snapshots, zone config) is written under a caller-supplied scratch
`--workdir`, reported by count, and removed unless `--keep` is passed. No
frame, crop or embedding is retained after the run.

Run from the repo root:
    python scripts/measure_live_baseline.py --duration 60 --json out.json
"""

import os
import socket
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------------------------------------------------------------------------
# Outbound-network guard.
#
# Installed BEFORE any project or third-party import, so an import-time
# connectivity probe (the exact thing config/offline.py suppresses in
# ultralytics) is recorded rather than missed. Every hook records and then
# delegates to the original - this observes, it never blocks, so it cannot
# change what the pipeline does.
#
# Limitation, stated because it bounds the claim: this sees the CPython
# `socket` module surface only. A library calling `_socket` directly, or
# issuing traffic from native code, would not appear here.
# ---------------------------------------------------------------------------

_NET_LOCK = threading.Lock()
_NET_EVENTS: list = []
_NET_COUNTS: dict = {}
_NET_EVENT_CAP = 200


def _classify_host(host) -> str:
    if host is None:
        return "local"
    text = str(host).lower()
    if text in ("", "localhost", "127.0.0.1", "::1", "0.0.0.0", "::"):
        return "loopback"
    if text.startswith("127."):
        return "loopback"
    return "external"


def _note_network(kind: str, target) -> None:
    if isinstance(target, tuple) and target:
        host = target[0]
        label = f"{target[0]}:{target[1]}" if len(target) > 1 else str(target[0])
    else:
        host = target
        label = str(target)
    category = _classify_host(host)
    with _NET_LOCK:
        key = (kind, label, category)
        _NET_COUNTS[key] = _NET_COUNTS.get(key, 0) + 1
        if len(_NET_EVENTS) < _NET_EVENT_CAP:
            _NET_EVENTS.append(
                {
                    "kind": kind,
                    "target": label,
                    "category": category,
                    "thread": threading.current_thread().name,
                }
            )


def _install_network_guard() -> None:
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_sendto = socket.socket.sendto
    original_create_connection = socket.create_connection
    original_getaddrinfo = socket.getaddrinfo

    def connect(self, address):
        _note_network("connect", address)
        return original_connect(self, address)

    def connect_ex(self, address):
        _note_network("connect_ex", address)
        return original_connect_ex(self, address)

    def sendto(self, *args):
        # sendto(data, address) or sendto(data, flags, address)
        _note_network("sendto", args[-1] if args else None)
        return original_sendto(self, *args)

    def create_connection(address, *args, **kwargs):
        _note_network("create_connection", address)
        return original_create_connection(address, *args, **kwargs)

    def getaddrinfo(host, port, *args, **kwargs):
        _note_network("getaddrinfo", (host, port))
        return original_getaddrinfo(host, port, *args, **kwargs)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    socket.socket.sendto = sendto
    socket.create_connection = create_connection
    socket.getaddrinfo = getaddrinfo


_install_network_guard()

# ---------------------------------------------------------------------------
# Project imports (after the guard, deliberately).
# ---------------------------------------------------------------------------

import argparse  # noqa: E402
import json  # noqa: E402
import logging  # noqa: E402
import platform  # noqa: E402
import shutil  # noqa: E402
from collections import deque  # noqa: E402
from datetime import datetime  # noqa: E402

import cv2  # noqa: E402

from activity_gate.gate import ActivityGate  # noqa: E402
from alerts.alert_manager import AlertManager  # noqa: E402
from alerts.dispatch import AlertDispatcher  # noqa: E402
from camera.health import CameraErrorIsolator, CameraHealth  # noqa: E402
from camera.source import CameraSource  # noqa: E402
from camera.stream_manager import StreamManager  # noqa: E402
from capabilities import CapabilityRegistry  # noqa: E402
from config.settings import (  # noqa: E402
    ALERT_COOLDOWN_SECONDS,
    ALERT_DISPATCH_QUEUE_SIZE,
    BRIGHTNESS_THRESHOLD,
    CAMERA_HEIGHT,
    CAMERA_SOURCES,
    CAMERA_WIDTH,
    CURFEW_END_HOUR,
    CURFEW_START_HOUR,
    DETECTION_CONFIDENCE,
    DETECTION_MODEL_PATH,
    LOW_FPS_INTERVAL,
    MOTION_THRESHOLD,
    REID_SIMILARITY_THRESHOLD,
    REID_TTL_SECONDS,
    SYSLOG_HOST,
    SYSLOG_PORT,
    WATCHLIST_SIMILARITY_THRESHOLD,
    WEBHOOK_URL,
    configure_logging,
)
from database.incident_store import IncidentStore  # noqa: E402
from detection.draw import draw_detections  # noqa: E402
from face.face_recognizer import FaceRecognizer, buffalo_weights_available  # noqa: E402
from face.watchlist import WatchlistDB, WatchlistMatcher  # noqa: E402
from filtering.false_alarm import FalseAlarmFilter  # noqa: E402
from integration.syslog_notifier import SyslogNotifier  # noqa: E402
from integration.webhook import WebhookNotifier  # noqa: E402
from intelligence.threat_rules import ThreatRulesDB  # noqa: E402
from intelligence.threat_score import ThreatScorer  # noqa: E402
from metrics import MetricsCollector, ResourceSampler  # noqa: E402
from preprocessing.enhance import Preprocessor  # noqa: E402
from reid.embedder import ResNetEmbedder, resnet18_weights_available  # noqa: E402
from reid.reid import PersonGallery  # noqa: E402
from tracking.tracker import Tracker  # noqa: E402
from zones.zone_engine import ZoneEngine  # noqa: E402

log = logging.getLogger("ibvap.live_baseline")


# ---------------------------------------------------------------------------
# Device-level capture timing, via CameraStream's existing camera_factory hook.
# ---------------------------------------------------------------------------


class TimedCameraSource(CameraSource):
    """`CameraSource` that times its own open() and read() calls.

    These run on the `CameraStream` producer thread, so this is the only place
    the true device capture cost is visible - by the time a frame reaches the
    application loop it has been through a queue, and the number measured
    there is a queue wait, not a capture.

    Timing only: behaviour is the base class's, unchanged.
    """

    def __init__(self, source, width, height, *, camera_name, metrics, stats):
        super().__init__(source, width=width, height=height)
        self.camera_name = camera_name
        self._metrics = metrics
        self._stats = stats

    def open(self) -> None:
        started = time.perf_counter()
        try:
            super().open()
        finally:
            elapsed = time.perf_counter() - started
            self._stats["open_calls"] += 1
            self._stats["open_seconds"].append(elapsed)

    def read(self):
        started = time.perf_counter()
        frame = super().read()
        elapsed = time.perf_counter() - started
        if frame is None:
            self._stats["read_none"] += 1
            return None
        self._stats["read_ok"] += 1
        if self._stats["first_frame_at"] is None:
            # The first read after open() also pays the sensor's own start-up
            # (exposure/auto-gain settling), so it is recorded separately
            # rather than being allowed to set the steady-state maximum.
            self._stats["first_frame_at"] = time.perf_counter()
            self._stats["first_read_seconds"] = elapsed
            return frame
        self._stats["read_seconds"].append(elapsed)
        self._metrics.record(self.camera_name, "00_capture_device", elapsed)
        return frame


def make_camera_factory(sources: dict, metrics, stats_by_name: dict):
    """Builds the per-source factory `StreamManager` hands to each stream.

    `camera_factory` is passed once for all streams and receives only the
    source, so the source is reverse-mapped back to its camera name here -
    that keeps the harness correct if more than one camera is configured.
    """
    source_to_name = {str(source): name for name, source in sources.items()}

    def factory(source, width=640, height=480):
        name = source_to_name.get(str(source), "unknown")
        return TimedCameraSource(
            source,
            width,
            height,
            camera_name=name,
            metrics=metrics,
            stats=stats_by_name[name],
        )

    return factory


def new_capture_stats() -> dict:
    return {
        "open_calls": 0,
        "open_seconds": [],
        "read_ok": 0,
        "read_none": 0,
        "first_frame_at": None,
        "first_read_seconds": None,
        "read_seconds": [],
    }


# ---------------------------------------------------------------------------
# Reporting helpers
# ---------------------------------------------------------------------------


def percentile(ordered: list, fraction: float) -> float:
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, max(0, round(fraction * (len(ordered) - 1))))
    return ordered[index]


def summarise(samples: list) -> dict:
    if not samples:
        return {"count": 0}
    ordered = sorted(samples)
    return {
        "count": len(ordered),
        "mean_ms": 1000 * sum(ordered) / len(ordered),
        "p50_ms": 1000 * percentile(ordered, 0.50),
        "p95_ms": 1000 * percentile(ordered, 0.95),
        "max_ms": 1000 * ordered[-1],
    }


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

        from detection.detector import CPU_EXECUTION_PROVIDER, ONNX_PROVIDERS_AVAILABLE

        env["onnxruntime"] = onnxruntime.__version__
        env["onnx_providers_available"] = list(ONNX_PROVIDERS_AVAILABLE)
        env["onnx_provider_pinned"] = CPU_EXECUTION_PROVIDER
    except Exception:
        env["onnxruntime"] = "unavailable"
    return env


def scan_artifacts(workdir: str) -> dict:
    """Counts and sizes everything the run wrote, before it is purged."""
    files = []
    for root, _dirs, names in os.walk(workdir):
        for name in names:
            path = os.path.join(root, name)
            try:
                files.append((os.path.relpath(path, workdir), os.path.getsize(path)))
            except OSError:
                continue
    by_ext: dict = {}
    for rel, size in files:
        ext = os.path.splitext(rel)[1].lower() or "(none)"
        entry = by_ext.setdefault(ext, {"files": 0, "bytes": 0})
        entry["files"] += 1
        entry["bytes"] += size
    return {
        "total_files": len(files),
        "total_bytes": sum(size for _, size in files),
        "by_ext": by_ext,
    }


def network_report() -> dict:
    with _NET_LOCK:
        counts = dict(_NET_COUNTS)
        events = list(_NET_EVENTS)
    rows = [
        {"kind": kind, "target": target, "category": category, "count": count}
        for (kind, target, category), count in sorted(counts.items())
    ]
    external = [row for row in rows if row["category"] == "external"]
    return {
        "rows": rows,
        "external_attempts": sum(row["count"] for row in external),
        "external_targets": sorted({row["target"] for row in external}),
        "loopback_attempts": sum(
            row["count"] for row in rows if row["category"] == "loopback"
        ),
        "events_recorded": len(events),
        "event_cap_reached": len(events) >= _NET_EVENT_CAP,
    }


# ---------------------------------------------------------------------------
# The measured run
# ---------------------------------------------------------------------------


def run(args) -> int:
    configure_logging()

    if not os.path.exists(args.model):
        print(f"BLOCKED: model weights not found at {args.model}", file=sys.stderr)
        return 2

    sources = dict(CAMERA_SOURCES)
    if args.camera:
        if args.camera not in sources:
            print(
                f"BLOCKED: camera {args.camera!r} not in CAMERA_SOURCES ({list(sources)})",
                file=sys.stderr,
            )
            return 2
        sources = {args.camera: sources[args.camera]}
    if not sources:
        print("BLOCKED: no cameras configured", file=sys.stderr)
        return 2

    workdir = os.path.abspath(args.workdir)
    os.makedirs(workdir, exist_ok=True)
    evidence_dir = os.path.join(workdir, "evidence")

    metrics = MetricsCollector(window=args.window)
    resources = ResourceSampler(min_interval_s=args.resource_interval)
    capture_stats = {name: new_capture_stats() for name in sources}

    print("=" * 78)
    print("IBVAP PHASE 1 - LIVE CAMERA BASELINE")
    print("=" * 78)
    env = environment()
    for key, value in env.items():
        print(f"  {key:24} {value}")
    print(f"  {'cameras':24} {sources}")
    print(f"  {'requested capture':24} {CAMERA_WIDTH}x{CAMERA_HEIGHT}")
    print(f"  {'duration budget':24} {args.duration:.0f} s (warm-up {args.warmup} frames)")
    print(f"  {'scratch workdir':24} {workdir} (purge={not args.keep})")

    rss_before_model = resources.sample(force=True)

    # ---- build the pipeline exactly as app.py does ------------------------
    load_started = time.perf_counter()
    trackers = {
        name: Tracker(model_path=args.model, confidence=args.confidence) for name in sources
    }
    model_load_s = time.perf_counter() - load_started

    preprocessors = {
        name: Preprocessor(name, brightness_threshold=BRIGHTNESS_THRESHOLD) for name in sources
    }
    gates = {name: ActivityGate(motion_threshold=MOTION_THRESHOLD) for name in sources}
    false_alarm_filters = {name: FalseAlarmFilter() for name in sources}
    frame_counters = {name: 0 for name in sources}

    capabilities = CapabilityRegistry()
    embedder = capabilities.load(
        "reid_embedding", ResNetEmbedder, precheck=resnet18_weights_available
    )
    person_gallery = (
        PersonGallery(
            embed_fn=embedder.embed,
            similarity_threshold=REID_SIMILARITY_THRESHOLD,
            ttl_seconds=REID_TTL_SECONDS,
        )
        if embedder is not None
        else None
    )
    zone_engines = {
        name: ZoneEngine(
            config_path=os.path.join(workdir, f"zones_{name}.json"),
            curfew_start_hour=CURFEW_START_HOUR,
            curfew_end_hour=CURFEW_END_HOUR,
        )
        for name in sources
    }
    face_recognizer = capabilities.load(
        "face_recognition", FaceRecognizer, precheck=buffalo_weights_available
    )
    watchlist_db = capabilities.load(
        "watchlist",
        lambda: WatchlistDB(
            db_path=os.path.join(workdir, "watchlist.db"),
            key_path=os.path.join(workdir, "watchlist.key"),
        ),
    )
    watchlist_matcher = (
        WatchlistMatcher(watchlist_db, similarity_threshold=WATCHLIST_SIMILARITY_THRESHOLD)
        if watchlist_db is not None
        else None
    )
    threat_rules = ThreatRulesDB(db_path=os.path.join(workdir, "threat_rules.db"))
    threat_scorer = ThreatScorer(threat_rules)
    incident_store = IncidentStore(
        db_path=os.path.join(workdir, "incidents.db"),
        evidence_dir=evidence_dir,
        key_path=os.path.join(workdir, "evidence.key"),
    )
    webhook = WebhookNotifier(url=WEBHOOK_URL)
    syslog = SyslogNotifier(host=SYSLOG_HOST, port=SYSLOG_PORT)
    alert_dispatcher = AlertDispatcher(maxsize=ALERT_DISPATCH_QUEUE_SIZE)
    alert_manager = AlertManager(
        snapshot_dir=os.path.join(workdir, "snapshots"),
        cooldown_seconds=ALERT_COOLDOWN_SECONDS,
        incident_store=incident_store,
        webhook=webhook,
        syslog=syslog,
        dispatcher=alert_dispatcher,
    )
    frame_buffers = {name: deque(maxlen=3) for name in sources}
    isolator = CameraErrorIsolator()

    print(f"\n  optional capabilities    {capabilities.summary()}")
    for cap_name, entry in sorted(capabilities.states().items()):
        if entry["state"] != "available":
            print(f"    {cap_name}: {entry['state'].upper()} - {entry['detail']}")

    rss_after_model = resources.sample(force=True)
    threads_after_model = rss_after_model.get("threads")

    # ---- camera startup ---------------------------------------------------
    manager = StreamManager(
        sources,
        width=CAMERA_WIDTH,
        height=CAMERA_HEIGHT,
        camera_factory=make_camera_factory(sources, metrics, capture_stats),
    )

    startup_started = time.perf_counter()
    manager.start_all()
    start_all_s = time.perf_counter() - startup_started

    online_at = None
    deadline = time.perf_counter() + args.online_timeout
    while time.perf_counter() < deadline:
        if all(state == CameraHealth.ONLINE for state in manager.health().values()):
            online_at = time.perf_counter()
            break
        time.sleep(0.01)
    time_to_online_s = None if online_at is None else online_at - startup_started

    first_frame_started = time.perf_counter()
    first_frame_s = None
    deadline = first_frame_started + args.first_frame_timeout
    while time.perf_counter() < deadline:
        frames = manager.read_all()
        if any(frame is not None for frame in frames.values()):
            first_frame_s = time.perf_counter() - first_frame_started
            break

    if first_frame_s is None:
        print(
            f"\nBLOCKED: no frame from {list(sources)} within "
            f"{args.first_frame_timeout:.0f}s; health={manager.health()}",
            file=sys.stderr,
        )
        manager.stop_all()
        alert_dispatcher.stop()
        threat_rules.close()
        incident_store.close()
        if watchlist_db is not None:
            watchlist_db.close()
        return 3

    print("\n  CAMERA STARTUP")
    print(f"    start_all()          {start_all_s * 1000:.0f} ms (blocking device open)")
    for name, stats in capture_stats.items():
        if stats["open_seconds"]:
            print(
                f"    device open [{name}]   {stats['open_seconds'][0] * 1000:.0f} ms"
                f"  (opens={stats['open_calls']})"
            )
    online_text = "n/a" if time_to_online_s is None else f"{time_to_online_s * 1000:.0f} ms"
    print(f"    time to ONLINE       {online_text}")
    print(f"    time to first frame  {first_frame_s * 1000:.0f} ms (after start_all)")
    print(f"    health               {manager.health()}")

    # ---- warm-up (executed, not measured) ---------------------------------
    # The first inference pays ONNX session construction and allocator
    # warm-up; folding that into the steady-state numbers would misreport it.
    warmup_done = 0
    first_inference_s = None
    warmup_deadline = time.perf_counter() + args.warmup_timeout
    while warmup_done < args.warmup and time.perf_counter() < warmup_deadline:
        for name, frame in manager.read_all().items():
            if frame is None:
                continue
            started = time.perf_counter()
            trackers[name].track(preprocessors[name].process(frame))
            if first_inference_s is None:
                first_inference_s = time.perf_counter() - started
            warmup_done += 1
            break

    rss_after_warmup = resources.sample(force=True)
    first_inference_ms = 0.0 if first_inference_s is None else first_inference_s * 1000
    print(f"\n  warm-up: {warmup_done} frame(s); first inference {first_inference_ms:.0f} ms")

    # ---- the measured loop, mirroring app.py's frame path ------------------
    queue_read_samples: list = []
    e2e_samples: list = []
    detection_counts: list = []
    resource_series: list = []
    health_transitions: list = []
    motion_samples: list = []
    brightness_samples: list = []
    last_health: dict = {}
    idle_polls = 0
    loop_iterations = 0
    frames_consumed = 0
    frames_full_pipeline = 0
    frames_active = 0
    frames_boosted = 0

    def process_camera_frame(name: str, frame) -> None:
        """One frame through the same stages, in the same order, as app.py."""
        nonlocal frames_full_pipeline, frames_active, frames_boosted
        with metrics.stage(name, "02_activity_gate"):
            active, motion_score = gates[name].is_active(frame)
        frame_counters[name] += 1
        motion_samples.append(motion_score)
        if active:
            frames_active += 1

        should_process = active or (frame_counters[name] % LOW_FPS_INTERVAL == 0)
        if not should_process:
            metrics.increment("frames_gated_out")
            return

        frame_started = time.perf_counter()
        preprocessor = preprocessors[name]
        with metrics.stage(name, "03_preprocess"):
            processed = preprocessor.process(frame)
        # Scene conditions, recorded so the preprocess cost below can be
        # attributed: the CLAHE/gamma low-light boost only runs when measured
        # brightness is under BRIGHTNESS_THRESHOLD, and it is far from free.
        brightness_samples.append(preprocessor.last_brightness)
        if preprocessor.last_boost_applied:
            frames_boosted += 1

        with metrics.stage(name, "04_detect_track"):
            detections = trackers[name].track(processed)
        with metrics.stage(name, "05_false_alarm_filter"):
            detections = false_alarm_filters[name].filter(detections)
        metrics.increment("detections_kept", len(detections))
        detection_counts.append(len(detections))

        with metrics.stage(name, "06_enrich_and_zone"):
            for det in detections:
                if (
                    person_gallery is not None
                    and det.track_id is not None
                    and det.category() == "person"
                ):
                    det.person_id = capabilities.call(
                        "reid_embedding",
                        person_gallery.resolve,
                        (name, det.track_id), processed, det.box,
                    )
                x1, y1, x2, y2 = det.box
                zone_result = zone_engines[name].classify(((x1 + x2) // 2, y2), det.direction)
                det.zone_tier = zone_result["tier"]
                det.zone_direction = zone_result["direction"]

                if face_recognizer is not None and det.category() == "person":
                    _face_box, embedding = capabilities.call(
                        "face_recognition",
                        face_recognizer.embed,
                        processed, det.box,
                        default=(None, None),
                    )
                    if embedding is not None and watchlist_matcher is not None:
                        match_name, similarity = capabilities.call(
                            "watchlist",
                            watchlist_matcher.match,
                            embedding,
                            default=(None, 0.0),
                        )
                        det.watchlist_match = match_name
                        det.watchlist_similarity = similarity

        with metrics.stage(name, "07_draw"):
            draw_detections(processed, detections)

        with metrics.stage(name, "08_threat_score"):
            hour = datetime.now().hour
            scores = [
                threat_scorer.score(
                    zone_tier=det.zone_tier,
                    hour=hour,
                    speed_px_per_frame=det.speed,
                    category=det.category(),
                )
                for det in detections
            ]

        frame_buffers[name].append(processed.copy())
        with metrics.stage(name, "09_alert_handle"):
            for det, score in zip(detections, scores):
                alert_manager.handle(det, score, list(frame_buffers[name]))

        e2e_samples.append(time.perf_counter() - frame_started)
        frames_full_pipeline += 1

    loop_started = time.perf_counter()
    interrupted = False
    try:
        while True:
            elapsed = time.perf_counter() - loop_started
            if elapsed >= args.duration or frames_consumed >= args.max_frames:
                break
            loop_iterations += 1

            health = manager.health()
            if health != last_health:
                if last_health:
                    health_transitions.append(
                        {"at_s": elapsed, "from": dict(last_health), "to": dict(health)}
                    )
                degraded = {n: s for n, s in health.items() if s != CameraHealth.ONLINE}
                if degraded:
                    metrics.increment("health_degraded_transitions")
                else:
                    metrics.increment("health_recovered_transitions")
                last_health = health

            read_started = time.perf_counter()
            frames = manager.read_all()
            queue_read_samples.append(time.perf_counter() - read_started)

            for name, frame in frames.items():
                if frame is None:
                    idle_polls += 1
                    continue
                frames_consumed += 1
                if not isolator.run(
                    name, process_camera_frame, name, frame, stage="frame-pipeline"
                ):
                    metrics.increment("frame_pipeline_failures")
                else:
                    metrics.increment("frames_processed")

            sample = resources.sample()
            if sample.get("available") and (
                not resource_series or sample is not resource_series[-1][1]
            ):
                resource_series.append((round(elapsed, 1), sample))
    except KeyboardInterrupt:
        interrupted = True
        print("\n  (interrupted - reporting what was measured)")

    wall_s = time.perf_counter() - loop_started
    rss_before_shutdown = resources.sample(force=True)

    # ---- shutdown, in app.py's order, with release verification -----------
    threads_before_shutdown = sorted(thread.name for thread in threading.enumerate())
    shutdown_started = time.perf_counter()
    manager.stop_all()
    stop_all_s = time.perf_counter() - shutdown_started

    dispatch_flushed = alert_dispatcher.stop(timeout=args.dispatch_flush_timeout)
    dispatch_stats = alert_dispatcher.stats()
    threat_rules.close()
    incident_store.close()
    if watchlist_db is not None:
        watchlist_db.close()
    shutdown_s = time.perf_counter() - shutdown_started

    time.sleep(args.settle)
    threads_after_shutdown = sorted(thread.name for thread in threading.enumerate())
    release_checks = {}
    for name, stream in manager.streams.items():
        thread = stream._thread
        release_checks[name] = {
            "health": stream.health,
            "producer_thread_alive": bool(thread is not None and thread.is_alive()),
            "capture_handle_cleared": stream._camera.cap is None,
            "capture_is_open": stream._camera.is_open(),
            "reconnect_count": stream.reconnect_count,
        }

    # Independent proof the OS handle was really given back: reopen the same
    # device after shutdown. If the handle had leaked this would fail.
    reacquire = {}
    if args.verify_reacquire:
        for name, source in sources.items():
            probe = cv2.VideoCapture(source)
            opened = probe.isOpened()
            probe.release()
            reacquire[name] = opened

    resources_final = resources.sample(force=True)

    # ---- report -----------------------------------------------------------
    snapshot = metrics.snapshot()

    print("\n  THROUGHPUT")
    interrupted_text = " (INTERRUPTED)" if interrupted else ""
    print(f"    measured wall time   {wall_s:.2f} s{interrupted_text}")
    print(f"    loop iterations      {loop_iterations}  ({loop_iterations / wall_s:.1f}/s)")
    for name, stats in capture_stats.items():
        device_reads = stats["read_ok"]
        print(
            f"    device frames [{name}]  {device_reads} captured "
            f"({device_reads / wall_s:.1f} FPS at the device, producer thread)"
        )
    print(f"    frames consumed      {frames_consumed}  ({frames_consumed / wall_s:.2f} FPS)")
    print(
        f"    frames full pipeline {frames_full_pipeline}  "
        f"({frames_full_pipeline / wall_s:.2f} FPS)"
    )
    print(f"    empty queue polls    {idle_polls}")
    if detection_counts:
        print(
            f"    detections/frame     mean {sum(detection_counts)/len(detection_counts):.2f}"
            f"  max {max(detection_counts)}  total {sum(detection_counts)}"
        )

    print("\n  SCENE CONDITIONS (what this workload actually was)")
    if motion_samples:
        print(
            f"    motion score         mean {sum(motion_samples)/len(motion_samples):.2f}  "
            f"max {max(motion_samples):.2f}  (threshold {MOTION_THRESHOLD:.1f})"
        )
        print(
            f"    frames 'active'      {frames_active}/{len(motion_samples)} "
            f"({100.0 * frames_active / len(motion_samples):.0f}%) - the rest ran only on "
            f"the 1-in-{LOW_FPS_INTERVAL} keep-alive"
        )
    if brightness_samples:
        print(
            f"    brightness           mean {sum(brightness_samples)/len(brightness_samples):.1f}"
            f"  min {min(brightness_samples):.1f}  max {max(brightness_samples):.1f}  "
            f"(boost threshold {BRIGHTNESS_THRESHOLD:.0f})"
        )
        print(
            f"    low-light boost      applied on {frames_boosted}/{len(brightness_samples)} "
            f"preprocessed frames ({100.0 * frames_boosted / len(brightness_samples):.0f}%)"
        )

    print("\n  PER-STAGE LATENCY (ms)")
    print(f"    {'stage':<28}{'n':>6}{'mean':>10}{'p50':>10}{'p95':>10}{'max':>10}")
    for key in sorted(snapshot["stages"]):
        stats = snapshot["stages"][key]
        if not stats.get("count"):
            continue
        label = key.split("/", 1)[1]
        print(
            f"    {label:<28}{stats['count']:>6}{stats['mean_ms']:>10.2f}"
            f"{stats['p50_ms']:>10.2f}{stats['p95_ms']:>10.2f}{stats['max_ms']:>10.2f}"
        )
    queue_summary = summarise(queue_read_samples)
    if queue_summary["count"]:
        print(
            f"    {'01_capture_queue(read_all)':<28}{queue_summary['count']:>6}"
            f"{queue_summary['mean_ms']:>10.2f}{queue_summary['p50_ms']:>10.2f}"
            f"{queue_summary['p95_ms']:>10.2f}{queue_summary['max_ms']:>10.2f}"
        )
    print("    NOTE: 00_capture_device and 01_capture_queue are BLOCKING WAITS for the")
    print("          next frame, not CPU cost. On a free-running camera their mean")
    print("          tends to the inter-frame interval (1/device FPS). Only the")
    print("          02..09 stages are work the pipeline performs.")
    for name, stats in capture_stats.items():
        if stats["first_read_seconds"] is not None:
            print(
                f"    first device read [{name}] {stats['first_read_seconds'] * 1000:.0f} ms "
                f"(sensor start-up; excluded from 00_capture_device above)"
            )

    e2e_summary = summarise(e2e_samples)
    if e2e_summary["count"]:
        print("\n  END-TO-END per fully processed frame (preprocess -> alert handoff), ms")
        print(
            f"    n {e2e_summary['count']}   mean {e2e_summary['mean_ms']:.2f}   "
            f"p50 {e2e_summary['p50_ms']:.2f}   p95 {e2e_summary['p95_ms']:.2f}   "
            f"max {e2e_summary['max_ms']:.2f}"
        )

    print("\n  PROCESS RESOURCES")
    if resources_final.get("available"):
        print(f"    RSS before model     {rss_before_model['rss_mb']:.1f} MB")
        print(f"    RSS after model load {rss_after_model['rss_mb']:.1f} MB")
        print(f"    RSS after warm-up    {rss_after_warmup['rss_mb']:.1f} MB")
        print(f"    RSS end of run       {rss_before_shutdown['rss_mb']:.1f} MB")
        print(f"    RSS after shutdown   {resources_final['rss_mb']:.1f} MB")
        print(
            f"    steady-state drift   "
            f"{rss_before_shutdown['rss_mb'] - rss_after_warmup['rss_mb']:+.1f} MB "
            f"over {frames_full_pipeline} measured frames"
        )
        cores = os.cpu_count() or 1
        cpu_raw = rss_before_shutdown["cpu_percent"]
        print(
            f"    CPU (end of run)     {cpu_raw:.1f} % of one core "
            f"= {cpu_raw / cores:.1f} % of {cores} logical cores"
        )
        print(f"    threads after model  {threads_after_model}")
        print(f"    threads end of run   {rss_before_shutdown['threads']}")
        print(f"    threads after stop   {resources_final['threads']}")
        if resource_series:
            trend = "  ".join(
                f"t{at}s:{sample['rss_mb']:.0f}MB/{sample['cpu_percent'] / cores:.0f}%cpu"
                for at, sample in resource_series[:10]
            )
            print(f"    trend (cpu per-core) {trend}")
    else:
        print("    UNAVAILABLE (psutil not installed)")

    print("\n  CAMERA HEALTH / RECONNECT")
    print(f"    final health         {manager.health()}")
    print(f"    health transitions   {len(health_transitions)}")
    for transition in health_transitions:
        print(f"      t={transition['at_s']:.1f}s  {transition['from']} -> {transition['to']}")
    for name, stats in capture_stats.items():
        print(
            f"    [{name}] device reads ok={stats['read_ok']} none={stats['read_none']} "
            f"opens={stats['open_calls']} reconnects={release_checks[name]['reconnect_count']}"
        )
    print(f"    pipeline failures    {dict(isolator.total_errors) or 0}")
    print(f"    counters             {snapshot['counters']}")

    print("\n  SHUTDOWN / RELEASE")
    print(f"    stop_all()           {stop_all_s * 1000:.0f} ms")
    print(f"    full shutdown        {shutdown_s * 1000:.0f} ms")
    print(f"    dispatcher flushed   {dispatch_flushed}")
    for name, checks in release_checks.items():
        print(f"    [{name}] {checks}")
    if reacquire:
        print(f"    device re-acquired   {reacquire} (proves the OS handle was released)")
    print(f"    threads before stop  {threads_before_shutdown}")
    print(f"    threads after stop   {threads_after_shutdown}")

    print("\n  ALERT DISPATCH")
    print(f"    {dispatch_stats}  flushed_cleanly={dispatch_flushed}")

    net = network_report()
    print("\n  OUTBOUND NETWORK (socket-level, guard installed before all imports)")
    print(f"    external attempts    {net['external_attempts']}")
    if net["external_targets"]:
        print(f"    external targets     {net['external_targets']}")
    print(f"    loopback attempts    {net['loopback_attempts']}")
    for row in net["rows"]:
        print(f"      {row['category']:<9} {row['kind']:<18} {row['target']}  x{row['count']}")

    artifacts = scan_artifacts(workdir)
    print("\n  DATA WRITTEN THIS RUN (scratch workdir)")
    print(f"    files {artifacts['total_files']}  bytes {artifacts['total_bytes']}")
    for ext, entry in sorted(artifacts["by_ext"].items()):
        print(f"      {ext:<10} {entry['files']} file(s)  {entry['bytes']} bytes")

    print("\n  COMPARABILITY")
    print("    This is a LIVE CAMERA run. The Phase 1 file baseline")
    print("    (scripts/measure_baseline.py) drives a synthetic clip panned from a")
    print("    still image. Different workload, different scene, different capture")
    print("    path - the numbers are NOT directly comparable. Only the per-stage")
    print("    code paths are identical.")
    print("=" * 78)

    payload = {
        "kind": "live_camera_baseline",
        "environment": env,
        "cameras": {name: str(source) for name, source in sources.items()},
        "requested_resolution": [CAMERA_WIDTH, CAMERA_HEIGHT],
        "interrupted": interrupted,
        "startup": {
            "model_load_ms": model_load_s * 1000,
            "start_all_ms": start_all_s * 1000,
            "device_open_ms": {
                name: (stats["open_seconds"][0] * 1000 if stats["open_seconds"] else None)
                for name, stats in capture_stats.items()
            },
            "time_to_online_ms": None if time_to_online_s is None else time_to_online_s * 1000,
            "time_to_first_frame_ms": first_frame_s * 1000,
            "first_inference_ms": None if first_inference_s is None else first_inference_s * 1000,
            "warmup_frames": warmup_done,
        },
        "throughput": {
            "wall_s": wall_s,
            "loop_iterations": loop_iterations,
            "frames_consumed": frames_consumed,
            "frames_full_pipeline": frames_full_pipeline,
            "empty_queue_polls": idle_polls,
            "device_frames": {n: s["read_ok"] for n, s in capture_stats.items()},
            "device_fps": {n: s["read_ok"] / wall_s for n, s in capture_stats.items()},
            "consumed_fps": frames_consumed / wall_s,
            "pipeline_fps": frames_full_pipeline / wall_s,
            "detections_per_frame_mean": (
                sum(detection_counts) / len(detection_counts) if detection_counts else 0.0
            ),
            "detections_total": sum(detection_counts),
        },
        "scene": {
            "motion_mean": (sum(motion_samples) / len(motion_samples)) if motion_samples else None,
            "motion_max": max(motion_samples) if motion_samples else None,
            "motion_threshold": MOTION_THRESHOLD,
            "frames_active": frames_active,
            "frames_gate_evaluated": len(motion_samples),
            "brightness_mean": (
                sum(brightness_samples) / len(brightness_samples) if brightness_samples else None
            ),
            "brightness_min": min(brightness_samples) if brightness_samples else None,
            "brightness_max": max(brightness_samples) if brightness_samples else None,
            "brightness_threshold": BRIGHTNESS_THRESHOLD,
            "frames_low_light_boosted": frames_boosted,
            "frames_preprocessed": len(brightness_samples),
            "low_fps_interval": LOW_FPS_INTERVAL,
        },
        "capture_device_first_read_ms": {
            name: (
                stats["first_read_seconds"] * 1000
                if stats["first_read_seconds"] is not None
                else None
            )
            for name, stats in capture_stats.items()
        },
        "stages": snapshot["stages"],
        "capture_queue": queue_summary,
        "end_to_end": e2e_summary,
        "counters": snapshot["counters"],
        "capabilities": capabilities.states(),
        "health": {
            "final": manager.health(),
            "transitions": health_transitions,
            "device_reads": {
                n: {"ok": s["read_ok"], "none": s["read_none"], "opens": s["open_calls"]}
                for n, s in capture_stats.items()
            },
            "release_checks": release_checks,
            "pipeline_failures": dict(isolator.total_errors),
        },
        "shutdown": {
            "stop_all_ms": stop_all_s * 1000,
            "total_ms": shutdown_s * 1000,
            "dispatcher_flushed": dispatch_flushed,
            "device_reacquired": reacquire,
            "threads_before": threads_before_shutdown,
            "threads_after": threads_after_shutdown,
        },
        "dispatch": dispatch_stats,
        "resources": {
            "rss_before_model_mb": rss_before_model.get("rss_mb"),
            "rss_after_model_mb": rss_after_model.get("rss_mb"),
            "rss_after_warmup_mb": rss_after_warmup.get("rss_mb"),
            "rss_end_of_run_mb": rss_before_shutdown.get("rss_mb"),
            "rss_after_shutdown_mb": resources_final.get("rss_mb"),
            "cpu_percent_end": rss_before_shutdown.get("cpu_percent"),
            "threads_after_model": threads_after_model,
            "threads_end_of_run": rss_before_shutdown.get("threads"),
            "threads_after_shutdown": resources_final.get("threads"),
            "series": [{"at_s": at, **sample} for at, sample in resource_series],
        },
        "network": net,
        "artifacts_written": artifacts,
    }

    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        print(f"  wrote {args.json}")

    if not args.keep:
        shutil.rmtree(workdir, ignore_errors=True)
        print(f"  purged scratch workdir {workdir} (exists={os.path.exists(workdir)})")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="IBVAP Phase 1 live-camera baseline")
    parser.add_argument("--duration", type=float, default=60.0, help="measured seconds")
    parser.add_argument("--max-frames", type=int, default=100_000)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--warmup-timeout", type=float, default=60.0)
    parser.add_argument("--camera", default=None, help="restrict to one CAMERA_SOURCES name")
    parser.add_argument("--model", default=DETECTION_MODEL_PATH)
    parser.add_argument("--confidence", type=float, default=DETECTION_CONFIDENCE)
    parser.add_argument("--window", type=int, default=4096)
    parser.add_argument("--resource-interval", type=float, default=2.0)
    parser.add_argument("--online-timeout", type=float, default=10.0)
    parser.add_argument("--first-frame-timeout", type=float, default=20.0)
    parser.add_argument("--dispatch-flush-timeout", type=float, default=15.0)
    parser.add_argument("--settle", type=float, default=0.5)
    parser.add_argument("--workdir", default="benchmark_out/live_scratch")
    parser.add_argument("--json", default=None)
    parser.add_argument(
        "--keep",
        action="store_true",
        help="keep the scratch workdir (evidence/snapshots) instead of purging it",
    )
    parser.add_argument(
        "--no-verify-reacquire", dest="verify_reacquire", action="store_false", default=True
    )
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())

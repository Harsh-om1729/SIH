import logging
import time
from collections import deque
from datetime import datetime

import cv2

from activity_gate.gate import ActivityGate
from alerts.alert_manager import AlertManager
from alerts.dispatch import AlertDispatcher
from camera.health import CameraErrorIsolator, CameraHealth
from camera.stream_manager import StreamManager
from capabilities import CapabilityRegistry
from metrics import MetricsCollector, NullCollector, ResourceSampler
from config.settings import (
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
    METRICS_ENABLED,
    METRICS_REPORT_INTERVAL_S,
    MOTION_THRESHOLD,
    REID_SIMILARITY_THRESHOLD,
    REID_TTL_SECONDS,
    SYSLOG_HOST,
    SYSLOG_PORT,
    WATCHLIST_SIMILARITY_THRESHOLD,
    WEBHOOK_URL,
    configure_logging,
)
from database.incident_store import IncidentStore
from detection.draw import draw_detections
from face.face_recognizer import FaceRecognizer, buffalo_weights_available
from face.watchlist import WatchlistDB, WatchlistMatcher
from filtering.false_alarm import FalseAlarmFilter
from integration.syslog_notifier import SyslogNotifier
from integration.webhook import WebhookNotifier
from intelligence.threat_rules import ThreatRulesDB
from intelligence.threat_score import ThreatScorer
from preprocessing.enhance import Preprocessor
from reid.embedder import ResNetEmbedder, resnet18_weights_available
from reid.reid import PersonGallery
from tracking.tracker import Tracker
from zones.drawer import ZoneDrawer
from zones.zone_engine import ZoneEngine

configure_logging()
log = logging.getLogger("ibvap")


def draw_debug_overlay(frame, preprocessor: Preprocessor, active: bool, motion_score: float):
    boost_status = "LOW-LIGHT BOOST: ON" if preprocessor.last_boost_applied else "LOW-LIGHT BOOST: OFF"
    boost_color = (0, 0, 255) if preprocessor.last_boost_applied else (0, 200, 0)
    boost_label = (
        f"{boost_status}  brightness={preprocessor.last_brightness:.1f} "
        f"(threshold={BRIGHTNESS_THRESHOLD:.0f})"
    )
    cv2.putText(frame, boost_label, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, boost_color, 2)

    activity_status = "ACTIVITY: HIGH (full pipeline)" if active else "ACTIVITY: LOW (keep-alive)"
    activity_color = (0, 0, 255) if active else (255, 150, 0)
    activity_label = f"{activity_status}  motion={motion_score:.2f} (threshold={MOTION_THRESHOLD:.1f})"
    cv2.putText(frame, activity_label, (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, activity_color, 2)


def draw_fps_overlay(frame, fps: float):
    cv2.putText(
        frame, f"FPS: {fps:.1f}", (10, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2
    )


TIER_COLORS = {"green": (0, 200, 0), "yellow": (0, 220, 220), "red": (0, 0, 255)}


def draw_threat_score_overlay(frame, det, scorer: ThreatScorer):
    score = scorer.score(
        zone_tier=det.zone_tier,
        hour=datetime.now().hour,
        speed_px_per_frame=det.speed,
        category=det.category(),
    )
    if det.watchlist_match is not None:
        # A watchlist match escalates to Red regardless of zone score — but
        # transparently: the log/overlay still shows the underlying S/T/K/C
        # breakdown, this just overrides the final tier per the roadmap.
        score.tier = "red"
        score.total = max(score.total, 70.0)

    x1, y1, x2, y2 = det.box
    color = TIER_COLORS[score.tier]
    label = (
        f"T={score.total:.0f} ({score.tier.upper()})  "
        f"S={score.sector_risk:.0f} T={score.time_risk:.0f} "
        f"K={score.kinematics_risk:.0f} C={score.class_confidence:.0f}"
    )
    cv2.putText(frame, label, (x1, y2 + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
    return score


def _log_metrics(metrics, resources, manager, capabilities=None) -> None:
    """Periodic observability line: per-stage p50/p95, counters, resources.

    Emitted from the loop that already runs, so nothing here is sampled on a
    background thread. Contains only stage names, camera names and numbers -
    never frames, source URLs or credentials.
    """
    snapshot = metrics.snapshot()
    parts = []
    for label in sorted(snapshot["stages"]):
        stats = snapshot["stages"][label]
        if stats.get("count"):
            parts.append(f"{label} p50={stats['p50_ms']:.1f}ms p95={stats['p95_ms']:.1f}ms")
    log.info("METRICS stages: %s", " | ".join(parts) if parts else "(none yet)")
    log.info("METRICS counters: %s health: %s", snapshot["counters"], manager.health())
    if capabilities is not None:
        log.info(
            "METRICS capabilities: %s failures: %s",
            capabilities.summary(), capabilities.failures(),
        )
    sample = resources.sample()
    if sample.get("available"):
        log.info(
            "METRICS process: rss=%.1fMB cpu=%.1f%% threads=%d uptime=%.0fs",
            sample["rss_mb"], sample["cpu_percent"], sample["threads"], snapshot["uptime_s"],
        )


def main() -> None:
    log.info("IBVAP starting up (Phase 16 — Command & Control Integration)")

    window_names = {name: f"IBVAP - {name} (press q to quit)" for name in CAMERA_SOURCES}
    for window_name in window_names.values():
        cv2.namedWindow(window_name)

    manager = StreamManager(CAMERA_SOURCES, width=CAMERA_WIDTH, height=CAMERA_HEIGHT)
    manager.start_all()
    preprocessors = {
        name: Preprocessor(name, brightness_threshold=BRIGHTNESS_THRESHOLD)
        for name in CAMERA_SOURCES
    }
    gates = {name: ActivityGate(motion_threshold=MOTION_THRESHOLD) for name in CAMERA_SOURCES}
    frame_counters = {name: 0 for name in CAMERA_SOURCES}
    trackers = {
        name: Tracker(model_path=DETECTION_MODEL_PATH, confidence=DETECTION_CONFIDENCE)
        for name in CAMERA_SOURCES
    }
    false_alarm_filters = {name: FalseAlarmFilter() for name in CAMERA_SOURCES}
    # Optional intelligence capabilities. Each is gated behind a local
    # weight-availability precheck so a cold cache disables the capability
    # instead of triggering a download, and so a missing optional model can
    # never stop core perception from starting. See capabilities.py.
    capabilities = CapabilityRegistry()
    embedder = capabilities.load(
        "reid_embedding", ResNetEmbedder, precheck=resnet18_weights_available
    )
    # One shared gallery across all cameras (Phase 15: cross-camera Re-ID) —
    # resolve() is called with a (camera_name, track_id) key, not a raw
    # track_id, so two cameras can't collide on the same track_id number.
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
            config_path=f"config/zones_{name}.json",
            curfew_start_hour=CURFEW_START_HOUR,
            curfew_end_hour=CURFEW_END_HOUR,
        )
        for name in CAMERA_SOURCES
    }
    zone_drawers = {
        name: ZoneDrawer(window_names[name], zone_engines[name]) for name in CAMERA_SOURCES
    }
    face_recognizer = capabilities.load(
        "face_recognition", FaceRecognizer, precheck=buffalo_weights_available
    )
    # The watchlist store is local SQLite and needs no weights, but it can
    # still fail on an unreadable key or disk, and that must not stop core
    # perception either. Watchlist matching is meaningless without face
    # embeddings, so it stays off when face recognition is unavailable.
    watchlist_db = capabilities.load("watchlist", WatchlistDB)
    watchlist_matcher = (
        WatchlistMatcher(watchlist_db, similarity_threshold=WATCHLIST_SIMILARITY_THRESHOLD)
        if watchlist_db is not None
        else None
    )
    threat_rules = ThreatRulesDB()
    threat_scorer = ThreatScorer(threat_rules)
    incident_store = IncidentStore()
    webhook = WebhookNotifier(url=WEBHOOK_URL)
    syslog = SyslogNotifier(host=SYSLOG_HOST, port=SYSLOG_PORT)
    # Webhook POSTs and evidence persistence run on this bounded background
    # worker so a slow/unreachable C2 host or disk cannot stall the camera loop.
    alert_dispatcher = AlertDispatcher(maxsize=ALERT_DISPATCH_QUEUE_SIZE)
    alert_manager = AlertManager(
        cooldown_seconds=ALERT_COOLDOWN_SECONDS,
        incident_store=incident_store,
        webhook=webhook,
        syslog=syslog,
        dispatcher=alert_dispatcher,
    )
    frame_buffers = {name: deque(maxlen=3) for name in CAMERA_SOURCES}
    last_frame_time = {name: None for name in CAMERA_SOURCES}
    fps_ema = {name: 0.0 for name in CAMERA_SOURCES}
    isolator = CameraErrorIsolator()
    last_health: dict[str, str] = {}
    # Phase 1 instrumentation. Bounded rings, no background thread; ~3us per
    # stage timing against a ~60ms detection stage, so it does not materially
    # alter pipeline behaviour. NullCollector removes even that when disabled.
    metrics = MetricsCollector() if METRICS_ENABLED else NullCollector()
    resources = ResourceSampler(min_interval_s=METRICS_REPORT_INTERVAL_S)
    last_metrics_report = time.perf_counter()

    # Say up front what the operator is actually running with, rather than
    # leaving a disabled capability to be inferred from absent overlays.
    log.info("Optional capability states at startup: %s", capabilities.summary())
    for cap_name, entry in sorted(capabilities.states().items()):
        if entry["state"] != "available":
            log.warning("  %s: %s — %s", cap_name, entry["state"].upper(), entry["detail"])

    def process_camera_frame(name: str, frame) -> None:
        """The full per-camera pipeline for one frame.

        Runs behind `isolator` below, so anything raised in here costs this
        one frame on this one camera instead of the whole loop.
        """
        with metrics.stage(name, "activity_gate"):
            active, motion_score = gates[name].is_active(frame)
        frame_counters[name] += 1

        # High activity: run the full pipeline every frame.
        # Idle: only run it every Nth frame (low-FPS keep-alive).
        should_process = active or (frame_counters[name] % LOW_FPS_INTERVAL == 0)
        if not should_process:
            return

        now = time.perf_counter()
        if last_frame_time[name] is not None:
            instant_fps = 1.0 / max(now - last_frame_time[name], 1e-6)
            fps_ema[name] = (0.9 * fps_ema[name]) + (0.1 * instant_fps)
        last_frame_time[name] = now

        preprocessor = preprocessors[name]
        with metrics.stage(name, "preprocess"):
            processed = preprocessor.process(frame)

        with metrics.stage(name, "detect_track"):
            detections = trackers[name].track(processed)
        with metrics.stage(name, "false_alarm_filter"):
            detections = false_alarm_filters[name].filter(detections)
        metrics.increment("detections_kept", len(detections))
        for det in detections:
            if (
                person_gallery is not None
                and det.track_id is not None
                and det.category() == "person"
            ):
                # A failing optional model degrades itself and leaves the
                # detection unenriched; it does not cost the frame.
                with metrics.stage(name, "reid"):
                    det.person_id = capabilities.call(
                        "reid_embedding",
                        person_gallery.resolve,
                        (name, det.track_id), processed, det.box,
                    )
            x1, y1, x2, y2 = det.box
            ground_point = ((x1 + x2) // 2, y2)
            zone_result = zone_engines[name].classify(ground_point, det.direction)
            det.zone_tier = zone_result["tier"]
            det.zone_direction = zone_result["direction"]

            if face_recognizer is not None and det.category() == "person":
                with metrics.stage(name, "face_embed"):
                    _face_box, embedding = capabilities.call(
                        "face_recognition",
                        face_recognizer.embed,
                        processed, det.box,
                        default=(None, None),
                    )
                if embedding is not None and watchlist_matcher is not None:
                    with metrics.stage(name, "watchlist_match"):
                        match_name, similarity = capabilities.call(
                            "watchlist",
                            watchlist_matcher.match,
                            embedding,
                            default=(None, 0.0),
                        )
                    det.watchlist_match = match_name
                    det.watchlist_similarity = similarity

        draw_detections(processed, detections)

        with metrics.stage(name, "threat_score"):
            scores = [
                draw_threat_score_overlay(processed, det, threat_scorer) for det in detections
            ]

        draw_debug_overlay(processed, preprocessor, active, motion_score)
        draw_fps_overlay(processed, fps_ema[name])
        zone_drawers[name].draw_overlay(processed)

        frame_buffers[name].append(processed.copy())
        with metrics.stage(name, "alert_handle"):
            for det, score in zip(detections, scores):
                alert_manager.handle(det, score, list(frame_buffers[name]))

        cv2.imshow(window_names[name], processed)

    try:
        while True:
            health = manager.health()
            if health != last_health:
                degraded = {n: s for n, s in health.items() if s != CameraHealth.ONLINE}
                if degraded:
                    log.warning("Camera health changed — degraded: %s (all: %s)", degraded, health)
                    metrics.increment("health_degraded_transitions")
                else:
                    log.info("Camera health changed — all cameras ONLINE")
                    metrics.increment("health_recovered_transitions")
                last_health = health

            frames = manager.read_all()
            for name, frame in frames.items():
                if frame is None:
                    continue
                # Per-camera failure boundary: a pipeline exception on one
                # camera drops that frame, is logged with the camera id and a
                # traceback, and leaves every other camera still processing.
                if not isolator.run(
                    name, process_camera_frame, name, frame, stage="frame-pipeline"
                ):
                    metrics.increment("frame_pipeline_failures")
                else:
                    metrics.increment("frames_processed")

            if METRICS_ENABLED:
                now_report = time.perf_counter()
                if now_report - last_metrics_report >= METRICS_REPORT_INTERVAL_S:
                    last_metrics_report = now_report
                    _log_metrics(metrics, resources, manager, capabilities)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            for drawer in zone_drawers.values():
                drawer.handle_key(key)
    finally:
        manager.stop_all()
        # Drain queued webhook/evidence work before closing the stores it uses.
        alert_dispatcher.stop()
        threat_rules.close()
        incident_store.close()
        watchlist_db.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

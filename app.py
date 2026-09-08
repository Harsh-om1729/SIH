import logging
import os
import sys
import time
from collections import deque
from datetime import datetime

# Must be set BEFORE cv2 is imported — OpenCV reads this when it initialises
# its FFmpeg backend.
#
# timeout;5000000 — 5s, in microseconds, instead of FFmpeg's 30s default. A
# dropped RTSP stream otherwise blocks the producer thread inside a single
# cap.read() for 30s ("Stream timeout triggered after 30100 ms"), far past the
# ~2.5s CameraStream.MAX_CONSECUTIVE_FAILURES budget meant to spot a dead
# camera quickly. "timeout" is the current option name and "stimeout" the
# pre-FFmpeg-5.0 one; both are passed so the limit applies whichever build
# OpenCV was linked against.
#
# rtsp_transport;tcp — measured, not assumed. Against this project's phone
# camera (Android IP Webcam, 1080p over Wi-Fi), 150 consecutive frames each way:
#   UDP (FFmpeg default): 68 and 108 decode errors across two runs, 5 frames lost
#   TCP                 : 0 decode errors across two runs, 0 frames lost
# UDP's losses arrive as "error while decoding MB" and "intra mode" corruption —
# garbled macroblocks handed straight to the detector, which is far worse for
# tracking than TCP's lower throughput. TCP is slower on a 1080p stream (~11-19
# fps vs UDP's buffered ~60), so the real win is lowering the *sender's*
# resolution: fewer bits makes TCP both clean and fast.
os.environ.setdefault(
    "OPENCV_FFMPEG_CAPTURE_OPTIONS",
    "rtsp_transport;tcp|timeout;5000000|stimeout;5000000",
)

import cv2  # noqa: E402

from activity_gate.gate import ActivityGate
from alerts.alert_manager import AlertManager
from camera.stream_manager import StreamManager
from config.settings import (
    ALERT_COOLDOWN_SECONDS,
    BRIGHTNESS_THRESHOLD,
    CAMERA_HEIGHT,
    CAMERA_SOURCES,
    CAMERA_WIDTH,
    _parse_camera_sources,
    CURFEW_END_HOUR,
    CURFEW_START_HOUR,
    DETECTION_CONFIDENCE,
    DETECTION_MODEL_PATH,
    IDLE_MIN_FPS,
    MOTION_THRESHOLD,
    REID_FACE_CHECK_INTERVAL,
    REID_MATCH_MARGIN,
    REID_MODEL_PATH,
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
from face.face_recognizer import FaceRecognizer
from face.watchlist import WatchlistDB, WatchlistMatcher
from filtering.false_alarm import FalseAlarmFilter
from integration.syslog_notifier import SyslogNotifier
from integration.webhook import WebhookNotifier
from intelligence.loiter import LoiterTracker
from intelligence.threat_rules import ThreatRulesDB
from intelligence.threat_score import ThreatScore, ThreatScorer
from preprocessing.enhance import Preprocessor
from reid.embedder import OSNetEmbedder
from reid.reid import PersonGallery
from tracking.tracker import Tracker
from zones.drawer import ZoneDrawer
from zones.zone_engine import ZoneEngine

configure_logging()
log = logging.getLogger("ibvap")


def cli_camera_sources(argv: list) -> "dict[str, int | str] | None":
    """Lets camera sources be given directly on the command line instead of
    only via CAMERA_SOURCES in .env — e.g.:

        python app.py rtsp://192.168.1.46:8080/h264_ulaw.sdp
        python app.py 0 rtsp://192.168.1.46:8080/h264_ulaw.sdp   # webcam + phone, both live
        python app.py cam_phone=rtsp://192.168.1.46:8080/h264_ulaw.sdp

    Each positional argument is one camera: a bare RTSP/URL or webcam index
    is auto-named cam0, cam1, ...; name=source gives it a custom name. Reuses
    config.settings' own parser so the two entry points parse identically.
    Returns None (meaning "use CAMERA_SOURCES from .env") if no camera
    arguments were given.
    """
    positional = [a for a in argv if not a.startswith("--")]
    if not positional:
        return None

    parts = []
    for i, entry in enumerate(positional):
        name, _, _value = entry.partition("=")
        # A real name=value split has a plain identifier before the "=". If
        # that part looks like a URL scheme or a webcam index instead, the
        # "=" almost certainly belongs to the URL itself (e.g. a query
        # string, "...?user=admin"), so treat the whole entry as bare.
        is_valid_name = "=" in entry and name and "://" not in name and not name.isdigit()
        parts.append(entry if is_valid_name else f"cam{i}={entry}")
    return _parse_camera_sources(",".join(parts))


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


def zone_group_count(detections: list) -> int:
    """How many people are inside a zone in this frame.

    Group risk is a property of the frame, not of one detection, so it is
    counted once here and handed to every person's score — a lone walker and
    one of five people at the line must not read the same."""
    return sum(
        1 for d in detections
        if d.category() == "person" and d.zone_tier and d.zone_tier != "none"
    )


def draw_threat_score_overlay(frame, det, scorer: ThreatScorer, dwell_seconds: float, group_count: int):
    score = scorer.score(
        zone_tier=det.zone_tier,
        hour=datetime.now().hour,
        speed_px_per_frame=det.speed,
        category=det.category(),
        zone_direction=det.zone_direction,
        dwell_seconds=dwell_seconds,
        group_count=group_count,
    )
    if det.watchlist_match is not None:
        # A watchlist match escalates to Red regardless of zone score. Setting
        # override_reason (not just the tier) is what makes breakdown() report
        # the cause — without it this was the one path that went Red with no
        # stated reason, logging an unexplained "score=70 zone=none" whenever a
        # match happened outside a zone. The crossing override already works
        # this way; this now matches it.
        score.override_reason = (
            f"watchlist match: {det.watchlist_match} "
            f"(similarity={det.watchlist_similarity:.2f})"
            if det.watchlist_similarity is not None
            else f"watchlist match: {det.watchlist_match}"
        )
        score.tier = "red"
        score.total = max(score.total, ThreatScore.OVERRIDE_MIN_TOTAL)

    x1, y1, x2, y2 = det.box
    color = TIER_COLORS[score.tier]
    label = (
        f"T={score.total:.0f} ({score.tier.upper()})  "
        f"S={score.sector_risk:.0f} T={score.time_risk:.0f} "
        f"K={score.kinematics_risk:.0f} C={score.class_confidence:.0f} "
        f"D={score.direction_risk:.0f} L={score.loiter_risk:.0f} G={score.group_risk:.0f}"
    )
    cv2.putText(frame, label, (x1, y2 + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
    if score.override_reason is not None:
        cv2.putText(
            frame, f"FORCED RED: {score.override_reason}", (x1, y2 + 32),
            cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1,
        )
    return score


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
    embedder = OSNetEmbedder(REID_MODEL_PATH)
    # One shared gallery across all cameras (Phase 15: cross-camera Re-ID) —
    # resolve() is called with a (camera_name, track_id) key, not a raw
    # track_id, so two cameras can't collide on the same track_id number.
    person_gallery = PersonGallery(
        embed_fn=embedder.embed,
        similarity_threshold=REID_SIMILARITY_THRESHOLD,
        ttl_seconds=REID_TTL_SECONDS,
        match_margin=REID_MATCH_MARGIN,
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
    loiter_trackers = {name: LoiterTracker() for name in CAMERA_SOURCES}

    # Without zones there is no border line, so sector/direction/loiter/group
    # all read zero and the score collapses to time + class + movement. That
    # silently turns a border system into a generic motion alarm, so say it
    # loudly rather than letting a sentry trust an un-configured camera.
    for name in CAMERA_SOURCES:
        if not zone_engines[name].zones:
            log.warning(
                "[%s] NO ZONES DEFINED (%s is empty) — border scoring is inactive: "
                "no sector, crossing-direction, loitering or group risk will be "
                "applied. Press 'z' on the video window to draw the border line "
                "(red), approach strip (yellow) and own territory (green).",
                name, f"config/zones_{name}.json",
            )
    face_recognizer = FaceRecognizer()
    watchlist_db = WatchlistDB()
    watchlist_matcher = WatchlistMatcher(watchlist_db, similarity_threshold=WATCHLIST_SIMILARITY_THRESHOLD)
    threat_rules = ThreatRulesDB()
    threat_scorer = ThreatScorer(threat_rules)
    incident_store = IncidentStore()
    webhook = WebhookNotifier(url=WEBHOOK_URL)
    syslog = SyslogNotifier(host=SYSLOG_HOST, port=SYSLOG_PORT)
    alert_manager = AlertManager(
        cooldown_seconds=ALERT_COOLDOWN_SECONDS,
        incident_store=incident_store,
        webhook=webhook,
        syslog=syslog,
    )
    # Seconds between full pipeline passes while a scene is idle. Guard against
    # a zero/negative setting turning the floor into a division error.
    idle_min_period = 1.0 / IDLE_MIN_FPS if IDLE_MIN_FPS > 0 else 0.0

    frame_buffers = {name: deque(maxlen=3) for name in CAMERA_SOURCES}
    last_frame_time = {name: None for name in CAMERA_SOURCES}
    fps_ema = {name: 0.0 for name in CAMERA_SOURCES}
    # Per-camera caches so a throttled (skipped) frame still shows the last
    # known identity/watchlist result instead of blanking it out.
    person_id_cache = {name: {} for name in CAMERA_SOURCES}
    watchlist_cache = {name: {} for name in CAMERA_SOURCES}

    try:
        while True:
            frames = manager.read_all()
            for name, frame in frames.items():
                if frame is None:
                    continue

                active, motion_score = gates[name].is_active(frame)
                frame_counters[name] += 1

                # High activity: run the full pipeline every frame.
                # Idle: hold a floor of IDLE_MIN_FPS full passes per second, so
                # a still scene still updates the window and keeps tracks alive.
                # Timed off the last processed frame rather than a frame count,
                # because a count makes the idle rate a function of the camera's
                # own fps — two cameras at different rates idled at different
                # speeds from one setting.
                now = time.perf_counter()
                last_processed = last_frame_time[name]
                due = last_processed is None or (now - last_processed) >= idle_min_period
                if not (active or due):
                    continue

                if last_processed is not None:
                    instant_fps = 1.0 / max(now - last_processed, 1e-6)
                    fps_ema[name] = (0.9 * fps_ema[name]) + (0.1 * instant_fps)
                last_frame_time[name] = now

                preprocessor = preprocessors[name]
                processed = preprocessor.process(frame)

                detections = trackers[name].track(processed)
                detections = false_alarm_filters[name].filter(detections)
                for det in detections:
                    if det.track_id is not None and det.category() == "person":
                        track_id = det.track_id
                        # A brand-new track is checked every frame (Re-ID
                        # needs consecutive samples to decide an identity at
                        # all — resolve() returns None while still buffering,
                        # so check *value*, not key presence, or a track
                        # stuck buffering would get throttled before it ever
                        # resolves); once resolved, re-checking every Nth
                        # frame is enough — appearance doesn't change frame-to-frame.
                        already_resolved = person_id_cache[name].get(track_id) is not None
                        due_for_check = frame_counters[name] % REID_FACE_CHECK_INTERVAL == 0
                        if not already_resolved or due_for_check:
                            det.person_id = person_gallery.resolve(
                                (name, track_id), processed, det.box
                            )
                            person_id_cache[name][track_id] = det.person_id
                        else:
                            det.person_id = person_id_cache[name][track_id]

                        if not already_resolved or due_for_check:
                            _face_box, embedding = face_recognizer.embed(processed, det.box)
                            if embedding is not None:
                                match_name, similarity = watchlist_matcher.match(embedding)
                                watchlist_cache[name][track_id] = (match_name, similarity)
                        cached_match, cached_similarity = watchlist_cache[name].get(
                            track_id, (None, 0.0)
                        )
                        det.watchlist_match = cached_match
                        det.watchlist_similarity = cached_similarity

                    x1, y1, x2, y2 = det.box
                    ground_point = ((x1 + x2) // 2, y2)
                    zone_result = zone_engines[name].classify(ground_point, det.direction)
                    det.zone_tier = zone_result["tier"]
                    det.zone_direction = zone_result["direction"]

                draw_detections(processed, detections)

                group_count = zone_group_count(detections)
                scores = []
                for det in detections:
                    # Dwell is keyed on the Re-ID person_id where we have one,
                    # so standing still behind cover — which makes ByteTrack
                    # churn the track_id — doesn't keep resetting the clock.
                    dwell_key = (
                        ("person", det.person_id) if det.person_id is not None
                        else ("track", det.track_id)
                    )
                    dwell = loiter_trackers[name].update(dwell_key, det.zone_tier)
                    scores.append(
                        draw_threat_score_overlay(
                            processed, det, threat_scorer, dwell, group_count
                        )
                    )

                draw_debug_overlay(processed, preprocessor, active, motion_score)
                draw_fps_overlay(processed, fps_ema[name])
                zone_drawers[name].draw_overlay(processed)

                frame_buffers[name].append(processed.copy())
                for det, score in zip(detections, scores):
                    alert_manager.handle(det, score, list(frame_buffers[name]))

                cv2.imshow(window_names[name], processed)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            for drawer in zone_drawers.values():
                drawer.handle_key(key)
    finally:
        manager.stop_all()
        threat_rules.close()
        incident_store.close()
        watchlist_db.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    cli_sources = cli_camera_sources(sys.argv[1:])
    if cli_sources is not None:
        CAMERA_SOURCES = cli_sources
        log.info("Using camera source(s) from command line: %s", CAMERA_SOURCES)
    main()

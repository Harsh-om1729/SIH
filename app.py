import logging
import time

import cv2

from activity_gate.gate import ActivityGate
from camera.stream_manager import StreamManager
from config.settings import (
    BRIGHTNESS_THRESHOLD,
    CAMERA_HEIGHT,
    CAMERA_SOURCES,
    CAMERA_WIDTH,
    DETECTION_CONFIDENCE,
    DETECTION_MODEL_PATH,
    LOW_FPS_INTERVAL,
    MOTION_THRESHOLD,
    REID_SIMILARITY_THRESHOLD,
    REID_TTL_SECONDS,
    configure_logging,
)
from detection.draw import draw_detections
from filtering.false_alarm import FalseAlarmFilter
from preprocessing.enhance import Preprocessor
from reid.embedder import ResNetEmbedder
from reid.reid import PersonGallery
from tracking.tracker import Tracker

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


def main() -> None:
    log.info("IBVAP starting up (Phase 7 — False-Alarm Filter + Re-ID)")

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
    embedder = ResNetEmbedder()
    person_galleries = {
        name: PersonGallery(
            embed_fn=embedder.embed,
            similarity_threshold=REID_SIMILARITY_THRESHOLD,
            ttl_seconds=REID_TTL_SECONDS,
        )
        for name in CAMERA_SOURCES
    }
    last_frame_time = {name: None for name in CAMERA_SOURCES}
    fps_ema = {name: 0.0 for name in CAMERA_SOURCES}

    try:
        while True:
            frames = manager.read_all()
            for name, frame in frames.items():
                if frame is None:
                    continue

                active, motion_score = gates[name].is_active(frame)
                frame_counters[name] += 1

                # High activity: run the full pipeline every frame.
                # Idle: only run it every Nth frame (low-FPS keep-alive).
                should_process = active or (frame_counters[name] % LOW_FPS_INTERVAL == 0)
                if not should_process:
                    continue

                now = time.perf_counter()
                if last_frame_time[name] is not None:
                    instant_fps = 1.0 / max(now - last_frame_time[name], 1e-6)
                    fps_ema[name] = (0.9 * fps_ema[name]) + (0.1 * instant_fps)
                last_frame_time[name] = now

                preprocessor = preprocessors[name]
                processed = preprocessor.process(frame)

                detections = trackers[name].track(processed)
                detections = false_alarm_filters[name].filter(detections)
                for det in detections:
                    if det.track_id is not None:
                        det.person_id = person_galleries[name].resolve(
                            det.track_id, processed, det.box
                        )
                draw_detections(processed, detections)
                draw_debug_overlay(processed, preprocessor, active, motion_score)
                draw_fps_overlay(processed, fps_ema[name])

                cv2.imshow(f"IBVAP - {name} (press q to quit)", processed)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        manager.stop_all()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

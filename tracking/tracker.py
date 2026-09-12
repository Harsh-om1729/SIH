import logging
import os
import time

from ultralytics import YOLO

from detection.detector import RELEVANT_CLASS_IDS, Detection, model_input_size
from tracking.history import TrackHistory

log = logging.getLogger("ibvap.tracking")

# More tolerant of frame-to-frame box drift than Ultralytics' bundled
# bytetrack.yaml — a corrupted decode on a noisy source (e.g. a phone's RTSP
# stream over Wi-Fi) can visibly shift/resize a box even when the person
# hasn't actually moved, which breaks the default's stricter IoU matching
# and mints unnecessary new track IDs. See tracking/bytetrack_tolerant.yaml.
DEFAULT_TRACKER_CONFIG = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "bytetrack_tolerant.yaml"
)


class Tracker:
    """Runs detection + ByteTrack (via Ultralytics' built-in .track()) so each
    person/vehicle/animal gets a stable track ID across frames, and keeps a
    short position history per track to derive a direction vector and a
    per-frame speed. Both feed the zone engine and kinematics score.

    The history lives in a `TrackHistory`, which retires tracks that have not
    been seen for `history_ttl_seconds` so the per-track_id dict cannot grow
    for the lifetime of the process.
    """

    def __init__(
        self,
        model_path: str = "models/yolov8s.onnx",
        confidence: float = 0.4,
        history_len: int = 10,
        tracker_config: str = DEFAULT_TRACKER_CONFIG,
        history_ttl_seconds: float = 30.0,
        now_fn=time.time,
    ):
        log.info("Loading YOLO model for tracking: %s", model_path)
        self._model = YOLO(model_path, task="detect")
        size = model_input_size(model_path)
        self._size_kwargs = {"imgsz": size} if size else {}
        self.confidence = confidence
        self.history_len = history_len
        self.tracker_config = tracker_config
        self._track_history = TrackHistory(
            history_len=history_len, ttl_seconds=history_ttl_seconds, now_fn=now_fn
        )

    def track(self, frame) -> list[Detection]:
        results = self._model.track(
            frame,
            conf=self.confidence,
            persist=True,
            tracker=self.tracker_config,
            verbose=False,
            **self._size_kwargs,
        )[0]

        detections = []
        if results.boxes is not None and results.boxes.id is not None:
            for box in results.boxes:
                class_id = int(box.cls[0])
                if class_id not in RELEVANT_CLASS_IDS:
                    continue

                track_id = int(box.id[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                center = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

                det = Detection(
                    class_id=class_id,
                    class_name=results.names[class_id],
                    confidence=float(box.conf[0]),
                    box=(x1, y1, x2, y2),
                )
                det.track_id = track_id
                det.direction, det.speed = self._track_history.update(track_id, center)
                detections.append(det)

        # Runs on every call, including frames with no detections at all, so
        # history for tracks that have gone for good is always reclaimed.
        self._track_history.purge_stale()
        return detections

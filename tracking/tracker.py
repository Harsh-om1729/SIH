import logging
import time

from ultralytics import YOLO

from detection.detector import RELEVANT_CLASS_IDS, Detection
from tracking.history import TrackHistory

log = logging.getLogger("ibvap.tracking")


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
        model_path: str = "models/yolov8n.onnx",
        confidence: float = 0.4,
        history_len: int = 10,
        history_ttl_seconds: float = 30.0,
        now_fn=time.time,
    ):
        log.info("Loading YOLO model for tracking: %s", model_path)
        self._model = YOLO(model_path)
        self.confidence = confidence
        self.history_len = history_len
        self._track_history = TrackHistory(
            history_len=history_len, ttl_seconds=history_ttl_seconds, now_fn=now_fn
        )

    def track(self, frame) -> list[Detection]:
        results = self._model.track(
            frame,
            conf=self.confidence,
            persist=True,
            tracker="bytetrack.yaml",
            verbose=False,
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

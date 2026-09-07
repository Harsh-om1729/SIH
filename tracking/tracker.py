import logging
import os

from ultralytics import YOLO

from detection.detector import RELEVANT_CLASS_IDS, Detection

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
    """

    def __init__(
        self,
        model_path: str = "models/yolov8s.onnx",
        confidence: float = 0.4,
        history_len: int = 10,
        tracker_config: str = DEFAULT_TRACKER_CONFIG,
    ):
        log.info("Loading YOLO model for tracking: %s", model_path)
        self._model = YOLO(model_path)
        self.confidence = confidence
        self.history_len = history_len
        self.tracker_config = tracker_config
        self._track_history: dict[int, list[tuple[float, float]]] = {}

    def track(self, frame) -> list[Detection]:
        results = self._model.track(
            frame,
            conf=self.confidence,
            persist=True,
            tracker=self.tracker_config,
            verbose=False,
        )[0]

        detections = []
        if results.boxes is None or results.boxes.id is None:
            return detections

        for box in results.boxes:
            class_id = int(box.cls[0])
            if class_id not in RELEVANT_CLASS_IDS:
                continue

            track_id = int(box.id[0])
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            center = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

            history = self._track_history.setdefault(track_id, [])
            history.append(center)
            if len(history) > self.history_len:
                history.pop(0)

            det = Detection(
                class_id=class_id,
                class_name=results.names[class_id],
                confidence=float(box.conf[0]),
                box=(x1, y1, x2, y2),
            )
            det.track_id = track_id
            det.direction, det.speed = self._compute_direction_and_speed(history)
            detections.append(det)

        return detections

    @staticmethod
    def _compute_direction_and_speed(history: list[tuple[float, float]]):
        if len(history) < 2:
            return None, 0.0
        (x1, y1), (x2, y2) = history[0], history[-1]
        direction = (x2 - x1, y2 - y1)
        elapsed_frames = len(history) - 1
        speed = (direction[0] ** 2 + direction[1] ** 2) ** 0.5 / elapsed_frames
        return direction, speed

import logging

from config.offline import configure_ultralytics_offline

# Ultralytics evaluates ONLINE = is_online() at import time, opening a TCP
# probe to public DNS. This must run before that import, not after it.
configure_ultralytics_offline()

import onnxruntime  # noqa: E402
from ultralytics import YOLO  # noqa: E402

log = logging.getLogger("ibvap.detection")

CPU_EXECUTION_PROVIDER = "CPUExecutionProvider"
# The provider list as ONNX Runtime actually reports it, captured once at
# import before any pinning, so diagnostics can still print the truth.
ONNX_PROVIDERS_AVAILABLE = tuple(onnxruntime.get_available_providers())
_providers_pinned = False


def force_cpu_only_onnx_providers() -> list[str]:
    """Pin every ONNX Runtime session in this process to CPU execution.

    Ultralytics' AutoBackend builds its session with
    `onnxruntime.get_available_providers()` verbatim. On a stock Windows
    `onnxruntime` wheel that list is
    `['AzureExecutionProvider', 'CPUExecutionProvider']`, so the session is
    created with a provider that dispatches to a remote Azure endpoint sitting
    ahead of CPU. IBVAP is specified to run air-gapped: no remote execution
    provider may be registered on a session at all, independently of whether it
    happens to claim any nodes for the current graph.

    Ultralytics exposes no provider argument and builds the session lazily on
    first inference, so the narrowest hook available is to constrain what
    `get_available_providers()` reports for the remainder of the process. That
    permanence is intentional - it is the same requirement for every model
    loaded here, not just the detector.

    Idempotent. Raises RuntimeError rather than falling back to a remote
    provider if this ONNX Runtime build has no CPU provider.
    """
    global _providers_pinned
    if _providers_pinned:
        return [CPU_EXECUTION_PROVIDER]
    if CPU_EXECUTION_PROVIDER not in ONNX_PROVIDERS_AVAILABLE:
        raise RuntimeError(
            f"{CPU_EXECUTION_PROVIDER} is not available in this ONNX Runtime build "
            f"(available: {list(ONNX_PROVIDERS_AVAILABLE)}); refusing to fall back to "
            "a remote execution provider on an air-gapped system"
        )
    excluded = [p for p in ONNX_PROVIDERS_AVAILABLE if p != CPU_EXECUTION_PROVIDER]
    if excluded:
        log.info(
            "Pinning ONNX Runtime to %s; excluding %s (air-gapped deployment)",
            CPU_EXECUTION_PROVIDER,
            excluded,
        )
    onnxruntime.get_available_providers = lambda: [CPU_EXECUTION_PROVIDER]
    _providers_pinned = True
    return [CPU_EXECUTION_PROVIDER]

# COCO class ids relevant to border surveillance (person / vehicle / animal)
PERSON_CLASS_IDS = {0}
VEHICLE_CLASS_IDS = {1, 2, 3, 5, 7}  # bicycle, car, motorcycle, bus, truck
ANIMAL_CLASS_IDS = {15, 16, 17, 18, 19, 20, 21, 22, 23}
RELEVANT_CLASS_IDS = PERSON_CLASS_IDS | VEHICLE_CLASS_IDS | ANIMAL_CLASS_IDS


class Detection:
    __slots__ = (
        "class_id",
        "class_name",
        "confidence",
        "box",
        "track_id",
        "direction",
        "speed",
        "person_id",
        "zone_tier",
        "zone_direction",
        "watchlist_match",
        "watchlist_similarity",
    )

    def __init__(self, class_id: int, class_name: str, confidence: float, box: tuple):
        self.class_id = class_id
        self.class_name = class_name
        self.confidence = confidence
        self.box = box  # (x1, y1, x2, y2) in pixel coords
        self.track_id: int | None = None  # raw ByteTrack id; churns on re-appearance
        self.direction: tuple[float, float] | None = None  # (dx, dy) over recent history
        self.speed: float = 0.0  # pixels/frame over recent history
        self.person_id: int | None = None  # persistent identity from the Re-ID gallery
        self.zone_tier: str | None = None  # "red" | "yellow" | "green" | "none"
        self.zone_direction: str | None = None  # "inward" | "outward" | None (yellow only)
        self.watchlist_match: str | None = None  # matched name, if any
        self.watchlist_similarity: float = 0.0

    def category(self) -> str:
        if self.class_id in PERSON_CLASS_IDS:
            return "person"
        if self.class_id in VEHICLE_CLASS_IDS:
            return "vehicle"
        return "animal"


class Detector:
    """Wraps a YOLOv8 model, filtered down to person/vehicle/animal classes."""

    def __init__(self, model_path: str = "models/yolov8n.onnx", confidence: float = 0.4):
        force_cpu_only_onnx_providers()
        log.info("Loading YOLO model: %s", model_path)
        self._model = YOLO(model_path)
        self.confidence = confidence

    def detect(self, frame) -> list[Detection]:
        results = self._model.predict(frame, conf=self.confidence, verbose=False)[0]
        detections = []
        for box in results.boxes:
            class_id = int(box.cls[0])
            if class_id not in RELEVANT_CLASS_IDS:
                continue
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            detections.append(
                Detection(
                    class_id=class_id,
                    class_name=results.names[class_id],
                    confidence=float(box.conf[0]),
                    box=(x1, y1, x2, y2),
                )
            )
        return detections

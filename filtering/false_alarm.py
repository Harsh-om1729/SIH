from detection.detector import Detection

# Expected (min, max) height/width ratio per category. Rejects boxes that are
# implausibly shaped for their class — a common tell for a misdetection on
# foliage, shadows, or reflections rather than a real person/vehicle/animal.
ASPECT_RATIO_RANGES = {
    "person": (1.0, 4.0),
    "vehicle": (0.3, 2.5),
    "animal": (0.3, 3.0),
}


class FalseAlarmFilter:
    """Rejects detections with an implausible aspect ratio for their class."""

    def filter(self, detections: list[Detection]) -> list[Detection]:
        return [det for det in detections if self._passes_aspect_ratio(det)]

    @staticmethod
    def _passes_aspect_ratio(det: Detection) -> bool:
        x1, y1, x2, y2 = det.box
        width = max(x2 - x1, 1)
        height = max(y2 - y1, 1)
        ratio = height / width
        min_ratio, max_ratio = ASPECT_RATIO_RANGES.get(det.category(), (0.0, 100.0))
        return min_ratio <= ratio <= max_ratio

import cv2
import numpy as np


class ActivityGate:
    """Cheap per-frame motion check: downscale + grayscale + blur, then diff
    against the previous frame. Runs every frame at negligible cost so the
    caller can decide whether to run the full (expensive) pipeline or a
    low-FPS keep-alive pass instead.
    """

    def __init__(self, motion_threshold: float = 2.0, downscale_width: int = 320):
        self.motion_threshold = motion_threshold
        self.downscale_width = downscale_width
        self._prev_gray: np.ndarray | None = None

    def _prepare(self, frame: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        scale = self.downscale_width / w
        small = cv2.resize(frame, (self.downscale_width, max(1, int(h * scale))))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        return cv2.GaussianBlur(gray, (5, 5), 0)

    def is_active(self, frame: np.ndarray) -> tuple[bool, float]:
        gray = self._prepare(frame)
        if self._prev_gray is None:
            self._prev_gray = gray
            return True, 0.0  # assume active until we have a baseline
        diff = cv2.absdiff(gray, self._prev_gray)
        self._prev_gray = gray
        score = float(diff.mean())
        return score > self.motion_threshold, score

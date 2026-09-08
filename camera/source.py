import logging
import os

import cv2

log = logging.getLogger("ibvap.camera")


class CameraSource:
    """Wraps a single camera feed: a USB index (0, 1, ...), an RTSP/ONVIF URL,
    or a local video file path (useful for testing against recorded footage,
    e.g. vehicles, when no live feed is available)."""

    def __init__(self, source: int | str, width: int = 640, height: int = 480):
        self.source = source
        self.width = width
        self.height = height
        self.is_file = isinstance(source, str) and os.path.isfile(source)
        self.cap: cv2.VideoCapture | None = None

    def open(self) -> None:
        self.cap = cv2.VideoCapture(self.source)
        if not self.cap.isOpened():
            raise RuntimeError(f"Could not open camera source: {self.source!r}")
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        log.info("Camera opened: %s (requested %dx%d)", self.source, self.width, self.height)

    def native_fps(self) -> float:
        fps = self.cap.get(cv2.CAP_PROP_FPS)
        return fps if fps and fps > 0 else 30.0

    def read(self):
        ok, frame = self.cap.read()
        if not ok:
            return None
        # cap.set(FRAME_WIDTH/HEIGHT) is only honored by local capture devices.
        # It is a silent no-op for video files AND for network streams — an
        # RTSP sender decides its own resolution, so a phone pushing 1080p was
        # driving every downstream stage at 6.75x the configured pixel budget
        # (the temporal median filter alone stacks 5 frames, ~31MB at 1080p).
        # Checking the actual size covers all three source types, and costs a
        # tuple compare when the camera already gave us what we asked for.
        h, w = frame.shape[:2]
        if (w, h) != (self.width, self.height):
            frame = cv2.resize(frame, (self.width, self.height))
        return frame

    def release(self) -> None:
        if self.cap is not None:
            self.cap.release()
            log.info("Camera released: %s", self.source)

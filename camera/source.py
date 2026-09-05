import logging

import cv2

log = logging.getLogger("ibvap.camera")


class CameraSource:
    """Wraps a single camera feed: a USB index (0, 1, ...) or an RTSP/ONVIF URL."""

    def __init__(self, source: int | str, width: int = 640, height: int = 480):
        self.source = source
        self.width = width
        self.height = height
        self.cap: cv2.VideoCapture | None = None

    def open(self) -> None:
        self.cap = cv2.VideoCapture(self.source)
        if not self.cap.isOpened():
            raise RuntimeError(f"Could not open camera source: {self.source!r}")
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        log.info("Camera opened: %s (requested %dx%d)", self.source, self.width, self.height)

    def read(self):
        ok, frame = self.cap.read()
        return frame if ok else None

    def release(self) -> None:
        if self.cap is not None:
            self.cap.release()
            log.info("Camera released: %s", self.source)

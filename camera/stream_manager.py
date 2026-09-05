import logging
import queue
import threading
import time

import cv2

from camera.source import CameraSource

log = logging.getLogger("ibvap.stream_manager")


class CameraStream:
    """Runs one camera in its own producer thread, feeding a bounded queue.

    Only the newest frame is kept: if the consumer falls behind, the oldest
    queued frame is dropped rather than letting a backlog build up.
    """

    def __init__(self, name: str, source: int | str, width: int = 640, height: int = 480):
        self.name = name
        self._camera = CameraSource(source, width=width, height=height)
        self._queue: queue.Queue = queue.Queue(maxsize=1)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._camera.open()
        self._thread = threading.Thread(
            target=self._run, name=f"camera-{self.name}", daemon=True
        )
        self._thread.start()

    def _run(self) -> None:
        frame_interval = 1.0 / self._camera.native_fps() if self._camera.is_file else 0.0
        next_frame_at = time.perf_counter()

        while not self._stop_event.is_set():
            frame = self._camera.read()
            if frame is None:
                if self._camera.is_file:
                    log.info("[%s] video file ended, looping back to start", self.name)
                    self._camera.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                log.warning("[%s] no frame received, stopping producer", self.name)
                break

            if self._camera.is_file:
                # Recorded files have no natural playback pace like a live
                # camera does, so throttle to the file's own FPS.
                now = time.perf_counter()
                sleep_for = next_frame_at - now
                if sleep_for > 0:
                    time.sleep(sleep_for)
                next_frame_at = max(now, next_frame_at) + frame_interval

            if self._queue.full():
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    pass
            self._queue.put(frame)

    def read(self, timeout: float = 0.1):
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._camera.release()


class StreamManager:
    def __init__(self, sources: dict[str, int | str], width: int = 640, height: int = 480):
        self.streams = {
            name: CameraStream(name, src, width=width, height=height)
            for name, src in sources.items()
        }

    def start_all(self) -> None:
        for stream in self.streams.values():
            stream.start()
        log.info("Started %d camera stream(s): %s", len(self.streams), list(self.streams))

    def read_all(self) -> dict[str, object]:
        return {name: stream.read() for name, stream in self.streams.items()}

    def stop_all(self) -> None:
        for stream in self.streams.values():
            stream.stop()
        log.info("Stopped all camera streams")

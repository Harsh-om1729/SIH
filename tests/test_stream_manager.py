"""Offline unit tests for camera capture recovery (Issue A) — no camera
hardware, RTSP stream or OpenCV backend required.
Run from ibvap/: python -m unittest tests.test_stream_manager

`CameraStream` takes a `camera_factory`, so these tests drive a scripted fake
capture layer instead of a real `CameraSource`: the fake can be told exactly
when to fail to open, when to fail to read, and how long to stay down. That
makes "the camera came back after 3 failed attempts" a deterministic
assertion rather than something only observable against physical hardware.

Reconnect delays are set to milliseconds here; production defaults
(1s -> 30s exponential backoff) are unchanged.
"""

import threading
import time
import unittest

from camera.health import CameraHealth
from camera.stream_manager import CameraStream, StreamManager

FAST = {
    "reconnect_initial_delay": 0.005,
    "reconnect_max_delay": 0.02,
    "max_read_failures": 2,
    "stop_timeout": 2.0,
}


class FakeCamera:
    """Scripted stand-in for CameraSource with the same surface the producer
    thread uses: open/is_open/read/rewind/release/native_fps/is_file."""

    def __init__(self, source, width=640, height=480):
        self.source = source
        self.width = width
        self.height = height
        self.is_file = False
        self._lock = threading.Lock()

        # Scripting knobs, set by the tests.
        self.fail_open = False          # raise from open() while True
        self.fail_read = False          # return None from read() while True
        self.open_delay = 0.0           # simulate a slow/blocking open
        # A real cap.read() blocks on the hardware for ~1/fps. Modelling that
        # matters: a fake that returns instantly spins the producer thread fast
        # enough to starve the consumer of the GIL, which no real camera does.
        self.read_delay = 0.002

        # Observed behaviour.
        self.open_calls = 0
        self.open_failures = 0
        self.release_calls = 0
        self.frames_served = 0
        self._opened = False

    def open(self):
        with self._lock:
            self.open_calls += 1
            fail = self.fail_open
            delay = self.open_delay
        if delay:
            time.sleep(delay)
        if fail:
            with self._lock:
                self.open_failures += 1
            raise RuntimeError(f"Could not open camera source: {self.source!r}")
        with self._lock:
            self._opened = True

    def is_open(self):
        with self._lock:
            return self._opened

    def native_fps(self):
        return 30.0

    def read(self):
        if self.read_delay:
            time.sleep(self.read_delay)
        with self._lock:
            if not self._opened or self.fail_read:
                return None
            self.frames_served += 1
            return f"frame-{self.source}-{self.frames_served}"

    def rewind(self):
        return False

    def release(self):
        with self._lock:
            self.release_calls += 1
            self._opened = False


def wait_for(predicate, timeout=5.0, interval=0.005):
    """Polls until `predicate()` is truthy. Returns whether it became true."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


class StreamTestCase(unittest.TestCase):
    """Guarantees every stream started by a test is stopped, so a failing
    assertion can't leak a producer thread into the next test."""

    def setUp(self):
        self._streams = []

    def tearDown(self):
        for stream in self._streams:
            try:
                stream.stop()
            except Exception:
                pass

    def make_stream(self, name="cam0", source="fake0", **kwargs):
        cameras = {}

        def factory(src, width=640, height=480):
            camera = FakeCamera(src, width=width, height=height)
            cameras["camera"] = camera
            return camera

        options = dict(FAST)
        options.update(kwargs)
        stream = CameraStream(name, source, camera_factory=factory, **options)
        self._streams.append(stream)
        return stream, cameras["camera"]


class TestInitialConnection(StreamTestCase):
    def test_successful_initial_connection_goes_online_and_serves_frames(self):
        stream, camera = self.make_stream()
        stream.start()

        self.assertEqual(stream.health, CameraHealth.ONLINE)
        self.assertTrue(wait_for(lambda: stream.read(timeout=0.5) is not None))
        self.assertEqual(camera.open_calls, 1)

    def test_camera_that_cannot_open_starts_reconnecting_instead_of_raising(self):
        """A dead camera at startup must not raise out of start() — that is
        what previously aborted start_all() and took every camera with it."""
        stream, camera = self.make_stream()
        camera.fail_open = True

        stream.start()  # must not raise

        self.assertEqual(stream.health, CameraHealth.RECONNECTING)
        self.assertTrue(wait_for(lambda: camera.open_failures >= 2))


class TestRecovery(StreamTestCase):
    def test_temporary_read_failure_is_followed_by_recovery_to_online(self):
        """ONLINE -> RECONNECTING -> ONLINE: reads break, the capture is
        released and reopened, and frames flow again."""
        stream, camera = self.make_stream()
        stream.start()
        self.assertTrue(wait_for(lambda: camera.frames_served > 0))

        camera.fail_read = True
        self.assertTrue(
            wait_for(lambda: stream.health == CameraHealth.RECONNECTING),
            "stream never reported RECONNECTING after read failures",
        )
        # The broken capture must actually be released, not left dangling.
        self.assertTrue(wait_for(lambda: camera.release_calls >= 1))

        camera.fail_read = False
        self.assertTrue(
            wait_for(lambda: stream.health == CameraHealth.ONLINE),
            "stream never recovered to ONLINE",
        )
        self.assertGreaterEqual(stream.reconnect_count, 1)

        served_before = camera.frames_served
        self.assertTrue(wait_for(lambda: camera.frames_served > served_before))

    def test_stale_frame_is_not_served_after_the_camera_breaks(self):
        """A frame captured before the outage must not be handed out as if it
        were a live view once the stream is RECONNECTING."""
        stream, camera = self.make_stream()
        stream.start()
        self.assertTrue(wait_for(lambda: camera.frames_served > 0))

        # Let a frame sit in the queue, then break the camera.
        camera.fail_read = True
        self.assertTrue(wait_for(lambda: stream.health == CameraHealth.RECONNECTING))

        self.assertIsNone(stream.read(timeout=0.05))

    def test_repeated_failure_retries_with_backoff_not_a_tight_loop(self):
        """A source that stays down must keep retrying, but with a growing
        delay — never a hot loop burning a core on reconnect attempts."""
        stream, camera = self.make_stream(reconnect_initial_delay=0.02, reconnect_max_delay=0.08)
        camera.fail_open = True

        started = time.monotonic()
        stream.start()
        self.assertTrue(wait_for(lambda: camera.open_failures >= 5, timeout=10.0))
        elapsed = time.monotonic() - started

        # Delays are 20, 40, 80, 80ms before attempts 2..5 (attempt 1 waits the
        # initial 20ms), so five failures cannot take less than ~0.24s. A tight
        # retry loop would reach five in microseconds.
        self.assertGreater(elapsed, 0.2, f"reconnects were not backing off (took {elapsed:.3f}s)")
        self.assertEqual(stream.health, CameraHealth.RECONNECTING)

    def test_bounded_attempts_end_in_offline_rather_than_retrying_forever(self):
        stream, camera = self.make_stream(max_reconnect_attempts=3)
        camera.fail_open = True
        stream.start()

        self.assertTrue(
            wait_for(lambda: stream.health == CameraHealth.OFFLINE),
            "stream never gave up after exhausting its reconnect budget",
        )
        self.assertLessEqual(camera.open_calls, 4)  # initial open + 3 attempts

    def test_reconnect_survives_an_exception_from_open_itself(self):
        """Reconnect failing in an unexpected way (not just RuntimeError) must
        still be retried rather than killing the producer thread."""
        stream, camera = self.make_stream()
        original_open = camera.open
        calls = {"n": 0}

        def flaky_open():
            calls["n"] += 1
            if calls["n"] <= 3:
                raise OSError("transport endpoint is not connected")
            original_open()

        camera.open = flaky_open
        stream.start()  # first open raises OSError

        self.assertTrue(
            wait_for(lambda: stream.health == CameraHealth.ONLINE),
            "stream did not recover after open() raised a non-RuntimeError",
        )


class TestShutdown(StreamTestCase):
    def test_stop_during_reconnect_terminates_cleanly(self):
        """stop() while the producer is in backoff must return quickly and
        leave no live thread behind."""
        stream, camera = self.make_stream(
            reconnect_initial_delay=0.5, reconnect_max_delay=0.5
        )
        camera.fail_open = True
        stream.start()
        self.assertTrue(wait_for(lambda: stream.health == CameraHealth.RECONNECTING))

        started = time.monotonic()
        stream.stop()
        elapsed = time.monotonic() - started

        self.assertLess(elapsed, 2.0, "stop() waited out the backoff delay")
        self.assertFalse(stream._thread.is_alive())
        self.assertEqual(stream.health, CameraHealth.OFFLINE)

    def test_stop_while_online_still_releases_and_joins(self):
        stream, camera = self.make_stream()
        stream.start()
        self.assertTrue(wait_for(lambda: camera.frames_served > 0))

        stream.stop()

        self.assertFalse(stream._thread.is_alive())
        self.assertGreaterEqual(camera.release_calls, 1)
        self.assertEqual(stream.health, CameraHealth.OFFLINE)


class TestStreamManagerIsolation(unittest.TestCase):
    def test_one_dead_camera_does_not_stop_the_others_from_running(self):
        cameras = {}

        def factory(src, width=640, height=480):
            camera = FakeCamera(src, width=width, height=height)
            camera.fail_open = src == "dead"
            cameras[src] = camera
            return camera

        manager = StreamManager(
            {"cam_bad": "dead", "cam_good": "alive", "cam_good2": "alive2"},
            camera_factory=factory,
            **FAST,
        )
        try:
            manager.start_all()  # must not raise even though cam_bad is dead

            health = manager.health()
            self.assertEqual(health["cam_bad"], CameraHealth.RECONNECTING)
            self.assertEqual(health["cam_good"], CameraHealth.ONLINE)
            self.assertEqual(health["cam_good2"], CameraHealth.ONLINE)

            self.assertTrue(
                wait_for(lambda: cameras["alive"].frames_served > 0),
                "healthy camera never produced a frame",
            )
            self.assertTrue(wait_for(lambda: cameras["alive2"].frames_served > 0))

            frames = manager.read_all()
            self.assertIsNone(frames["cam_bad"])
            self.assertIsNotNone(frames["cam_good"])
        finally:
            manager.stop_all()

        self.assertEqual(
            set(manager.health().values()), {CameraHealth.OFFLINE}, "stop_all left a camera running"
        )

    def test_stop_all_continues_after_one_stream_raises(self):
        manager = StreamManager({"a": "s1", "b": "s2"}, camera_factory=FakeCamera, **FAST)
        manager.start_all()
        manager.streams["a"].stop = lambda: (_ for _ in ()).throw(RuntimeError("boom"))

        manager.stop_all()  # must not propagate

        self.assertEqual(manager.streams["b"].health, CameraHealth.OFFLINE)


if __name__ == "__main__":
    unittest.main()

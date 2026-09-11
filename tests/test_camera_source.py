"""Offline unit tests for CameraSource's open/read/release contract (Issue A)
— cv2.VideoCapture is mocked, so no camera, file or RTSP stream is needed.
Run from ibvap/: python -m unittest tests.test_camera_source

These cover the guarantees the reconnect loop in camera/stream_manager.py
relies on: reopening never leaks a VideoCapture, a broken read surfaces as
None instead of an exception, an empty/invalid frame is not mistaken for a
good one, and nothing ever writes RTSP credentials to the log.
"""

import logging
import unittest
from unittest.mock import patch

import numpy as np

from camera.source import CameraSource, redact_source


class FakeCapture:
    """Stands in for cv2.VideoCapture."""

    def __init__(self, opened=True, frames=None, read_raises=None):
        self._opened = opened
        self._frames = list(frames) if frames is not None else []
        self._read_raises = read_raises
        self.released = False
        self.settings = []

    def isOpened(self):
        return self._opened and not self.released

    def set(self, prop, value):
        self.settings.append((prop, value))
        return True

    def get(self, prop):
        return 25.0

    def read(self):
        if self._read_raises is not None:
            raise self._read_raises
        if not self._frames:
            return False, None
        return True, self._frames.pop(0)

    def release(self):
        self.released = True
        self._opened = False


def good_frame():
    return np.zeros((480, 640, 3), dtype=np.uint8)


class TestOpenReleasesHandles(unittest.TestCase):
    def test_failed_open_releases_the_capture_and_raises(self):
        """A VideoCapture that fails to open still holds resources — leaving
        one behind per reconnect attempt is exactly the leak to avoid."""
        capture = FakeCapture(opened=False)
        with patch("camera.source.cv2.VideoCapture", return_value=capture):
            source = CameraSource("rtsp://cam.invalid/stream")
            with self.assertRaises(RuntimeError):
                source.open()

        self.assertTrue(capture.released)
        self.assertIsNone(source.cap)
        self.assertFalse(source.is_open())

    def test_reopening_releases_the_previous_capture_first(self):
        """The reconnect path calls open() repeatedly; each call must hand
        back the old handle rather than orphan it."""
        first, second = FakeCapture(), FakeCapture()
        with patch("camera.source.cv2.VideoCapture", side_effect=[first, second]):
            source = CameraSource(0)
            source.open()
            self.assertFalse(first.released)
            source.open()

        self.assertTrue(first.released, "previous VideoCapture was not released on reopen")
        self.assertFalse(second.released)
        self.assertIs(source.cap, second)

    def test_release_is_idempotent_and_clears_the_handle(self):
        capture = FakeCapture()
        with patch("camera.source.cv2.VideoCapture", return_value=capture):
            source = CameraSource(0)
            source.open()

        source.release()
        source.release()  # must not raise on an already-released source

        self.assertTrue(capture.released)
        self.assertIsNone(source.cap)

    def test_release_survives_a_capture_that_throws(self):
        capture = FakeCapture()
        capture.release = lambda: (_ for _ in ()).throw(RuntimeError("driver gone"))
        with patch("camera.source.cv2.VideoCapture", return_value=capture):
            source = CameraSource(0)
            source.open()

        source.release()  # must not propagate during shutdown
        self.assertIsNone(source.cap)


class TestReadIsFailSafe(unittest.TestCase):
    def _source(self, capture):
        with patch("camera.source.cv2.VideoCapture", return_value=capture):
            source = CameraSource(0)
            source.open()
        return source

    def test_read_without_an_open_capture_returns_none(self):
        source = CameraSource(0)
        self.assertIsNone(source.read())

    def test_read_returns_the_frame_then_none_when_the_source_dries_up(self):
        source = self._source(FakeCapture(frames=[good_frame()]))
        self.assertIsNotNone(source.read())
        self.assertIsNone(source.read())

    def test_empty_frame_is_rejected_rather_than_passed_downstream(self):
        """cap.read() can report success while handing back an unusable frame;
        treating that as a good frame would push garbage into the pipeline."""
        source = self._source(FakeCapture(frames=[np.zeros((0, 0, 3), dtype=np.uint8)]))
        self.assertIsNone(source.read())

    def test_read_that_raises_is_reported_as_a_failed_read_not_an_exception(self):
        """A dropped RTSP stream can surface as an OpenCV exception; the
        producer thread must see a normal read failure and reconnect."""
        source = self._source(FakeCapture(read_raises=RuntimeError("stream closed")))
        self.assertIsNone(source.read())

    def test_native_fps_falls_back_when_there_is_no_capture(self):
        self.assertEqual(CameraSource(0).native_fps(), 30.0)

    def test_rewind_without_a_capture_reports_failure(self):
        self.assertFalse(CameraSource(0).rewind())


class TestCredentialsAreNeverLogged(unittest.TestCase):
    URL = "rtsp://borderops:S3cretPass@10.0.0.7:554/stream1"

    def test_redact_source_masks_embedded_credentials(self):
        redacted = redact_source(self.URL)
        self.assertNotIn("S3cretPass", redacted)
        self.assertNotIn("borderops", redacted)
        self.assertIn("10.0.0.7", redacted)  # host still identifiable

    def test_redact_source_leaves_credential_free_sources_alone(self):
        self.assertEqual(redact_source(0), "0")
        self.assertEqual(redact_source("rtsp://10.0.0.7:554/s"), "rtsp://10.0.0.7:554/s")

    def test_open_failure_message_and_logs_carry_no_password(self):
        capture = FakeCapture(opened=False)
        with patch("camera.source.cv2.VideoCapture", return_value=capture):
            source = CameraSource(self.URL)
            with self.assertLogs("ibvap.camera", level=logging.DEBUG) as captured:
                with self.assertRaises(RuntimeError) as raised:
                    source.open()
                # assertLogs fails on no records, so emit one deliberately.
                logging.getLogger("ibvap.camera").debug("probe")

        self.assertNotIn("S3cretPass", str(raised.exception))
        self.assertNotIn("S3cretPass", "\n".join(captured.output))

    def test_successful_open_and_release_logs_carry_no_password(self):
        capture = FakeCapture(frames=[good_frame()])
        with patch("camera.source.cv2.VideoCapture", return_value=capture):
            source = CameraSource(self.URL)
            with self.assertLogs("ibvap.camera", level=logging.INFO) as captured:
                source.open()
                source.release()

        joined = "\n".join(captured.output)
        self.assertNotIn("S3cretPass", joined)
        self.assertIn("10.0.0.7", joined)


if __name__ == "__main__":
    unittest.main()

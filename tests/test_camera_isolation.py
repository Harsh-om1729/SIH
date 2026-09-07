"""Offline unit tests for per-camera processing failure isolation (Issue B).
Run from ibvap/: python -m unittest tests.test_camera_isolation

`app.py`'s main loop drives every camera's frame through
`CameraErrorIsolator.run(...)`. These tests exercise that boundary directly,
including a loop shaped exactly like app.py's, so "camera A blowing up does
not stop camera B" is asserted rather than assumed.
"""

import logging
import unittest

from camera.health import CameraErrorIsolator


class RecordingLogger:
    """Captures what would have been logged, including a mode that fails."""

    def __init__(self, explode=False):
        self.records = []
        self.explode = explode

    def error(self, message, *args):
        if self.explode:
            raise OSError("log device full")
        self.records.append(message % args if args else message)

    def rendered(self):
        return "\n".join(self.records)


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def run_one_cycle(isolator, frames, process_fn):
    """Mirrors app.py's per-frame loop: every camera with a frame is processed
    behind the isolator, and one camera's failure must not end the cycle."""
    for name, frame in frames.items():
        if frame is None:
            continue
        isolator.run(name, process_fn, name, frame, stage="frame-pipeline")


class TestFailureIsolation(unittest.TestCase):
    def test_one_camera_failing_does_not_stop_the_others_in_the_same_cycle(self):
        processed = []
        logger = RecordingLogger()
        isolator = CameraErrorIsolator(logger=logger)

        def process(name, frame):
            if name == "cam_b":
                raise ValueError("corrupt detection output")
            processed.append((name, frame))

        frames = {"cam_a": "f-a", "cam_b": "f-b", "cam_c": "f-c", "cam_d": "f-d"}
        run_one_cycle(isolator, frames, process)  # must not raise

        # Every other camera still processed its frame.
        self.assertEqual(processed, [("cam_a", "f-a"), ("cam_c", "f-c"), ("cam_d", "f-d")])
        # The bad frame was dropped, not half-processed or retried.
        self.assertNotIn("cam_b", [name for name, _ in processed])
        # The failure was recorded, not swallowed.
        self.assertEqual(isolator.failure_count("cam_b"), 1)
        self.assertEqual(isolator.failure_count("cam_a"), 0)

    def test_the_application_loop_keeps_running_across_many_cycles(self):
        """The original failure mode: one camera's exception escaping the loop
        killed capture for every camera. Here cam_b fails on every cycle and
        cam_a must keep going for all of them."""
        cycles = 25
        good_frames = []
        isolator = CameraErrorIsolator(logger=RecordingLogger())

        def process(name, frame):
            if name == "cam_b":
                raise RuntimeError("model inference failed")
            good_frames.append(frame)

        for i in range(cycles):
            run_one_cycle(isolator, {"cam_a": f"f{i}", "cam_b": f"f{i}"}, process)

        self.assertEqual(len(good_frames), cycles)
        self.assertEqual(isolator.failure_count("cam_b"), cycles)

    def test_failure_is_logged_with_camera_id_stage_type_and_traceback(self):
        logger = RecordingLogger()
        isolator = CameraErrorIsolator(logger=logger)

        def process(name, frame):
            raise KeyError("zones_cam_a.json")

        isolator.run("cam_a", process, "cam_a", "frame", stage="frame-pipeline")

        rendered = logger.rendered()
        self.assertIn("cam_a", rendered)
        self.assertIn("KeyError", rendered)
        self.assertIn("frame-pipeline", rendered)
        self.assertIn("Traceback", rendered)  # full context, not just a message
        self.assertIn("test_camera_isolation.py", rendered)

    def test_run_reports_success_and_failure_to_the_caller(self):
        isolator = CameraErrorIsolator(logger=RecordingLogger())
        self.assertTrue(isolator.run("cam_a", lambda: None))
        self.assertFalse(isolator.run("cam_a", lambda: 1 / 0))

    def test_keyboard_interrupt_is_not_swallowed(self):
        """Ctrl-C and shutdown signals must still reach the caller — the
        boundary is for processing errors, not for everything."""
        isolator = CameraErrorIsolator(logger=RecordingLogger())

        def process():
            raise KeyboardInterrupt

        with self.assertRaises(KeyboardInterrupt):
            isolator.run("cam_a", process)


class TestDegradedState(unittest.TestCase):
    def test_consecutive_failures_mark_a_camera_degraded_and_recovery_clears_it(self):
        isolator = CameraErrorIsolator(logger=RecordingLogger())
        state = {"fail": True}

        def process():
            if state["fail"]:
                raise ValueError("boom")

        for _ in range(3):
            isolator.run("cam_a", process)
        self.assertTrue(isolator.is_degraded("cam_a", threshold=3))

        state["fail"] = False
        isolator.run("cam_a", process)

        self.assertFalse(isolator.is_degraded("cam_a"))
        self.assertEqual(isolator.failure_count("cam_a"), 3)  # history is kept

    def test_cameras_track_their_failures_independently(self):
        isolator = CameraErrorIsolator(logger=RecordingLogger())
        isolator.run("cam_a", lambda: 1 / 0)
        isolator.run("cam_b", lambda: None)
        isolator.run("cam_a", lambda: 1 / 0)

        self.assertEqual(isolator.failure_count("cam_a"), 2)
        self.assertEqual(isolator.failure_count("cam_b"), 0)
        self.assertTrue(isolator.is_degraded("cam_a"))
        self.assertFalse(isolator.is_degraded("cam_b"))


class TestLogStormControl(unittest.TestCase):
    def test_repeated_identical_failures_are_throttled_but_still_reported(self):
        """A camera failing on every frame at 30fps must not write 30 log
        lines a second — but it must never go quiet either."""
        clock = Clock()
        logger = RecordingLogger()
        isolator = CameraErrorIsolator(
            log_burst=3, summary_interval=60.0, now_fn=clock, logger=logger
        )

        for _ in range(500):
            isolator.run("cam_a", lambda: 1 / 0)

        self.assertEqual(len(logger.records), 3, "burst limit not applied")

        clock.t = 61.0
        isolator.run("cam_a", lambda: 1 / 0)

        self.assertEqual(len(logger.records), 4, "throttled failure never re-reported")
        summary = logger.records[-1]
        self.assertIn("suppressed", summary)
        self.assertIn("total=501", summary)

    def test_a_different_exception_type_is_reported_immediately(self):
        """Throttling is per (camera, exception type), so a new kind of failure
        is never hidden behind an already-throttled one."""
        logger = RecordingLogger()
        isolator = CameraErrorIsolator(log_burst=2, logger=logger)

        for _ in range(20):
            isolator.run("cam_a", lambda: 1 / 0)
        self.assertEqual(len(logger.records), 2)

        isolator.run("cam_a", lambda: {}["missing"])

        self.assertEqual(len(logger.records), 3)
        self.assertIn("KeyError", logger.records[-1])

    def test_a_failing_logger_does_not_take_the_loop_down(self):
        """'What if logging itself fails?' — the frame is still dropped, the
        loop still runs, and the logging failure is counted, not hidden."""
        isolator = CameraErrorIsolator(logger=RecordingLogger(explode=True))

        self.assertFalse(isolator.run("cam_a", lambda: 1 / 0))

        self.assertEqual(isolator.logging_failures, 1)
        self.assertEqual(isolator.failure_count("cam_a"), 1)


class TestAgainstTheRealLoggingStack(unittest.TestCase):
    def test_default_logger_emits_at_error_level(self):
        isolator = CameraErrorIsolator()
        with self.assertLogs("ibvap.camera.health", level=logging.ERROR) as captured:
            isolator.run("cam_a", lambda: 1 / 0, stage="frame-pipeline")
        self.assertIn("cam_a", captured.output[0])
        self.assertIn("ZeroDivisionError", captured.output[0])


if __name__ == "__main__":
    unittest.main()

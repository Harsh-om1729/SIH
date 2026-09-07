"""Offline unit tests for the bounded alert dispatch queue (Phase 0B item 1).
Run from ibvap/: python -m unittest tests.test_alert_dispatch

These cover the guarantees the frame-processing path depends on: submitting
never blocks or raises, a full queue drops loudly rather than silently, a
failing job cannot kill the worker or reach the caller, and shutdown flushes
queued work instead of discarding it.
"""

import logging
import threading
import time
import unittest

from alerts.dispatch import AlertDispatcher


class TestDispatchExecution(unittest.TestCase):
    def test_runs_submitted_job_on_background_thread(self):
        dispatcher = AlertDispatcher()
        seen = {}
        done = threading.Event()

        def job(value):
            seen["thread"] = threading.current_thread().name
            seen["value"] = value
            done.set()

        self.assertTrue(dispatcher.submit("job", job, 42))
        self.assertTrue(done.wait(2.0))
        dispatcher.stop()

        self.assertEqual(seen["value"], 42)
        self.assertNotEqual(seen["thread"], threading.current_thread().name)
        self.assertEqual(dispatcher.stats()["completed"], 1)

    def test_submit_does_not_block_the_caller(self):
        """The whole point: a slow webhook must not stall frame processing."""
        dispatcher = AlertDispatcher()
        release = threading.Event()

        dispatcher.submit("slow", release.wait, 5.0)
        started = time.perf_counter()
        for i in range(10):
            dispatcher.submit("fast", lambda: None)
        elapsed = time.perf_counter() - started

        release.set()
        dispatcher.stop()
        self.assertLess(elapsed, 0.5, "submit() blocked behind the slow job")

    def test_preserves_submission_order(self):
        dispatcher = AlertDispatcher()
        order = []
        for i in range(20):
            dispatcher.submit("job", order.append, i)
        dispatcher.stop()
        self.assertEqual(order, list(range(20)))


class TestDispatchBounded(unittest.TestCase):
    def test_full_queue_drops_loudly_and_is_counted(self):
        dispatcher = AlertDispatcher(maxsize=2)
        block = threading.Event()
        dispatcher.submit("blocker", block.wait, 5.0)
        time.sleep(0.1)  # let the worker pick the blocker up

        # Fill the 2 slots, then overflow.
        accepted = [dispatcher.submit("job", lambda: None) for _ in range(6)]

        with self.assertLogs("ibvap.alerts.dispatch", level=logging.ERROR) as captured:
            self.assertFalse(dispatcher.submit("overflow", lambda: None))
        block.set()
        dispatcher.stop()

        self.assertIn("queue full", "\n".join(captured.output))
        self.assertGreater(dispatcher.stats()["dropped"], 0)
        self.assertLessEqual(sum(accepted), 2, "queue accepted more than maxsize")

    def test_queue_never_grows_past_maxsize(self):
        dispatcher = AlertDispatcher(maxsize=4)
        block = threading.Event()
        dispatcher.submit("blocker", block.wait, 5.0)
        time.sleep(0.1)
        for _ in range(500):
            dispatcher.submit("job", lambda: None)
        self.assertLessEqual(dispatcher.pending(), 4)
        block.set()
        dispatcher.stop()


class TestDispatchFailureIsolation(unittest.TestCase):
    def test_failing_job_does_not_kill_worker_or_reach_caller(self):
        dispatcher = AlertDispatcher()
        survived = threading.Event()

        with self.assertLogs("ibvap.alerts.dispatch", level=logging.ERROR) as captured:
            dispatcher.submit("boom", self._explode)
            dispatcher.submit("after", survived.set)
            self.assertTrue(survived.wait(2.0))

        dispatcher.stop()
        joined = "\n".join(captured.output)
        self.assertIn("boom", joined)
        self.assertIn("RuntimeError", joined, "traceback not logged")
        self.assertEqual(dispatcher.stats()["failed"], 1)
        self.assertEqual(dispatcher.stats()["completed"], 1)

    @staticmethod
    def _explode():
        raise RuntimeError("webhook exploded")


class TestDispatchShutdown(unittest.TestCase):
    def test_stop_flushes_queued_work(self):
        dispatcher = AlertDispatcher()
        done = []
        for i in range(25):
            dispatcher.submit("job", done.append, i)
        self.assertTrue(dispatcher.stop(timeout=5.0))
        self.assertEqual(len(done), 25, "queued alerts were discarded at shutdown")

    def test_submit_after_stop_is_rejected_loudly(self):
        dispatcher = AlertDispatcher()
        dispatcher.stop()
        with self.assertLogs("ibvap.alerts.dispatch", level=logging.ERROR):
            self.assertFalse(dispatcher.submit("late", lambda: None))

    def test_stop_is_idempotent(self):
        dispatcher = AlertDispatcher()
        dispatcher.submit("job", lambda: None)
        self.assertTrue(dispatcher.stop())
        self.assertTrue(dispatcher.stop())

    def test_worker_thread_does_not_outlive_stop(self):
        before = threading.active_count()
        dispatcher = AlertDispatcher()
        dispatcher.submit("job", lambda: None)
        dispatcher.stop()
        time.sleep(0.2)
        self.assertLessEqual(threading.active_count(), before)


if __name__ == "__main__":
    unittest.main()

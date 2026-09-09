"""Offline unit tests for Phase 1 instrumentation (metrics/collector.py).
Run from ibvap/: python -m unittest tests.test_metrics

Instrumentation sits on the frame-processing path, so these assert the same
properties Phase 0A demanded of everything else there: bounded memory, no
silent error swallowing, and no background threads.
"""

import threading
import unittest

from metrics.collector import MetricsCollector, NullCollector, ResourceSampler


class TestStageTiming(unittest.TestCase):
    def test_records_a_sample_per_stage_entry(self):
        metrics = MetricsCollector()
        for _ in range(5):
            with metrics.stage("cam0", "detect"):
                pass
        self.assertEqual(metrics.stage_stats("cam0", "detect")["count"], 5)

    def test_unknown_stage_reports_zero_count(self):
        self.assertEqual(MetricsCollector().stage_stats("cam0", "nope"), {"count": 0})

    def test_percentiles_are_ordered(self):
        metrics = MetricsCollector()
        for value in [0.001, 0.002, 0.003, 0.010, 0.100]:
            metrics.record("cam0", "detect", value)
        stats = metrics.stage_stats("cam0", "detect")
        self.assertLessEqual(stats["p50_ms"], stats["p95_ms"])
        self.assertLessEqual(stats["p95_ms"], stats["max_ms"])
        self.assertAlmostEqual(stats["max_ms"], 100.0, places=6)

    def test_cameras_are_tracked_separately(self):
        metrics = MetricsCollector()
        metrics.record("cam0", "detect", 0.01)
        metrics.record("cam1", "detect", 0.02)
        self.assertEqual(metrics.stage_stats("cam0", "detect")["count"], 1)
        self.assertEqual(metrics.stage_stats("cam1", "detect")["count"], 1)
        self.assertEqual(metrics.tracked_keys(), 2)


class TestBounded(unittest.TestCase):
    def test_sample_ring_never_exceeds_window(self):
        metrics = MetricsCollector(window=50)
        for i in range(10_000):
            metrics.record("cam0", "detect", i / 1000.0)
        self.assertEqual(metrics.stage_stats("cam0", "detect")["count"], 50)

    def test_key_space_is_bounded_by_code_not_traffic(self):
        """Keys come from camera+stage names, so heavy traffic adds no keys."""
        metrics = MetricsCollector(window=16)
        for i in range(5_000):
            with metrics.stage("cam0", "detect"):
                pass
        self.assertEqual(metrics.tracked_keys(), 1)

    def test_reset_clears_everything(self):
        metrics = MetricsCollector()
        metrics.record("cam0", "detect", 0.01)
        metrics.increment("errors")
        metrics.reset()
        self.assertEqual(metrics.tracked_keys(), 0)
        self.assertEqual(metrics.counters(), {})


class TestErrorVisibility(unittest.TestCase):
    def test_exception_is_not_swallowed_and_is_still_timed(self):
        metrics = MetricsCollector()
        with self.assertRaises(ValueError):
            with metrics.stage("cam0", "detect"):
                raise ValueError("stage blew up")
        self.assertEqual(metrics.stage_stats("cam0", "detect")["count"], 1)
        self.assertEqual(metrics.counters().get("stage_exception"), 1)

    def test_counters_accumulate(self):
        metrics = MetricsCollector()
        metrics.increment("reconnect")
        metrics.increment("reconnect", 3)
        self.assertEqual(metrics.counters()["reconnect"], 4)


class TestNoBackgroundThreads(unittest.TestCase):
    def test_collector_and_sampler_start_no_threads(self):
        before = threading.active_count()
        metrics = MetricsCollector()
        sampler = ResourceSampler()
        for _ in range(100):
            with metrics.stage("cam0", "detect"):
                pass
        sampler.sample(force=True)
        self.assertEqual(threading.active_count(), before)


class TestThreadSafety(unittest.TestCase):
    def test_concurrent_writers_lose_no_samples(self):
        metrics = MetricsCollector(window=4096)
        def worker():
            for _ in range(500):
                metrics.record("cam0", "detect", 0.001)
        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(metrics.stage_stats("cam0", "detect")["count"], 2000)


class TestResourceSampler(unittest.TestCase):
    def test_reports_availability_honestly(self):
        sampler = ResourceSampler()
        sample = sampler.sample(force=True)
        if sampler.available:
            self.assertGreater(sample["rss_mb"], 0)
            self.assertGreaterEqual(sample["threads"], 1)
        else:
            # Unavailable must read as None, never as a fabricated zero.
            self.assertIsNone(sample["rss_mb"])
            self.assertFalse(sample["available"])

    def test_rate_limits_between_forced_samples(self):
        sampler = ResourceSampler(min_interval_s=3600.0)
        if not sampler.available:
            self.skipTest("psutil not installed")
        first = sampler.sample(force=True)
        second = sampler.sample()
        self.assertIs(first, second)


class TestNullCollector(unittest.TestCase):
    def test_is_inert_but_api_compatible(self):
        null = NullCollector()
        with null.stage("cam0", "detect"):
            pass
        null.record("cam0", "detect", 1.0)
        null.increment("errors")
        self.assertEqual(null.stage_stats("cam0", "detect"), {"count": 0})
        self.assertEqual(null.tracked_keys(), 0)
        self.assertEqual(null.snapshot()["stages"], {})

    def test_does_not_suppress_exceptions(self):
        with self.assertRaises(RuntimeError):
            with NullCollector().stage("cam0", "detect"):
                raise RuntimeError("boom")


if __name__ == "__main__":
    unittest.main()

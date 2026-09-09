"""Bounded runtime instrumentation for the perception pipeline (Phase 1).

Phase 1 measures; it does not optimise. This module exists so per-stage
latency, throughput, resource use and degraded-mode events can be observed on
the real pipeline instead of estimated.

Design constraints, which follow from the same reliability rules as Phase 0A:

- **Bounded.** Each (camera, stage) key keeps a fixed-length ring of recent
  durations. Keys come from the code's own stage names and the configured
  camera list, never from data, so the key space cannot grow with traffic.
- **No threads.** Sampling is pulled by the caller from the loop it already
  runs; nothing here starts a background thread or writes to disk.
- **Cheap.** One `perf_counter` pair and a deque append per stage. The
  overhead is itself measurable — see `scripts/measure_baseline.py`.
- **Never sensitive.** Only stage names, camera names and numbers are held.
  No frames, no URLs, no credentials, no biometric data.

`NullCollector` is the zero-overhead stand-in, so instrumentation can be
switched off without the call sites changing shape.
"""

import logging
import threading
import time
from collections import deque

log = logging.getLogger("ibvap.metrics")

try:
    import psutil

    _PSUTIL_AVAILABLE = True
except ImportError:
    # Optional: psutil is not in requirements.txt, so resource sampling
    # degrades to unavailable rather than becoming a hard dependency.
    _PSUTIL_AVAILABLE = False


def _percentile(ordered: list, fraction: float) -> float:
    """Nearest-rank percentile over an already-sorted list."""
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, max(0, round(fraction * (len(ordered) - 1))))
    return ordered[index]


class _Stopwatch:
    """Context manager returned by `MetricsCollector.stage()`.

    Records the elapsed time even when the body raises, so a failing stage
    still shows up in the latency profile instead of silently vanishing. The
    exception is never suppressed.
    """

    __slots__ = ("_collector", "_camera", "_stage", "_start")

    def __init__(self, collector, camera: str, stage: str):
        self._collector = collector
        self._camera = camera
        self._stage = stage
        self._start = 0.0

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb):
        elapsed = time.perf_counter() - self._start
        self._collector.record(self._camera, self._stage, elapsed)
        if exc_type is not None:
            self._collector.increment("stage_exception")
        return False  # never swallow


class MetricsCollector:
    """Collects per-(camera, stage) latency samples and named event counters."""

    def __init__(self, window: int = 512):
        if window < 1:
            raise ValueError("window must be at least 1")
        self.window = window
        self._lock = threading.Lock()
        self._samples: dict = {}
        self._counters: dict = {}
        self._started = time.perf_counter()

    def stage(self, camera: str, stage: str) -> _Stopwatch:
        """`with metrics.stage("cam0", "detection"):` — times the block."""
        return _Stopwatch(self, camera, stage)

    def record(self, camera: str, stage: str, seconds: float) -> None:
        key = (camera, stage)
        with self._lock:
            ring = self._samples.get(key)
            if ring is None:
                ring = deque(maxlen=self.window)
                self._samples[key] = ring
            ring.append(seconds)

    def increment(self, event: str, amount: int = 1) -> None:
        """Counts a named event (errors, reconnects, degraded transitions)."""
        with self._lock:
            self._counters[event] = self._counters.get(event, 0) + amount

    def counters(self) -> dict:
        with self._lock:
            return dict(self._counters)

    def stage_stats(self, camera: str, stage: str) -> dict:
        with self._lock:
            ring = self._samples.get((camera, stage))
            values = sorted(ring) if ring else []
        if not values:
            return {"count": 0}
        return {
            "count": len(values),
            "mean_ms": 1000 * sum(values) / len(values),
            "p50_ms": 1000 * _percentile(values, 0.50),
            "p95_ms": 1000 * _percentile(values, 0.95),
            "max_ms": 1000 * values[-1],
        }

    def snapshot(self) -> dict:
        """All stage statistics plus counters and uptime.

        Sorted deterministically so successive reports are diffable.
        """
        with self._lock:
            keys = sorted(self._samples.keys())
            counters = dict(self._counters)
            uptime = time.perf_counter() - self._started
        return {
            "uptime_s": uptime,
            "counters": counters,
            "stages": {
                f"{camera}/{stage}": self.stage_stats(camera, stage)
                for camera, stage in keys
            },
        }

    def reset(self) -> None:
        with self._lock:
            self._samples.clear()
            self._counters.clear()
            self._started = time.perf_counter()

    def tracked_keys(self) -> int:
        """How many (camera, stage) rings exist — asserts boundedness."""
        with self._lock:
            return len(self._samples)


class NullCollector:
    """Does nothing, at as close to zero cost as Python allows."""

    __slots__ = ()

    def stage(self, camera: str, stage: str) -> "_NullStopwatch":
        return _NULL_STOPWATCH

    def record(self, camera: str, stage: str, seconds: float) -> None:
        pass

    def increment(self, event: str, amount: int = 1) -> None:
        pass

    def counters(self) -> dict:
        return {}

    def stage_stats(self, camera: str, stage: str) -> dict:
        return {"count": 0}

    def snapshot(self) -> dict:
        return {"uptime_s": 0.0, "counters": {}, "stages": {}}

    def reset(self) -> None:
        pass

    def tracked_keys(self) -> int:
        return 0


class _NullStopwatch:
    __slots__ = ()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


_NULL_STOPWATCH = _NullStopwatch()


class ResourceSampler:
    """Pull-based process resource readings (RSS, CPU%, threads).

    Pulled by the caller from a loop it already runs — no background thread.
    Returns `None` for every field when psutil is unavailable rather than
    guessing, so a missing optional dependency is visible as "unmeasured"
    instead of being mistaken for a real figure.
    """

    def __init__(self, min_interval_s: float = 5.0):
        self.min_interval_s = min_interval_s
        self.available = _PSUTIL_AVAILABLE
        self._process = psutil.Process() if _PSUTIL_AVAILABLE else None
        self._last_sample_at = 0.0
        self._last: dict = {}
        if _PSUTIL_AVAILABLE:
            # First call establishes the CPU-percent baseline; its return
            # value is meaningless by definition, so it is discarded here.
            self._process.cpu_percent(None)
        else:
            log.info("psutil not installed - process resource metrics unavailable")

    def sample(self, force: bool = False) -> dict:
        """Returns a reading, rate-limited to `min_interval_s`.

        Between intervals the previous reading is returned unchanged, so
        calling this every frame is safe.
        """
        if not self.available:
            return {"available": False, "rss_mb": None, "cpu_percent": None, "threads": None}
        now = time.perf_counter()
        if not force and self._last and (now - self._last_sample_at) < self.min_interval_s:
            return self._last
        try:
            with self._process.oneshot():
                rss = self._process.memory_info().rss
                cpu = self._process.cpu_percent(None)
                threads = self._process.num_threads()
        except Exception as exc:
            # A sampling failure must never take down the pipeline it observes,
            # but it is reported rather than swallowed.
            log.warning("Resource sample failed (%s: %s)", type(exc).__name__, exc)
            return {"available": False, "rss_mb": None, "cpu_percent": None, "threads": None}
        self._last_sample_at = now
        self._last = {
            "available": True,
            "rss_mb": rss / (1024 * 1024),
            "cpu_percent": cpu,
            "threads": threads,
        }
        return self._last

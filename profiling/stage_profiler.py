"""Per-stage latency instrumentation for the live pipeline.

Opt-in: the profiler is inert unless it is explicitly enabled (env var
IBVAP_PROFILE=1, or `enabled=True`). When inert, `stage()` returns a shared
do-nothing context manager, so an instrumented loop runs the same code path
and allocates nothing extra — measuring the system must not change it.

Timings use perf_counter (monotonic, highest resolution available) and are
folded into running aggregates rather than appended to a list, so memory
stays flat over a long run and the per-call cost is a few arithmetic ops.
"""
import os
import time
from contextlib import contextmanager

try:
    import psutil
except ImportError:  # optional — CPU figures are simply omitted without it
    psutil = None


class _Stage:
    __slots__ = ("name", "count", "total", "max", "min")

    def __init__(self, name: str):
        self.name = name
        self.count = 0
        self.total = 0.0
        self.max = 0.0
        self.min = float("inf")

    def add(self, elapsed: float) -> None:
        self.count += 1
        self.total += elapsed
        if elapsed > self.max:
            self.max = elapsed
        if elapsed < self.min:
            self.min = elapsed

    @property
    def mean(self) -> float:
        return self.total / self.count if self.count else 0.0


class _NoOp:
    """Reusable do-nothing context manager.

    Must be a class, not a @contextmanager generator: a generator-based one is
    single-use (its __enter__ deletes the stored func/args), so a shared
    instance blows up with AttributeError the second time it is entered — and
    the disabled path enters one once per stage per frame. A plain object with
    __enter__/__exit__ is reentrant and allocates nothing.
    """
    __slots__ = ()

    def __enter__(self):
        return None

    def __exit__(self, *exc_info):
        return False


_NOOP = _NoOp()


class StageProfiler:
    """Accumulates wall-clock time per named pipeline stage.

        with profiler.stage("detect_track"):
            detections = tracker.track(frame)

    Stages are recorded in first-seen order so the report reads in pipeline
    order rather than alphabetically.
    """

    def __init__(self, enabled: "bool | None" = None):
        if enabled is None:
            enabled = os.getenv("IBVAP_PROFILE", "").strip() not in ("", "0", "false", "False")
        self.enabled = enabled
        self._stages: "dict[str, _Stage]" = {}
        self._frames = 0
        self._wall_start = time.perf_counter()
        self._proc = psutil.Process() if (enabled and psutil is not None) else None
        if self._proc is not None:
            self._proc.cpu_percent(None)  # prime the sampler; first call is meaningless
        self._cpu_start = time.process_time()

    @contextmanager
    def _timed(self, name: str):
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start
            stage = self._stages.get(name)
            if stage is None:
                stage = self._stages[name] = _Stage(name)
            stage.add(elapsed)

    def stage(self, name: str):
        # Returning a pre-built no-op keeps the disabled path free of generator
        # setup; the `with` statement on it is effectively free.
        if not self.enabled:
            return _NOOP
        return self._timed(name)

    def frame_done(self) -> None:
        if self.enabled:
            self._frames += 1

    # -- reporting ----------------------------------------------------------
    def report(self) -> str:
        if not self.enabled or not self._stages:
            return ""

        wall = time.perf_counter() - self._wall_start
        cpu_time = time.process_time() - self._cpu_start
        # Sum of stage means is the modelled per-frame cost; comparing it with
        # measured wall time per frame exposes time spent outside any stage.
        accounted = sum(s.total for s in self._stages.values())

        lines = []
        lines.append("")
        lines.append("=" * 78)
        lines.append("PIPELINE STAGE PROFILE")
        lines.append("=" * 78)
        lines.append(
            f"{'stage':<22}{'calls':>7}{'avg ms':>10}{'max ms':>10}"
            f"{'min ms':>10}{'total s':>10}{'% time':>9}"
        )
        lines.append("-" * 78)
        for stage in self._stages.values():
            share = (stage.total / accounted * 100.0) if accounted else 0.0
            lines.append(
                f"{stage.name:<22}{stage.count:>7}{stage.mean * 1000:>10.2f}"
                f"{stage.max * 1000:>10.2f}{stage.min * 1000:>10.2f}"
                f"{stage.total:>10.2f}{share:>8.1f}%"
            )
        lines.append("-" * 78)

        slowest = max(self._stages.values(), key=lambda s: s.total)
        lines.append(f"frames processed      : {self._frames}")
        if wall > 0:
            lines.append(f"throughput            : {self._frames / wall:.1f} fps "
                         f"over {wall:.1f}s wall")
        if self._frames:
            lines.append(f"per-frame accounted   : {accounted / self._frames * 1000:.2f} ms")
        lines.append(f"CPU time (this proc)  : {cpu_time:.1f}s "
                     f"({cpu_time / wall * 100:.0f}% of one core)" if wall > 0 else "")
        if self._proc is not None:
            try:
                lines.append(f"CPU now               : {self._proc.cpu_percent(None):.0f}% "
                             f"(100% = one core)")
                lines.append(f"RSS                   : "
                             f"{self._proc.memory_info().rss / 1024 / 1024:.0f} MB")
            except Exception:
                pass
        lines.append(f"BOTTLENECK            : {slowest.name} "
                     f"({slowest.total / accounted * 100:.0f}% of accounted time, "
                     f"{slowest.mean * 1000:.2f} ms avg)")
        lines.append("=" * 78)
        return "\n".join(l for l in lines if l != "")

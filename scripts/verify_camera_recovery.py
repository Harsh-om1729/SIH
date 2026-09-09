"""Phase 1 camera RECOVERY verification against a real device (fault injection).

`scripts/measure_live_baseline.py` proved a real camera opens, reaches ONLINE,
delivers frames and shuts down cleanly. What it could not prove is the other
half of the dependability claim: that when the camera actually goes away the
system notices, says so truthfully, retries, and comes back. This script
closes that gap by breaking a live capture and then restoring it.

WHAT IS REAL HERE
- the real `CameraStream` producer thread, its health state machine, its
  backoff and its reconnect loop (`camera/stream_manager.py`) - untouched
- the real `CameraSource` open/read/release wrapper (`camera/source.py`)
- the real physical camera from CAMERA_SOURCES, opened by real OpenCV
- the real consumer path: `StreamManager.read_all()` + `CameraErrorIsolator`
- production reconnect settings (1s -> 30s backoff, 3 read failures)

WHAT IS INJECTED
Physically unplugging the device is not available here (the camera is an
internal UVC device and disabling it needs Administrator), so the smallest
equivalent fault is applied through `CameraStream`'s existing `camera_factory`
hook, at the device handle itself:

  1. "unplug": the live `cv2.VideoCapture` is released *on the producer
     thread*, so the very next production `CameraSource.read()` performs a
     real `cap.read()` against an invalid handle and gets `ok=False` - the
     same signal a yanked USB cable produces. While unplugged, the source is
     pointed at an absent device index, so every production reopen attempt is
     a real OpenCV open of a device that genuinely is not there.
  2. "replug": the source is pointed back at the real camera index. Nothing
     tells the stream to recover - the production reconnect loop finds the
     device on its own.

No production module is modified, and no reconnect is simulated: the recovery
observed is a real `cv2.VideoCapture(<real index>)` reopening real hardware
and real frames flowing again.

Run from the repo root:
    python scripts/verify_camera_recovery.py --json out.json
"""

import argparse
import json
import logging
import os
import platform
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2  # noqa: E402

from activity_gate.gate import ActivityGate  # noqa: E402
from camera.health import CameraErrorIsolator, CameraHealth  # noqa: E402
from camera.source import CameraSource, redact_source  # noqa: E402
from camera.stream_manager import StreamManager  # noqa: E402
from config.settings import (  # noqa: E402
    BRIGHTNESS_THRESHOLD,
    CAMERA_HEIGHT,
    CAMERA_SOURCES,
    CAMERA_WIDTH,
    MOTION_THRESHOLD,
)
from metrics.collector import MetricsCollector  # noqa: E402
from preprocessing.enhance import Preprocessor  # noqa: E402

log = logging.getLogger("ibvap.verify_recovery")

RUN_START = time.monotonic()


def now() -> float:
    """Seconds since the run started (monotonic, immune to clock changes)."""
    return time.monotonic() - RUN_START


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------


class Timeline:
    """Ordered, timestamped record of everything observed during the run."""

    def __init__(self):
        self._lock = threading.Lock()
        self.events: list[dict] = []

    def mark(self, kind: str, detail: str = "", **fields) -> float:
        stamp = now()
        entry = {"t": round(stamp, 4), "kind": kind, "detail": detail}
        entry.update(fields)
        with self._lock:
            self.events.append(entry)
        log.info("[t=%7.3fs] %-26s %s", stamp, kind, detail)
        return stamp

    def first(self, kind: str) -> dict | None:
        with self._lock:
            for entry in self.events:
                if entry["kind"] == kind:
                    return entry
        return None

    def snapshot(self) -> list[dict]:
        with self._lock:
            return list(self.events)


# ---------------------------------------------------------------------------
# Fault injection at the device handle (harness only)
# ---------------------------------------------------------------------------


class UnpluggableCameraSource(CameraSource):
    """The production `CameraSource` plus a controlled "the device is gone".

    Every capture behaviour below is the base class's. The subclass only
    (a) counts what the production code did, and (b) applies the fault:

    - `unplug()` marks the device absent. The next `read()` - which runs on
      the production producer thread, the same thread that would otherwise be
      inside `cap.read()`, so nothing is freed from under another thread -
      releases the live `cv2.VideoCapture` and then calls the *unmodified*
      base `read()`, which performs a real `cap.read()` on that dead handle
      and gets `ok=False` back from OpenCV.
    - While unplugged, `open()` targets an absent device index, so the
      production reconnect loop's reopen attempts really fail inside OpenCV.
    - `replug()` restores the real index; the next production reopen attempt
      finds the camera again on its own.
    """

    def __init__(self, source, width, height, *, camera_name, absent_source, timeline):
        super().__init__(source, width=width, height=height)
        self.camera_name = camera_name
        self.real_source = source
        self.absent_source = absent_source
        self.timeline = timeline
        self._unplugged = threading.Event()
        self._lock = threading.Lock()
        self.stats = {
            "open_attempts": 0,
            "open_successes": 0,
            "open_failures": 0,
            "release_calls": 0,
            "read_ok": 0,
            "read_none": 0,
            "handle_invalidations": 0,
            "first_failed_read_at": None,
            "first_reopen_success_at": None,
        }

    # -- fault control (called from the harness thread) --------------------
    def unplug(self) -> None:
        self.source = self.absent_source
        self._unplugged.set()

    def replug(self) -> None:
        self._unplugged.clear()
        self.source = self.real_source

    def is_unplugged(self) -> bool:
        return self._unplugged.is_set()

    # -- production surface, instrumented ----------------------------------
    def open(self) -> None:
        # Re-read the plug state at open time: an absent device cannot be
        # opened, a present one can. `self.source` is what the base class
        # hands to cv2.VideoCapture.
        self.source = self.absent_source if self._unplugged.is_set() else self.real_source
        with self._lock:
            self.stats["open_attempts"] += 1
            attempt = self.stats["open_attempts"]
        started = time.perf_counter()
        try:
            super().open()
        except Exception as exc:
            with self._lock:
                self.stats["open_failures"] += 1
            self.timeline.mark(
                "reopen_attempt_failed",
                f"attempt #{attempt} on {redact_source(self.source)}: {type(exc).__name__}",
                attempt=attempt,
                seconds=round(time.perf_counter() - started, 4),
            )
            raise
        with self._lock:
            self.stats["open_successes"] += 1
            if attempt > 1 and self.stats["first_reopen_success_at"] is None:
                self.stats["first_reopen_success_at"] = now()
        self.timeline.mark(
            "device_opened",
            f"attempt #{attempt} on {redact_source(self.source)} in "
            f"{1000 * (time.perf_counter() - started):.0f}ms",
            attempt=attempt,
        )

    def read(self):
        if self._unplugged.is_set() and self.cap is not None:
            # Invalidate the real handle, on the producer thread. Subsequent
            # base-class reads hit a dead capture, exactly as they would after
            # the device disappeared.
            cap = self.cap
            with self._lock:
                self.stats["handle_invalidations"] += 1
                first = self.stats["handle_invalidations"] == 1
            cap.release()
            if first:
                self.timeline.mark(
                    "device_handle_invalidated",
                    "live cv2.VideoCapture released on the producer thread",
                )
        frame = super().read()
        failed_first = False
        with self._lock:
            if frame is None:
                self.stats["read_none"] += 1
                if self.stats["first_failed_read_at"] is None:
                    self.stats["first_failed_read_at"] = now()
                    failed_first = True
            else:
                self.stats["read_ok"] += 1
        if failed_first:
            self.timeline.mark("first_failed_device_read", "real cap.read() returned ok=False")
        return frame

    def release(self) -> None:
        with self._lock:
            self.stats["release_calls"] += 1
        super().release()


# ---------------------------------------------------------------------------
# Resource sampling
# ---------------------------------------------------------------------------


def resource_snapshot(label: str) -> dict:
    snap = {
        "label": label,
        "t": round(now(), 3),
        "python_threads": threading.active_count(),
        "thread_names": sorted(t.name for t in threading.enumerate()),
        "camera_threads": sorted(
            t.name for t in threading.enumerate() if t.name.startswith("camera-")
        ),
    }
    try:
        import psutil

        proc = psutil.Process()
        snap["os_threads"] = proc.num_threads()
        snap["rss_mb"] = round(proc.memory_info().rss / (1024 * 1024), 2)
        if hasattr(proc, "num_handles"):
            snap["handles"] = proc.num_handles()
        snap["open_files"] = len(proc.open_files())
    except Exception as exc:  # psutil missing or a permission issue
        snap["psutil_error"] = f"{type(exc).__name__}: {exc}"
    return snap


# ---------------------------------------------------------------------------
# Health watcher
# ---------------------------------------------------------------------------


class HealthWatcher(threading.Thread):
    """Polls the production `StreamManager.health()` and records transitions.

    This is the same API `app.py` polls in its main loop, so what it sees is
    what the application would see.
    """

    def __init__(self, manager: StreamManager, camera: str, timeline: Timeline, interval=0.005):
        super().__init__(name="health-watcher", daemon=True)
        self.manager = manager
        self.camera = camera
        self.timeline = timeline
        self.interval = interval
        self.transitions: list[dict] = []
        self._stop = threading.Event()
        self._last: str | None = None

    def poll_once(self) -> str:
        state = self.manager.health()[self.camera]
        if state != self._last:
            self.transitions.append({"t": round(now(), 4), "from": self._last, "to": state})
            self.timeline.mark(
                "health_transition", f"{(self._last or 'init').upper()} -> {state.upper()}"
            )
            self._last = state
        return state

    def run(self) -> None:
        while not self._stop.is_set():
            self.poll_once()
            self._stop.wait(self.interval)

    def stop(self) -> None:
        self._stop.set()
        self.join(timeout=2.0)
        self.poll_once()

    def time_of(self, state: str, after: float = -1.0) -> float | None:
        for entry in self.transitions:
            if entry["to"] == state and entry["t"] > after:
                return entry["t"]
        return None


# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------


class PhaseCounters:
    def __init__(self):
        self.frames = 0
        self.processed = 0
        self.pipeline_failures = 0
        self.first_frame_at: float | None = None
        self.last_frame_at: float | None = None
        # Delivery time of every frame in the phase. The staleness question is
        # not "did any frame arrive after the fault was armed" - the camera is
        # still genuinely delivering until the producer's next read hits the
        # dead handle - but "did any frame arrive after the stream admitted it
        # was RECONNECTING", which is what the queue drain must guarantee.
        self.times: list[float] = []


def run(args) -> int:
    sources = dict(CAMERA_SOURCES)
    name = args.camera or next(iter(sources))
    if name not in sources:
        print(f"BLOCKED: camera {name!r} not in CAMERA_SOURCES ({list(sources)})", file=sys.stderr)
        return 2
    source = sources[name]

    timeline = Timeline()
    metrics = MetricsCollector(window=4096)
    isolator = CameraErrorIsolator()
    preprocessor = Preprocessor(name, brightness_threshold=BRIGHTNESS_THRESHOLD)
    gate = ActivityGate(motion_threshold=MOTION_THRESHOLD)

    camera_holder: dict[str, UnpluggableCameraSource] = {}

    def camera_factory(src, width=640, height=480):
        camera = UnpluggableCameraSource(
            src,
            width,
            height,
            camera_name=name,
            absent_source=args.absent_index,
            timeline=timeline,
        )
        camera_holder["camera"] = camera
        return camera

    # Production defaults govern everything about recovery; only the camera
    # construction is hooked.
    manager = StreamManager(
        {name: source},
        width=CAMERA_WIDTH,
        height=CAMERA_HEIGHT,
        camera_factory=camera_factory,
    )
    stream = manager.streams[name]

    phases = {
        "before_fault": PhaseCounters(),
        "outage": PhaseCounters(),
        "after_recovery": PhaseCounters(),
    }
    resources = [resource_snapshot("before_start")]
    outcome: dict = {"blocked": None, "code": 0}

    def process(frame) -> None:
        """A real slice of the application's per-frame work, run through the
        production error isolator exactly as `app.py` runs its pipeline."""
        with metrics.stage(name, "preprocess"):
            processed = preprocessor.process(frame)
        with metrics.stage(name, "activity_gate"):
            gate.is_active(processed)

    def pump(phase: str, seconds: float, until=None) -> None:
        """Consumes frames the way the application loop does, for `seconds`
        or until `until()` is true."""
        counters = phases[phase]
        deadline = now() + seconds
        while now() < deadline:
            if until is not None and until():
                return
            frame = manager.read_all()[name]
            if frame is None:
                time.sleep(0.002)
                continue
            counters.frames += 1
            if counters.first_frame_at is None:
                counters.first_frame_at = now()
                timeline.mark(f"first_frame_{phase}", f"consumer received frame #1 of '{phase}'")
            counters.last_frame_at = now()
            counters.times.append(counters.last_frame_at)
            if isolator.run(name, process, frame, stage="frame-pipeline"):
                counters.processed += 1
            else:
                counters.pipeline_failures += 1

    timeline.mark("run_start", f"camera {name} -> {redact_source(source)}")
    manager.start_all()
    camera = camera_holder["camera"]
    watcher = HealthWatcher(manager, name, timeline)
    watcher.start()
    try:
        # ---- Phase 1: ONLINE ------------------------------------------
        deadline = now() + args.online_timeout
        while stream.health != CameraHealth.ONLINE and now() < deadline:
            time.sleep(0.01)
        if stream.health != CameraHealth.ONLINE:
            outcome["blocked"] = "camera never reached ONLINE - cannot test recovery"
            return 1
        pump("before_fault", args.online_seconds)
        if phases["before_fault"].frames == 0:
            outcome["blocked"] = "no frames before the fault - nothing to interrupt"
            return 1
        resources.append(resource_snapshot("online_before_fault"))

        # ---- Phase 2: fault -------------------------------------------
        fault_at = timeline.mark(
            "FAULT_INJECTED",
            f"camera marked absent (source -> {args.absent_index}); the live handle "
            "is released on the producer thread",
        )
        camera.unplug()
        pump("outage", args.outage_seconds)
        resources.append(resource_snapshot("during_outage"))
        if watcher.time_of(CameraHealth.RECONNECTING, after=fault_at) is None:
            outcome["blocked"] = (
                "health never left ONLINE after the camera was broken - falsely healthy"
            )
            return 1

        # ---- Phase 3: restore -----------------------------------------
        timeline.mark(
            "CAMERA_RESTORED", f"camera marked present again (source -> {redact_source(source)})"
        )
        camera.replug()
        pump(
            "after_recovery",
            args.recovery_timeout,
            until=lambda: stream.health == CameraHealth.ONLINE
            and phases["after_recovery"].frames > 0,
        )
        if watcher.time_of(CameraHealth.ONLINE, after=fault_at) is None:
            outcome["blocked"] = "camera never returned to ONLINE within the recovery timeout"
            return 1

        # ---- Phase 4: sustained processing after recovery -------------
        pump("after_recovery", args.post_seconds)
        resources.append(resource_snapshot("after_recovery"))
        return 0
    finally:
        watcher.stop()
        timeline.mark("shutdown_start", "manager.stop_all()")
        stop_started = time.perf_counter()
        manager.stop_all()
        stop_seconds = time.perf_counter() - stop_started
        timeline.mark("shutdown_done", f"stop_all() returned in {stop_seconds:.3f}s")
        time.sleep(0.2)  # let a joined thread be reaped before counting
        resources.append(resource_snapshot("after_shutdown"))
        report(
            args, name, source, stream, camera, watcher, timeline, phases, resources,
            metrics, isolator, outcome, stop_seconds,
        )


def report(args, name, source, stream, camera, watcher, timeline, phases, resources,
           metrics, isolator, outcome, stop_seconds) -> None:
    fault = timeline.first("FAULT_INJECTED")
    restored = timeline.first("CAMERA_RESTORED")
    first_bad_read = timeline.first("first_failed_device_read")
    fault_at = fault["t"] if fault else None
    restore_at = restored["t"] if restored else None
    reconnecting_at = watcher.time_of(CameraHealth.RECONNECTING, after=fault_at or -1.0)
    online_again_at = watcher.time_of(CameraHealth.ONLINE, after=fault_at or -1.0)
    after = phases["after_recovery"]

    def delta(a, b):
        return round(b - a, 3) if (a is not None and b is not None) else None

    # Frames the consumer got while the stream was admitting it was down. Any
    # of these would be a stale scene presented as a live view.
    stale_frames = (
        [t for t in phases["outage"].times if reconnecting_at is not None and t > reconnecting_at]
        if reconnecting_at is not None
        else []
    )
    # Frames delivered between arming the fault and the stream detecting it:
    # the camera really was still working then, so these are live, not stale.
    live_frames_before_detection = [
        t for t in phases["outage"].times if reconnecting_at is None or t <= reconnecting_at
    ]

    threads = {snap["label"]: snap for snap in resources}
    result = {
        "camera": name,
        "source": redact_source(source),
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "opencv": cv2.__version__,
        },
        "fault_injection": {
            "method": "live cv2.VideoCapture released on the producer thread, "
                      "source pointed at an absent device index",
            "absent_index": args.absent_index,
            "production_code_modified": False,
        },
        "settings": {
            "reconnect_initial_delay": stream.reconnect_initial_delay,
            "reconnect_max_delay": stream.reconnect_max_delay,
            "max_read_failures": stream.max_read_failures,
            "max_reconnect_attempts": stream.max_reconnect_attempts,
        },
        "health_transitions": watcher.transitions,
        "timings_s": {
            "fault_injected_at": fault_at,
            "first_failed_device_read_at": first_bad_read["t"] if first_bad_read else None,
            "reconnecting_at": reconnecting_at,
            "camera_restored_at": restore_at,
            "online_again_at": online_again_at,
            "detection_latency": delta(fault_at, reconnecting_at),
            "failure_to_recovery": delta(fault_at, online_again_at),
            "restore_to_online": delta(restore_at, online_again_at),
            "restore_to_first_frame": delta(restore_at, after.first_frame_at),
        },
        "reconnect": {
            "reconnect_count": stream.reconnect_count,
            "reopen_attempts_total": camera.stats["open_attempts"],
            "reopen_attempts_after_fault": camera.stats["open_attempts"] - 1,
            "reopen_failures": camera.stats["open_failures"],
            "reopen_successes": camera.stats["open_successes"],
            "capture_releases": camera.stats["release_calls"],
            "device_handle_invalidations": camera.stats["handle_invalidations"],
            "device_reads_ok": camera.stats["read_ok"],
            "device_reads_failed": camera.stats["read_none"],
        },
        "frames": {
            phase: {
                "delivered_to_consumer": counters.frames,
                "processed_ok": counters.processed,
                "pipeline_failures": counters.pipeline_failures,
                "first_frame_at": counters.first_frame_at,
                "last_frame_at": counters.last_frame_at,
            }
            for phase, counters in phases.items()
        },
        "staleness": {
            "frames_after_reconnecting_declared": len(stale_frames),
            "live_frames_between_fault_and_detection": len(live_frames_before_detection),
            "last_live_frame_at": (
                round(live_frames_before_detection[-1], 4) if live_frames_before_detection else None
            ),
        },
        "processing_resumed": bool(after.processed > 0),
        "resources": resources,
        "shutdown": {
            "stop_all_seconds": round(stop_seconds, 3),
            "producer_thread_alive": bool(stream._thread and stream._thread.is_alive()),
            "final_health": stream.health,
            "camera_threads_after_shutdown": threads["after_shutdown"]["camera_threads"],
        },
        "isolator": {
            "processing_failures": isolator.failure_count(name),
            "logging_failures": isolator.logging_failures,
        },
        "metrics": metrics.snapshot(),
        "blocked_reason": outcome["blocked"],
    }

    checks = {
        "went_online_before_fault": any(
            entry["to"] == CameraHealth.ONLINE and (fault_at is None or entry["t"] < fault_at)
            for entry in watcher.transitions
        ),
        "frames_before_fault": phases["before_fault"].frames > 0,
        "failure_detected": camera.stats["read_none"] > 0,
        "health_left_online_truthfully": reconnecting_at is not None,
        "no_stale_frames_while_reconnecting": not stale_frames,
        "reopen_attempted": camera.stats["open_attempts"] > 1,
        "reopen_failed_while_absent": camera.stats["open_failures"] > 0,
        "reconnect_count_incremented": stream.reconnect_count > 0,
        "returned_to_online": online_again_at is not None,
        "frames_resumed": after.frames > 0,
        "processing_resumed": after.processed > 0,
        "no_thread_leak": (
            threads["after_recovery"]["camera_threads"]
            == threads["online_before_fault"]["camera_threads"]
            if "after_recovery" in threads and "online_before_fault" in threads
            else False
        ),
        "clean_shutdown": (
            not (stream._thread and stream._thread.is_alive())
            and stream.health == CameraHealth.OFFLINE
            and not threads["after_shutdown"]["camera_threads"]
        ),
    }
    result["checks"] = checks
    result["verdict"] = "VERIFIED" if all(checks.values()) and not outcome["blocked"] else "BLOCKED"

    print()
    print("=" * 78)
    print(f"  IBVAP Phase 1 - REAL CAMERA FAULT INJECTION / RECOVERY  [{name}]")
    print("=" * 78)
    print(f"  source                  : {redact_source(source)}")
    print(f"  fault method            : {result['fault_injection']['method']}")
    print("  production code changed : no")
    print()
    print("  HEALTH TRANSITIONS")
    for entry in watcher.transitions:
        label = (entry["from"] or "init").upper()
        print(f"    t={entry['t']:8.3f}s  {label:>12} -> {entry['to'].upper()}")
    print()
    print("  TIMELINE")
    for entry in timeline.snapshot():
        if entry["kind"] == "health_transition":
            continue
        print(f"    t={entry['t']:8.3f}s  {entry['kind']:<28} {entry['detail']}")
    print()
    print("  RECOVERY")
    timings = result["timings_s"]
    for key in (
        "detection_latency",
        "failure_to_recovery",
        "restore_to_online",
        "restore_to_first_frame",
    ):
        value = timings[key]
        print(f"    {key:<28}: {'n/a' if value is None else f'{value:.3f}s'}")
    for key, value in result["reconnect"].items():
        print(f"    {key:<28}: {value}")
    print()
    print("  FRAMES")
    for phase, data in result["frames"].items():
        print(
            f"    {phase:<16}: delivered={data['delivered_to_consumer']:<6} "
            f"processed={data['processed_ok']:<6} failures={data['pipeline_failures']}"
        )
    stale = result["staleness"]
    print(
        f"    {'staleness':<16}: live frames between fault and detection="
        f"{stale['live_frames_between_fault_and_detection']} (last at "
        f"{stale['last_live_frame_at']}s), frames served while RECONNECTING="
        f"{stale['frames_after_reconnecting_declared']}"
    )
    print()
    print("  RESOURCES")
    for snap in resources:
        print(
            f"    {snap['label']:<20} threads(py)={snap['python_threads']:<3} "
            f"os={snap.get('os_threads', '?'):<3} handles={snap.get('handles', '?'):<5} "
            f"rss={snap.get('rss_mb', '?')}MB camera_threads={snap['camera_threads']}"
        )
    print()
    print("  SHUTDOWN")
    for key, value in result["shutdown"].items():
        print(f"    {key:<34}: {value}")
    print()
    print("  CHECKS")
    for key, value in checks.items():
        print(f"    [{'PASS' if value else 'FAIL'}] {key}")
    print()
    print(f"  VERDICT: {result['verdict']}")
    if outcome["blocked"]:
        print(f"  BLOCKED: {outcome['blocked']}")
    print("=" * 78)

    if args.json:
        directory = os.path.dirname(os.path.abspath(args.json))
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2, default=str)
        print(f"  JSON written to {args.json}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="IBVAP Phase 1 real-camera fault-injection recovery test"
    )
    parser.add_argument("--camera", default=None, help="CAMERA_SOURCES name (default: the first)")
    parser.add_argument("--online-seconds", type=float, default=6.0)
    parser.add_argument("--outage-seconds", type=float, default=8.0)
    parser.add_argument("--post-seconds", type=float, default=6.0)
    parser.add_argument("--online-timeout", type=float, default=20.0)
    parser.add_argument("--recovery-timeout", type=float, default=60.0)
    parser.add_argument(
        "--absent-index",
        type=int,
        default=900,
        help="device index used while the camera is 'unplugged' (must not exist)",
    )
    parser.add_argument("--json", default=None)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        stream=sys.stdout,
    )
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())

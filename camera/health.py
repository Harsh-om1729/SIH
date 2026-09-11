"""Camera reliability primitives shared by the capture layer (`camera/`) and
the application loop (`app.py`).

Two pieces, both about keeping one camera's problems contained:

- `CameraHealth` — the state a stream is in, so the rest of the application
  can tell a live feed apart from one that is mid-recovery or given up on.
- `CameraErrorIsolator` — a per-camera boundary for *processing* errors, so an
  exception while handling one camera's frame drops that frame instead of
  taking the whole surveillance loop (and every other camera) down with it.
"""

import logging
import threading
import time
import traceback

log = logging.getLogger("ibvap.camera.health")


class CameraHealth:
    """Health states a camera stream can be in.

    ONLINE       — capture is open and delivering frames.
    RECONNECTING — capture is broken; the producer is retrying with backoff.
    OFFLINE      — not running: never started, deliberately stopped, or the
                   reconnect budget was exhausted.
    """

    ONLINE = "online"
    RECONNECTING = "reconnecting"
    OFFLINE = "offline"


class CameraErrorIsolator:
    """Runs one camera's per-frame processing behind a failure boundary.

    An exception raised while processing a frame is caught here, recorded, and
    logged with the camera identifier, the exception type and a full
    traceback; the offending frame is dropped and the caller carries on with
    the next camera. Errors are never silently swallowed.

    To keep a camera that fails on *every* frame from flooding the log, the
    first `log_burst` occurrences of a given (camera, exception type) are
    logged in full, and after that they are throttled to one summary line
    every `summary_interval` seconds carrying the suppressed count — the
    failure stays visible, the log stays readable.

    `KeyboardInterrupt`/`SystemExit` are deliberately *not* caught (they are
    not `Exception` subclasses), so Ctrl-C and shutdown still work normally.
    """

    def __init__(
        self,
        log_burst: int = 3,
        summary_interval: float = 60.0,
        now_fn=time.monotonic,
        logger: logging.Logger | None = None,
    ):
        self.log_burst = log_burst
        self.summary_interval = summary_interval
        self._now = now_fn
        self._log = logger if logger is not None else log
        self._lock = threading.Lock()
        # (camera_name, exception type name) -> throttling counters
        self._signatures: dict[tuple[str, str], dict] = {}
        self.total_errors: dict[str, int] = {}
        self.consecutive_errors: dict[str, int] = {}
        # Incremented if the logging call itself blew up (see _emit).
        self.logging_failures: int = 0

    def run(self, camera_name: str, fn, *args, stage: str | None = None, **kwargs) -> bool:
        """Calls `fn(*args, **kwargs)` for `camera_name`.

        Returns True if it completed, False if it raised (in which case the
        frame is considered dropped and the error has been recorded).
        """
        try:
            fn(*args, **kwargs)
        except Exception as exc:  # deliberate per-camera failure boundary
            self._record(camera_name, exc, stage)
            return False
        self.consecutive_errors[camera_name] = 0
        return True

    def failure_count(self, camera_name: str) -> int:
        """Total processing failures recorded for this camera."""
        return self.total_errors.get(camera_name, 0)

    def is_degraded(self, camera_name: str, threshold: int = 1) -> bool:
        """True while this camera has failed `threshold` frames in a row."""
        return self.consecutive_errors.get(camera_name, 0) >= threshold

    def _record(self, camera_name: str, exc: Exception, stage: str | None) -> None:
        now = self._now()
        signature = (camera_name, type(exc).__name__)

        # The lock covers only the counter bookkeeping — never the logging I/O
        # below it, which can block on a slow handler.
        with self._lock:
            total = self.total_errors.get(camera_name, 0) + 1
            self.total_errors[camera_name] = total
            consecutive = self.consecutive_errors.get(camera_name, 0) + 1
            self.consecutive_errors[camera_name] = consecutive

            state = self._signatures.setdefault(
                signature, {"count": 0, "suppressed": 0, "last_log": None}
            )
            state["count"] += 1
            suppressed = 0
            if state["count"] <= self.log_burst:
                decision = "full"
                state["last_log"] = now
            elif state["last_log"] is None or (now - state["last_log"]) >= self.summary_interval:
                decision = "summary"
                suppressed = state["suppressed"]
                state["suppressed"] = 0
                state["last_log"] = now
            else:
                decision = "suppress"
                state["suppressed"] += 1

        if decision != "suppress":
            self._emit(decision, camera_name, exc, stage, consecutive, total, suppressed)

    def _emit(
        self,
        decision: str,
        camera_name: str,
        exc: Exception,
        stage: str | None,
        consecutive: int,
        total: int,
        suppressed: int,
    ) -> None:
        where = f" stage={stage}" if stage else ""
        try:
            if decision == "full":
                trace = "".join(
                    traceback.format_exception(type(exc), exc, exc.__traceback__)
                ).rstrip()
                self._log.error(
                    "[%s] camera processing failed%s (%s: %s) — frame dropped, other "
                    "cameras unaffected [consecutive=%d total=%d]\n%s",
                    camera_name, where, type(exc).__name__, exc, consecutive, total, trace,
                )
            else:
                self._log.error(
                    "[%s] camera processing still failing%s (%s: %s) — %d further "
                    "identical failure(s) suppressed since the last report "
                    "[consecutive=%d total=%d]",
                    camera_name, where, type(exc).__name__, exc, suppressed, consecutive, total,
                )
        except Exception:
            # A broken log handler (full disk, dead syslog socket) must not be
            # what takes surveillance down. Not silent: the count is exposed on
            # the isolator so a caller/monitor can see logging itself is failing.
            self.logging_failures += 1

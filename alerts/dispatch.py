"""Background dispatch for slow alert side effects (Phase 0B, item 1).

An alert's *decision* (tier, escalation, cooldown) is cheap and stays on the
frame-processing path. Its *side effects* are not: a webhook POST waits on a
remote C2/SIEM host (up to `WebhookNotifier.timeout`, 3s by default), and
recording evidence JPEG-encodes and Fernet-encrypts several frames to disk.
Doing either inline stalls the camera loop for every camera.

`AlertDispatcher` runs those side effects on one small background worker fed
by a bounded queue, so the frame path only ever pays an enqueue.

Deliberate properties:

- **Bounded.** The queue has a fixed `maxsize`; it cannot grow into memory
  pressure no matter how fast alerts arrive.
- **Never silently lossy.** A full queue is a *loud* drop: logged at ERROR
  with the job name and counted in `dropped`, which is readable at any time.
  Nothing is discarded without a record.
- **Ordered.** A single worker means webhook/evidence side effects still run
  in the order the alerts fired.
- **Isolated.** A job that raises is logged with a traceback and counted in
  `failed`; the worker survives and keeps draining. A dispatch failure can
  never propagate into camera processing.
- **Flushes on shutdown.** `stop()` waits (briefly, bounded) for queued work
  so a clean exit doesn't throw away pending evidence.
"""

import logging
import queue
import threading

log = logging.getLogger("ibvap.alerts.dispatch")


class AlertDispatcher:
    """Runs `(name, fn, args, kwargs)` jobs on one bounded background worker."""

    def __init__(
        self,
        maxsize: int = 64,
        stop_timeout: float = 5.0,
        name: str = "alert-dispatch",
        poll_interval: float = 0.05,
    ):
        if maxsize < 1:
            raise ValueError("maxsize must be at least 1")
        self.maxsize = maxsize
        self.stop_timeout = stop_timeout
        self._poll_interval = poll_interval
        self._queue: queue.Queue = queue.Queue(maxsize=maxsize)
        self._stopping = threading.Event()
        self._lock = threading.Lock()
        # Observability counters — read these to tell a healthy dispatcher
        # from one that is dropping or failing work.
        self.submitted = 0
        self.completed = 0
        self.dropped = 0
        self.failed = 0
        self._thread = threading.Thread(target=self._run, name=name, daemon=True)
        self._thread.start()

    def submit(self, job_name: str, fn, *args, **kwargs) -> bool:
        """Queues `fn(*args, **kwargs)`. Returns True if accepted.

        Never blocks the caller and never raises: the frame-processing path
        must not wait on, or be broken by, alert delivery. A rejected job is
        logged at ERROR and counted — it is dropped loudly, not silently.
        """
        if self._stopping.is_set():
            with self._lock:
                self.dropped += 1
            log.error(
                "Alert dispatch is shutting down - dropped %r (total dropped=%d)",
                job_name, self.dropped,
            )
            return False
        try:
            self._queue.put_nowait((job_name, fn, args, kwargs))
        except queue.Full:
            with self._lock:
                self.dropped += 1
            log.error(
                "Alert dispatch queue full (maxsize=%d) - dropped %r. The alert was "
                "still raised and logged; only this side effect was lost. "
                "[dropped=%d submitted=%d]",
                self.maxsize, job_name, self.dropped, self.submitted,
            )
            return False
        with self._lock:
            self.submitted += 1
        return True

    def _run(self) -> None:
        while True:
            try:
                item = self._queue.get(timeout=self._poll_interval)
            except queue.Empty:
                # Only exit once stopping *and* nothing is left, so shutdown
                # flushes queued evidence rather than discarding it.
                if self._stopping.is_set():
                    return
                continue
            try:
                self._execute(*item)
            finally:
                self._queue.task_done()

    def _execute(self, job_name: str, fn, args, kwargs) -> None:
        try:
            fn(*args, **kwargs)
        except Exception:
            # Per-job failure boundary: one bad webhook or unwritable evidence
            # path must not kill the worker or reach camera processing. Logged
            # with a traceback and counted, never swallowed silently.
            with self._lock:
                self.failed += 1
            log.exception(
                "Alert dispatch job %r failed [failed=%d] - worker continuing", job_name, self.failed
            )
        else:
            with self._lock:
                self.completed += 1

    def pending(self) -> int:
        return self._queue.qsize()

    def stats(self) -> dict:
        with self._lock:
            return {
                "submitted": self.submitted,
                "completed": self.completed,
                "dropped": self.dropped,
                "failed": self.failed,
                "pending": self._queue.qsize(),
            }

    def stop(self, timeout: "float | None" = None) -> bool:
        """Stops accepting work, drains what is queued, and joins the worker.

        Returns True if the worker finished within the timeout. Bounded on
        purpose: a wedged webhook must not hang application shutdown.
        """
        self._stopping.set()
        if not self._thread.is_alive():
            return True
        timeout = self.stop_timeout if timeout is None else timeout
        self._thread.join(timeout=timeout)
        if self._thread.is_alive():
            log.warning(
                "Alert dispatch worker still running after %.1fs (likely blocked in a "
                "webhook or disk write); it is a daemon thread and will not outlive "
                "the process. %d job(s) still queued.",
                timeout, self._queue.qsize(),
            )
            return False
        stats = self.stats()
        log.info("Alert dispatch stopped - %s", stats)
        return True

"""Optional intelligence capabilities and their availability state.

Core perception - detection, tracking, zones, scoring, alerting - is
mandatory. Face recognition, Re-ID and watchlist matching are optional
enrichment: valuable when their locally provisioned weights are present, but
never a reason for the pipeline to refuse to start.

Two rules drive this module:

- **No startup downloads.** IBVAP is specified to run air-gapped, and both
  InsightFace and torchvision fetch weights over HTTPS when their local cache
  is cold. Every optional capability is therefore gated behind an explicit
  local-availability precheck that runs *before* the library is constructed,
  so the network is never reached at all - rather than letting a download be
  attempted and catching the failure afterwards.
- **Nothing fails silently.** An unavailable or degraded capability is logged
  with its reason and exposed through `states()`, so the periodic metrics
  line keeps reporting it for as long as the process runs.

A capability that is missing yields `None` from `load()`. Call sites check
for `None` rather than receiving a stub, so a disabled capability is visible
in the pipeline code instead of silently doing nothing.
"""

import logging

log = logging.getLogger("ibvap.capabilities")

AVAILABLE = "available"
UNAVAILABLE = "unavailable"
DEGRADED = "degraded"


class CapabilityRegistry:
    """Tracks which optional capabilities loaded, and which are failing.

    `log_every` rate-limits repeated runtime-failure logging: the first
    failure of a capability is logged with a traceback, then every Nth after
    that. A per-frame failure at 15 FPS would otherwise flood the log, but
    every failure is still counted and still reflected in `states()`, so
    rate-limiting the log is not the same as swallowing the error.
    """

    def __init__(self, log_every: int = 100):
        if log_every < 1:
            raise ValueError("log_every must be at least 1")
        self.log_every = log_every
        self._states: dict[str, dict] = {}
        self._failures: dict[str, int] = {}

    def _mark(self, name: str, state: str, detail: str) -> None:
        self._states[name] = {"state": state, "detail": detail}

    def load(self, name: str, factory, *, precheck=None):
        """Constructs an optional capability, or returns None with a reason.

        `precheck` is a zero-argument callable returning `(ok, reason)`. It
        must decide from local filesystem state only - it exists precisely so
        that `factory` is never invoked when that would trigger a download.
        """
        if precheck is not None:
            ok, reason = precheck()
            if not ok:
                self._mark(name, UNAVAILABLE, reason)
                log.warning(
                    "Optional capability '%s' UNAVAILABLE: %s. "
                    "Core perception continues without it; no download attempted.",
                    name, reason,
                )
                return None

        try:
            instance = factory()
        except Exception as exc:
            reason = f"{type(exc).__name__}: {exc}"
            self._mark(name, UNAVAILABLE, reason)
            log.warning(
                "Optional capability '%s' failed to initialise (%s). "
                "Core perception continues without it.",
                name, reason, exc_info=True,
            )
            return None

        self._mark(name, AVAILABLE, "initialised")
        log.info("Optional capability '%s' AVAILABLE", name)
        return instance

    def call(self, name: str, fn, *args, default=None):
        """Invokes an optional capability, containing a failure to itself.

        A raising optional model marks that capability DEGRADED and returns
        `default`, so the frame keeps its detections, tracks, zones, scores
        and alerts instead of being dropped. Core-pipeline exceptions are not
        routed through here - those still reach the Phase 0A camera isolator.
        """
        try:
            return fn(*args)
        except Exception as exc:
            self.record_failure(name, exc)
            return default

    def record_failure(self, name: str, exc: BaseException) -> None:
        count = self._failures.get(name, 0) + 1
        self._failures[name] = count
        self._mark(name, DEGRADED, f"{type(exc).__name__}: {exc} (failures={count})")
        if count == 1:
            log.warning(
                "Optional capability '%s' failed at runtime; marking DEGRADED. "
                "Core detection/tracking continues.",
                name, exc_info=exc,
            )
        elif count % self.log_every == 0:
            log.warning(
                "Optional capability '%s' has now failed %d times; latest %s: %s",
                name, count, type(exc).__name__, exc,
            )

    def states(self) -> dict:
        """Capability -> {"state": ..., "detail": ...}, for logs and metrics."""
        return {name: dict(entry) for name, entry in self._states.items()}

    def summary(self) -> dict:
        """Compact capability -> state mapping for the periodic metrics line."""
        return {name: entry["state"] for name, entry in sorted(self._states.items())}

    def failures(self) -> dict:
        return dict(self._failures)

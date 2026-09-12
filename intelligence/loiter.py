import time
from typing import Callable, Hashable


class LoiterTracker:
    """Tracks how long each person has been continuously inside a zone.

    Standing at the fence is reconnaissance, and it is invisible to every
    other rule in the system: a stationary subject has no speed, no crossing
    direction, and the same sector/time/class risk as someone passing through.
    Dwell time is the only signal that separates "walked past the line" from
    "has been watching the line for four minutes".

    Keyed on the Re-ID `person_id` rather than the raw track_id, so the clock
    survives ByteTrack losing and re-acquiring the same person — which is
    exactly what happens when someone stands still behind a bush and the
    detector drops them for a few frames. A short `grace_seconds` bridges
    those gaps instead of resetting the timer to zero on every blink.
    """

    def __init__(
        self,
        grace_seconds: float = 5.0,
        now_fn: Callable[[], float] = time.time,
    ):
        self.grace_seconds = grace_seconds
        self._now = now_fn
        # key -> {"since": float, "last_seen": float, "zone_tier": str}
        self._dwell: dict[Hashable, dict] = {}

    def update(self, key: Hashable, zone_tier: "str | None") -> float:
        """Records that `key` was seen in `zone_tier` now; returns the dwell
        time in seconds. Leaving the zone (or changing tier) restarts it."""
        now = self._now()
        self._expire(now)

        if not zone_tier or zone_tier == "none":
            self._dwell.pop(key, None)
            return 0.0

        entry = self._dwell.get(key)
        if entry is None or entry["zone_tier"] != zone_tier:
            # Entering a zone, or moving between zones of different tiers —
            # either way the dwell clock for *this* zone starts now.
            self._dwell[key] = {"since": now, "last_seen": now, "zone_tier": zone_tier}
            return 0.0

        entry["last_seen"] = now
        return now - entry["since"]

    def forget(self, key: Hashable) -> None:
        self._dwell.pop(key, None)

    def _expire(self, now: float) -> None:
        stale = [
            k for k, e in self._dwell.items()
            if now - e["last_seen"] > self.grace_seconds
        ]
        for k in stale:
            del self._dwell[k]

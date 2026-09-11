import logging
import os
import time
from collections import deque

import cv2
import numpy as np

log = logging.getLogger("ibvap.alerts")

try:
    import pygame

    pygame.mixer.init()
    _AUDIO_AVAILABLE = True
except Exception as e:
    _AUDIO_AVAILABLE = False
    log.warning("Audio unavailable (%s) — alerts will be visual/log-only", e)


def _synth_tone(frequency: float, duration: float, volume: float = 0.4, sample_rate: int = 44100):
    """Synthesizes a short sine-wave tone in memory — no external audio file
    needed, matching the zero-cost build (pygame.mixer per the roadmap's stack)."""
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    wave = np.sin(2 * np.pi * frequency * t) * volume
    stereo = np.column_stack([wave, wave])
    audio = (stereo * 32767).astype(np.int16)
    return pygame.sndarray.make_sound(np.ascontiguousarray(audio))


class AlertManager:
    """Reacts per threat tier, per the roadmap:
    - Green: silent log only.
    - Yellow: on-screen highlight (drawn upstream) + soft chime + a snapshot.
    - Red: siren + a snapshot burst (several recent frames, not the same
      frame repeated) + a logged stand-in for optional VHF/LoRa radio
      metadata (no real radio hardware in this zero-cost build).

    Rate-limited per track, in three layers (Phase 18 — alert discipline):

    1. N-of-M confirmation. A tier must be observed `confirm_n` times in the
       last `confirm_window` scoring cycles before it is *confirmed*. A single
       borderline frame — a face similarity landing on 0.50, one noisy speed
       estimate — can no longer start an incident.
    2. Hysteresis on the way down. A confirmed tier is only released once the
       whole window sits below it. Without this, a score oscillating around a
       threshold kept de-escalating and re-escalating, and since an escalation
       bypasses the cooldown by design, every oscillation bought a free siren:
       the observed failure was nine Red alerts for one stationary person in
       52 seconds, two of them 1-2s apart.
    3. Backoff on repeats. A track that stays at the same confirmed tier
       re-alerts after `cooldown_seconds`, then twice that, then twice again,
       capped at `max_cooldown_seconds` — so a genuine sustained presence is
       reported promptly and then stops shouting.

    An escalation to a *newly confirmed* higher tier still alerts immediately;
    that is the point of confirming it.
    """

    TIER_RANK = {"green": 0, "yellow": 1, "red": 2}

    def __init__(
        self,
        snapshot_dir: str = "snapshots",
        cooldown_seconds: float = 8.0,
        now_fn=time.time,
        incident_store=None,
        webhook=None,
        syslog=None,
        confirm_n: int = 2,
        confirm_window: int = 3,
        max_cooldown_seconds: float = 64.0,
    ):
        if confirm_n > confirm_window:
            raise ValueError(
                f"confirm_n ({confirm_n}) cannot exceed confirm_window ({confirm_window}) "
                "— no tier would ever confirm and the system would go silent"
            )
        self.snapshot_dir = snapshot_dir
        self.cooldown_seconds = cooldown_seconds
        self.confirm_n = confirm_n
        self.confirm_window = confirm_window
        self.max_cooldown_seconds = max_cooldown_seconds
        self._now = now_fn
        self.incident_store = incident_store
        self.webhook = webhook
        self.syslog = syslog
        os.makedirs(snapshot_dir, exist_ok=True)
        self._last_tier: dict = {}
        self._last_alert_time: dict = {}
        self._history: dict = {}
        self._repeats: dict = {}

        self._yellow_chime = _synth_tone(880, 0.15, volume=0.25) if _AUDIO_AVAILABLE else None
        self._red_siren = _synth_tone(1200, 0.4, volume=0.5) if _AUDIO_AVAILABLE else None

    def handle(self, det, score, recent_frames: list) -> None:
        track_key = det.person_id if det.person_id is not None else det.track_id
        if track_key is None:
            return
        # Two different id namespaces reach this point: a Re-ID person_id, and
        # a raw track_id for a detection whose identity hasn't resolved yet
        # (still buffering samples, or box too small to embed). Printing both
        # as "person #N" made a track_id look like a person_id in the log —
        # e.g. "person #247" in a run that only ever issued 20 person_ids.
        # Label them the way the video overlay already does: #N vs TN.
        label = (
            f"#{det.person_id}" if det.person_id is not None else f"T{det.track_id}"
        )
        prev_tier = self._last_tier.get(track_key, "green")
        tier = self._confirmed_tier(track_key, score.tier)

        if tier == "green":
            log.debug(
                "Green: %s %s score=%.0f (observed %s)",
                det.category(), label, score.total, score.tier,
            )
            return

        now = self._now()
        escalated = self.TIER_RANK.get(tier, 0) > self.TIER_RANK.get(prev_tier, 0)
        if escalated:
            # A newly confirmed higher tier resets the backoff: this is a
            # different event from the one already being reported.
            self._repeats[track_key] = 0
        cooled_down = (
            now - self._last_alert_time.get(track_key, 0) >= self._effective_cooldown(track_key)
        )

        if not (escalated or cooled_down):
            return
        if not escalated:
            self._repeats[track_key] = self._repeats.get(track_key, 0) + 1

        self._last_alert_time[track_key] = now
        self._notify_integrations(det, score, track_key, now)

        if tier == "yellow":
            log.info(
                "YELLOW ALERT: %s %s score=%.0f [%s] — chime + snapshot",
                det.category(), label, score.total, score.breakdown(),
            )
            self._play(self._yellow_chime)
            self._record_evidence(det, score, recent_frames[-1:])
        elif tier == "red":
            # The breakdown is the whole point of an additive score: a sentry
            # needs to see which component drove a Red, and whether an override
            # forced it, not just the number.
            log.warning(
                "RED ALERT: %s %s score=%.0f [%s] — siren + snapshot burst",
                det.category(), label, score.total, score.breakdown(),
            )
            log.warning(
                "  [radio-metadata stub] zone=%s tier=%s score=%.0f ts=%.0f "
                "(no VHF/LoRa hardware in this build)",
                det.zone_tier, tier, score.total, now,
            )
            self._play(self._red_siren)
            self._record_evidence(det, score, recent_frames)

    def _confirmed_tier(self, track_key, observed_tier: str) -> str:
        """N-of-M confirmation on the way up, full-window hysteresis on the way
        down. Returns the tier the alerting logic should act on, which is not
        necessarily the tier this single frame scored."""
        history = self._history.setdefault(
            track_key, deque(maxlen=self.confirm_window)
        )
        history.append(observed_tier)
        confirmed = self._last_tier.get(track_key, "green")

        # Up: any tier above the confirmed one that has reached N observations
        # in the window. Highest such tier wins, so a burst of Red is not
        # masked by the Yellows around it.
        for candidate in ("red", "yellow"):
            if self.TIER_RANK[candidate] <= self.TIER_RANK[confirmed]:
                break
            if history.count(candidate) >= self.confirm_n:
                self._last_tier[track_key] = candidate
                return candidate

        # Down: only once the window is full *and* every observation in it sits
        # below the confirmed tier. A lone sub-threshold frame no longer drops
        # the tier — which is what previously let the next frame re-escalate
        # and bypass the cooldown.
        if len(history) == self.confirm_window and all(
            self.TIER_RANK[t] < self.TIER_RANK[confirmed] for t in history
        ):
            released = max(history, key=lambda t: self.TIER_RANK[t])
            self._last_tier[track_key] = released
            return released

        self._last_tier[track_key] = confirmed
        return confirmed

    def _effective_cooldown(self, track_key) -> float:
        """Exponential backoff for a track parked at the same confirmed tier."""
        repeats = self._repeats.get(track_key, 0)
        return min(self.cooldown_seconds * (2 ** repeats), self.max_cooldown_seconds)

    def forget(self, track_key) -> None:
        """Drops all per-track state. Callers that retire tracks should use it;
        without it these dicts grow for the life of the process (Phase 20)."""
        for state in (self._last_tier, self._last_alert_time, self._history, self._repeats):
            state.pop(track_key, None)

    def _play(self, sound) -> None:
        if sound is not None:
            sound.play()

    def _notify_integrations(self, det, score, track_key, now: float) -> None:
        """Phase 16: outbound webhook (JSON POST) + syslog-formatted event,
        so this platform can feed whatever C2/SIEM system a deploying force
        already runs, without it needing to know this platform's internals.
        """
        payload = {
            "track_id": det.track_id,
            "person_id": det.person_id,
            "category": det.category(),
            "zone_tier": det.zone_tier,
            "tier": score.tier,
            "score": score.total,
            "timestamp": now,
        }
        if self.webhook is not None:
            self.webhook.notify(payload)
        if self.syslog is not None:
            self.syslog.emit(
                f"ALERT tier={score.tier} category={det.category()} "
                f"score={score.total:.0f} track={track_key} zone={det.zone_tier}"
            )

    def _record_evidence(self, det, score, frames: list) -> None:
        """Delegates to the encrypted, queryable IncidentStore (Phase 12) when
        one is wired in; otherwise falls back to plain unencrypted snapshot
        files (e.g. when running without persistence, as in unit tests)."""
        if self.incident_store is not None:
            crop = self._crop(frames[-1], det.box)
            self.incident_store.record(
                det, score, frames[-1], crop_frame=crop, burst_frames=frames[:-1] or None
            )
        else:
            track_key = det.person_id if det.person_id is not None else det.track_id
            self._save_snapshot(frames, score.tier, det, track_key)

    @staticmethod
    def _crop(frame, box):
        x1, y1, x2, y2 = box
        x1, y1 = max(x1, 0), max(y1, 0)
        return frame[y1:y2, x1:x2]

    def _save_snapshot(self, frames: list, tier: str, det, track_key) -> None:
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        saved = 0
        for i, frame in enumerate(frames):
            path = os.path.join(
                self.snapshot_dir, f"{tier}_{det.category()}_{track_key}_{timestamp}_{i}.jpg"
            )
            if cv2.imwrite(path, frame):
                saved += 1
        log.info("Saved %d snapshot(s) to %s/", saved, self.snapshot_dir)

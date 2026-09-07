import logging
import os
import time

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

    Rate-limited per track: an escalation (tier increasing) always alerts
    immediately; otherwise a track only re-alerts after `cooldown_seconds`,
    so a siren/snapshot doesn't spam every frame while someone lingers.
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
        state_ttl_seconds: float = 300.0,
        dispatcher=None,
    ):
        self.snapshot_dir = snapshot_dir
        self.cooldown_seconds = cooldown_seconds
        self._now = now_fn
        self.incident_store = incident_store
        self.webhook = webhook
        self.syslog = syslog
        # Optional `AlertDispatcher` (alerts/dispatch.py). When set, the slow
        # side effects — webhook POST, syslog emit, evidence persistence — are
        # handed to its background worker instead of running on the frame
        # path. Tier/escalation/cooldown decisions stay synchronous either
        # way, so alert semantics are identical; only *when* the I/O happens
        # changes. Left None (the default) everything runs inline exactly as
        # before, which is what the unit tests rely on.
        self.dispatcher = dispatcher
        os.makedirs(snapshot_dir, exist_ok=True)
        # Per-track alert state is keyed by an identity that churns (ByteTrack
        # mints a new id on every re-acquisition), so keeping it forever means
        # growing forever. The TTL is floored at the cooldown deliberately:
        # evicting a track whose cooldown is still running would let it alert
        # again immediately, so this floor guarantees eviction can never change
        # rate-limiting behaviour for a track that is still being tracked.
        self.state_ttl_seconds = max(state_ttl_seconds, cooldown_seconds)
        self._last_tier: dict = {}
        self._last_alert_time: dict = {}
        self._last_seen: dict = {}
        self._last_purge: float = self._now()

        self._yellow_chime = _synth_tone(880, 0.15, volume=0.25) if _AUDIO_AVAILABLE else None
        self._red_siren = _synth_tone(1200, 0.4, volume=0.5) if _AUDIO_AVAILABLE else None

    def handle(self, det, score, recent_frames: list) -> None:
        track_key = det.person_id if det.person_id is not None else det.track_id
        if track_key is None:
            return
        tier = score.tier
        now = self._now()
        self._last_seen[track_key] = now
        self._purge_stale(now)

        if tier == "green":
            log.debug("Green: %s #%s score=%.0f", det.category(), track_key, score.total)
            self._last_tier[track_key] = tier
            return

        prev_tier = self._last_tier.get(track_key, "green")
        escalated = self.TIER_RANK.get(tier, 0) > self.TIER_RANK.get(prev_tier, 0)
        cooled_down = now - self._last_alert_time.get(track_key, 0) >= self.cooldown_seconds

        if not (escalated or cooled_down):
            self._last_tier[track_key] = tier
            return

        self._last_tier[track_key] = tier
        self._last_alert_time[track_key] = now
        self._offload("notify_integrations", self._notify_integrations, det, score, track_key, now)

        if tier == "yellow":
            log.info(
                "YELLOW ALERT: %s #%s score=%.0f — chime + snapshot",
                det.category(), track_key, score.total,
            )
            self._play(self._yellow_chime)
            self._offload("record_evidence", self._record_evidence, det, score, recent_frames[-1:])
        elif tier == "red":
            log.warning(
                "RED ALERT: %s #%s score=%.0f — siren + snapshot burst",
                det.category(), track_key, score.total,
            )
            log.warning(
                "  [radio-metadata stub] zone=%s tier=%s score=%.0f ts=%.0f "
                "(no VHF/LoRa hardware in this build)",
                det.zone_tier, tier, score.total, now,
            )
            self._play(self._red_siren)
            self._offload("record_evidence", self._record_evidence, det, score, recent_frames)

    def _offload(self, job_name: str, fn, *args) -> None:
        """Runs an alert side effect off the frame path when a dispatcher is
        wired in, inline otherwise.

        A rejected submission (queue full) is already logged and counted by the
        dispatcher; the alert itself has been logged and rate-limit state
        recorded before we get here, so the alert is never lost — only this
        one delivery/persistence attempt is.
        """
        if self.dispatcher is None:
            fn(*args)
            return
        self.dispatcher.submit(job_name, fn, *args)

    def _purge_stale(self, now: float) -> None:
        """Evicts alert state for identities not seen for `state_ttl_seconds`.

        Swept at most once per TTL window rather than on every detection, so
        the cost stays negligible while the state stays bounded to roughly the
        identities seen in the last two windows. Only keys that have been
        absent for a full TTL are dropped, and that TTL is never shorter than
        the cooldown, so an active track's cooldown/escalation state is never
        the thing being removed.
        """
        if self._last_purge > now:
            # Wall clock stepped backwards (e.g. an NTP correction) - re-base
            # rather than never sweeping again.
            self._last_purge = now
        if now - self._last_purge < self.state_ttl_seconds:
            return
        self._last_purge = now

        stale = [key for key, seen in self._last_seen.items() if now - seen > self.state_ttl_seconds]
        for key in stale:
            self._last_seen.pop(key, None)
            self._last_tier.pop(key, None)
            self._last_alert_time.pop(key, None)
        if stale:
            log.debug("Evicted alert state for %d stale identit(ies)", len(stale))

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

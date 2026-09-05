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
    ):
        self.snapshot_dir = snapshot_dir
        self.cooldown_seconds = cooldown_seconds
        self._now = now_fn
        self.incident_store = incident_store
        self.webhook = webhook
        self.syslog = syslog
        os.makedirs(snapshot_dir, exist_ok=True)
        self._last_tier: dict = {}
        self._last_alert_time: dict = {}

        self._yellow_chime = _synth_tone(880, 0.15, volume=0.25) if _AUDIO_AVAILABLE else None
        self._red_siren = _synth_tone(1200, 0.4, volume=0.5) if _AUDIO_AVAILABLE else None

    def handle(self, det, score, recent_frames: list) -> None:
        track_key = det.person_id if det.person_id is not None else det.track_id
        if track_key is None:
            return
        tier = score.tier

        if tier == "green":
            log.debug("Green: %s #%s score=%.0f", det.category(), track_key, score.total)
            self._last_tier[track_key] = tier
            return

        now = self._now()
        prev_tier = self._last_tier.get(track_key, "green")
        escalated = self.TIER_RANK.get(tier, 0) > self.TIER_RANK.get(prev_tier, 0)
        cooled_down = now - self._last_alert_time.get(track_key, 0) >= self.cooldown_seconds

        if not (escalated or cooled_down):
            self._last_tier[track_key] = tier
            return

        self._last_tier[track_key] = tier
        self._last_alert_time[track_key] = now
        self._notify_integrations(det, score, track_key, now)

        if tier == "yellow":
            log.info(
                "YELLOW ALERT: %s #%s score=%.0f — chime + snapshot",
                det.category(), track_key, score.total,
            )
            self._play(self._yellow_chime)
            self._record_evidence(det, score, recent_frames[-1:])
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
            self._record_evidence(det, score, recent_frames)

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

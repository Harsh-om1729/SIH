"""Offline unit tests for the alert manager's tiering/rate-limit logic — no
camera, audio device, or real file I/O required (snapshot/play calls are
monkeypatched to record invocations instead of doing real work).
Run from ibvap/: python -m unittest tests.test_alert_manager
"""

import tempfile
import unittest
from pathlib import Path

from alerts.alert_manager import AlertManager
from detection.detector import Detection
from intelligence.threat_score import ThreatScore


def make_detection(track_id=1, person_id=1, category_class_id=0) -> Detection:
    det = Detection(class_id=category_class_id, class_name="person", confidence=0.9, box=(0, 0, 50, 100))
    det.track_id = track_id
    det.person_id = person_id
    det.zone_tier = "red"
    return det


def make_score(tier: str) -> ThreatScore:
    totals = {"green": 10, "yellow": 40, "red": 85}
    # Reverse-engineer a ThreatScore with the right tier by giving it all the
    # risk in one bucket — simplest way to get a specific tier deterministically.
    return ThreatScore(sector_risk=totals[tier], time_risk=0, kinematics_risk=0, class_confidence=0)


class RecordingAlertManager(AlertManager):
    """Same logic as AlertManager, but records calls instead of doing real
    audio playback or disk writes."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.play_calls = []
        self.snapshot_calls = []

    def _play(self, sound) -> None:
        self.play_calls.append(sound)

    def _save_snapshot(self, frames, tier, det, track_key) -> None:
        self.snapshot_calls.append((tier, track_key, len(frames)))


class TestAlertManager(unittest.TestCase):
    def _manager(self, **kwargs) -> RecordingAlertManager:
        tmp_dir = tempfile.mkdtemp()
        return RecordingAlertManager(snapshot_dir=str(Path(tmp_dir) / "snapshots"), **kwargs)

    @staticmethod
    def _observe(mgr, det, tier, times=1, frames=("f",)):
        """Feeds `times` scoring cycles at one tier. Phase 18 confirmation means
        a single observation is deliberately not enough to alert, so tests state
        how many cycles they are simulating rather than calling handle() once."""
        for _ in range(times):
            mgr.handle(det, make_score(tier), recent_frames=list(frames))

    # --- tier behaviour -------------------------------------------------

    def test_green_never_plays_or_snapshots(self):
        mgr = self._manager()
        det = make_detection()
        self._observe(mgr, det, "green", times=5)
        self.assertEqual(mgr.play_calls, [])
        self.assertEqual(mgr.snapshot_calls, [])

    def test_confirmed_yellow_plays_and_snapshots_once_frame(self):
        mgr = self._manager()
        det = make_detection()
        self._observe(mgr, det, "yellow", times=2, frames=("f1", "f2", "f3"))
        self.assertEqual(len(mgr.play_calls), 1)
        self.assertEqual(mgr.snapshot_calls, [("yellow", 1, 1)])  # only the latest frame

    def test_confirmed_red_plays_and_snapshots_full_burst(self):
        mgr = self._manager()
        det = make_detection()
        self._observe(mgr, det, "red", times=2, frames=("f1", "f2", "f3"))
        self.assertEqual(len(mgr.play_calls), 1)
        self.assertEqual(mgr.snapshot_calls, [("red", 1, 3)])  # all buffered frames

    # --- Phase 18: N-of-M confirmation ----------------------------------

    def test_single_observation_does_not_alert(self):
        """The core of Phase 18: one borderline frame — a face similarity
        landing on 0.50 — must not be able to start an incident."""
        mgr = self._manager()
        det = make_detection()
        self._observe(mgr, det, "red", times=1)
        self.assertEqual(mgr.play_calls, [])
        self.assertEqual(mgr.snapshot_calls, [])

    def test_confirmation_threshold_is_configurable(self):
        mgr = self._manager(confirm_n=3, confirm_window=4)
        det = make_detection()
        self._observe(mgr, det, "red", times=2)
        self.assertEqual(mgr.play_calls, [], "2 of 4 should not confirm when N=3")
        self._observe(mgr, det, "red", times=1)
        self.assertEqual(len(mgr.play_calls), 1)

    def test_confirm_n_above_window_is_rejected(self):
        """A window that can never reach N would silence the system entirely —
        fail loudly at construction rather than at 2am on a border post."""
        with self.assertRaises(ValueError):
            self._manager(confirm_n=4, confirm_window=3)

    # --- Phase 18: hysteresis -------------------------------------------

    def test_flapping_score_does_not_buy_repeated_alerts(self):
        """Regression test for the observed failure: a watchlist similarity
        oscillating around its 0.50 threshold flipped the tier green<->red
        several times a second. Each re-escalation bypassed the cooldown by
        design, producing nine Red alerts for one stationary person in 52
        seconds. With hysteresis the flapping confirms Red once and then stays
        confirmed, so the cooldown actually governs."""
        clock = {"t": 0.0}
        mgr = self._manager(cooldown_seconds=100.0, now_fn=lambda: clock["t"])
        det = make_detection()

        for i in range(20):
            clock["t"] = i * 0.1  # ~10fps of flapping, all inside one cooldown
            self._observe(mgr, det, "red" if i % 2 == 0 else "green")

        self.assertEqual(
            len(mgr.play_calls), 1,
            f"flapping produced {len(mgr.play_calls)} alerts; expected exactly one",
        )

    def test_tier_releases_only_after_full_window_below_it(self):
        mgr = self._manager(cooldown_seconds=100.0)
        det = make_detection()

        self._observe(mgr, det, "red", times=2)      # confirmed red
        self.assertEqual(mgr._last_tier[1], "red")

        self._observe(mgr, det, "green", times=2)    # window not yet all-green
        self.assertEqual(mgr._last_tier[1], "red", "partial window must not release")

        self._observe(mgr, det, "green", times=1)    # now all three are green
        self.assertEqual(mgr._last_tier[1], "green")

    def test_confirmed_escalation_alerts_inside_cooldown(self):
        """Escalation still bypasses the cooldown — but only once the higher
        tier is confirmed, which is the whole point of confirming it."""
        clock = {"t": 0.0}
        mgr = self._manager(cooldown_seconds=100.0, now_fn=lambda: clock["t"])
        det = make_detection()

        self._observe(mgr, det, "yellow", times=2)
        self.assertEqual(len(mgr.play_calls), 1)

        clock["t"] = 1.0  # well within cooldown, but escalating yellow -> red
        self._observe(mgr, det, "red", times=2)
        self.assertEqual(len(mgr.play_calls), 2)

    # --- Phase 18: backoff ----------------------------------------------

    def test_same_tier_within_cooldown_does_not_re_alert(self):
        clock = {"t": 0.0}
        mgr = self._manager(cooldown_seconds=10.0, now_fn=lambda: clock["t"])
        det = make_detection()

        self._observe(mgr, det, "yellow", times=2)
        clock["t"] = 2.0  # within cooldown, same tier
        self._observe(mgr, det, "yellow", times=2)

        self.assertEqual(len(mgr.play_calls), 1)  # second call suppressed

    def test_repeat_cooldown_doubles_each_time(self):
        clock = {"t": 0.0}
        mgr = self._manager(cooldown_seconds=10.0, max_cooldown_seconds=1000.0,
                            now_fn=lambda: clock["t"])
        det = make_detection()

        self._observe(mgr, det, "yellow", times=2)          # alert 1 at t=0
        clock["t"] = 10.0
        self._observe(mgr, det, "yellow", times=1)          # alert 2 — 10s elapsed
        self.assertEqual(len(mgr.play_calls), 2)

        clock["t"] = 25.0                                    # only 15s since alert 2
        self._observe(mgr, det, "yellow", times=1)
        self.assertEqual(len(mgr.play_calls), 2, "second repeat must wait 20s, not 10s")

        clock["t"] = 30.0                                    # 20s since alert 2
        self._observe(mgr, det, "yellow", times=1)
        self.assertEqual(len(mgr.play_calls), 3)

    def test_backoff_is_capped(self):
        mgr = self._manager(cooldown_seconds=10.0, max_cooldown_seconds=15.0)
        mgr._repeats[1] = 8  # would be 10 * 2**8 = 2560s uncapped
        self.assertEqual(mgr._effective_cooldown(1), 15.0)

    def test_escalation_resets_backoff(self):
        clock = {"t": 0.0}
        mgr = self._manager(cooldown_seconds=10.0, now_fn=lambda: clock["t"])
        det = make_detection()

        self._observe(mgr, det, "yellow", times=2)
        clock["t"] = 10.0
        self._observe(mgr, det, "yellow", times=1)  # repeat -> backoff now 20s
        self.assertEqual(mgr._repeats[1], 1)

        clock["t"] = 11.0
        self._observe(mgr, det, "red", times=2)     # new confirmed tier
        self.assertEqual(mgr._repeats[1], 0)
        self.assertEqual(len(mgr.play_calls), 3)

    # --- bookkeeping -----------------------------------------------------

    def test_different_tracks_alert_independently(self):
        clock = {"t": 0.0}
        mgr = self._manager(cooldown_seconds=100.0, now_fn=lambda: clock["t"])
        det_a = make_detection(track_id=1, person_id=1)
        det_b = make_detection(track_id=2, person_id=2)

        self._observe(mgr, det_a, "yellow", times=2)
        self._observe(mgr, det_b, "yellow", times=2)

        self.assertEqual(len(mgr.play_calls), 2)

    def test_forget_clears_per_track_state(self):
        mgr = self._manager()
        det = make_detection()
        self._observe(mgr, det, "red", times=2)
        self.assertIn(1, mgr._history)

        mgr.forget(1)
        for state in (mgr._last_tier, mgr._last_alert_time, mgr._history, mgr._repeats):
            self.assertNotIn(1, state)


if __name__ == "__main__":
    unittest.main()

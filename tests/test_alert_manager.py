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

    def test_green_never_plays_or_snapshots(self):
        mgr = self._manager()
        det = make_detection()
        mgr.handle(det, make_score("green"), recent_frames=["frame"])
        self.assertEqual(mgr.play_calls, [])
        self.assertEqual(mgr.snapshot_calls, [])

    def test_yellow_plays_and_snapshots_once_frame(self):
        mgr = self._manager()
        det = make_detection()
        mgr.handle(det, make_score("yellow"), recent_frames=["f1", "f2", "f3"])
        self.assertEqual(len(mgr.play_calls), 1)
        self.assertEqual(mgr.snapshot_calls, [("yellow", 1, 1)])  # only the latest frame

    def test_red_plays_and_snapshots_full_burst(self):
        mgr = self._manager()
        det = make_detection()
        mgr.handle(det, make_score("red"), recent_frames=["f1", "f2", "f3"])
        self.assertEqual(len(mgr.play_calls), 1)
        self.assertEqual(mgr.snapshot_calls, [("red", 1, 3)])  # all buffered frames

    def test_escalation_always_alerts_immediately(self):
        clock = {"t": 0.0}
        mgr = self._manager(cooldown_seconds=100.0, now_fn=lambda: clock["t"])
        det = make_detection()

        mgr.handle(det, make_score("yellow"), recent_frames=["f"])
        clock["t"] = 1.0  # well within cooldown, but escalating yellow -> red
        mgr.handle(det, make_score("red"), recent_frames=["f"])

        self.assertEqual(len(mgr.play_calls), 2)

    def test_same_tier_within_cooldown_does_not_re_alert(self):
        clock = {"t": 0.0}
        mgr = self._manager(cooldown_seconds=10.0, now_fn=lambda: clock["t"])
        det = make_detection()

        mgr.handle(det, make_score("yellow"), recent_frames=["f"])
        clock["t"] = 2.0  # within cooldown, same tier
        mgr.handle(det, make_score("yellow"), recent_frames=["f"])

        self.assertEqual(len(mgr.play_calls), 1)  # second call suppressed

    def test_same_tier_after_cooldown_re_alerts(self):
        clock = {"t": 0.0}
        mgr = self._manager(cooldown_seconds=5.0, now_fn=lambda: clock["t"])
        det = make_detection()

        mgr.handle(det, make_score("yellow"), recent_frames=["f"])
        clock["t"] = 6.0  # past cooldown
        mgr.handle(det, make_score("yellow"), recent_frames=["f"])

        self.assertEqual(len(mgr.play_calls), 2)

    def test_different_tracks_alert_independently(self):
        clock = {"t": 0.0}
        mgr = self._manager(cooldown_seconds=100.0, now_fn=lambda: clock["t"])
        det_a = make_detection(track_id=1, person_id=1)
        det_b = make_detection(track_id=2, person_id=2)

        mgr.handle(det_a, make_score("yellow"), recent_frames=["f"])
        mgr.handle(det_b, make_score("yellow"), recent_frames=["f"])

        self.assertEqual(len(mgr.play_calls), 2)


if __name__ == "__main__":
    unittest.main()

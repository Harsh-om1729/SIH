"""Offline unit tests for the threat scoring engine — no camera required.
Run from ibvap/: python -m unittest tests.test_threat_score
"""

import tempfile
import unittest
from pathlib import Path

from intelligence.threat_rules import ThreatRulesDB
from intelligence.threat_score import ThreatScore, ThreatScorer


def _steps(start: float, end: float, count: int) -> list:
    """`count` evenly spaced speeds from start to end, inclusive."""
    return [start + (end - start) * i / (count - 1) for i in range(count)]


class TestThreatScore(unittest.TestCase):
    def test_total_is_sum_of_components(self):
        score = ThreatScore(sector_risk=10, time_risk=5, kinematics_risk=3, class_confidence=2)
        self.assertEqual(score.total, 20)

    def test_tier_boundaries(self):
        self.assertEqual(ThreatScore(0, 0, 0, 0).tier, "green")
        self.assertEqual(ThreatScore(30, 0, 0, 0).tier, "green")
        self.assertEqual(ThreatScore(31, 0, 0, 0).tier, "yellow")
        self.assertEqual(ThreatScore(69, 0, 0, 0).tier, "yellow")
        self.assertEqual(ThreatScore(70, 0, 0, 0).tier, "red")
        self.assertEqual(ThreatScore(100, 0, 0, 0).tier, "red")

    def test_ceiling_caps_tier_and_total(self):
        score = ThreatScore(100, 0, 0, 0, tier_ceiling="yellow", ceiling_reason="no zone")
        self.assertEqual(score.tier, "yellow")
        self.assertEqual(score.total, 69, "total must stay consistent with the capped tier")

    def test_ceiling_never_raises_a_tier(self):
        score = ThreatScore(10, 0, 0, 0, tier_ceiling="red", ceiling_reason="irrelevant")
        self.assertEqual(score.tier, "green")
        self.assertEqual(score.total, 10)

    def test_ceiling_binds_an_override(self):
        """The design decision behind Phase 18's no-zone ceiling: an override
        says the pattern matters, the ceiling says we cannot tell where it is
        happening, and the ceiling qualifies the override rather than the other
        way round."""
        score = ThreatScore(
            0, 0, 0, 0,
            override_reason="watchlist match: Test Subject (similarity=0.51)",
            tier_ceiling="yellow", ceiling_reason="no zone defined for this camera",
        )
        self.assertEqual(score.tier, "yellow")
        self.assertIn("forced RED", score.breakdown(), "the reason must survive the cap")
        self.assertIn("capped at YELLOW", score.breakdown())


class TestThreatScorer(unittest.TestCase):
    def _scorer(self) -> ThreatScorer:
        tmp_dir = tempfile.mkdtemp()
        rules = ThreatRulesDB(db_path=str(Path(tmp_dir) / "threat_rules.db"))
        return ThreatScorer(rules)

    def test_kinematics_stationary_is_max_risk(self):
        """The U-curve's whole point: a near-stationary subject is a man lying
        up at the fence, not an absence of threat. The old linear rule scored
        this as zero, which is backwards for a border."""
        scorer = self._scorer()
        config = scorer.rules.get_movement_config()
        max_risk = config["max_movement_risk"]
        self.assertEqual(scorer._kinematics_risk(0.0), max_risk)
        self.assertEqual(
            scorer._kinematics_risk(config["still_speed_px_per_frame"]), max_risk
        )

    def test_kinematics_above_fast_threshold_is_max_risk(self):
        scorer = self._scorer()
        config = scorer.rules.get_movement_config()
        self.assertEqual(scorer._kinematics_risk(config["fast_speed_px_per_frame"]), config["max_movement_risk"])
        self.assertEqual(scorer._kinematics_risk(1000.0), config["max_movement_risk"])

    def test_kinematics_walking_band_is_zero_risk(self):
        """An ordinary walking pace is the least interesting thing on the feed
        — the trough of the U."""
        scorer = self._scorer()
        config = scorer.rules.get_movement_config()
        walk_min = config["walk_min_px_per_frame"]
        walk_max = config["walk_max_px_per_frame"]
        self.assertEqual(scorer._kinematics_risk(walk_min), 0.0)
        self.assertEqual(scorer._kinematics_risk((walk_min + walk_max) / 2), 0.0)
        self.assertEqual(scorer._kinematics_risk(walk_max), 0.0)

    def test_kinematics_ramps_monotonically_out_of_each_extreme(self):
        """Between the extremes and the walking band the curve must ramp, not
        step — otherwise a subject slowing to a halt jumps from 0 to max in one
        frame and drags the tier with it."""
        scorer = self._scorer()
        config = scorer.rules.get_movement_config()
        still, walk_min = config["still_speed_px_per_frame"], config["walk_min_px_per_frame"]
        walk_max, fast = config["walk_max_px_per_frame"], config["fast_speed_px_per_frame"]

        slowing = [scorer._kinematics_risk(s) for s in _steps(walk_min, still, 6)]
        self.assertEqual(slowing, sorted(slowing), "risk must rise as speed falls to still")

        speeding = [scorer._kinematics_risk(s) for s in _steps(walk_max, fast, 6)]
        self.assertEqual(speeding, sorted(speeding), "risk must rise as speed rises to fast")

    @unittest.expectedFailure
    def test_person_in_red_zone_at_night_moving_fast_scores_red(self):
        """KNOWN GAP — audit finding A1, scheduled for Phase 19.

        Person + red zone + 2am + running, with no direction label, totals
        25+18+10+12 = 65 -> Yellow. Red (70) is currently reachable only
        through the crossing override, which needs a direction label, which
        needs >=4px of movement (ZoneEngine.MIN_DIRECTION_MAGNITUDE). A
        stationary or distant subject never gets one, so the textbook
        infiltration posture caps at a soft chime.

        Left as an expected failure rather than relaxed to match the code:
        the assertion is right, the scoring is wrong. Phase 19 adds a
        sustained-presence override, after which this should pass and the
        decorator comes off.
        """
        scorer = self._scorer()
        score = scorer.score(zone_tier="red", hour=2, speed_px_per_frame=50.0, category="person")
        self.assertEqual(score.tier, "red")
        self.assertGreaterEqual(score.total, 70)

    def test_person_in_red_zone_at_night_crossing_inward_scores_red(self):
        """The path that does reach Red today, so the gap above is bounded:
        with a direction label the crossing override fires."""
        scorer = self._scorer()
        score = scorer.score(
            zone_tier="red", hour=2, speed_px_per_frame=50.0,
            category="person", zone_direction="inward",
        )
        self.assertEqual(score.tier, "red")
        self.assertGreaterEqual(score.total, 70)
        self.assertIsNotNone(score.override_reason)

    def test_animal_in_green_zone_by_day_standing_still_scores_green(self):
        scorer = self._scorer()
        score = scorer.score(zone_tier="green", hour=14, speed_px_per_frame=0.0, category="animal")
        self.assertEqual(score.tier, "green")

    def test_yellow_zone_person_moving_moderately_scores_yellow(self):
        scorer = self._scorer()
        # yellow(15) + daytime(5) + person(15) = 35 baseline, comfortably yellow
        # even with zero kinematics risk added.
        score = scorer.score(zone_tier="yellow", hour=14, speed_px_per_frame=0.0, category="person")
        self.assertEqual(score.tier, "yellow")

    def test_watchlist_match_in_a_zone_forces_red(self):
        scorer = self._scorer()
        score = scorer.score(
            zone_tier="yellow", hour=2, speed_px_per_frame=3.0, category="person",
            watchlist_match="Test Subject", watchlist_similarity=0.83,
        )
        self.assertEqual(score.tier, "red")
        self.assertIn("watchlist match: Test Subject", score.breakdown())

    def test_watchlist_match_outside_any_zone_is_capped_at_yellow(self):
        """The live failure this fixes: with config/zones_cam0.json empty, every
        watchlist hit logged "score=70 zone=none" and sounded the siren, on
        similarities as low as 0.50. Un-zoned footage has no sector, no line to
        cross and nothing to loiter at, so it tops out at Yellow — logged and
        snapshotted, not screamed about."""
        scorer = self._scorer()
        score = scorer.score(
            zone_tier="none", hour=2, speed_px_per_frame=3.0, category="person",
            watchlist_match="Test Subject", watchlist_similarity=0.51,
        )
        self.assertEqual(score.tier, "yellow")
        self.assertLessEqual(score.total, 69)
        self.assertIn("watchlist match: Test Subject", score.breakdown())
        self.assertIn("no zone defined", score.breakdown())

    def test_no_zone_never_reaches_red_on_ordinary_terms(self):
        scorer = self._scorer()
        for hour in range(24):
            for speed in (0.0, 1.0, 5.0, 50.0):
                score = scorer.score(
                    zone_tier="none", hour=hour,
                    speed_px_per_frame=speed, category="person",
                )
                self.assertNotEqual(
                    score.tier, "red",
                    f"un-zoned person at hour={hour} speed={speed} reached Red",
                )

    def test_unknown_zone_tier_behaves_like_none(self):
        scorer = self._scorer()
        score = scorer.score(zone_tier=None, hour=14, speed_px_per_frame=0.0, category="animal")
        self.assertEqual(score.sector_risk, 0.0)


if __name__ == "__main__":
    unittest.main()

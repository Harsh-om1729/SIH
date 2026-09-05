"""Offline unit tests for the threat scoring engine — no camera required.
Run from ibvap/: python -m unittest tests.test_threat_score
"""

import tempfile
import unittest
from pathlib import Path

from intelligence.threat_rules import ThreatRulesDB
from intelligence.threat_score import ThreatScore, ThreatScorer


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


class TestThreatScorer(unittest.TestCase):
    def _scorer(self) -> ThreatScorer:
        tmp_dir = tempfile.mkdtemp()
        rules = ThreatRulesDB(db_path=str(Path(tmp_dir) / "threat_rules.db"))
        return ThreatScorer(rules)

    def test_kinematics_below_slow_threshold_is_zero_risk(self):
        scorer = self._scorer()
        self.assertEqual(scorer._kinematics_risk(0.0), 0.0)
        self.assertEqual(scorer._kinematics_risk(1.0), 0.0)  # below default slow=2.0

    def test_kinematics_above_fast_threshold_is_max_risk(self):
        scorer = self._scorer()
        config = scorer.rules.get_movement_config()
        self.assertEqual(scorer._kinematics_risk(config["fast_speed_px_per_frame"]), config["max_movement_risk"])
        self.assertEqual(scorer._kinematics_risk(1000.0), config["max_movement_risk"])

    def test_kinematics_midpoint_is_roughly_half_max_risk(self):
        scorer = self._scorer()
        config = scorer.rules.get_movement_config()
        midpoint = (config["slow_speed_px_per_frame"] + config["fast_speed_px_per_frame"]) / 2
        risk = scorer._kinematics_risk(midpoint)
        self.assertAlmostEqual(risk, config["max_movement_risk"] / 2, places=4)

    def test_person_in_red_zone_at_night_moving_fast_scores_red(self):
        scorer = self._scorer()
        score = scorer.score(zone_tier="red", hour=2, speed_px_per_frame=50.0, category="person")
        self.assertEqual(score.tier, "red")
        self.assertGreaterEqual(score.total, 70)

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

    def test_unknown_zone_tier_behaves_like_none(self):
        scorer = self._scorer()
        score = scorer.score(zone_tier=None, hour=14, speed_px_per_frame=0.0, category="animal")
        self.assertEqual(score.sector_risk, 0.0)


if __name__ == "__main__":
    unittest.main()

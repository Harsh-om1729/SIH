"""Offline unit tests for the threat rules DB — no camera required.
Run from ibvap/: python -m unittest tests.test_threat_rules
"""

import tempfile
import unittest
from pathlib import Path

from intelligence.threat_rules import ThreatRulesDB


class TestThreatRulesDB(unittest.TestCase):
    def _db(self) -> ThreatRulesDB:
        tmp_dir = tempfile.mkdtemp()
        return ThreatRulesDB(db_path=str(Path(tmp_dir) / "threat_rules.db"))

    def test_default_sector_risk_ordering(self):
        db = self._db()
        # Red must outrank Yellow must outrank Green must outrank none —
        # this ordering is what the Phase 10 scoring formula depends on.
        self.assertGreater(db.get_sector_risk("red"), db.get_sector_risk("yellow"))
        self.assertGreater(db.get_sector_risk("yellow"), db.get_sector_risk("green"))
        self.assertGreater(db.get_sector_risk("green"), db.get_sector_risk("none"))

    def test_sector_risk_within_spec_range(self):
        db = self._db()
        for tier in ("red", "yellow", "green", "none"):
            self.assertGreaterEqual(db.get_sector_risk(tier), 0.0)
            self.assertLessEqual(db.get_sector_risk(tier), 30.0)

    def test_time_risk_night_higher_than_day(self):
        db = self._db()
        self.assertGreater(db.get_time_risk(2), db.get_time_risk(14))  # 2am vs 2pm

    def test_time_risk_within_spec_range(self):
        db = self._db()
        for hour in range(24):
            self.assertGreaterEqual(db.get_time_risk(hour), 0.0)
            self.assertLessEqual(db.get_time_risk(hour), 25.0)

    def test_class_confidence_person_highest(self):
        db = self._db()
        self.assertGreater(db.get_class_confidence("person"), db.get_class_confidence("vehicle"))
        self.assertGreater(db.get_class_confidence("vehicle"), db.get_class_confidence("animal"))

    def test_class_confidence_within_spec_range(self):
        db = self._db()
        for category in ("person", "vehicle", "animal"):
            self.assertGreaterEqual(db.get_class_confidence(category), 0.0)
            self.assertLessEqual(db.get_class_confidence(category), 15.0)

    def test_unknown_key_returns_safe_default(self):
        db = self._db()
        self.assertEqual(db.get_sector_risk("unknown_tier"), 0.0)
        self.assertEqual(db.get_class_confidence("unknown_category"), 0.0)

    def test_movement_config_has_expected_keys(self):
        db = self._db()
        config = db.get_movement_config()
        self.assertIn("slow_speed_px_per_frame", config)
        self.assertIn("fast_speed_px_per_frame", config)
        self.assertIn("max_movement_risk", config)
        self.assertLessEqual(config["max_movement_risk"], 30.0)

    def test_hand_edited_value_survives_reconnection_without_being_overwritten(self):
        """Rules are only seeded once; a locally tuned value must persist
        across restarts, matching the roadmap's 'tune locally, no code
        changes' requirement.
        """
        tmp_dir = tempfile.mkdtemp()
        db_path = str(Path(tmp_dir) / "threat_rules.db")

        db_a = ThreatRulesDB(db_path=db_path)
        db_a._conn.execute("UPDATE sector_risk SET risk = 99 WHERE zone_tier = 'red'")
        db_a._conn.commit()
        db_a.close()

        db_b = ThreatRulesDB(db_path=db_path)  # reopening must not re-seed over the edit
        self.assertEqual(db_b.get_sector_risk("red"), 99.0)


if __name__ == "__main__":
    unittest.main()

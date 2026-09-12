"""Offline unit tests for the zone engine — no camera/GUI required.
Run from ibvap/: python -m unittest tests.test_zone_engine
"""

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from zones.zone_engine import Zone, ZoneEngine

# A simple square red zone and, beside it, a square yellow zone.
RED_ZONE = Zone("red", [(0, 0), (100, 0), (100, 100), (0, 100)])
YELLOW_ZONE = Zone("yellow", [(100, 0), (200, 0), (200, 100), (100, 100)])
GREEN_ZONE = Zone("green", [(200, 0), (300, 0), (300, 100), (200, 100)])


class TestZoneEngine(unittest.TestCase):
    def _engine(self, zones=None, **kwargs) -> ZoneEngine:
        tmp_dir = tempfile.mkdtemp()
        engine = ZoneEngine(config_path=str(Path(tmp_dir) / "zones.json"), **kwargs)
        for zone in zones or []:
            engine.add_zone(zone)
        return engine

    def test_point_inside_zone_returns_its_tier(self):
        engine = self._engine([RED_ZONE])
        result = engine.classify((50, 50))
        self.assertEqual(result["tier"], "red")

    def test_point_outside_all_zones_returns_none(self):
        engine = self._engine([RED_ZONE])
        result = engine.classify((500, 500))
        self.assertEqual(result["tier"], "none")

    def test_overlapping_zones_favor_higher_priority(self):
        overlapping_yellow = Zone("yellow", [(0, 0), (100, 0), (100, 100), (0, 100)])
        engine = self._engine([overlapping_yellow, RED_ZONE])
        result = engine.classify((50, 50))
        self.assertEqual(result["tier"], "red")

    def test_yellow_zone_direction_inward_toward_red(self):
        engine = self._engine([RED_ZONE, YELLOW_ZONE])
        # Yellow zone centroid is around (150, 50); red zone centroid (50, 50)
        # is to the left, so a leftward direction vector is "inward".
        result = engine.classify((150, 50), direction=(-10.0, 0.0))
        self.assertEqual(result["tier"], "yellow")
        self.assertEqual(result["direction"], "inward")

    def test_yellow_zone_direction_outward_away_from_red(self):
        engine = self._engine([RED_ZONE, YELLOW_ZONE])
        result = engine.classify((150, 50), direction=(10.0, 0.0))
        self.assertEqual(result["tier"], "yellow")
        self.assertEqual(result["direction"], "outward")

    def test_green_zone_retiered_to_yellow_during_curfew(self):
        curfew_midnight = datetime(2026, 1, 1, 0, 30)  # 00:30, inside 23:00-05:00
        engine = self._engine(
            [GREEN_ZONE], curfew_start_hour=23, curfew_end_hour=5, now_fn=lambda: curfew_midnight
        )
        result = engine.classify((250, 50))
        self.assertEqual(result["tier"], "yellow")

    def test_green_zone_stays_green_outside_curfew(self):
        midday = datetime(2026, 1, 1, 12, 0)
        engine = self._engine(
            [GREEN_ZONE], curfew_start_hour=23, curfew_end_hour=5, now_fn=lambda: midday
        )
        result = engine.classify((250, 50))
        self.assertEqual(result["tier"], "green")

    def test_zones_persist_across_reload(self):
        tmp_dir = tempfile.mkdtemp()
        config_path = str(Path(tmp_dir) / "zones.json")
        engine_a = ZoneEngine(config_path=config_path)
        engine_a.add_zone(RED_ZONE)

        engine_b = ZoneEngine(config_path=config_path)
        self.assertEqual(len(engine_b.zones), 1)
        self.assertEqual(engine_b.zones[0].zone_type, "red")


class TestFixedTierZoneEngine(unittest.TestCase):
    """A camera assigned one tier for its whole frame (CAMERA_ZONE_TIERS) -
    no polygons drawn, no config/zones_<camera>.json needed at all."""

    def _engine(self, fixed_tier, **kwargs) -> ZoneEngine:
        tmp_dir = tempfile.mkdtemp()
        return ZoneEngine(
            config_path=str(Path(tmp_dir) / "zones.json"), fixed_tier=fixed_tier, **kwargs
        )

    def test_every_point_gets_the_fixed_tier_regardless_of_position(self):
        engine = self._engine("red")
        self.assertEqual(engine.classify((0, 0))["tier"], "red")
        self.assertEqual(engine.classify((9999, 9999))["tier"], "red")

    def test_works_with_no_zones_json_on_disk(self):
        engine = self._engine("yellow")
        self.assertEqual(engine.zones, [])
        self.assertEqual(engine.classify((50, 50))["tier"], "yellow")

    def test_direction_inward_when_descending_toward_camera(self):
        engine = self._engine("red")
        result = engine.classify((50, 50), direction=(0.0, 10.0))
        self.assertEqual(result["direction"], "inward")

    def test_direction_outward_when_rising_away_from_camera(self):
        engine = self._engine("red")
        result = engine.classify((50, 50), direction=(0.0, -10.0))
        self.assertEqual(result["direction"], "outward")

    def test_direction_parallel_when_lateral_dominant(self):
        engine = self._engine("red")
        result = engine.classify((50, 50), direction=(10.0, 1.0))
        self.assertEqual(result["direction"], "parallel")

    def test_direction_none_below_minimum_magnitude(self):
        engine = self._engine("red")
        result = engine.classify((50, 50), direction=(1.0, 1.0))
        self.assertIsNone(result["direction"])

    def test_direction_none_when_not_provided(self):
        engine = self._engine("red")
        result = engine.classify((50, 50))
        self.assertIsNone(result["direction"])

    def test_fixed_green_retiers_to_yellow_during_curfew(self):
        curfew_midnight = datetime(2026, 1, 1, 0, 30)
        engine = self._engine(
            "green", curfew_start_hour=23, curfew_end_hour=5, now_fn=lambda: curfew_midnight
        )
        self.assertEqual(engine.classify((50, 50))["tier"], "yellow")

    def test_fixed_green_stays_green_outside_curfew(self):
        midday = datetime(2026, 1, 1, 12, 0)
        engine = self._engine(
            "green", curfew_start_hour=23, curfew_end_hour=5, now_fn=lambda: midday
        )
        self.assertEqual(engine.classify((50, 50))["tier"], "green")


if __name__ == "__main__":
    unittest.main()

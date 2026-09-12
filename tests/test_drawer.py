"""ZoneDrawer overlay tests — needs a real (even if headless) OpenCV window,
so these are skipped where cv2.namedWindow can't succeed at all.
Run from ibvap/: python -m unittest tests.test_drawer
"""
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from zones.drawer import ZoneDrawer
from zones.zone_engine import Zone, ZoneEngine

RED_ZONE = Zone("red", [(0, 0), (100, 0), (100, 100), (0, 100)])


def _can_open_a_window() -> bool:
    try:
        cv2.namedWindow("ibvap-test-probe")
        cv2.destroyWindow("ibvap-test-probe")
        return True
    except cv2.error:
        return False


@unittest.skipUnless(_can_open_a_window(), "no display available for cv2.namedWindow")
class TestZoneDrawerFixedTier(unittest.TestCase):
    def _drawer(self, fixed_tier=None) -> ZoneDrawer:
        win = f"test-{fixed_tier}"
        cv2.namedWindow(win)
        self.addCleanup(cv2.destroyWindow, win)
        tmp_dir = tempfile.mkdtemp()
        engine = ZoneEngine(config_path=str(Path(tmp_dir) / "zones.json"), fixed_tier=fixed_tier)
        engine.add_zone(RED_ZONE)
        return ZoneDrawer(win, engine)

    def test_drawn_zones_are_not_rendered_in_fixed_tier_mode(self):
        """The bug this fixes: a camera pinned via CAMERA_ZONE_TIERS still had
        its old config/zones_<camera>.json polygons drawn on screen, even
        though ZoneEngine.classify() no longer uses them for scoring at all -
        three unrelated lines on every frame with no explanation."""
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        self._drawer(fixed_tier="red").draw_overlay(frame)
        # Only the fixed-tier label (top-left) and the bottom hint bar should
        # draw anything - nothing in the middle of the frame, where the red
        # zone's polygon border would otherwise land.
        middle_strip = frame[80:120, 80:120]
        self.assertEqual(np.count_nonzero(middle_strip), 0)

    def test_drawn_zones_still_render_without_a_fixed_tier(self):
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        self._drawer(fixed_tier=None).draw_overlay(frame)
        # The red zone's polygon border passes through this strip.
        middle_strip = frame[95:100, 0:100]
        self.assertGreater(np.count_nonzero(middle_strip), 0)

    def test_fixed_tier_label_uses_the_tier_color(self):
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        self._drawer(fixed_tier="red").draw_overlay(frame)
        # ZONE_COLORS["red"] is BGR (0, 0, 255) - some pixel in the label
        # region (top-left, where the text is drawn) should carry pure red.
        label_region = frame[0:30, 0:250]
        reds = (label_region[:, :, 2] == 255) & (label_region[:, :, 0] == 0)
        self.assertTrue(reds.any())


if __name__ == "__main__":
    unittest.main()

import logging

import cv2
import numpy as np

from zones.border_line import BorderLine
from zones.zone_engine import Zone, ZoneEngine

log = logging.getLogger("ibvap.zones")

ZONE_COLORS = {"red": (0, 0, 255), "yellow": (0, 255, 255), "green": (0, 255, 0)}
KEY_TO_ZONE_TYPE = {ord("r"): "red", ord("y"): "yellow", ord("g"): "green"}

# The border line is drawn in the same interaction as a zone but is a different
# kind of object — exactly 2 points, and it feeds the kinematic model's geometry
# rather than the sector lookup. "border" is kept out of KEY_TO_ZONE_TYPE so it
# can never be passed to Zone() as a zone_type.
BORDER_KEY = ord("b")
BORDER_COLOR = (255, 0, 255)


class ZoneDrawer:
    """Interactive mouse-based zone drawing on a named OpenCV window.

    Press 'r'/'y'/'g' to start drawing a Red/Yellow/Green zone polygon,
    left-click to add vertices, Enter/Space to finish (needs >= 3 points),
    Esc to cancel the current polygon, 'c' to clear all saved zones.

    Press 'b' to draw the border LINE for the predictive kinematic model:
    click exactly 2 points, Enter/Space to save. Available only when the
    drawer was given a border store.
    """

    def __init__(self, window_name: str, engine: ZoneEngine, border_store=None):
        self.window_name = window_name
        self.engine = engine
        self.border_store = border_store
        self._drawing_type: "str | None" = None
        self._current_points: list = []
        cv2.setMouseCallback(window_name, self._on_mouse)

    def _on_mouse(self, event, x, y, flags, param) -> None:
        if event == cv2.EVENT_LBUTTONDOWN and self._drawing_type is not None:
            self._current_points.append((x, y))

    def handle_key(self, key: int) -> None:
        if key in KEY_TO_ZONE_TYPE:
            self._drawing_type = KEY_TO_ZONE_TYPE[key]
            self._current_points = []
            log.info(
                "[%s] drawing a %s zone — click points, Enter/Space to finish, Esc to cancel",
                self.window_name, self._drawing_type,
            )
        elif key == BORDER_KEY and self.border_store is not None:
            self._drawing_type = "border"
            self._current_points = []
            log.info(
                "[%s] drawing the BORDER LINE — click 2 points, Enter/Space to save",
                self.window_name,
            )
        elif key in (13, 10, 32) and self._drawing_type is not None:  # Enter (CR/LF) or Space
            if self._drawing_type == "border":
                if len(self._current_points) >= 2:
                    # Take the first and last click, so a stray extra click
                    # still yields the line the operator clearly intended.
                    line = BorderLine(self._current_points[0], self._current_points[-1])
                    self.border_store.set_line(line)
                    log.info("[%s] saved border line %s", self.window_name, line)
                else:
                    log.warning(
                        "[%s] border line needs 2 points, got %d — not saved",
                        self.window_name, len(self._current_points),
                    )
            elif len(self._current_points) >= 3:
                self.engine.add_zone(Zone(self._drawing_type, self._current_points))
                log.info(
                    "[%s] saved %s zone with %d points",
                    self.window_name, self._drawing_type, len(self._current_points),
                )
            self._drawing_type = None
            self._current_points = []
        elif key == 27:  # Esc
            self._drawing_type = None
            self._current_points = []
        elif key == ord("c"):
            self.engine.clear()
            log.info("[%s] cleared all zones", self.window_name)

    def draw_overlay(self, frame) -> None:
        h, w = frame.shape[:2]

        if self.engine.fixed_tier is not None:
            # This camera is pinned to one tier via CAMERA_ZONE_TIERS - any
            # polygons still sitting in its zones.json are leftovers from
            # before that switch and are no longer used for scoring at all
            # (see ZoneEngine.classify). Drawing them would show boundaries
            # that don't mean anything anymore, so a label replaces the lines.
            color = ZONE_COLORS[self.engine.fixed_tier]
            cv2.putText(
                frame, f"FIXED TIER: {self.engine.fixed_tier.upper()}", (10, 24),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2,
            )
        else:
            for zone in self.engine.zones:
                color = ZONE_COLORS[zone.zone_type]
                pts = np.array(zone.polygon, dtype=np.int32)
                cv2.polylines(frame, [pts], True, color, 2)

        # A saved border line stays visible so the operator can see the geometry
        # the kinematic score is measuring against.
        if self.border_store is not None and self.border_store.line is not None:
            line = self.border_store.line
            p1 = (int(line.p1[0]), int(line.p1[1]))
            p2 = (int(line.p2[0]), int(line.p2[1]))
            cv2.line(frame, p1, p2, BORDER_COLOR, 2)
            cv2.putText(frame, "BORDER", (p1[0] + 4, p1[1] - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, BORDER_COLOR, 1)

        if self._drawing_type is not None:
            border = self._drawing_type == "border"
            color = BORDER_COLOR if border else ZONE_COLORS[self._drawing_type]
            for point in self._current_points:
                cv2.circle(frame, point, 4, color, -1)
            if len(self._current_points) >= 2:
                pts = np.array(self._current_points, dtype=np.int32)
                cv2.polylines(frame, [pts], False, color, 1)

            n = len(self._current_points)
            needed = 2 if border else 3
            status = (f"need {needed} points" if n < needed
                      else "ready — press ENTER to finish")
            what = "BORDER LINE" if border else f"{self._drawing_type.upper()} zone"
            hint = f"Drawing {what}: {n} point(s) clicked ({status}). ESC to cancel."
            cv2.rectangle(frame, (0, h - 30), (w, h), (0, 0, 0), -1)
            cv2.putText(frame, hint, (10, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        else:
            hint = "Press r/y/g to draw a Red/Yellow/Green zone, c to clear all"
            if self.border_store is not None:
                hint = "Press r/y/g for zones, b for the border line, c to clear zones"
            cv2.rectangle(frame, (0, h - 30), (w, h), (0, 0, 0), -1)
            cv2.putText(
                frame, hint, (10, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 2
            )

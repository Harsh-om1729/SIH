import logging

import cv2
import numpy as np

from zones.zone_engine import Zone, ZoneEngine

log = logging.getLogger("ibvap.zones")

ZONE_COLORS = {"red": (0, 0, 255), "yellow": (0, 255, 255), "green": (0, 255, 0)}
KEY_TO_ZONE_TYPE = {ord("r"): "red", ord("y"): "yellow", ord("g"): "green"}


class ZoneDrawer:
    """Interactive mouse-based zone drawing on a named OpenCV window.

    Press 'r'/'y'/'g' to start drawing a Red/Yellow/Green zone polygon,
    left-click to add vertices, Enter/Space to finish (needs >= 3 points),
    Esc to cancel the current polygon, 'c' to clear all saved zones.
    """

    def __init__(self, window_name: str, engine: ZoneEngine):
        self.window_name = window_name
        self.engine = engine
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
        elif key in (13, 10, 32) and self._drawing_type is not None:  # Enter (CR/LF) or Space
            if len(self._current_points) >= 3:
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

        for zone in self.engine.zones:
            color = ZONE_COLORS[zone.zone_type]
            pts = np.array(zone.polygon, dtype=np.int32)
            cv2.polylines(frame, [pts], True, color, 2)

        if self._drawing_type is not None:
            color = ZONE_COLORS[self._drawing_type]
            for point in self._current_points:
                cv2.circle(frame, point, 4, color, -1)
            if len(self._current_points) >= 2:
                pts = np.array(self._current_points, dtype=np.int32)
                cv2.polylines(frame, [pts], False, color, 1)

            n = len(self._current_points)
            status = "need 3+ points" if n < 3 else "ready — press ENTER to finish"
            hint = f"Drawing {self._drawing_type.upper()} zone: {n} point(s) clicked ({status}). ESC to cancel."
            cv2.rectangle(frame, (0, h - 30), (w, h), (0, 0, 0), -1)
            cv2.putText(frame, hint, (10, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        else:
            hint = "Press r/y/g to draw a Red/Yellow/Green zone, c to clear all"
            cv2.rectangle(frame, (0, h - 30), (w, h), (0, 0, 0), -1)
            cv2.putText(
                frame, hint, (10, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 2
            )
